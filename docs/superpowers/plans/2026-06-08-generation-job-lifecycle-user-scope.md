# Generation Job Lifecycle And User Scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent graph generation jobs from disappearing by ensuring resumed jobs fail cleanly on errors, authenticated users are attached to generation jobs, and stale running jobs stop looking like active successful work.

**Architecture:** Keep the existing FE -> BFF/Next proxy -> Orchestrator shape. Fix the lifecycle at the orchestrator boundary, then fix user identity propagation at both browser API-client and server proxy boundaries, then add a small stale-job guard so old `running/planning` rows become visible failures instead of invisible limbo.

**Tech Stack:** Next.js route handlers, TypeScript/Vitest, Fastify BFF/Jest or Vitest, FastAPI/Pydantic, LangGraph execution bridge, Postgres-backed generation job service, pytest.

---

## File Structure

- Modify: `orchestrator/app/generation_jobs/execution.py`
  - Responsibility: execute and resume LangGraph generation jobs; convert graph errors into job lifecycle states.
- Modify: `orchestrator/app/generation_jobs/service.py`
  - Responsibility: generation job persistence operations and job response normalization.
- Modify: `orchestrator/app/api/routers/generation_jobs.py`
  - Responsibility: API route lifecycle guard before returning job state.
- Modify: `orchestrator/tests/test_generation_job_graph_execution.py`
  - Responsibility: graph execution/resume lifecycle tests.
- Modify: `orchestrator/tests/test_api_generation_jobs_router.py`
  - Responsibility: route-level stale-job behavior tests.
- Modify: `apps/web/lib/api-client.ts`
  - Responsibility: browser-side API calls and Supabase bearer forwarding.
- Modify: `apps/web/lib/api-client.test.ts`
  - Responsibility: API-client request/header tests.
- Modify: `apps/web/app/api/_proxy/orchestrator.ts`
  - Responsibility: same-origin Next proxy to orchestrator, including verified Supabase user id injection for generation job creation.
- Create: `apps/web/app/api/_proxy/orchestrator.test.ts`
  - Responsibility: Next proxy auth/user-id behavior tests.
- Modify: `apps/web/app/api/generation-jobs/route.ts`
  - Responsibility: normalize generation job creation payload and request authenticated user injection.
- Modify: `apps/web/app/api/generation-jobs/[jobId]/answer/route.ts`
  - Responsibility: normalize generation job answer proxy and keep auth validation path available.
- Modify: `apps/bff/src/app.js`
  - Responsibility: standalone BFF user resolution for generation job answer requests.
- Modify: `apps/bff/tests/generate.test.js`
  - Responsibility: BFF generation job auth propagation tests.

---

### Task 1: Make Graph Resume Failures Persist As Failed Jobs

**Files:**
- Modify: `orchestrator/app/generation_jobs/execution.py:438-520`
- Test: `orchestrator/tests/test_generation_job_graph_execution.py`

- [ ] **Step 1: Write the failing test**

Add this test after `test_resume_generation_job_graph_continues_waiting_job` in `orchestrator/tests/test_generation_job_graph_execution.py`:

```python
def test_resume_generation_job_graph_marks_failed_when_graph_raises(monkeypatch):
    calls = []
    expected_job_id = None
    expected_thread_id = None

    class MockSharedGraph:
        def invoke(self, payload, config: dict | None = None) -> dict:
            nonlocal expected_job_id, expected_thread_id
            calls.append(payload)
            if len(calls) == 1:
                state = dict(payload)
                expected_job_id = state["job_id"]
                expected_thread_id = state["thread_id"]
                state["__interrupt__"] = [
                    FakeInterrupt(
                        {
                            "type": "option_question",
                            "job_id": state["job_id"],
                            "thread_id": state["thread_id"],
                            "option_question": {
                                "field": "item_or_service",
                                "question": "홍보할 상품이나 서비스는 무엇인가요?",
                                "options": [{"id": 1, "label": "대표 메뉴", "value": "대표 메뉴"}],
                            },
                        }
                    )
                ]
                state["status"] = "waiting_user_input"
                state["messages"] = [{"role": "assistant", "content": "홍보할 상품이나 서비스는 무엇인가요?"}]
                return state

            raise RuntimeError("resume graph crashed while planning image generation")

    shared_graph = MockSharedGraph()
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: shared_graph)

    request = GenerationJobCreateRequest(user_input="햄버거집 광고 만들어줘", run_mode="graph_job")
    job = create_generation_job(request)
    waiting = execute_generation_job_graph(job.job_id, request)
    assert waiting.status == "waiting_user_input"

    answer = GenerationJobAnswerRequest(field="item_or_service", value="햄버거 대표 메뉴", display_text="햄버거 대표 메뉴")
    resumed = resume_generation_job_graph(waiting.job_id, answer)

    assert resumed.status == "failed"
    assert resumed.progress.current_stage == "failed"
    assert resumed.error is not None
    assert resumed.error.error_code == "generation_job_execution_failed"
    assert resumed.metadata["execution_mode"] == "graph_resume_failed"
    assert "resume graph crashed" in resumed.error.detail
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_generation_job_graph_execution.py::test_resume_generation_job_graph_marks_failed_when_graph_raises -q
```

Expected: FAIL because `resume_generation_job_graph()` raises the `RuntimeError` or leaves the job `running/planning` instead of returning a failed job.

- [ ] **Step 3: Write minimal implementation**

Replace the body of `resume_generation_job_graph()` after the precondition checks with this structure in `orchestrator/app/generation_jobs/execution.py`:

```python
    try:
        running = mark_generation_job_running(job_id, stage="planning")
        job = running or job

        resume_payload = answer.to_resume_payload(job_id=job_id, thread_id=job.thread_id)
        append_generation_job_user_answer_message(job_id, answer)
        graph = get_generation_job_graph()
        result_state = graph.invoke(
            Command(resume=resume_payload),
            config={"configurable": {"thread_id": job.thread_id}},
        )
        changed_fields = calculate_changed_fields(None, result_state)

        if "__interrupt__" in result_state:
            assistant_message = _assistant_message_from_interrupt(result_state, "추가 정보가 필요해요.")
            updated = mark_generation_job_waiting_user_input(
                job_id=job_id,
                result_state=result_state,
                changed_fields=changed_fields,
                assistant_message=assistant_message,
            )
            return updated or job

        if result_state.get("status") == "modal_running":
            context = _resolve_graph_job_context(job_id, job)
            return _mark_graph_modal_pending(
                job_id=job_id,
                job=job,
                result_state=result_state,
                changed_fields=changed_fields,
                request_run_mode="graph_job",
                workspace_id=str(context["workspace_id"]),
                public_job_id=str(context["public_job_id"]),
                internal_job_id=str(context["internal_job_id"]),
                parent_snapshot_id=context.get("parent_snapshot_id"),
            )

        if result_state.get("status") == "done":
            done = mark_generation_job_done(
                job_id,
                result_payload=result_state.get("result_payload") or {},
                output_path=result_state.get("final_image_path"),
                metadata={
                    "requested_run_mode": "graph_job",
                    "effective_run_mode": "graph_job",
                    "execution_mode": "graph_execution",
                    "final_brief": result_state.get("current_brief"),
                },
            )
            return done or job

        if result_state.get("status") == "failed":
            error_info = result_state.get("error_info") or {}
            failed = mark_generation_job_failed(
                job_id,
                {
                    "error_code": error_info.get("error_code") or "generation_job_execution_failed",
                    "error_type": error_info.get("error_type"),
                    "message": error_info.get("message") or "Graph execution failed",
                    "detail": result_state.get("error_message"),
                },
                metadata={"execution_mode": "graph_execution_failed"},
            )
            return failed or job

        raise ValueError(f"Unexpected graph result status: {result_state.get('status')}")
    except Exception as exc:
        failed = mark_generation_job_failed(
            job_id,
            {
                "error_code": "generation_job_execution_failed",
                "message": "Generation job graph resume failed.",
                "detail": str(exc),
            },
            metadata={"execution_mode": "graph_resume_failed"},
        )
        return failed or job
```

Keep these precondition checks outside the `try` block so invalid route usage still returns a route-level conflict instead of silently marking unrelated jobs failed:

```python
    job = get_generation_job(job_id)
    if not job:
        raise ValueError("generation job was not found")
    if job.status != "waiting_user_input" and not (allow_running and job.status == "running"):
        raise ValueError("generation job is not waiting for user input")
    if not job.thread_id:
        raise ValueError("generation job has no thread_id")
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_generation_job_graph_execution.py::test_resume_generation_job_graph_marks_failed_when_graph_raises -q
```

Expected: PASS.

- [ ] **Step 5: Run related graph tests**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_generation_job_graph_execution.py -q
```

Expected: all tests in the file pass.

- [ ] **Step 6: Commit**

```bash
git add orchestrator/app/generation_jobs/execution.py orchestrator/tests/test_generation_job_graph_execution.py
git commit -m "fix(orchestrator): fail graph resume errors cleanly"
```

---

### Task 2: Forward Supabase Auth On Generation Job Answers

**Files:**
- Modify: `apps/web/lib/api-client.ts:642-644`
- Test: `apps/web/lib/api-client.test.ts`

- [ ] **Step 1: Write the failing test**

Add this test after `it("answers generation job questions through the BFF", async () => { ... })` in `apps/web/lib/api-client.test.ts`:

```ts
  it("forwards Supabase authorization when answering generation job questions", async () => {
    vi.doMock("./supabase/browser", () => ({
      createSupabaseBrowserClient: () => ({
        auth: {
          getSession: async () => ({ data: { session: { access_token: "access_token_1" } } })
        }
      })
    }));
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      jsonResponse({
        success: true,
        job: {
          job_id: "job_1",
          status: "waiting_user_input",
          progress: { progress_percent: 50, current_stage: "waiting_user_input" },
          metadata: {}
        }
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await answerGenerationJob("job_1", {
      field: "item_or_service",
      value: "햄버거 대표 메뉴"
    });

    expect(fetchMock.mock.calls[0][1]?.headers).toEqual(
      expect.objectContaining({ authorization: "Bearer access_token_1" })
    );
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
npm --prefix apps/web test -- --run lib/api-client.test.ts
```

Expected: FAIL because `answerGenerationJob()` does not call `getSupabaseAuthorizationHeader()`.

- [ ] **Step 3: Write minimal implementation**

Change `answerGenerationJob()` in `apps/web/lib/api-client.ts` from:

```ts
export function answerGenerationJob(jobId: string, payload: GenerationJobAnswerPayload): Promise<GenerationJobResponse> {
  return postJson<GenerationJobResponse>(`/api/generation-jobs/${encodeURIComponent(jobId)}/answer`, compactPayload(payload));
}
```

to:

```ts
export async function answerGenerationJob(jobId: string, payload: GenerationJobAnswerPayload): Promise<GenerationJobResponse> {
  const authHeaders = await getSupabaseAuthorizationHeader();
  return postJson<GenerationJobResponse>(
    `/api/generation-jobs/${encodeURIComponent(jobId)}/answer`,
    compactPayload(payload),
    authHeaders
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
npm --prefix apps/web test -- --run lib/api-client.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/lib/api-client.ts apps/web/lib/api-client.test.ts
git commit -m "fix(web): forward auth on generation job answers"
```

---

### Task 3: Inject Verified User Id In The Same-Origin Next Orchestrator Proxy

**Files:**
- Modify: `apps/web/app/api/_proxy/orchestrator.ts`
- Modify: `apps/web/app/api/generation-jobs/route.ts`
- Modify: `apps/web/app/api/generation-jobs/[jobId]/answer/route.ts`
- Create: `apps/web/app/api/_proxy/orchestrator.test.ts`

- [ ] **Step 1: Write the failing proxy tests**

Create `apps/web/app/api/_proxy/orchestrator.test.ts`:

```ts
import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { proxyOrchestratorJson } from "./orchestrator";

function jsonResponse(payload: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(payload), {
    status: init.status ?? 200,
    headers: { "content-type": "application/json" }
  });
}

describe("proxyOrchestratorJson", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("verifies Supabase bearer tokens and injects userId into generation job create payloads", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://supabase.example.com");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon_key");
    const fetchMock = vi.fn(async (url: RequestInfo | URL) => {
      if (String(url).includes("/auth/v1/user")) {
        return jsonResponse({ id: "user_uuid_1" });
      }
      return jsonResponse({
        success: true,
        job: {
          job_id: "job_1",
          status: "queued",
          progress: { progress_percent: 0, current_stage: "queued" },
          metadata: {}
        }
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    const request = new NextRequest("http://localhost/api/generation-jobs", {
      method: "POST",
      headers: {
        authorization: "Bearer access_token_1",
        "content-type": "application/json"
      },
      body: JSON.stringify({ userInput: "햄버거 광고", runMode: "graph_job", userId: "spoofed_user" })
    });

    const response = await proxyOrchestratorJson(request, "POST", "/api/v1/generation-jobs", undefined, {
      injectVerifiedUserId: true
    });

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "https://supabase.example.com/auth/v1/user",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          apikey: "anon_key",
          authorization: "Bearer access_token_1"
        })
      })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://orchestrator/api/v1/generation-jobs",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ userInput: "햄버거 광고", runMode: "graph_job", userId: "user_uuid_1" })
      })
    );
  });

  it("returns a friendly 503 when auth is present but Supabase proxy config is missing", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const request = new NextRequest("http://localhost/api/generation-jobs", {
      method: "POST",
      headers: {
        authorization: "Bearer access_token_1",
        "content-type": "application/json"
      },
      body: JSON.stringify({ userInput: "햄버거 광고", runMode: "graph_job" })
    });

    const response = await proxyOrchestratorJson(request, "POST", "/api/v1/generation-jobs", undefined, {
      injectVerifiedUserId: true
    });
    const body = await response.json();

    expect(response.status).toBe(503);
    expect(body.error_code).toBe("supabase_auth_configuration_missing");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
npm --prefix apps/web test -- --run app/api/_proxy/orchestrator.test.ts
```

Expected: FAIL because `proxyOrchestratorJson()` does not accept `injectVerifiedUserId` and does not verify Supabase tokens.

- [ ] **Step 3: Write minimal implementation**

Update `apps/web/app/api/_proxy/orchestrator.ts`:

```ts
import { NextRequest, NextResponse } from "next/server";

const ORCHESTRATOR_BASE_URL = process.env.ORCHESTRATOR_BASE_URL || "http://localhost:8000";

type ProxyMethod = "GET" | "POST" | "PATCH";
type ProxyOptions = {
  injectVerifiedUserId?: boolean;
};

function buildTargetUrl(path: string, request: NextRequest): string {
  const target = new URL(path, ORCHESTRATOR_BASE_URL);
  request.nextUrl.searchParams.forEach((value, key) => {
    target.searchParams.append(key, value);
  });
  return target.toString();
}

function normalizeBearerHeader(value: string | null): string | null {
  if (!value) {
    return null;
  }
  const normalized = value.trim();
  if (!normalized) {
    return null;
  }
  if (!normalized.toLowerCase().startsWith("bearer ")) {
    throw new Error("invalid authorization header");
  }
  return normalized;
}

async function resolveSupabaseUserId(request: NextRequest): Promise<string | null> {
  const authorization = normalizeBearerHeader(request.headers.get("authorization"));
  if (!authorization) {
    return null;
  }
  const supabaseUrl = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseAnonKey = process.env.SUPABASE_ANON_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!supabaseUrl || !supabaseAnonKey) {
    const error = new Error("supabase auth configuration is missing");
    (error as Error & { statusCode?: number; errorCode?: string }).statusCode = 503;
    (error as Error & { statusCode?: number; errorCode?: string }).errorCode = "supabase_auth_configuration_missing";
    throw error;
  }

  const response = await fetch(`${supabaseUrl.replace(/\/+$/, "")}/auth/v1/user`, {
    method: "GET",
    headers: {
      accept: "application/json",
      apikey: supabaseAnonKey,
      authorization
    }
  });
  if (!response.ok) {
    const error = new Error("invalid or expired session");
    (error as Error & { statusCode?: number; errorCode?: string }).statusCode = 401;
    (error as Error & { statusCode?: number; errorCode?: string }).errorCode = "invalid_or_expired_session";
    throw error;
  }
  const payload = await response.json().catch(() => ({}));
  if (!payload?.id) {
    const error = new Error("invalid or expired session");
    (error as Error & { statusCode?: number; errorCode?: string }).statusCode = 401;
    (error as Error & { statusCode?: number; errorCode?: string }).errorCode = "invalid_or_expired_session";
    throw error;
  }
  return String(payload.id);
}

export async function proxyOrchestratorJson(
  request: NextRequest,
  method: ProxyMethod,
  path: string,
  bodyTransform?: (body: unknown) => unknown,
  options: ProxyOptions = {}
) {
  const init: RequestInit = {
    method,
    headers: { "content-type": "application/json" },
    cache: "no-store"
  };

  if (method !== "GET") {
    const body = await request.text();
    if (body) {
      const rawPayload = bodyTransform ? bodyTransform(JSON.parse(body)) : JSON.parse(body);
      const payload = rawPayload && typeof rawPayload === "object" && !Array.isArray(rawPayload)
        ? { ...(rawPayload as Record<string, unknown>) }
        : rawPayload;
      if (options.injectVerifiedUserId && payload && typeof payload === "object" && !Array.isArray(payload)) {
        delete (payload as Record<string, unknown>).user_id;
        delete (payload as Record<string, unknown>).userId;
        const userId = await resolveSupabaseUserId(request);
        if (userId) {
          (payload as Record<string, unknown>).userId = userId;
        }
      }
      init.body = JSON.stringify(payload);
    }
  }

  try {
    const response = await fetch(buildTargetUrl(path, request), init);
    const payload = await response.json().catch(() => ({}));
    return NextResponse.json(payload, { status: response.status });
  } catch (error) {
    const statusCode = (error as Error & { statusCode?: number }).statusCode;
    const errorCode = (error as Error & { errorCode?: string }).errorCode;
    if (statusCode) {
      return NextResponse.json(
        {
          success: false,
          error_code: errorCode || "orchestrator_proxy_error",
          message: error instanceof Error ? error.message : "Proxy request failed."
        },
        { status: statusCode }
      );
    }
    return NextResponse.json(
      {
        success: false,
        error_code: "orchestrator_unavailable",
        message: "Orchestrator API is unavailable.",
        detail: "Failed to reach the orchestrator backend from the BFF proxy."
      },
      { status: 502 }
    );
  }
}
```

- [ ] **Step 4: Enable user injection on generation job routes**

Change `apps/web/app/api/generation-jobs/route.ts` return call to pass options:

```ts
  return proxyOrchestratorJson(request, "POST", "/api/v1/generation-jobs", (body) => {
    const payload = { ...(body as Record<string, unknown>) };
    payload.selected_reference_template_id = payload.selected_reference_template_id ?? payload.selectedReferenceTemplateId;
    payload.selected_copy_id = payload.selected_copy_id ?? payload.selectedCopyId;
    payload.selected_channel_id = payload.selected_channel_id ?? payload.selectedChannelId;
    payload.selected_tone = payload.selected_tone ?? payload.selectedTone;
    payload.custom_direction = payload.custom_direction ?? payload.customDirection;
    payload.user_custom_headline = payload.user_custom_headline ?? payload.userCustomHeadline;
    payload.user_custom_subcopy = payload.user_custom_subcopy ?? payload.userCustomSubcopy;
    payload.source_image_path = payload.source_image_path ?? payload.sourceImagePath;
    payload.reference_image_path = payload.reference_image_path ?? payload.referenceImagePath;
    delete payload.selectedReferenceTemplateId;
    delete payload.selectedCopyId;
    delete payload.selectedChannelId;
    delete payload.selectedTone;
    delete payload.customDirection;
    delete payload.userCustomHeadline;
    delete payload.userCustomSubcopy;
    delete payload.sourceImagePath;
    delete payload.referenceImagePath;
    return payload;
  }, { injectVerifiedUserId: true });
```

Change `apps/web/app/api/generation-jobs/[jobId]/answer/route.ts` to keep the same auth-validation path available:

```ts
export function POST(request: NextRequest, { params }: { params: { jobId: string } }) {
  return proxyOrchestratorJson(
    request,
    "POST",
    `/api/v1/generation-jobs/${encodeURIComponent(params.jobId)}/answer`,
    undefined,
    { injectVerifiedUserId: true }
  );
}
```

- [ ] **Step 5: Run proxy tests**

Run:

```bash
npm --prefix apps/web test -- --run app/api/_proxy/orchestrator.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/web/app/api/_proxy/orchestrator.ts apps/web/app/api/_proxy/orchestrator.test.ts apps/web/app/api/generation-jobs/route.ts apps/web/app/api/generation-jobs/[jobId]/answer/route.ts
git commit -m "fix(web): attach verified user to generation job proxy"
```

---

### Task 4: Make Standalone BFF Generation Job Answers Validate The Same User Session

**Files:**
- Modify: `apps/bff/src/app.js:548-560`
- Test: `apps/bff/tests/generate.test.js`

- [ ] **Step 1: Write the failing BFF test**

Add this test after `it("proxies generation job answers to the orchestrator", async () => { ... })` in `apps/bff/tests/generate.test.js`:

```js
  it("verifies Supabase sessions before forwarding generation job answers", async () => {
    const fetchImpl = vi.fn(async (url, init) => {
      if (String(url).includes("/auth/v1/user")) {
        return jsonResponse({ id: "user_uuid_1", email: "owner@example.com" });
      }
      return jsonResponse({
        success: true,
        job: {
          job_id: "job_1",
          status: "done",
          progress: { progress_percent: 100, current_stage: "completed", stage_order: [] },
          metadata: { execution_mode: "graph_execution" }
        }
      });
    });
    const app = buildApp({
      orchestratorBaseUrl: "http://orchestrator",
      fetchImpl,
      supabaseUrl: "https://supabase.example.com",
      supabaseAnonKey: "anon_key"
    });

    const response = await app.inject({
      method: "POST",
      url: "/api/generation-jobs/job_1/answer",
      headers: { authorization: "Bearer access_token_1" },
      payload: { field: "business_type", value: "restaurant", userId: "spoofed_user" }
    });

    expect(response.statusCode).toBe(200);
    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "https://supabase.example.com/auth/v1/user",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          apikey: "anon_key",
          authorization: "Bearer access_token_1"
        })
      })
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://orchestrator/api/v1/generation-jobs/job_1/answer",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ field: "business_type", value: "restaurant", userId: "user_uuid_1" })
      })
    );
    await app.close();
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
npm --prefix apps/bff test -- tests/generate.test.js
```

Expected: FAIL because the answer route forwards the body without resolving the Supabase session.

- [ ] **Step 3: Write minimal implementation**

Change the answer route in `apps/bff/src/app.js` from:

```js
  app.post("/api/generation-jobs/:jobId/answer", async (request, reply) => {
    const parsed = generationJobAnswerSchema.safeParse(request.body);
    if (!parsed.success) {
      return reply.code(400).send({ error: "invalid_request", issues: parsed.error.issues });
    }

    return proxyJson({
      fetchImpl,
      url: `${orchestratorBaseUrl}/api/v1/generation-jobs/${encodeURIComponent(request.params.jobId)}/answer`,
      body: parsed.data
    });
  });
```

to:

```js
  app.post("/api/generation-jobs/:jobId/answer", async (request, reply) => {
    const parsed = generationJobAnswerSchema.safeParse(request.body);
    if (!parsed.success) {
      return reply.code(400).send({ error: "invalid_request", issues: parsed.error.issues });
    }
    const userId = await resolveSupabaseUserId({ request, fetchImpl, supabaseUrl, supabaseAnonKey });
    const {
      userId: _clientUserId,
      user_id: _clientUserIdSnake,
      ...clientPayload
    } = parsed.data;

    return proxyJson({
      fetchImpl,
      url: `${orchestratorBaseUrl}/api/v1/generation-jobs/${encodeURIComponent(request.params.jobId)}/answer`,
      body: {
        ...clientPayload,
        ...(userId ? { userId } : {})
      }
    });
  });
```

- [ ] **Step 4: Run BFF tests**

Run:

```bash
npm --prefix apps/bff test -- tests/generate.test.js
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/bff/src/app.js apps/bff/tests/generate.test.js
git commit -m "fix(bff): validate auth on generation job answers"
```

---

### Task 5: Mark Stale Running Planning Jobs As Failed On Read

**Files:**
- Modify: `orchestrator/app/generation_jobs/service.py`
- Modify: `orchestrator/app/api/routers/generation_jobs.py`
- Test: `orchestrator/tests/test_api_generation_jobs_router.py`

- [ ] **Step 1: Write the failing service-level route test**

Add imports near the top of `orchestrator/tests/test_api_generation_jobs_router.py`:

```python
from datetime import datetime, timedelta, timezone

from orchestrator.app.api.schemas.generation_jobs import GenerationJobResponse, GenerationProgress
```

Add this test near `test_create_generation_job_and_get_job`:

```python
def test_get_generation_job_marks_stale_running_planning_job_failed(client, monkeypatch):
    stale_job = GenerationJobResponse(
        job_id="job_stale_1",
        thread_id="thread_stale_1",
        user_id="user_1",
        status="running",
        progress=GenerationProgress(progress_percent=50, current_stage="planning", stage_order=[]),
        created_at=(datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(),
        updated_at=(datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(),
        metadata={"execution_mode": "graph_execution"},
    )
    failed_job = stale_job.model_copy(
        update={
            "status": "failed",
            "progress": GenerationProgress(progress_percent=50, current_stage="failed", stage_order=[]),
            "metadata": {"execution_mode": "stale_running_recovered"},
        }
    )
    calls = []

    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.get_generation_job", lambda job_id: stale_job)

    def fake_maybe_mark_stale_generation_job_failed(job):
        calls.append(job.job_id)
        return failed_job

    monkeypatch.setattr(
        "orchestrator.app.api.routers.generation_jobs.maybe_mark_stale_generation_job_failed",
        fake_maybe_mark_stale_generation_job_failed,
    )

    response = client.get("/api/v1/generation-jobs/job_stale_1")

    assert response.status_code == 200
    assert response.json()["job"]["status"] == "failed"
    assert response.json()["job"]["progress"]["current_stage"] == "failed"
    assert calls == ["job_stale_1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_api_generation_jobs_router.py::test_get_generation_job_marks_stale_running_planning_job_failed -q
```

Expected: FAIL because `maybe_mark_stale_generation_job_failed` is not imported/called by the route.

- [ ] **Step 3: Add stale recovery service function**

Add these imports near the top of `orchestrator/app/generation_jobs/service.py` if not already present:

```python
from datetime import datetime, timedelta, timezone
```

Add this helper near `mark_generation_job_failed()`:

```python
STALE_RUNNING_STAGE_NAMES = {"planning", "running"}
DEFAULT_STALE_RUNNING_AFTER_SECONDS = 15 * 60


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def maybe_mark_stale_generation_job_failed(
    job: GenerationJobResponse,
    *,
    now: datetime | None = None,
    stale_after_seconds: int = DEFAULT_STALE_RUNNING_AFTER_SECONDS,
) -> GenerationJobResponse:
    if job.status != "running":
        return job
    if job.progress.current_stage not in STALE_RUNNING_STAGE_NAMES:
        return job
    updated_at = _parse_iso_datetime(job.updated_at)
    if not updated_at:
        return job
    current_time = now or datetime.now(timezone.utc)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    if current_time - updated_at < timedelta(seconds=stale_after_seconds):
        return job

    failed = mark_generation_job_failed(
        job.job_id,
        {
            "error_code": "generation_job_stale_running",
            "message": "Generation job stopped while preparing the request.",
            "detail": "The job stayed in running/planning longer than the allowed stale threshold.",
        },
        metadata={
            **(job.metadata or {}),
            "execution_mode": "stale_running_recovered",
            "stale_running_stage": job.progress.current_stage,
        },
    )
    return failed or job
```

- [ ] **Step 4: Call stale recovery from the GET route**

Update imports in `orchestrator/app/api/routers/generation_jobs.py`:

```python
from orchestrator.app.generation_jobs.service import (
    create_generation_job,
    get_generation_job,
    mark_generation_job_running,
    maybe_mark_stale_generation_job_failed,
    maybe_poll_generation_job_from_modal,
    maybe_submit_generation_job_to_modal,
    should_route_generation_job_to_modal,
)
```

Update `get_generation_job_route()`:

```python
@router.get("/generation-jobs/{job_id}", response_model=GenerationJobGetResponse)
def get_generation_job_route(job_id: str) -> GenerationJobGetResponse:
    job = get_generation_job(job_id)
    if not job:
        _generation_job_not_found(job_id)
    job = maybe_mark_stale_generation_job_failed(job)
    if job.status != "failed":
        job = maybe_poll_generation_job_from_modal(job)
    return GenerationJobGetResponse(job=job)
```

- [ ] **Step 5: Run route stale test**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_api_generation_jobs_router.py::test_get_generation_job_marks_stale_running_planning_job_failed -q
```

Expected: PASS.

- [ ] **Step 6: Add direct service tests for stale threshold**

Add this test to `orchestrator/tests/test_generation_job_service.py`:

```python
from datetime import datetime, timedelta, timezone

from orchestrator.app.api.schemas.generation_jobs import GenerationJobResponse, GenerationProgress
from orchestrator.app.generation_jobs.service import maybe_mark_stale_generation_job_failed


def test_maybe_mark_stale_generation_job_failed_keeps_fresh_running_job(monkeypatch):
    now = datetime(2026, 6, 8, 9, 0, tzinfo=timezone.utc)
    fresh_job = GenerationJobResponse(
        job_id="job_fresh",
        status="running",
        progress=GenerationProgress(progress_percent=50, current_stage="planning", stage_order=[]),
        created_at=(now - timedelta(minutes=1)).isoformat(),
        updated_at=(now - timedelta(minutes=1)).isoformat(),
        metadata={},
    )

    result = maybe_mark_stale_generation_job_failed(fresh_job, now=now, stale_after_seconds=900)

    assert result is fresh_job
```

- [ ] **Step 7: Run service and router tests**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_generation_job_service.py orchestrator/tests/test_api_generation_jobs_router.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add orchestrator/app/generation_jobs/service.py orchestrator/app/api/routers/generation_jobs.py orchestrator/tests/test_api_generation_jobs_router.py orchestrator/tests/test_generation_job_service.py
git commit -m "fix(orchestrator): recover stale running generation jobs"
```

---

### Task 6: Full Verification

**Files:**
- No new files.
- Verify all changed surfaces.

- [ ] **Step 1: Run orchestrator tests for graph/job routes**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_generation_job_graph_execution.py orchestrator/tests/test_api_generation_jobs_router.py orchestrator/tests/test_generation_job_service.py -q
```

Expected: PASS.

- [ ] **Step 2: Run Web tests for API/proxy behavior**

Run:

```bash
npm --prefix apps/web test -- --run lib/api-client.test.ts app/api/_proxy/orchestrator.test.ts
```

Expected: PASS.

- [ ] **Step 3: Run BFF generation tests**

Run:

```bash
npm --prefix apps/bff test -- tests/generate.test.js
```

Expected: PASS.

- [ ] **Step 4: Run TypeScript check**

Run:

```bash
npx tsc --noEmit
```

Expected: PASS.

- [ ] **Step 5: Check patch hygiene**

Run:

```bash
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 6: Manual DB sanity check**

Run a new logged-in generation flow in local UI, then query only non-secret public ids and lifecycle fields:

```bash
uv run python scripts/debug_recent_generation_jobs.py --keyword 햄버거
```

Expected for the new job:

```text
requested_by: <logged-in user uuid>
workspace.owner_user_id: <logged-in user uuid>
status: waiting_user_input | running | modal_running | done | failed
status must not remain running/planning after a graph resume error
done jobs should have public_output_id and public_archive_id
```

If `scripts/debug_recent_generation_jobs.py` does not exist, use a short local Python DB query that prints only `public_job_id`, `status`, `current_stage`, `requested_by`, `public_thread_id`, `owner_user_id`, `public_output_id`, and `public_archive_id`. Do not print environment variables or secrets.

- [ ] **Step 7: Final commit if Task 6 produced any verification-only doc/script edits**

```bash
git status --short
git add <only verification scripts or docs created in Task 6>
git commit -m "test: add generation job lifecycle verification"
```

---

## Manual QA Script

Use this exact flow after the code lands locally:

1. Start the web app, BFF if used, and orchestrator.
2. Log in with Google.
3. Go to reference gallery.
4. Choose a burger or restaurant reference style.
5. Start chat generation with `리얼 프레시 버거 피드 스타일로 버거92의 음식점 광고를 만들어줘`.
6. Answer the item/service question with `햄버거 대표 메뉴`.
7. Continue through copy selection or brief confirmation.
8. Confirm:
   - The thread remains visible in recent workspaces.
   - The DB row has `requested_by` set to the Google auth UUID.
   - The workspace has `owner_user_id` set to the same UUID.
   - If generation succeeds, archive contains the result.
   - If generation fails, UI shows a failed job instead of silently disappearing.

---

## Self-Review

**Spec coverage:**  
The plan covers the diagnosed failures: graph resume limbo, missing authenticated user propagation, stale running job visibility, and archive absence through incomplete `done` flow.

**Placeholder scan:**  
No task uses TBD/TODO/fill-in placeholders. Every code-changing step includes concrete code snippets and exact commands.

**Type consistency:**  
The plan uses existing names observed in the codebase: `GenerationJobAnswerRequest`, `GenerationJobResponse`, `GenerationProgress`, `answerGenerationJob`, `proxyOrchestratorJson`, `mark_generation_job_failed`, `maybe_poll_generation_job_from_modal`, `requested_by`, and `userId`.

