# Generation Stability And Guest Scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make chat/image generation usable for signed-in and guest users without leaking internal `workspaceId` errors, and prevent job/status routes from losing the user scope after creation.

**Architecture:** Keep the existing Supabase anonymous-user approach: guests are real Supabase anonymous principals with `accountType=guest`, not unscoped browser traffic. The web client must attach auth to generation create/get/answer calls, the Next proxy must forward verified identity in headers, and the orchestrator must resolve workspace from either trusted principal or the existing job. User-facing errors are mapped in the FE instead of displaying backend implementation messages.

**Tech Stack:** Next.js 14 App Router Route Handlers, Supabase JS, TypeScript/Vitest, FastAPI, Pytest, Postgres workspace repositories.

---

## Current-State Notes

- `apps/web/lib/supabase/session.ts` already creates anonymous Supabase sessions for user-scoped APIs.
- `apps/web/app/api/_proxy/orchestrator.ts` already supports `injectVerifiedUserId` and `injectVerifiedUserIdHeader`.
- `orchestrator/app/api/routers/generation_jobs.py` already reads `X-EasyAds-User-Id` and `X-EasyAds-Account-Type`.
- The remaining stabilization work is to lock this behavior with tests, ensure read/resume calls use the same scope, and make UI errors friendly.

## File Structure

- Modify `apps/web/lib/api-client.ts`: generation GET must attach Supabase auth like create/answer.
- Modify `apps/web/lib/chat-flow.ts`: map workspace/auth/thread-limit errors into user-facing Korean copy.
- Modify `apps/web/app/api/generation-jobs/[jobId]/route.ts`: pass verified identity headers to orchestrator.
- Modify `apps/web/app/api/generation-jobs/[jobId]/answer/route.ts`: keep verified identity headers for answer/resume.
- Modify `orchestrator/app/api/routers/generation_jobs.py`: preserve fallback to existing job scope and account type.
- Tests:
  - `apps/web/lib/api-client.test.ts`
  - `apps/web/app/api/_proxy/orchestrator.test.ts`
  - `orchestrator/tests/test_api_generation_jobs_workspace_scope.py`

### Task 1: Web Generation Status Calls Carry Guest/Auth Headers

**Files:**
- Modify: `apps/web/lib/api-client.ts`
- Test: `apps/web/lib/api-client.test.ts`

- [x] **Step 1: Write the failing test**

Add this test near the generation job tests in `apps/web/lib/api-client.test.ts`:

```ts
it("forwards Supabase authorization when reading a generation job", async () => {
  vi.doMock("./supabase/browser", () => ({
    createSupabaseBrowserClient: () => ({
      auth: {
        getSession: async () => ({ data: { session: { access_token: "guest_access_token_1" } } })
      }
    })
  }));
  const fetchMock = vi.fn(async () =>
    jsonResponse({
      success: true,
      job: {
        job_id: "job_guest_1",
        status: "running",
        progress: { progress_percent: 25, current_stage: "planning", stage_order: [] },
        metadata: {}
      }
    })
  );
  vi.stubGlobal("fetch", fetchMock);

  await getGenerationJob("job_guest_1");

  expect(fetchMock.mock.calls[0][1]?.headers).toEqual(
    expect.objectContaining({ authorization: "Bearer guest_access_token_1" })
  );
});
```

- [x] **Step 2: Run the test to verify it fails**

Run:

```bash
cd apps/web && npx vitest run lib/api-client.test.ts
```

Expected: FAIL because `getGenerationJob()` currently calls `getJson()` without `getSupabaseAuthorizationHeader()`.

- [x] **Step 3: Implement the minimal client change**

In `apps/web/lib/api-client.ts`, replace:

```ts
export function getGenerationJob(jobId: string): Promise<GenerationJobResponse> {
  return getJson<GenerationJobResponse>(`/api/generation-jobs/${encodeURIComponent(jobId)}`);
}
```

with:

```ts
export async function getGenerationJob(jobId: string): Promise<GenerationJobResponse> {
  const authHeaders = await getSupabaseAuthorizationHeader();
  return getJson<GenerationJobResponse>(`/api/generation-jobs/${encodeURIComponent(jobId)}`, undefined, authHeaders);
}
```

- [x] **Step 4: Run tests to verify it passes**

Run:

```bash
cd apps/web && npx vitest run lib/api-client.test.ts
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add apps/web/lib/api-client.ts apps/web/lib/api-client.test.ts
git commit -m "fix(fe): forward auth when reading generation jobs"
```

### Task 2: Next Generation Job GET Proxy Injects Verified Headers

**Files:**
- Modify: `apps/web/app/api/generation-jobs/[jobId]/route.ts`
- Test: `apps/web/app/api/_proxy/orchestrator.test.ts`

- [x] **Step 1: Write the failing proxy test**

Append this test in `apps/web/app/api/_proxy/orchestrator.test.ts`:

```ts
it("injects verified user headers for generation job GET routes", async () => {
  vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
  vi.stubEnv("SUPABASE_URL", "http://supabase.local");
  vi.stubEnv("SUPABASE_ANON_KEY", "anon");
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse({ id: "guest_uuid_1", is_anonymous: true }))
    .mockResolvedValueOnce(jsonResponse({ success: true, job: { job_id: "job_1", status: "queued", progress: {} } }));
  vi.stubGlobal("fetch", fetchMock);

  const request = new NextRequest("http://localhost/api/generation-jobs/job_1", {
    headers: { authorization: "Bearer guest_access_token_1" }
  });
  await proxyOrchestratorJson(request, "GET", "/api/v1/generation-jobs/job_1", undefined, {
    injectVerifiedUserIdHeader: true
  });

  const init = fetchMock.mock.calls[1][1] as RequestInit;
  expect(init.headers).toEqual(
    expect.objectContaining({
      "X-EasyAds-User-Id": "guest_uuid_1",
      "X-EasyAds-Account-Type": "guest"
    })
  );
});
```

- [x] **Step 2: Run the test**

Run:

```bash
cd apps/web && npx vitest run app/api/_proxy/orchestrator.test.ts
```

Expected: PASS for the proxy helper, but the route itself still needs to opt in.

- [x] **Step 3: Update the GET route**

Change `apps/web/app/api/generation-jobs/[jobId]/route.ts` to:

```ts
import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function GET(request: NextRequest, { params }: { params: { jobId: string } }) {
  return proxyOrchestratorJson(
    request,
    "GET",
    `/api/v1/generation-jobs/${encodeURIComponent(params.jobId)}`,
    undefined,
    { injectVerifiedUserIdHeader: true }
  );
}
```

- [x] **Step 4: Run focused tests**

Run:

```bash
cd apps/web && npx vitest run app/api/_proxy/orchestrator.test.ts lib/api-client.test.ts
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add apps/web/app/api/generation-jobs/[jobId]/route.ts apps/web/app/api/_proxy/orchestrator.test.ts
git commit -m "fix(bff): inject verified principal for generation job reads"
```

### Task 3: User-Friendly Workspace/Auth Error Mapping

**Files:**
- Modify: `apps/web/lib/chat-flow.ts`
- Test: `apps/web/lib/chat-flow.test.ts`

- [x] **Step 1: Write failing tests**

Add these cases to `apps/web/lib/chat-flow.test.ts`:

```ts
it("maps workspace_required into a friendly retry message", () => {
  const failed = chatFailureFromError({
    errorCode: "workspace_required",
    message: "workspaceId is required."
  });

  expect(failed.message).toBe("작업방을 준비하지 못했어요. 잠시 후 다시 시도해 주세요.");
  expect(failed.errorCode).toBe("workspace_required");
});

it("maps invalid_or_expired_session into a login refresh message", () => {
  const failed = chatFailureFromError({
    errorCode: "invalid_or_expired_session",
    message: "Invalid or expired session."
  });

  expect(failed.message).toBe("로그인이 만료됐어요. 다시 로그인한 뒤 이어서 진행해 주세요.");
  expect(failed.errorCode).toBe("invalid_or_expired_session");
});
```

- [x] **Step 2: Run the test to verify it fails**

Run:

```bash
cd apps/web && npx vitest run lib/chat-flow.test.ts
```

Expected: FAIL until the mapper knows these codes.

- [x] **Step 3: Implement explicit mappings**

In `apps/web/lib/chat-flow.ts`, add mappings in the existing error conversion function:

```ts
const CHAT_ERROR_MESSAGE_BY_CODE: Record<string, string> = {
  thread_limit_reached: "비로그인 상태에서는 작업방을 3개까지 만들 수 있어요. 기존 작업방을 삭제하거나 로그인하면 계속 만들 수 있어요.",
  workspace_required: "작업방을 준비하지 못했어요. 잠시 후 다시 시도해 주세요.",
  archive_workspace_required: "보관함을 준비하지 못했어요. 잠시 후 다시 시도해 주세요.",
  usage_workspace_required: "사용량 정보를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.",
  invalid_or_expired_session: "로그인이 만료됐어요. 다시 로그인한 뒤 이어서 진행해 주세요.",
  supabase_auth_configuration_missing: "로그인 설정을 확인해야 해요. 관리자에게 문의해 주세요."
};
```

Use this map before falling back to raw backend messages:

```ts
const friendlyMessage = errorCode ? CHAT_ERROR_MESSAGE_BY_CODE[errorCode] : undefined;
return {
  message: friendlyMessage ?? fallbackMessage,
  errorCode
};
```

- [x] **Step 4: Run tests**

Run:

```bash
cd apps/web && npx vitest run lib/chat-flow.test.ts app/generate/chat/ChatGenerateClient.test.tsx
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add apps/web/lib/chat-flow.ts apps/web/lib/chat-flow.test.ts
git commit -m "fix(fe): hide internal workspace errors from chat users"
```

### Task 4: Orchestrator Scope Fallback Regression

**Files:**
- Modify: `orchestrator/tests/test_api_generation_jobs_workspace_scope.py`
- Modify: `orchestrator/app/api/routers/generation_jobs.py`

- [x] **Step 1: Write regression tests**

Add this test to `orchestrator/tests/test_api_generation_jobs_workspace_scope.py`:

```python
def test_generation_job_get_route_resolves_scope_from_existing_job_when_header_missing(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        "orchestrator.app.api.routers.generation_jobs.resolve_generation_job_scope_from_existing_job",
        lambda job_id: ("11111111-1111-1111-1111-111111111111", "guest_uuid_1"),
    )
    monkeypatch.setattr(
        "orchestrator.app.api.routers.generation_jobs.resolve_scoped_workspace_id",
        lambda workspace_id, user_id, account_type=None: workspace_id,
    )

    def fake_get_generation_job(job_id, *, workspace_id=None, user_id=None):
        captured.update({"job_id": job_id, "workspace_id": workspace_id, "user_id": user_id})
        return GenerationJobResponse(
            job_id=job_id,
            thread_id="thread_guest",
            user_id=user_id,
            status="queued",
            progress=GenerationProgress(progress_percent=0, current_stage="queued", stage_order=[]),
            created_at="2026-06-12T00:00:00+00:00",
            updated_at="2026-06-12T00:00:00+00:00",
            metadata={},
        )

    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.get_generation_job_scoped", fake_get_generation_job)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.maybe_mark_stale_generation_job_failed", lambda job, **kwargs: job)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.maybe_poll_generation_job_from_modal", lambda job, **kwargs: job)

    response = TestClient(create_app()).get("/api/v1/generation-jobs/job_guest")

    assert response.status_code == 200
    assert captured == {
        "job_id": "job_guest",
        "workspace_id": "11111111-1111-1111-1111-111111111111",
        "user_id": "guest_uuid_1",
    }
```

- [x] **Step 2: Run the test**

Run:

```bash
EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests/test_api_generation_jobs_workspace_scope.py -q
```

Expected: PASS if the current route fallback is intact. If FAIL, restore fallback before proceeding.

- [x] **Step 3: Keep route fallback code explicit**

Ensure `orchestrator/app/api/routers/generation_jobs.py` contains this shape in both GET and answer routes:

```python
resolved_workspace_id, resolved_user_id = _route_scope(workspace_id, principal)
if not resolved_workspace_id and not resolved_user_id:
    resolved_workspace_id, resolved_user_id = resolve_generation_job_scope_from_existing_job(job_id)
resolved_workspace_id = resolve_scoped_workspace_id(
    resolved_workspace_id,
    resolved_user_id,
    account_type=principal.account_type,
)
job = get_generation_job_scoped(job_id, workspace_id=resolved_workspace_id, user_id=resolved_user_id)
```

- [x] **Step 4: Run backend focused tests**

Run:

```bash
EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests/test_api_generation_jobs_workspace_scope.py orchestrator/tests/test_generation_job_service_db_backend.py orchestrator/tests/test_chat_thread_service.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add orchestrator/app/api/routers/generation_jobs.py orchestrator/tests/test_api_generation_jobs_workspace_scope.py
git commit -m "test(srv): lock generation job scope fallback"
```

## Final Verification

Run:

```bash
cd apps/web && npx vitest run lib/api-client.test.ts lib/chat-flow.test.ts app/api/_proxy/orchestrator.test.ts app/generate/chat/ChatGenerateClient.test.tsx && npx tsc --noEmit
cd ../..
EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests/test_api_generation_jobs_workspace_scope.py orchestrator/tests/test_generation_job_service_db_backend.py orchestrator/tests/test_chat_thread_service.py -q
```

Expected: all tests pass. Existing React `act(...)` warnings are acceptable only if they match the known baseline.
