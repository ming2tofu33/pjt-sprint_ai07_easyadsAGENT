# Generation Job Resume Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let final `graph_immediate` generation jobs pause for missing context, show the graph question in the UI, accept the user's answer, and resume the same LangGraph job until it completes or asks another supported question.

**Architecture:** Orchestrator will expose pending graph interrupt payloads on `GenerationJob.metadata.pending_interrupt` and add `POST /api/v1/generation-jobs/{job_id}/answer` to resume a waiting graph job with `Command(resume=...)`. The web app will proxy that route, read `pending_interrupt` from polled jobs, reuse the existing chat question UI for `option_question`, and continue polling after each answer. This phase supports the missing-context `option_question` loop directly and keeps non-option interrupts visible as a safe unsupported-interrupt state rather than pretending generation completed.

**Tech Stack:** FastAPI/Pydantic, LangGraph `Command`, Next.js route handlers, Fastify BFF, React/TypeScript, Vitest, Pytest.

---

## Scope

Included:
- Persist the graph interrupt payload into generation job metadata.
- Add Orchestrator answer route for waiting generation jobs.
- Add Next.js and Fastify BFF proxy routes.
- Add web API client function for answering a generation job question.
- Reuse `ChatContextQuestionStep` for final generation `option_question` prompts.
- Continue polling the same job after an answer.
- Update UI-orchestrator route coverage to mark final generation as graph + resume loop.

Excluded:
- A production-grade persistent LangGraph checkpointer beyond the current shared in-process graph.
- A rich UI for `copy_candidate_selection` or `custom_copy_input` interrupts during final generation.
- Replacing the legacy `/generate/chat/start`, `/answer`, `/brief` intake APIs.

## Important Design Decision

`execute_generation_job_graph()` currently builds a fresh graph instance each time. LangGraph resume requires the same compiled graph/checkpointer for the same `thread_id`, just like the existing chat APIs use `MARKETING_GRAPH`. This plan changes generation job graph execution to use a shared graph accessor so initial graph execution and answer resume share the same in-process checkpoint.

If the process restarts between interrupt and resume, the answer endpoint should fail clearly instead of silently claiming success. Persistent checkpointer hardening can be a later deployment-focused phase.

## File Structure

- Modify: `orchestrator/app/api/schemas/generation_jobs.py`
  - Add `GenerationJobAnswerRequest`.
- Modify: `orchestrator/app/generation_jobs/execution.py`
  - Add shared graph accessor.
  - Add `resume_generation_job_graph()`.
  - Factor graph result finalization enough for initial execution and resume to share behavior.
- Modify: `orchestrator/app/generation_jobs/service.py`
  - Save sanitized pending interrupt metadata when a graph job waits for user input.
  - Clear pending interrupt metadata when the job runs/done/fails.
- Modify: `orchestrator/app/api/routers/generation_jobs.py`
  - Add `POST /generation-jobs/{job_id}/answer`.
- Modify: `orchestrator/tests/test_generation_job_graph_execution.py`
  - Verify pending interrupt metadata and resume execution.
- Modify: `orchestrator/tests/test_api_generation_jobs_router.py`
  - Verify answer route validation and routing.
- Modify: `apps/web/lib/api-client.ts`
  - Add generation job pending interrupt types and `answerGenerationJob()`.
- Modify: `apps/web/lib/api-client.test.ts`
  - Verify BFF answer endpoint call.
- Create: `apps/web/lib/generation-job-interrupt.ts`
  - Extract `option_question` from `GenerationJob.metadata.pending_interrupt`.
- Create: `apps/web/lib/generation-job-interrupt.test.ts`
  - Verify supported and unsupported interrupt parsing.
- Modify: `apps/web/app/api/generation-jobs/[jobId]/answer/route.ts`
  - Add Next.js proxy route for Vercel/local Next API usage.
- Modify: `apps/bff/src/app.js`
  - Add Fastify BFF answer route and schema.
- Modify: `apps/bff/tests/generate.test.js`
  - Verify BFF answer proxy.
- Modify: `apps/web/types/marketing.ts`
  - Add generation job question actions.
- Modify: `apps/web/lib/chat-flow.ts`
  - Store generation job question state and answer loading state.
- Modify: `apps/web/lib/chat-flow.test.ts`
  - Verify reducer state transitions for generation job questions.
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx`
  - Detect waiting jobs, show question step, submit answers, resume polling.
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`
  - Verify waiting question -> answer -> final completion.
- Modify: `apps/web/lib/ui-orchestrator-route-coverage.ts`
  - Mark final generation as graph job with resume.
- Modify: `apps/web/lib/ui-orchestrator-route-coverage.test.ts`
  - Verify resume API appears in coverage.

---

### Task 1: Orchestrator Answer Schema

**Files:**
- Modify: `orchestrator/app/api/schemas/generation_jobs.py`
- Test: `orchestrator/tests/test_api_contract_generation_jobs.py`

- [ ] **Step 1: Write the failing schema test**

Add this import to `orchestrator/tests/test_api_contract_generation_jobs.py`:

```python
    GenerationJobAnswerRequest,
```

Add this test:

```python
def test_generation_job_answer_request_builds_option_resume_payload():
    request = GenerationJobAnswerRequest(
        field="business_type",
        value="cafe",
        custom_text=None,
    )

    payload = request.to_resume_payload(job_id="job_1", thread_id="thread_1")

    assert payload == {
        "job_id": "job_1",
        "thread_id": "thread_1",
        "field": "business_type",
        "value": "cafe",
    }
```

Add this test:

```python
def test_generation_job_answer_request_supports_camel_case_custom_text():
    request = GenerationJobAnswerRequest.model_validate(
        {
            "field": "item_or_service",
            "value": "custom",
            "customText": "딸기라떼",
        }
    )

    payload = request.to_resume_payload(job_id="job_1", thread_id="thread_1")

    assert payload["custom_text"] == "딸기라떼"
```

- [ ] **Step 2: Run the schema tests to verify they fail**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_api_contract_generation_jobs.py::test_generation_job_answer_request_builds_option_resume_payload orchestrator/tests/test_api_contract_generation_jobs.py::test_generation_job_answer_request_supports_camel_case_custom_text -q
```

Expected: FAIL because `GenerationJobAnswerRequest` does not exist.

- [ ] **Step 3: Add the request schema**

In `orchestrator/app/api/schemas/generation_jobs.py`, add this class after `GenerationJobCreateRequest`:

```python
class GenerationJobAnswerRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    field: str | None = None
    value: str | None = None
    custom_text: str | None = Field(default=None, alias="customText")
    selected_copy_id: str | None = Field(default=None, alias="selectedCopyId")
    user_custom_headline: str | None = Field(default=None, alias="userCustomHeadline")
    user_custom_subcopy: str | None = Field(default=None, alias="userCustomSubcopy")
    payload: dict[str, Any] = Field(default_factory=dict)

    def to_resume_payload(self, *, job_id: str, thread_id: str) -> dict[str, Any]:
        resume_payload: dict[str, Any] = {
            "job_id": job_id,
            "thread_id": thread_id,
        }
        if self.field is not None:
            resume_payload["field"] = self.field
        if self.value is not None:
            resume_payload["value"] = self.value
        if self.custom_text:
            resume_payload["custom_text"] = self.custom_text
        if self.selected_copy_id:
            resume_payload["selected_copy_id"] = self.selected_copy_id
        if self.user_custom_headline:
            resume_payload["user_custom_headline"] = self.user_custom_headline
        if self.user_custom_subcopy:
            resume_payload["user_custom_subcopy"] = self.user_custom_subcopy
        resume_payload.update(self.payload)
        return resume_payload
```

- [ ] **Step 4: Run the schema tests to verify they pass**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_api_contract_generation_jobs.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add orchestrator/app/api/schemas/generation_jobs.py orchestrator/tests/test_api_contract_generation_jobs.py
git commit -m "feat(orchestrator): add generation job answer schema"
```

---

### Task 2: Pending Interrupt Metadata

**Files:**
- Modify: `orchestrator/app/generation_jobs/service.py`
- Test: `orchestrator/tests/test_generation_job_graph_execution.py`

- [ ] **Step 1: Write the failing metadata test**

Add this helper class and test to `orchestrator/tests/test_generation_job_graph_execution.py`:

```python
class FakeInterrupt:
    def __init__(self, value):
        self.value = value


def test_waiting_generation_job_exposes_pending_option_question(monkeypatch):
    class MockGraphWaiting:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            state = dict(payload)
            state["__interrupt__"] = [
                FakeInterrupt(
                    {
                        "type": "option_question",
                        "job_id": state["job_id"],
                        "thread_id": state["thread_id"],
                        "option_question": {
                            "field": "business_type",
                            "question": "어떤 업종의 광고인가요?",
                            "options": [
                                {"id": 1, "label": "카페", "value": "cafe"},
                                {"id": 2, "label": "직접 입력", "value": "custom"},
                            ],
                        },
                    }
                )
            ]
            state["status"] = "waiting_user_input"
            state["messages"] = [{"role": "assistant", "content": "어떤 업종의 광고인가요?"}]
            return state

    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: MockGraphWaiting())

    request = GenerationJobCreateRequest(user_input="광고 만들어줘", run_mode="graph_immediate")
    job = create_generation_job(request)
    executed = execute_generation_job_graph(job.job_id, request)

    assert executed.status == "waiting_user_input"
    assert executed.metadata["pending_interrupt"]["type"] == "option_question"
    assert executed.metadata["pending_interrupt"]["option_question"]["field"] == "business_type"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_generation_job_graph_execution.py::test_waiting_generation_job_exposes_pending_option_question -q
```

Expected: FAIL because waiting jobs do not expose `metadata.pending_interrupt`.

- [ ] **Step 3: Add interrupt extraction helper**

In `orchestrator/app/generation_jobs/service.py`, import the sanitizer:

```python
from orchestrator.app.chat_threads.sanitization import sanitize_chat_payload
```

Add this helper near `mark_generation_job_waiting_user_input`:

```python
def _pending_interrupt_from_state(result_state: dict) -> dict | None:
    interrupts = result_state.get("__interrupt__") or []
    if not interrupts:
        return None
    raw_value = getattr(interrupts[0], "value", None)
    if not isinstance(raw_value, dict):
        return None
    return sanitize_chat_payload(raw_value)
```

- [ ] **Step 4: Save pending interrupt in memory waiting jobs**

In `mark_generation_job_waiting_user_input()`, before `update_generation_job(...)`, add:

```python
    pending_interrupt = _pending_interrupt_from_state(result_state)
    metadata = {
        **(existing.metadata or {}),
        "pending_interrupt": pending_interrupt,
        "assistant_message": assistant_message,
    }
```

Then update the call:

```python
    updated = update_generation_job(
        job_id,
        status="waiting_user_input",
        progress=progress,
        metadata=metadata,
    )
```

- [ ] **Step 5: Save pending interrupt in DB waiting jobs**

In `_mark_generation_job_waiting_user_input_db()`, after `existing` is loaded, add:

```python
        pending_interrupt = _pending_interrupt_from_state(result_state)
        metadata = {
            **(existing.get("metadata") or {}),
            "pending_interrupt": pending_interrupt,
            "assistant_message": assistant_message,
        }
```

Then include metadata in `update_generation_job_row(...)`:

```python
            metadata=metadata,
```

- [ ] **Step 6: Clear stale pending interrupt on running/done/failed**

In `mark_generation_job_running()`, when updating metadata for memory jobs, ensure:

```python
metadata = {**(existing.metadata or {})}
metadata.pop("pending_interrupt", None)
metadata.pop("assistant_message", None)
```

Pass that metadata to `update_generation_job(...)`.

In `_mark_generation_job_running_db()`, merge existing row metadata and remove the same keys before updating the DB row.

In `mark_generation_job_done()` and `mark_generation_job_failed()`, ensure metadata passed to the final job does not keep `pending_interrupt` or `assistant_message`.

- [ ] **Step 7: Run the metadata test to verify it passes**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_generation_job_graph_execution.py::test_waiting_generation_job_exposes_pending_option_question -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add orchestrator/app/generation_jobs/service.py orchestrator/tests/test_generation_job_graph_execution.py
git commit -m "feat(orchestrator): expose generation job graph interrupts"
```

---

### Task 3: Shared Graph Accessor And Resume Execution

**Files:**
- Modify: `orchestrator/app/generation_jobs/execution.py`
- Test: `orchestrator/tests/test_generation_job_graph_execution.py`

- [ ] **Step 1: Write the failing resume test**

Add this test to `orchestrator/tests/test_generation_job_graph_execution.py`:

```python
def test_resume_generation_job_graph_continues_waiting_job(monkeypatch):
    calls = []

    class MockSharedGraph:
        def invoke(self, payload, config: dict | None = None) -> dict:
            calls.append(payload)
            if len(calls) == 1:
                state = dict(payload)
                state["__interrupt__"] = [
                    FakeInterrupt(
                        {
                            "type": "option_question",
                            "job_id": state["job_id"],
                            "thread_id": state["thread_id"],
                            "option_question": {
                                "field": "business_type",
                                "question": "어떤 업종인가요?",
                                "options": [{"id": 1, "label": "카페", "value": "cafe"}],
                            },
                        }
                    )
                ]
                state["status"] = "waiting_user_input"
                state["messages"] = [{"role": "assistant", "content": "어떤 업종인가요?"}]
                return state

            assert getattr(payload, "resume", None) == {
                "job_id": "job_1",
                "thread_id": "thread_1",
                "field": "business_type",
                "value": "cafe",
            }
            return {
                "job_id": "job_1",
                "thread_id": "thread_1",
                "status": "done",
                "result_payload": {"final_image_path": "/fake/final.png"},
                "final_image_path": "/fake/final.png",
            }

    shared_graph = MockSharedGraph()
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: shared_graph)

    request = GenerationJobCreateRequest(user_input="광고 만들어줘", run_mode="graph_immediate")
    job = create_generation_job(request)
    job = execute_generation_job_graph(job.job_id, request)
    assert job.status == "waiting_user_input"

    answer = GenerationJobAnswerRequest(field="business_type", value="cafe")
    resumed = resume_generation_job_graph(job.job_id, answer)

    assert resumed.status == "done"
    assert len(calls) == 2
```

Update imports:

```python
from orchestrator.app.api.schemas.generation_jobs import GenerationJobAnswerRequest, GenerationJobCreateRequest
from orchestrator.app.generation_jobs.execution import execute_generation_job_graph, resume_generation_job_graph
```

- [ ] **Step 2: Run the resume test to verify it fails**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_generation_job_graph_execution.py::test_resume_generation_job_graph_continues_waiting_job -q
```

Expected: FAIL because `resume_generation_job_graph()` and shared graph accessor do not exist.

- [ ] **Step 3: Add shared graph accessor**

In `orchestrator/app/generation_jobs/execution.py`, add:

```python
def get_generation_job_graph():
    from orchestrator.app.api.marketing_graph import MARKETING_GRAPH

    return MARKETING_GRAPH
```

Replace:

```python
        graph = build_marketing_graph()
```

inside `execute_generation_job_graph()` with:

```python
        graph = get_generation_job_graph()
```

Remove the local import of `build_marketing_graph` from `execute_generation_job_graph()` once no longer needed.

- [ ] **Step 4: Factor graph result finalization**

Create a private helper in `orchestrator/app/generation_jobs/execution.py`:

```python
def _finalize_graph_result(job_id: str, request: GenerationJobCreateRequest, result_state: dict, input_snapshot, *, changed_fields: list[str]) -> GenerationJobResponse:
    from orchestrator.app.generation_jobs.service import mark_generation_job_done, mark_generation_job_failed, mark_generation_job_waiting_user_input

    job = get_generation_job(job_id)
    if not job:
        raise ValueError("generation job was not found")

    if "__interrupt__" in result_state:
        last_message = None
        for message in reversed(result_state.get("messages", [])):
            if message.get("role") == "assistant":
                last_message = message
                break
        assistant_message = last_message.get("content") if last_message else "추가 정보가 필요해요."
        updated = mark_generation_job_waiting_user_input(
            job_id=job_id,
            result_state=result_state,
            changed_fields=changed_fields,
            assistant_message=assistant_message,
        )
        return updated or job

    if result_state.get("status") == "done":
        result_payload = result_state.get("result_payload") or {}
        done = mark_generation_job_done(
            job_id,
            result_payload=result_payload,
            output_path=result_state.get("final_image_path"),
            metadata={
                "requested_run_mode": request.run_mode,
                "effective_run_mode": "graph_immediate",
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
```

When factoring, keep the existing snapshot-saving behavior for completed jobs by moving that save into the helper or by keeping a small wrapper block in `execute_generation_job_graph()` before calling `mark_generation_job_done`.

- [ ] **Step 5: Implement resume execution**

Add this function to `orchestrator/app/generation_jobs/execution.py`:

```python
def resume_generation_job_graph(job_id: str, answer: GenerationJobAnswerRequest) -> GenerationJobResponse:
    from langgraph.types import Command
    from orchestrator.app.chat_threads.state_snapshot import calculate_changed_fields
    from orchestrator.app.generation_jobs.service import mark_generation_job_running

    job = get_generation_job(job_id)
    if not job:
        raise ValueError("generation job was not found")
    if job.status != "waiting_user_input":
        raise ValueError("generation job is not waiting for user input")
    if not job.thread_id:
        raise ValueError("generation job has no thread_id")

    running = mark_generation_job_running(job_id, stage="planning")
    job = running or job

    resume_payload = answer.to_resume_payload(job_id=job_id, thread_id=job.thread_id)
    graph = get_generation_job_graph()
    result_state = graph.invoke(
        Command(resume=resume_payload),
        config={"configurable": {"thread_id": job.thread_id}},
    )
    changed_fields = calculate_changed_fields(None, result_state)

    synthetic_request = GenerationJobCreateRequest(
        userInput=str((job.metadata or {}).get("user_input_preview") or "resume generation job"),
        threadId=job.thread_id,
        runMode="graph_immediate",
        metadata=job.metadata or {},
    )
    return _finalize_graph_result(
        job_id,
        synthetic_request,
        result_state,
        input_snapshot=None,
        changed_fields=changed_fields,
    )
```

- [ ] **Step 6: Run graph execution tests**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_generation_job_graph_execution.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add orchestrator/app/generation_jobs/execution.py orchestrator/tests/test_generation_job_graph_execution.py
git commit -m "feat(orchestrator): resume waiting generation jobs"
```

---

### Task 4: Orchestrator Answer Route

**Files:**
- Modify: `orchestrator/app/api/routers/generation_jobs.py`
- Test: `orchestrator/tests/test_api_generation_jobs_router.py`

- [ ] **Step 1: Write the failing route test**

Add this test:

```python
def test_generation_job_answer_route_resumes_waiting_job(client, monkeypatch):
    captured = {}

    def fake_resume_generation_job_graph(job_id, answer):
        from orchestrator.app.generation_jobs.service import get_generation_job, update_generation_job

        captured["job_id"] = job_id
        captured["payload"] = answer.to_resume_payload(job_id=job_id, thread_id="thread_1")
        updated = update_generation_job(
            job_id,
            status="done",
            metadata={"execution_mode": "graph_execution"},
        )
        return updated or get_generation_job(job_id)

    monkeypatch.setattr(
        "orchestrator.app.api.routers.generation_jobs.resume_generation_job_graph",
        fake_resume_generation_job_graph,
    )

    create_response = client.post(
        "/api/v1/generation-jobs",
        json={"user_input": "광고 만들어줘", "run_mode": "queued_only"},
    )
    job = create_response.json()["job"]
    from orchestrator.app.generation_jobs.service import update_generation_job
    update_generation_job(job["job_id"], status="waiting_user_input")

    answer_response = client.post(
        f"/api/v1/generation-jobs/{job['job_id']}/answer",
        json={"field": "business_type", "value": "cafe"},
    )

    assert answer_response.status_code == 200
    assert captured["job_id"] == job["job_id"]
    assert captured["payload"]["field"] == "business_type"
    assert captured["payload"]["value"] == "cafe"
```

- [ ] **Step 2: Run the route test to verify it fails**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_api_generation_jobs_router.py::test_generation_job_answer_route_resumes_waiting_job -q
```

Expected: FAIL because the route does not exist.

- [ ] **Step 3: Add route imports**

In `orchestrator/app/api/routers/generation_jobs.py`, add:

```python
    GenerationJobAnswerRequest,
```

to schema imports, and add:

```python
    resume_generation_job_graph,
```

to execution imports.

- [ ] **Step 4: Add answer route**

Add this route below `get_generation_job_route`:

```python
@router.post("/generation-jobs/{job_id}/answer", response_model=GenerationJobGetResponse)
def answer_generation_job_route(job_id: str, request: GenerationJobAnswerRequest) -> GenerationJobGetResponse:
    job = get_generation_job(job_id)
    if not job:
        _generation_job_not_found(job_id)
    try:
        resumed = resume_generation_job_graph(job_id, request)
    except ValueError as exc:
        raise_api_error(
            status_code=409,
            error_code="generation_job_resume_failed",
            message="Generation job could not be resumed.",
            detail=str(exc),
        )
    return GenerationJobGetResponse(job=resumed)
```

- [ ] **Step 5: Run router tests**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_api_generation_jobs_router.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add orchestrator/app/api/routers/generation_jobs.py orchestrator/tests/test_api_generation_jobs_router.py
git commit -m "feat(orchestrator): add generation job answer route"
```

---

### Task 5: BFF And Next Proxy Routes

**Files:**
- Modify: `apps/bff/src/app.js`
- Modify: `apps/bff/tests/generate.test.js`
- Create: `apps/web/app/api/generation-jobs/[jobId]/answer/route.ts`

- [ ] **Step 1: Write the failing BFF test**

Add this test to `apps/bff/tests/generate.test.js` near the existing generation job proxy test:

```js
it("proxies generation job answers to the orchestrator", async () => {
  const fetchImpl = vi.fn(async () =>
    jsonResponse({
      success: true,
      job: {
        job_id: "job_1",
        status: "done",
        progress: { progress_percent: 100, current_stage: "completed", stage_order: [] },
        metadata: { execution_mode: "graph_execution" }
      }
    })
  );
  const app = buildApp({ orchestratorBaseUrl: "http://orchestrator", fetchImpl });

  const response = await app.inject({
    method: "POST",
    url: "/api/generation-jobs/job_1/answer",
    payload: { field: "business_type", value: "cafe" }
  });

  expect(response.statusCode).toBe(200);
  expect(response.json().job.status).toBe("done");
  expect(fetchImpl).toHaveBeenCalledWith(
    "http://orchestrator/api/v1/generation-jobs/job_1/answer",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ field: "business_type", value: "cafe" })
    })
  );
  await app.close();
});
```

- [ ] **Step 2: Run the BFF test to verify it fails**

Run:

```bash
npm test -- --run tests/generate.test.js
```

from `apps/bff`.

Expected: FAIL because the BFF route does not exist.

- [ ] **Step 3: Add BFF answer schema**

In `apps/bff/src/app.js`, add:

```js
const generationJobAnswerSchema = z.object({
  field: z.string().trim().min(1).optional(),
  value: z.string().optional(),
  customText: z.string().optional(),
  selectedCopyId: z.string().optional(),
  userCustomHeadline: z.string().optional(),
  userCustomSubcopy: z.string().optional(),
  payload: z.record(z.unknown()).optional()
}).passthrough();
```

- [ ] **Step 4: Add BFF answer route**

Below the GET generation job route, add:

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

- [ ] **Step 5: Create Next.js proxy route**

Create `apps/web/app/api/generation-jobs/[jobId]/answer/route.ts`:

```ts
import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function POST(request: NextRequest, { params }: { params: { jobId: string } }) {
  return proxyOrchestratorJson(request, "POST", `/api/v1/generation-jobs/${encodeURIComponent(params.jobId)}/answer`);
}
```

- [ ] **Step 6: Run BFF tests**

Run:

```bash
npm test -- --run tests/generate.test.js
```

from `apps/bff`.

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/bff/src/app.js apps/bff/tests/generate.test.js apps/web/app/api/generation-jobs/[jobId]/answer/route.ts
git commit -m "feat(api): proxy generation job answers"
```

---

### Task 6: Web API Client And Interrupt Parsing

**Files:**
- Modify: `apps/web/lib/api-client.ts`
- Modify: `apps/web/lib/api-client.test.ts`
- Create: `apps/web/lib/generation-job-interrupt.ts`
- Create: `apps/web/lib/generation-job-interrupt.test.ts`

- [ ] **Step 1: Write API client test**

In `apps/web/lib/api-client.test.ts`, add `answerGenerationJob` to the import list and add:

```ts
it("answers generation job questions through the BFF", async () => {
  const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
    jsonResponse({
      success: true,
      job: {
        job_id: "job_1",
        status: "done",
        progress: { progress_percent: 100, current_stage: "completed" },
        metadata: { execution_mode: "graph_execution" }
      }
    })
  );
  vi.stubGlobal("fetch", fetchMock);

  const response = await answerGenerationJob("job_1", {
    field: "business_type",
    value: "cafe",
    customText: undefined
  });

  expect(String(fetchMock.mock.calls[0][0])).toBe("http://127.0.0.1:4000/api/generation-jobs/job_1/answer");
  expect(fetchMock.mock.calls[0][1]).toEqual(
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ field: "business_type", value: "cafe" })
    })
  );
  expect(response.job.status).toBe("done");
});
```

- [ ] **Step 2: Write interrupt parser test**

Create `apps/web/lib/generation-job-interrupt.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { getPendingGenerationJobOptionQuestion, hasPendingGenerationJobInterrupt } from "./generation-job-interrupt";
import type { GenerationJob } from "./api-client";

describe("generation job interrupt helpers", () => {
  it("extracts option questions from generation job metadata", () => {
    const job: GenerationJob = {
      job_id: "job_1",
      status: "waiting_user_input",
      progress: { progress_percent: 50, current_stage: "waiting_user_input" },
      metadata: {
        pending_interrupt: {
          type: "option_question",
          option_question: {
            field: "business_type",
            question: "어떤 업종인가요?",
            options: [{ id: 1, label: "카페", value: "cafe" }]
          }
        }
      }
    };

    expect(hasPendingGenerationJobInterrupt(job)).toBe(true);
    expect(getPendingGenerationJobOptionQuestion(job)?.field).toBe("business_type");
  });

  it("returns null for unsupported interrupts", () => {
    const job: GenerationJob = {
      job_id: "job_1",
      status: "waiting_user_input",
      metadata: { pending_interrupt: { type: "copy_candidate_selection" } }
    };

    expect(hasPendingGenerationJobInterrupt(job)).toBe(true);
    expect(getPendingGenerationJobOptionQuestion(job)).toBeNull();
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
npm test -- --run lib/api-client.test.ts lib/generation-job-interrupt.test.ts
```

from `apps/web`.

Expected: FAIL because the client function and parser file do not exist.

- [ ] **Step 4: Add API client types and function**

In `apps/web/lib/api-client.ts`, add:

```ts
export type GenerationJobAnswerPayload = {
  field?: string;
  value?: string;
  customText?: string;
  selectedCopyId?: string;
  userCustomHeadline?: string;
  userCustomSubcopy?: string;
  payload?: Record<string, unknown>;
};
```

Add:

```ts
function compactPayload(payload: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(payload).filter(([, value]) => value !== undefined && value !== null));
}
```

Add:

```ts
export function answerGenerationJob(jobId: string, payload: GenerationJobAnswerPayload): Promise<GenerationJobResponse> {
  return postJson<GenerationJobResponse>(`/api/generation-jobs/${encodeURIComponent(jobId)}/answer`, compactPayload(payload));
}
```

- [ ] **Step 5: Create interrupt parser**

Create `apps/web/lib/generation-job-interrupt.ts`:

```ts
import type { GenerationJob } from "./api-client";
import type { OptionQuestion } from "@/types/marketing";

export type GenerationJobPendingInterrupt = {
  type?: string;
  option_question?: OptionQuestion;
  [key: string]: unknown;
};

export function getPendingGenerationJobInterrupt(job: GenerationJob | null | undefined): GenerationJobPendingInterrupt | null {
  const metadata = job?.metadata;
  const pending = metadata?.pending_interrupt;
  if (!pending || typeof pending !== "object" || Array.isArray(pending)) {
    return null;
  }
  return pending as GenerationJobPendingInterrupt;
}

export function hasPendingGenerationJobInterrupt(job: GenerationJob | null | undefined): boolean {
  return getPendingGenerationJobInterrupt(job) !== null;
}

export function getPendingGenerationJobOptionQuestion(job: GenerationJob | null | undefined): OptionQuestion | null {
  if (job?.status !== "waiting_user_input") {
    return null;
  }
  const interrupt = getPendingGenerationJobInterrupt(job);
  if (interrupt?.type !== "option_question") {
    return null;
  }
  return interrupt.option_question ?? null;
}
```

- [ ] **Step 6: Run web helper tests**

Run:

```bash
npm test -- --run lib/api-client.test.ts lib/generation-job-interrupt.test.ts
```

from `apps/web`.

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/web/lib/api-client.ts apps/web/lib/api-client.test.ts apps/web/lib/generation-job-interrupt.ts apps/web/lib/generation-job-interrupt.test.ts
git commit -m "feat(web): add generation job answer client"
```

---

### Task 7: Chat Flow State For Generation Job Questions

**Files:**
- Modify: `apps/web/types/marketing.ts`
- Modify: `apps/web/lib/chat-flow.ts`
- Modify: `apps/web/lib/chat-flow.test.ts`

- [ ] **Step 1: Write reducer tests**

Add tests to `apps/web/lib/chat-flow.test.ts`:

```ts
it("stores a generation job question while preserving the final step", () => {
  const initial = createInitialChatFlowState();
  const state = chatFlowReducer(initial, {
    type: "generationJobQuestionReceived",
    generationJob: {
      job_id: "job_1",
      status: "waiting_user_input",
      progress: { progress_percent: 50, current_stage: "waiting_user_input" }
    },
    question: {
      field: "business_type",
      question: "어떤 업종인가요?",
      options: [{ id: 1, label: "카페", value: "cafe" }]
    }
  });

  expect(state.step).toBe(4);
  expect(state.currentQuestion?.field).toBe("business_type");
  expect(state.conversationMessages.at(-1)?.text).toBe("어떤 업종인가요?");
  expect(state.isLoading).toBe(false);
});

it("marks generation job answer submission as loading", () => {
  const initial = createInitialChatFlowState();
  const asked = chatFlowReducer(initial, {
    type: "generationJobQuestionReceived",
    generationJob: { job_id: "job_1", status: "waiting_user_input" },
    question: {
      field: "business_type",
      question: "어떤 업종인가요?",
      options: [{ id: 1, label: "카페", value: "cafe" }]
    }
  });
  const answered = chatFlowReducer(asked, { type: "submitGenerationJobAnswer", label: "카페" });

  expect(answered.isLoading).toBe(true);
  expect(answered.conversationMessages.at(-1)?.text).toBe("카페");
});
```

- [ ] **Step 2: Run reducer tests to verify they fail**

Run:

```bash
npm test -- --run lib/chat-flow.test.ts
```

from `apps/web`.

Expected: FAIL because the new action types do not exist.

- [ ] **Step 3: Add action types**

In `apps/web/types/marketing.ts`, add to `ChatFlowAction`:

```ts
  | {
      type: "generationJobQuestionReceived";
      generationJob: GenerationJob;
      question: OptionQuestion;
    }
  | { type: "submitGenerationJobAnswer"; label: string }
```

- [ ] **Step 4: Add reducer cases**

In `apps/web/lib/chat-flow.ts`, add:

```ts
    case "generationJobQuestionReceived":
      return {
        ...state,
        step: 4,
        progress: { current: 4, total: 4, label: "추가 정보" },
        generationJob: action.generationJob,
        currentQuestion: action.question,
        conversationMessages: [
          ...state.conversationMessages,
          { role: "assistant", text: action.question.question }
        ],
        isLoading: false,
        errorMessage: null
      };

    case "submitGenerationJobAnswer":
      return {
        ...state,
        conversationMessages: [...state.conversationMessages, { role: "user", text: action.label }],
        isLoading: true,
        errorMessage: null
      };
```

When `generationJobUpdated` receives a non-waiting job, clear `currentQuestion`:

```ts
currentQuestion: action.generationJob.status === "waiting_user_input" ? state.currentQuestion : null,
```

- [ ] **Step 5: Run reducer tests**

Run:

```bash
npm test -- --run lib/chat-flow.test.ts
```

from `apps/web`.

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/web/types/marketing.ts apps/web/lib/chat-flow.ts apps/web/lib/chat-flow.test.ts
git commit -m "feat(web): store generation job questions"
```

---

### Task 8: ChatGenerateClient Resume Flow

**Files:**
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx`
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`

- [ ] **Step 1: Write UI flow test**

Add this test to `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`:

```ts
it("answers a waiting generation job question and resumes polling", async () => {
  const api = await import("@/lib/api-client");
  vi.mocked(api.createGenerationJob).mockResolvedValueOnce({
    success: true,
    job: {
      job_id: "generation_job_waiting",
      thread_id: "thread_1",
      status: "waiting_user_input",
      progress: { progress_percent: 50, current_stage: "waiting_user_input" },
      metadata: {
        pending_interrupt: {
          type: "option_question",
          option_question: {
            field: "business_type",
            question: "어떤 업종인가요?",
            options: [{ id: 1, label: "카페", value: "cafe" }]
          }
        }
      }
    }
  });
  vi.mocked(api.answerGenerationJob).mockResolvedValueOnce({
    success: true,
    job: {
      job_id: "generation_job_waiting",
      thread_id: "thread_1",
      status: "done",
      progress: { progress_percent: 100, current_stage: "completed" },
      result_payload: {
        schema_version: "result_artifact_v1",
        preview_image_url: "/api/generated-assets?path=data%2Foutputs%2Fgeneration_job_waiting%2Ffinal_0.png",
        final_image_path: "data/outputs/generation_job_waiting/final_0.png",
        engine: "gpt_image_2"
      }
    }
  });

  (globalThis as typeof globalThis & { React: typeof React }).React = React;
  const { ChatGenerateClient } = await import("./ChatGenerateClient");

  render(<ChatGenerateClient initialSurface="chat" />);

  fireEvent.change(screen.getByLabelText("광고 요청 입력"), {
    target: { value: "광고 만들어줘" }
  });
  fireEvent.click(screen.getByText("AI 자동 완성"));
  fireEvent.click(screen.getByLabelText("요청 보내기"));

  await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
  fireEvent.click(screen.getByText(/생성 결과 확인하기/));

  await waitFor(() => expect(screen.getByText("어떤 업종인가요?")).toBeTruthy());
  fireEvent.click(screen.getByText("카페"));

  await waitFor(() =>
    expect(api.answerGenerationJob).toHaveBeenCalledWith("generation_job_waiting", {
      field: "business_type",
      value: "cafe",
      customText: undefined
    })
  );
  await waitFor(() => expect(screen.getByText("찰떡 광고 시안이 완성됐어요")).toBeTruthy());
});
```

Update the top mock to include:

```ts
answerGenerationJob: vi.fn(),
```

- [ ] **Step 2: Run UI test to verify it fails**

Run:

```bash
npm test -- --run app/generate/chat/ChatGenerateClient.test.tsx
```

from `apps/web`.

Expected: FAIL because waiting generation jobs still go to complete state and no answer client is wired.

- [ ] **Step 3: Add imports**

In `ChatGenerateClient.tsx`, import:

```ts
  answerGenerationJob,
```

from `@/lib/api-client`, and import:

```ts
import { getPendingGenerationJobOptionQuestion } from "@/lib/generation-job-interrupt";
```

- [ ] **Step 4: Extract polling helper**

Inside `ChatGenerateClient`, create:

```ts
  async function pollGenerationJobUntilTerminalOrQuestion(initialJob: GenerationJob): Promise<GenerationJob> {
    let currentJob = initialJob;
    dispatch({ type: "generationJobUpdated", generationJob: currentJob });
    setGenerationProgress(generationProgressFromJob(currentJob));

    const pendingQuestion = getPendingGenerationJobOptionQuestion(currentJob);
    if (pendingQuestion) {
      dispatch({ type: "generationJobQuestionReceived", generationJob: currentJob, question: pendingQuestion });
      setGenerationStage("jobQuestion");
      lastPrimedStageRef.current = "generating";
      navigateTo("chat", "generating");
      return currentJob;
    }

    for (let attempt = 0; attempt < GENERATION_JOB_MAX_POLLS && !isTerminalGenerationJobStatus(currentJob.status); attempt += 1) {
      await delay(GENERATION_JOB_POLL_INTERVAL_MS);
      const response = await getGenerationJob(currentJob.job_id);
      currentJob = response.job;
      dispatch({ type: "generationJobUpdated", generationJob: currentJob });
      setGenerationProgress(generationProgressFromJob(currentJob));

      const nextQuestion = getPendingGenerationJobOptionQuestion(currentJob);
      if (nextQuestion) {
        dispatch({ type: "generationJobQuestionReceived", generationJob: currentJob, question: nextQuestion });
        setGenerationStage("jobQuestion");
        lastPrimedStageRef.current = "generating";
        navigateTo("chat", "generating");
        return currentJob;
      }
    }

    setGenerationProgress(generationProgressFromJob(currentJob));
    setGenerationStage("complete");
    lastPrimedStageRef.current = "complete";
    navigateTo("chat", "complete");
    return currentJob;
  }
```

Add `"jobQuestion"` to `GenerationStage`:

```ts
type GenerationStage = "brief" | "generating" | "jobQuestion" | "browsing" | "complete" | "similarBrowsing";
```

- [ ] **Step 5: Use polling helper after create**

In `handleOpenGeneratedResult()`, replace the manual polling loop with:

```ts
      await pollGenerationJobUntilTerminalOrQuestion(created.job);
```

- [ ] **Step 6: Add answer handler**

Add:

```ts
  async function handleAnswerGenerationJobQuestion(input: { value: string; label: string; customText?: string }) {
    const question = state.currentQuestion;
    const jobId = state.generationJob?.job_id;
    if (!question || !jobId) {
      return;
    }

    dispatch({ type: "submitGenerationJobAnswer", label: input.label });
    setGenerationStage("generating");
    setGenerationProgress((current) => Math.max(current, 52));

    try {
      const response = await answerGenerationJob(jobId, {
        field: question.field,
        value: input.value,
        customText: input.customText
      });
      await pollGenerationJobUntilTerminalOrQuestion(response.job);
    } catch (error) {
      dispatch({
        type: "generationJobFailed",
        message: error instanceof Error ? error.message : "추가 정보를 보내지 못했어요. 잠시 후 다시 시도해주세요."
      });
      setGenerationStage("jobQuestion");
    }
  }
```

- [ ] **Step 7: Render question step during final generation**

Add this render block before `GenerationInProgressStep`:

```tsx
      {appSurface === "chat" && state.step === 4 && generationStage === "jobQuestion" && state.currentQuestion ? (
        <ChatContextQuestionStep
          state={state}
          onBack={() => setGenerationStage("brief")}
          onAnswer={handleAnswerGenerationJobQuestion}
        />
      ) : null}
```

- [ ] **Step 8: Run UI test**

Run:

```bash
npm test -- --run app/generate/chat/ChatGenerateClient.test.tsx
```

from `apps/web`.

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add apps/web/app/generate/chat/ChatGenerateClient.tsx apps/web/app/generate/chat/ChatGenerateClient.test.tsx
git commit -m "feat(web): resume generation job questions"
```

---

### Task 9: Coverage Matrix Update

**Files:**
- Modify: `apps/web/lib/ui-orchestrator-route-coverage.ts`
- Modify: `apps/web/lib/ui-orchestrator-route-coverage.test.ts`

- [ ] **Step 1: Update coverage test**

In `apps/web/lib/ui-orchestrator-route-coverage.test.ts`, update the final generation API expectation:

```ts
expect(row?.apiCalls).toEqual([
  "POST /api/generation-jobs",
  "GET /api/generation-jobs/{job_id}",
  "POST /api/generation-jobs/{job_id}/answer"
]);
```

Add:

```ts
expect(row?.graphNodesReached).toEqual(expect.arrayContaining(["options", "state_update"]));
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
npm test -- --run lib/ui-orchestrator-route-coverage.test.ts
```

from `apps/web`.

Expected: FAIL because coverage does not include answer API yet.

- [ ] **Step 3: Update coverage row**

In `apps/web/lib/ui-orchestrator-route-coverage.ts`, update final generation `apiCalls`:

```ts
apiCalls: [
  "POST /api/generation-jobs",
  "GET /api/generation-jobs/{job_id}",
  "POST /api/generation-jobs/{job_id}/answer"
],
```

Update `graphNodesReached`:

```ts
graphNodesReached: ["options", "state_update", ...FINAL_GENERATION_GRAPH_CHAIN],
```

Update note:

```ts
notes: "현재 UI의 모델 선택은 graph_immediate generation job으로 전달되며, 부족한 컨텍스트가 있으면 generation job answer API로 같은 graph thread를 resume한다."
```

- [ ] **Step 4: Run coverage test**

Run:

```bash
npm test -- --run lib/ui-orchestrator-route-coverage.test.ts
```

from `apps/web`.

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/lib/ui-orchestrator-route-coverage.ts apps/web/lib/ui-orchestrator-route-coverage.test.ts
git commit -m "test(web): cover generation job resume loop"
```

---

### Task 10: Full Verification

**Files:**
- Verify only.

- [ ] **Step 1: Run targeted web tests**

Run:

```bash
npm test -- --run lib/api-client.test.ts lib/generation-job-interrupt.test.ts lib/chat-flow.test.ts app/generate/chat/ChatGenerateClient.test.tsx lib/ui-orchestrator-route-coverage.test.ts
```

from `apps/web`.

Expected: PASS. Existing React `act(...)` warnings may appear.

- [ ] **Step 2: Run BFF tests**

Run:

```bash
npm test -- --run tests/generate.test.js
```

from `apps/bff`.

Expected: PASS.

- [ ] **Step 3: Run orchestrator tests**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_api_contract_generation_jobs.py orchestrator/tests/test_generation_job_graph_execution.py orchestrator/tests/test_api_generation_jobs_router.py -q
```

from the repo root.

Expected: PASS.

- [ ] **Step 4: Run TypeScript check**

Run:

```bash
npx tsc --noEmit
```

from `apps/web`.

Expected: PASS.

- [ ] **Step 5: Run whitespace check**

Run:

```bash
git diff --check
```

from the repo root.

Expected: no output.

---

## Expected End State

- A final generation job can return `status: "waiting_user_input"` with `metadata.pending_interrupt`.
- The UI shows the graph's option question instead of incorrectly moving to final results.
- The user answer is sent to `POST /api/generation-jobs/{job_id}/answer`.
- Orchestrator resumes the same graph thread with `Command(resume=...)`.
- The UI returns to progress polling and eventually displays the generated result.
- Unsupported interrupts are not treated as successful generated images.

## Self-Review

- Spec coverage: The plan covers Orchestrator schema, interrupt metadata, resume execution, API route, BFF/Next proxy, web API client, UI state, UI rendering, coverage, and verification.
- Placeholder scan: No unfinished markers or open-ended implementation placeholders remain.
- Type consistency: `GenerationJobAnswerRequest`, `answerGenerationJob`, `pending_interrupt`, `option_question`, and `generationJobQuestionReceived` names are consistent across backend, BFF, frontend, and tests.
