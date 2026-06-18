# Thread Resume Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make generated workspaces resume deterministically so completed posters open as results, pending jobs resume the correct waiting job, stale snapshots do not create duplicate jobs, and native copy overflow cannot crash image generation.

**Architecture:** Move "what should this thread do when opened?" into a backend-owned resume contract, then make the frontend render and navigate from that contract instead of inferring from `thread.status`. Guard generation job creation with explicit continuation modes and strip transient snapshot state when starting a new turn. Add a defensive native-copy fitting layer so long model copy is shortened before Pydantic validation.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, Postgres repositories, pytest, Next.js 14, React 18, TypeScript, Vitest.

---

## Why This Plan Exists

The investigated beauty-salon case had two different outcomes in the same thread family:

- A completed poster output exists for `thread_40f80c2d7e5448d389f270abbaa533d3`, with R2 object `final_composite_poster.png`.
- The same thread later had `job_dc3424008afd4d329bb504433dca8d1d` in `waiting_user_input`, so the latest snapshot asked "어떤 업종의 광고인가요?" even though the original prompt already included "프리미엄 뷰티살롱".
- A later 강남-style generation failed before image generation because `NativeCopyCandidate.total_character_count` received 96 characters while the schema limit is 80.

The root problem is not only extraction quality. The current system has no canonical resume decision. The frontend uses `thread.status` to choose "보기" vs "이어하기", the backend clears `active_job_id` when a job waits for user input, and creating a new job on an existing thread blindly restores the latest snapshot. That allows stale waiting state to mask a completed result and can create a new duplicate job from the wrong state.

This plan fixes the lifecycle contract first, then the UI and copy overflow symptom.

## Scope Check

This is one cohesive subsystem: generated thread lifecycle and resume. It touches backend schemas/repositories/service, generation job creation rules, frontend thread opening behavior, and one defensive native-copy validator. It does not redesign the whole marketing-intake graph, R2 storage, archive system, or visual rendering pipeline.

## File Structure

Create:

- `orchestrator/app/chat_threads/resume_policy.py` - Pure policy function that turns thread/job/snapshot rows into a typed resume state.
- `orchestrator/tests/test_chat_thread_resume_policy.py` - Fast unit tests for resume-action precedence.
- `orchestrator/tests/test_chat_thread_resume_api.py` - API/service tests for the new `/resume-state` contract.

Modify:

- `orchestrator/app/api/schemas/chat_threads.py` - Add `ChatThreadResumeStateResponse`, expose `resume_state` and public `final_output_id`.
- `orchestrator/app/db/repositories/chat_threads.py` - Join final output public id and final job public id in thread reads.
- `orchestrator/app/db/repositories/generation_jobs.py` - Add latest waiting-job lookup for a thread.
- `orchestrator/app/chat_threads/service.py` - Attach resume state to thread responses and add `get_chat_thread_resume_state`.
- `orchestrator/app/api/routers/chat_threads.py` - Add `GET /chat-threads/{thread_id}/resume-state`.
- `orchestrator/app/chat_threads/errors.py` - Add pending-job conflict error.
- `orchestrator/app/api/schemas/generation_jobs.py` - Add `continuation_mode`.
- `orchestrator/app/generation_jobs/service.py` - Enforce continuation modes and use mode-aware state restore.
- `orchestrator/app/chat_threads/state_service.py` - Add transient-state stripping for new generation turns.
- `orchestrator/app/llm/native_copy_candidate_service.py` - Fit candidate copy to schema capacity before constructing `NativeCopyCandidate`.
- `orchestrator/tests/test_generation_jobs.py` - Add pending/final-output creation guard regressions.
- `orchestrator/tests/test_native_copy_candidates.py` - Add long-copy regression.
- `apps/web/lib/api-client.ts` - Add resume-state types and API client function.
- `apps/web/components/generate/StudioEntryStep.tsx` - Use server resume action for button labels.
- `apps/web/app/generate/chat/ChatGenerateClient.tsx` - Open threads using resume state and pass explicit `continuationMode` on create.
- `apps/web/app/generate/chat/ChatGenerateClient.test.tsx` - Add UI regressions for completed-draft and pending-thread behavior.

## Data Contract

The backend will expose this action set:

```python
ThreadResumeAction = Literal[
    "view_result",
    "answer_pending_job",
    "retry_failed_job",
    "continue_draft",
    "locked_running",
]
```

Action meanings:

- `view_result`: The thread has a public final output. The backend should include the public final job id in `resume_job_id` when it can be resolved, and the frontend should load that job with `getGenerationJob` instead of creating a new job.
- `answer_pending_job`: A graph job is waiting for user input. The frontend should render the pending question and answer that job via `/generation-jobs/{job_id}/answer`.
- `retry_failed_job`: The latest meaningful state is failed and there is no final output to view. The frontend can show retry affordance.
- `continue_draft`: The thread is a real draft with no result, no running job, and no pending waiting job.
- `locked_running`: The thread has an active generation job. The frontend should poll or show progress.

Precedence:

1. Archived threads remain listed separately by the existing UI, but their resume state still reflects their underlying result/pending/draft state.
2. `locked_running` wins when `active_job_id` exists.
3. `view_result` wins when a public final output exists, unless a waiting job has explicit metadata `continuation_mode` in `{"new_turn", "retry_failed", "regenerate_from_output"}`.
4. `answer_pending_job` wins for non-final threads with latest waiting job.
5. `retry_failed_job` wins when latest snapshot kind is `job_failed` or thread status is `failed`.
6. Otherwise `continue_draft`.

The explicit final-output preference fixes legacy contaminated data: a completed result followed by an accidental waiting job opens the poster instead of asking a stale first-question prompt.

---

### Task 1: Add Pure Resume Policy and Schema

**Files:**

- Create: `orchestrator/app/chat_threads/resume_policy.py`
- Create: `orchestrator/tests/test_chat_thread_resume_policy.py`
- Modify: `orchestrator/app/api/schemas/chat_threads.py`

- [ ] **Step 1: Write failing resume policy tests**

Create `orchestrator/tests/test_chat_thread_resume_policy.py`:

```python
from types import SimpleNamespace

from orchestrator.app.chat_threads.resume_policy import compute_thread_resume_state


def _snapshot(kind: str, snapshot_id: str = "snapshot_1"):
    return SimpleNamespace(snapshot_kind=kind, snapshot_id=snapshot_id, state_payload={})


def test_resume_state_views_final_output_even_when_legacy_waiting_job_exists():
    state = compute_thread_resume_state(
        thread={
            "public_thread_id": "thread_done",
            "status": "draft",
            "active_public_job_id": None,
            "final_public_job_id": "job_done",
            "final_public_output_id": "output_done",
        },
        latest_snapshot=_snapshot("waiting_user_input"),
        waiting_job={
            "public_job_id": "job_waiting",
            "metadata": {"assistant_message": "어떤 업종의 광고인가요?"},
        },
    )

    assert state.action == "view_result"
    assert state.final_output_id == "output_done"
    assert state.resume_job_id == "job_done"
    assert state.reason == "thread_has_final_output"


def test_resume_state_answers_explicit_continuation_waiting_job_over_final_output():
    state = compute_thread_resume_state(
        thread={
            "public_thread_id": "thread_editing",
            "status": "draft",
            "active_public_job_id": None,
            "final_public_job_id": "job_done",
            "final_public_output_id": "output_done",
        },
        latest_snapshot=_snapshot("waiting_user_input"),
        waiting_job={
            "public_job_id": "job_waiting",
            "metadata": {
                "continuation_mode": "new_turn",
                "pending_interrupt": {"field": "business_type", "question": "어떤 업종의 광고인가요?"},
            },
        },
    )

    assert state.action == "answer_pending_job"
    assert state.resume_job_id == "job_waiting"
    assert state.final_output_id == "output_done"
    assert state.current_question == {"field": "business_type", "question": "어떤 업종의 광고인가요?"}


def test_resume_state_locks_running_thread():
    state = compute_thread_resume_state(
        thread={
            "public_thread_id": "thread_running",
            "status": "generating",
            "active_public_job_id": "job_running",
            "final_public_output_id": None,
        },
        latest_snapshot=None,
        waiting_job=None,
    )

    assert state.action == "locked_running"
    assert state.resume_job_id == "job_running"
    assert state.reason == "thread_has_active_job"


def test_resume_state_answers_pending_thread_without_output():
    state = compute_thread_resume_state(
        thread={
            "public_thread_id": "thread_pending",
            "status": "draft",
            "active_public_job_id": None,
            "final_public_output_id": None,
        },
        latest_snapshot=_snapshot("waiting_user_input"),
        waiting_job={
            "public_job_id": "job_waiting",
            "metadata": {
                "pending_interrupt": {"field": "business_type"},
                "assistant_message": "어떤 업종의 광고인가요?",
            },
        },
    )

    assert state.action == "answer_pending_job"
    assert state.resume_job_id == "job_waiting"
    assert state.current_question == {"field": "business_type"}


def test_resume_state_retries_failed_thread_without_output():
    state = compute_thread_resume_state(
        thread={
            "public_thread_id": "thread_failed",
            "status": "failed",
            "active_public_job_id": None,
            "final_public_output_id": None,
        },
        latest_snapshot=_snapshot("job_failed", snapshot_id="snapshot_failed"),
        waiting_job=None,
    )

    assert state.action == "retry_failed_job"
    assert state.latest_snapshot_id == "snapshot_failed"
    assert state.reason == "latest_snapshot_failed"


def test_resume_state_continues_plain_draft():
    state = compute_thread_resume_state(
        thread={
            "public_thread_id": "thread_draft",
            "status": "draft",
            "active_public_job_id": None,
            "final_public_output_id": None,
        },
        latest_snapshot=_snapshot("input"),
        waiting_job=None,
    )

    assert state.action == "continue_draft"
    assert state.reason == "thread_is_draft"
```

- [ ] **Step 2: Run policy tests and confirm missing module failure**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_chat_thread_resume_policy.py -q
```

Expected: fail during import with `ModuleNotFoundError: No module named 'orchestrator.app.chat_threads.resume_policy'`.

- [ ] **Step 3: Add resume schema types**

In `orchestrator/app/api/schemas/chat_threads.py`, after `ChatThreadStatus`, add:

```python
ThreadResumeAction = Literal[
    "view_result",
    "answer_pending_job",
    "retry_failed_job",
    "continue_draft",
    "locked_running",
]
```

After `ChatMessageCreateRequest`, add:

```python
class ChatThreadResumeStateResponse(BaseModel):
    action: ThreadResumeAction
    thread_id: str
    resume_job_id: str | None = None
    final_output_id: str | None = None
    latest_snapshot_id: str | None = None
    snapshot_kind: str | None = None
    reason: str
    current_question: dict[str, Any] | None = None
```

Update `ChatThreadResponse`:

```python
class ChatThreadResponse(BaseModel):
    thread_id: str
    title: str | None = None
    status: ChatThreadStatus
    brand_kit_id: str | None = None
    project_id: str | None = None
    final_brief: dict[str, Any] = Field(default_factory=dict)
    active_job_id: str | None = None
    final_output_id: str | None = None
    has_final_output: bool = False
    resume_state: ChatThreadResumeStateResponse | None = None
    last_message_at: str
    archived_at: str | None = None
    created_at: str
    updated_at: str
```

After `ChatThreadGetResponse`, add:

```python
class ChatThreadResumeStateGetResponse(BaseModel):
    success: Literal[True] = True
    resume_state: ChatThreadResumeStateResponse
    meta: ApiMeta = Field(default_factory=ApiMeta)
```

- [ ] **Step 4: Add pure policy implementation**

Create `orchestrator/app/chat_threads/resume_policy.py`:

```python
"""Pure resume-action policy for generated chat threads."""

from __future__ import annotations

from typing import Any

from orchestrator.app.api.schemas.chat_threads import ChatThreadResumeStateResponse

_EXPLICIT_PENDING_MODES = {"new_turn", "retry_failed", "regenerate_from_output"}


def _get_value(source: Any, key: str, default: Any = None) -> Any:
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _public_thread_id(thread: Any) -> str:
    return str(_get_value(thread, "public_thread_id") or _get_value(thread, "thread_id") or "")


def _snapshot_id(snapshot: Any) -> str | None:
    value = _get_value(snapshot, "snapshot_id")
    return str(value) if value else None


def _snapshot_kind(snapshot: Any) -> str | None:
    value = _get_value(snapshot, "snapshot_kind")
    return str(value) if value else None


def _metadata(job: Any) -> dict[str, Any]:
    value = _get_value(job, "metadata") or {}
    return value if isinstance(value, dict) else {}


def _pending_question(job: Any) -> dict[str, Any] | None:
    metadata = _metadata(job)
    pending = metadata.get("pending_interrupt")
    if isinstance(pending, dict) and pending:
        return pending
    assistant_message = metadata.get("assistant_message")
    if isinstance(assistant_message, str) and assistant_message.strip():
        return {"message": assistant_message.strip()}
    return None


def _waiting_job_is_explicit_continuation(job: Any) -> bool:
    mode = _metadata(job).get("continuation_mode")
    return isinstance(mode, str) and mode in _EXPLICIT_PENDING_MODES


def compute_thread_resume_state(
    *,
    thread: Any,
    latest_snapshot: Any,
    waiting_job: Any,
) -> ChatThreadResumeStateResponse:
    """Return the single server-owned action for opening a generated thread."""

    thread_id = _public_thread_id(thread)
    active_job_id = _get_value(thread, "active_public_job_id") or _get_value(thread, "active_job_id")
    active_job_id = str(active_job_id) if active_job_id else None
    final_job_id = _get_value(thread, "final_public_job_id")
    final_job_id = str(final_job_id) if final_job_id and str(final_job_id).startswith("job_") else None
    final_output_id = _get_value(thread, "final_public_output_id") or _get_value(thread, "final_output_id")
    final_output_id = str(final_output_id) if final_output_id and str(final_output_id).startswith("output_") else None
    waiting_job_id = _get_value(waiting_job, "public_job_id") or _get_value(waiting_job, "job_id")
    waiting_job_id = str(waiting_job_id) if waiting_job_id else None
    snapshot_id = _snapshot_id(latest_snapshot)
    snapshot_kind = _snapshot_kind(latest_snapshot)
    status = str(_get_value(thread, "status") or "draft")

    if active_job_id:
        return ChatThreadResumeStateResponse(
            action="locked_running",
            thread_id=thread_id,
            resume_job_id=active_job_id,
            final_output_id=final_output_id,
            latest_snapshot_id=snapshot_id,
            snapshot_kind=snapshot_kind,
            reason="thread_has_active_job",
        )

    if final_output_id and not (waiting_job_id and _waiting_job_is_explicit_continuation(waiting_job)):
        return ChatThreadResumeStateResponse(
            action="view_result",
            thread_id=thread_id,
            resume_job_id=final_job_id,
            final_output_id=final_output_id,
            latest_snapshot_id=snapshot_id,
            snapshot_kind=snapshot_kind,
            reason="thread_has_final_output",
        )

    if waiting_job_id:
        return ChatThreadResumeStateResponse(
            action="answer_pending_job",
            thread_id=thread_id,
            resume_job_id=waiting_job_id,
            final_output_id=final_output_id,
            latest_snapshot_id=snapshot_id,
            snapshot_kind=snapshot_kind,
            reason="thread_has_waiting_job",
            current_question=_pending_question(waiting_job),
        )

    if status == "failed" or snapshot_kind == "job_failed":
        reason = "latest_snapshot_failed" if snapshot_kind == "job_failed" else "thread_status_failed"
        return ChatThreadResumeStateResponse(
            action="retry_failed_job",
            thread_id=thread_id,
            resume_job_id=None,
            final_output_id=final_output_id,
            latest_snapshot_id=snapshot_id,
            snapshot_kind=snapshot_kind,
            reason=reason,
        )

    return ChatThreadResumeStateResponse(
        action="continue_draft",
        thread_id=thread_id,
        resume_job_id=None,
        final_output_id=final_output_id,
        latest_snapshot_id=snapshot_id,
        snapshot_kind=snapshot_kind,
        reason="thread_is_draft",
    )
```

- [ ] **Step 5: Run policy tests**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_chat_thread_resume_policy.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add orchestrator/app/api/schemas/chat_threads.py orchestrator/app/chat_threads/resume_policy.py orchestrator/tests/test_chat_thread_resume_policy.py
git commit -m "feat: add chat thread resume policy"
```

Expected: commit succeeds. If the worktree contains unrelated user changes, stage only the three files listed above.

---

### Task 2: Expose Resume State From Backend

**Files:**

- Modify: `orchestrator/app/db/repositories/chat_threads.py`
- Modify: `orchestrator/app/db/repositories/generation_jobs.py`
- Modify: `orchestrator/app/chat_threads/service.py`
- Modify: `orchestrator/app/api/routers/chat_threads.py`
- Create: `orchestrator/tests/test_chat_thread_resume_api.py`

- [ ] **Step 1: Write failing service/API tests**

Create `orchestrator/tests/test_chat_thread_resume_api.py`:

```python
from types import SimpleNamespace

from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app
from orchestrator.app.chat_threads import service as chat_service


def test_thread_response_contains_resume_state_for_final_output(monkeypatch):
    monkeypatch.setattr(chat_service.db_settings, "get_db_backend", lambda: "postgres")
    monkeypatch.setattr(
        chat_service,
        "_ensure_workspace_for_user",
        lambda user_id, connection=None, account_type=None: {"id": "workspace_1"},
    )
    monkeypatch.setattr(
        chat_service.chat_thread_repo,
        "get_chat_thread_by_public_id",
        lambda *args, **kwargs: {
            "public_thread_id": "thread_done",
            "title": "프리미엄 뷰티살롱",
            "status": "draft",
            "brand_kit_id": None,
            "project_id": None,
            "final_brief": {},
            "active_public_job_id": None,
            "final_public_job_id": "job_done",
            "final_public_output_id": "output_done",
            "final_output_id": "internal-output-uuid",
            "last_message_at": "2026-06-17T03:37:45+00:00",
            "archived_at": None,
            "created_at": "2026-06-17T03:30:00+00:00",
            "updated_at": "2026-06-17T03:37:45+00:00",
        },
    )
    monkeypatch.setattr(
        chat_service.state_service,
        "get_latest_thread_state_snapshot",
        lambda *args, **kwargs: SimpleNamespace(
            snapshot_id="snapshot_waiting",
            snapshot_kind="waiting_user_input",
            state_payload={},
        ),
    )
    monkeypatch.setattr(
        chat_service.generation_job_repo,
        "get_latest_waiting_generation_job_for_thread",
        lambda *args, **kwargs: {
            "public_job_id": "job_waiting",
            "metadata": {"assistant_message": "어떤 업종의 광고인가요?"},
        },
    )

    thread = chat_service.get_chat_thread("thread_done", user_id="user_1")

    assert thread is not None
    assert thread.final_output_id == "output_done"
    assert thread.resume_state is not None
    assert thread.resume_state.action == "view_result"
    assert thread.resume_state.resume_job_id == "job_done"
    assert thread.resume_state.final_output_id == "output_done"


def test_resume_state_route_returns_pending_job(monkeypatch):
    app = create_app()
    client = TestClient(app)

    monkeypatch.setattr(
        chat_service,
        "get_chat_thread_resume_state",
        lambda thread_id, user_id=None, account_type=None: SimpleNamespace(
            action="answer_pending_job",
            thread_id=thread_id,
            resume_job_id="job_waiting",
            final_output_id=None,
            latest_snapshot_id="snapshot_waiting",
            snapshot_kind="waiting_user_input",
            reason="thread_has_waiting_job",
            current_question={"field": "business_type"},
        ),
    )

    response = client.get("/api/v1/chat-threads/thread_pending/resume-state")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["resume_state"]["action"] == "answer_pending_job"
    assert payload["resume_state"]["resume_job_id"] == "job_waiting"
    assert payload["resume_state"]["current_question"] == {"field": "business_type"}
```

- [ ] **Step 2: Run tests and confirm missing API/service support**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_chat_thread_resume_api.py -q
```

Expected: fail because `generation_job_repo` is not imported in `chat_threads/service.py`, the repo lookup does not exist, and the route is not registered.

- [ ] **Step 3: Join public final output id in thread repository**

In `orchestrator/app/db/repositories/chat_threads.py`, replace `_SELECT_THREAD_WITH_ACTIVE_JOB` with:

```python
_SELECT_THREAD_WITH_ACTIVE_JOB = """
    select
        ct.*,
        aj.public_job_id as active_public_job_id,
        fo.public_output_id as final_public_output_id,
        fj.public_job_id as final_public_job_id
    from chat_threads ct
    left join generation_jobs aj on aj.id = ct.active_job_id
    left join generation_outputs fo on fo.id = ct.final_output_id
    left join generation_jobs fj on fj.id = fo.job_id
"""
```

- [ ] **Step 4: Add latest waiting-job repository lookup**

In `orchestrator/app/db/repositories/generation_jobs.py`, after `get_generation_job_by_public_id`, add:

```python
def get_latest_waiting_generation_job_for_thread(
    *,
    public_thread_id: str,
    workspace_id: str,
    connection: object | None = None,
    for_update: bool = False,
) -> dict | None:
    lock_clause = " for update of gj" if for_update else ""
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select gj.*, ct.public_thread_id as public_thread_id
                from generation_jobs gj
                join chat_threads ct on ct.id = gj.thread_id
                where ct.public_thread_id = %s
                  and gj.workspace_id = %s::uuid
                  and gj.status = 'waiting_user_input'
                order by gj.updated_at desc, gj.created_at desc
                limit 1
                {lock_clause}
                """,
                (public_thread_id, workspace_id),
            )
            return cur.fetchone()
```

- [ ] **Step 5: Wire resume state in chat service**

In `orchestrator/app/chat_threads/service.py`, update imports:

```python
from orchestrator.app.api.schemas.chat_threads import (
    ChatMessageCreateRequest,
    ChatMessageResponse,
    ChatThreadCreateRequest,
    ChatThreadResponse,
    ChatThreadResumeStateResponse,
    ChatThreadUpdateRequest,
)
from orchestrator.app.chat_threads import state_service
from orchestrator.app.chat_threads.resume_policy import compute_thread_resume_state
from orchestrator.app.db.repositories import generation_jobs as generation_job_repo
```

Replace `_thread_row_to_response` with:

```python
def _thread_row_to_response(
    row: dict,
    *,
    latest_snapshot: object | None = None,
    waiting_job: dict | None = None,
) -> ChatThreadResponse:
    """DB row -> ChatThreadResponse. Public ids only."""
    active_job_id = row.get("active_public_job_id") or None
    if active_job_id and not str(active_job_id).startswith("job_"):
        active_job_id = None

    final_output_id = row.get("final_public_output_id") or None
    if final_output_id and not str(final_output_id).startswith("output_"):
        final_output_id = None

    resume_state = compute_thread_resume_state(
        thread=row,
        latest_snapshot=latest_snapshot,
        waiting_job=waiting_job,
    )

    return ChatThreadResponse(
        thread_id=str(row["public_thread_id"]),
        title=row.get("title"),
        status=row.get("status") or "draft",
        brand_kit_id=str(row["brand_kit_id"]) if row.get("brand_kit_id") else None,
        project_id=str(row["project_id"]) if row.get("project_id") else None,
        final_brief=sanitize_chat_payload(row.get("final_brief") or {}),
        active_job_id=str(active_job_id) if active_job_id else None,
        final_output_id=str(final_output_id) if final_output_id else None,
        has_final_output=final_output_id is not None,
        resume_state=resume_state,
        last_message_at=_iso(row.get("last_message_at")),
        archived_at=_iso(row["archived_at"]) if row.get("archived_at") else None,
        created_at=_iso(row.get("created_at")),
        updated_at=_iso(row.get("updated_at")),
    )
```

Add this helper below `_thread_row_to_response`:

```python
def _thread_resume_inputs(
    *,
    public_thread_id: str,
    workspace_id: str,
    user_id: str | None = None,
    connection: object | None = None,
) -> tuple[object | None, dict | None]:
    latest_snapshot = state_service.get_latest_thread_state_snapshot(
        public_thread_id=public_thread_id,
        workspace_id=workspace_id,
        user_id=user_id,
        connection=connection,
    )
    waiting_job = generation_job_repo.get_latest_waiting_generation_job_for_thread(
        public_thread_id=public_thread_id,
        workspace_id=workspace_id,
        connection=connection,
    )
    return latest_snapshot, waiting_job
```

Update `_get_chat_thread_db` so it fetches resume inputs before returning:

```python
def _get_chat_thread_db(thread_id: str, user_id: str | None = None, account_type: str | None = None) -> ChatThreadResponse | None:
    with db_transaction() as conn:
        workspace = _ensure_workspace_for_user(user_id, connection=conn, account_type=account_type)
        row = chat_thread_repo.get_chat_thread_by_public_id(thread_id, workspace_id=str(workspace["id"]), connection=conn)
        if not row:
            return None
        latest_snapshot, waiting_job = _thread_resume_inputs(
            public_thread_id=thread_id,
            workspace_id=str(workspace["id"]),
            user_id=user_id,
            connection=conn,
        )
        return _thread_row_to_response(row, latest_snapshot=latest_snapshot, waiting_job=waiting_job)
```

Update `_list_chat_threads_db` by replacing its row mapping with:

```python
threads = []
for row in rows:
    public_thread_id = str(row["public_thread_id"])
    latest_snapshot, waiting_job = _thread_resume_inputs(
        public_thread_id=public_thread_id,
        workspace_id=str(workspace["id"]),
        user_id=user_id,
        connection=conn,
    )
    threads.append(_thread_row_to_response(row, latest_snapshot=latest_snapshot, waiting_job=waiting_job))
return threads, total
```

Add public service function near `get_chat_thread_with_workspace`:

```python
def get_chat_thread_resume_state(
    thread_id: str,
    user_id: str | None = None,
    account_type: str | None = None,
) -> ChatThreadResumeStateResponse | None:
    if not _use_postgres():
        thread = _get_chat_thread_memory(thread_id, user_id=user_id)
        if not thread:
            return None
        return thread.resume_state

    with db_transaction() as conn:
        workspace = _ensure_workspace_for_user(user_id, connection=conn, account_type=account_type)
        workspace_id = str(workspace["id"])
        row = chat_thread_repo.get_chat_thread_by_public_id(
            thread_id,
            workspace_id=workspace_id,
            connection=conn,
        )
        if not row:
            return None
        latest_snapshot, waiting_job = _thread_resume_inputs(
            public_thread_id=thread_id,
            workspace_id=workspace_id,
            user_id=user_id,
            connection=conn,
        )
        return compute_thread_resume_state(
            thread=row,
            latest_snapshot=latest_snapshot,
            waiting_job=waiting_job,
        )
```

For memory responses, update `_create_chat_thread_memory`, `_get_chat_thread_memory`, and list mapping only if tests fail because `ChatThreadResponse.resume_state` is required. Since `resume_state` is optional, memory can continue returning `None`.

- [ ] **Step 6: Add resume-state route**

In `orchestrator/app/api/routers/chat_threads.py`, update schema imports:

```python
    ChatThreadResumeStateGetResponse,
```

Add this route before `/chat-threads/{thread_id}/state`:

```python
@router.get(
    "/chat-threads/{thread_id}/resume-state",
    response_model=ChatThreadResumeStateGetResponse,
)
def get_chat_thread_resume_state_route(
    thread_id: str,
    user_id: str | None = Query(default=None, alias="userId"),
    account_type: str | None = Query(default=None, alias="accountType"),
) -> ChatThreadResumeStateGetResponse:
    resume_state = chat_service.get_chat_thread_resume_state(
        thread_id,
        **_user_scope_kwargs(user_id, account_type),
    )
    if not resume_state:
        _not_found(thread_id)
    return ChatThreadResumeStateGetResponse(resume_state=resume_state)
```

- [ ] **Step 7: Run backend resume API tests**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_chat_thread_resume_policy.py orchestrator/tests/test_chat_thread_resume_api.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit Task 2**

Run:

```bash
git add orchestrator/app/db/repositories/chat_threads.py orchestrator/app/db/repositories/generation_jobs.py orchestrator/app/chat_threads/service.py orchestrator/app/api/routers/chat_threads.py orchestrator/tests/test_chat_thread_resume_api.py
git commit -m "feat: expose chat thread resume state"
```

Expected: commit succeeds with only listed files staged.

---

### Task 3: Guard Job Creation With Explicit Continuation Modes

**Files:**

- Modify: `orchestrator/app/chat_threads/errors.py`
- Modify: `orchestrator/app/api/schemas/generation_jobs.py`
- Modify: `orchestrator/app/api/routers/generation_jobs.py`
- Modify: `orchestrator/app/chat_threads/state_service.py`
- Modify: `orchestrator/app/generation_jobs/service.py`
- Modify: `orchestrator/tests/test_generation_jobs.py`

- [ ] **Step 1: Add failing job-creation tests**

Append to `orchestrator/tests/test_generation_jobs.py`:

```python
def test_create_generation_job_rejects_pending_thread_without_continuation_mode(monkeypatch):
    from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest
    from orchestrator.app.chat_threads.errors import ChatThreadHasPendingJobError
    from orchestrator.app.generation_jobs import service

    monkeypatch.setattr(service.db_settings, "get_db_backend", lambda: "postgres")
    monkeypatch.setattr(service, "_resolve_db_workspace_for_generation_request", lambda request, connection=None: {"id": "workspace_1"})
    monkeypatch.setattr(
        service.chat_thread_repo,
        "get_chat_thread_by_public_id",
        lambda *args, **kwargs: {
            "id": "thread-internal",
            "public_thread_id": "thread_pending",
            "archived_at": None,
            "active_job_id": None,
            "final_output_id": None,
        },
    )
    monkeypatch.setattr(
        service.generation_job_repo,
        "get_latest_waiting_generation_job_for_thread",
        lambda *args, **kwargs: {"public_job_id": "job_waiting", "metadata": {}},
    )

    request = GenerationJobCreateRequest(
        threadId="thread_pending",
        userInput="다시 이어서 만들어줘",
        runMode="queued_only",
    )

    with pytest.raises(ChatThreadHasPendingJobError):
        service.create_generation_job(request)


def test_restore_thread_state_for_generation_strips_waiting_transients():
    from types import SimpleNamespace

    from orchestrator.app.chat_threads.state_service import restore_thread_state_for_generation

    snapshot = SimpleNamespace(
        state_payload={
            "business_type": "beauty_salon",
            "missing_fields": ["item_or_service"],
            "context": {"pending_question": "어떤 업종의 광고인가요?"},
            "copy_candidates": [{"id": "old"}],
            "result_payload": {"image_url": "old.png"},
            "selected_reference_template_id": "ref_1",
            "brand_kit_id": "brand_1",
        }
    )

    restored = restore_thread_state_for_generation(
        snapshot,
        current_request_fields={"ad_format": "poster"},
        user_input="강남 프리미엄 뷰티살롱 포스터",
        continuation_mode="new_turn",
    )

    assert restored["business_type"] == "beauty_salon"
    assert restored["selected_reference_template_id"] == "ref_1"
    assert restored["brand_kit_id"] == "brand_1"
    assert restored["ad_format"] == "poster"
    assert restored["user_input"] == "강남 프리미엄 뷰티살롱 포스터"
    assert restored["continuation_mode"] == "new_turn"
    assert "missing_fields" not in restored
    assert "context" not in restored
    assert "copy_candidates" not in restored
    assert "result_payload" not in restored
```

- [ ] **Step 2: Run tests and confirm failures**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_generation_jobs.py::test_create_generation_job_rejects_pending_thread_without_continuation_mode orchestrator/tests/test_generation_jobs.py::test_restore_thread_state_for_generation_strips_waiting_transients -q
```

Expected: fail because `ChatThreadHasPendingJobError` and `restore_thread_state_for_generation` do not exist.

- [ ] **Step 3: Add pending-job error**

In `orchestrator/app/chat_threads/errors.py`, after `ChatThreadHasActiveJobError`, add:

```python
class ChatThreadHasPendingJobError(ChatThreadServiceError):
    def __init__(self, message: str = "Chat thread has a generation job waiting for user input.") -> None:
        super().__init__("chat_thread_has_pending_job", message)
```

In `orchestrator/app/api/routers/generation_jobs.py`, update `_chat_thread_error`:

```python
    elif exc.error_code in {
        "chat_thread_archived",
        "chat_thread_has_active_job",
        "chat_thread_has_pending_job",
        "thread_limit_reached",
    }:
        status_code = 409
```

In `orchestrator/app/api/routers/chat_threads.py`, update `_handle_service_error` to return 409 for the new error:

```python
    if exc.error_code in {"chat_thread_has_active_job", "chat_thread_has_pending_job"}:
        raise_api_error(
            status_code=409,
            error_code=exc.error_code,
            message=exc.message,
            detail=f"thread_id={thread_id}",
        )
        return
```

- [ ] **Step 4: Add continuation mode schema**

In `orchestrator/app/api/schemas/generation_jobs.py`, after `GenerationRunMode`, add:

```python
GenerationContinuationMode = Literal[
    "new_thread",
    "new_turn",
    "retry_failed",
    "regenerate_from_output",
]
```

In `GenerationJobCreateRequest`, after `thread_id`, add:

```python
    continuation_mode: GenerationContinuationMode | None = Field(default=None, alias="continuationMode")
```

Inside `validate_asset_conflicts`, before `return self`, add:

```python
        if self.thread_id is None and self.continuation_mode not in {None, "new_thread"}:
            raise ValueError("continuation_mode requires thread_id unless it is 'new_thread'")
        if self.thread_id is not None and self.continuation_mode == "new_thread":
            raise ValueError("continuation_mode 'new_thread' cannot be used with thread_id")
```

- [ ] **Step 5: Add mode-aware state restore**

In `orchestrator/app/chat_threads/state_service.py`, after `restore_thread_state`, add:

```python
_NEW_GENERATION_TRANSIENT_KEYS = {
    "job_id",
    "missing_fields",
    "context",
    "current_brief",
    "marketing_copy",
    "copy_candidates",
    "copy_candidate_origin",
    "progress_state",
    "quality_gate_decision",
    "quality_gate_status",
    "quality_gate_retry_feedback",
    "ocr_gate_decision",
    "ocr_gate_status",
    "ocr_gate_retry_feedback",
    "image_prompt_spec",
    "copy_spec",
    "copy_required",
    "text_layout_spec",
    "text_style_spec",
    "text_overlay_pending",
    "t2i_request",
    "t2i_result",
    "candidates",
    "artifact_refs",
    "background_validation_report",
    "safe_area_report",
    "readability_report",
    "render_result",
    "final_validation_report",
    "result_payload",
    "final_image_path",
    "error_message",
    "error_info",
    "selected_copy",
    "selected_copy_id",
    "selected_channel_id",
    "selected_tone",
    "custom_direction",
    "user_custom_headline",
    "user_custom_subcopy",
}


def restore_thread_state_for_generation(
    latest_snapshot: ChatStateSnapshotResponse | None,
    current_request_fields: dict[str, Any],
    user_input: str,
    *,
    continuation_mode: str,
) -> dict[str, Any]:
    from orchestrator.app.chat_threads.state_snapshot import restore_persistent_state

    restored = restore_persistent_state(latest_snapshot.state_payload if latest_snapshot else None)
    if continuation_mode in {"new_turn", "retry_failed", "regenerate_from_output"}:
        for key in _NEW_GENERATION_TRANSIENT_KEYS:
            restored.pop(key, None)
    for key, value in current_request_fields.items():
        restored[key] = value
    restored["user_input"] = user_input
    restored["continuation_mode"] = continuation_mode
    return restored
```

Keep existing `restore_thread_state` unchanged so older tests and call sites keep working until migrated.

- [ ] **Step 6: Enforce pending/final-output guards in generation job creation**

In `orchestrator/app/generation_jobs/service.py`, update the chat-thread error imports:

```python
from orchestrator.app.chat_threads.errors import (
    ChatThreadArchivedError,
    ChatThreadHasActiveJobError,
    ChatThreadHasPendingJobError,
    ChatThreadNotFoundError,
)
```

In `_create_generation_job_db`, inside the `if request.thread_id:` block after the active-job check, add:

```python
            pending_job = generation_job_repo.get_latest_waiting_generation_job_for_thread(
                public_thread_id=request.thread_id,
                workspace_id=workspace_id,
                connection=conn,
                for_update=True,
            )
            if pending_job and not request.continuation_mode:
                raise ChatThreadHasPendingJobError(
                    "This thread is waiting for an answer. Resume the waiting generation job instead of creating a new one."
                )
            if thread_row.get("final_output_id") and not request.continuation_mode:
                raise InvalidChatThreadRequestError(
                    "Completed threads require continuationMode before creating another generation job."
                )
```

Add `continuation_mode` to metadata:

```python
            "continuation_mode": request.continuation_mode or ("new_thread" if not request.thread_id else "new_turn"),
```

Replace the `restored_payload = state_service.restore_thread_state(...)` call with:

```python
        continuation_mode = request.continuation_mode or ("new_thread" if not request.thread_id else "new_turn")
        restored_payload = state_service.restore_thread_state_for_generation(
            latest_snapshot,
            current_request_fields=explicit_fields,
            user_input=request.user_input,
            continuation_mode=continuation_mode,
        )
```

This keeps normal draft continuation compatible while blocking accidental create calls on pending or completed threads.

- [ ] **Step 7: Run focused backend tests**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_generation_jobs.py::test_create_generation_job_rejects_pending_thread_without_continuation_mode orchestrator/tests/test_generation_jobs.py::test_restore_thread_state_for_generation_strips_waiting_transients -q
```

Expected: all tests pass.

- [ ] **Step 8: Run resume-related backend suite**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_chat_thread_resume_policy.py orchestrator/tests/test_chat_thread_resume_api.py orchestrator/tests/test_generation_jobs.py::test_create_generation_job_rejects_pending_thread_without_continuation_mode orchestrator/tests/test_generation_jobs.py::test_restore_thread_state_for_generation_strips_waiting_transients -q
```

Expected: all tests pass.

- [ ] **Step 9: Commit Task 3**

Run:

```bash
git add orchestrator/app/chat_threads/errors.py orchestrator/app/api/schemas/generation_jobs.py orchestrator/app/api/routers/generation_jobs.py orchestrator/app/api/routers/chat_threads.py orchestrator/app/chat_threads/state_service.py orchestrator/app/generation_jobs/service.py orchestrator/tests/test_generation_jobs.py
git commit -m "fix: guard chat thread generation continuation"
```

Expected: commit succeeds with only listed files staged.

---

### Task 4: Make Frontend Consume Resume State

**Files:**

- Modify: `apps/web/lib/api-client.ts`
- Modify: `apps/web/components/generate/StudioEntryStep.tsx`
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx`
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`

- [ ] **Step 1: Add failing frontend tests**

In the `vi.mock("@/lib/api-client", () => ({ ... }))` block at the top of `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`, add this default mock next to `getChatThread`:

```tsx
  getChatThreadResumeState: vi.fn(async () => ({
    success: true,
    resume_state: {
      action: "continue_draft",
      thread_id: "thread_1",
      resume_job_id: null,
      final_output_id: null,
      latest_snapshot_id: null,
      snapshot_kind: null,
      reason: "thread_is_draft",
      current_question: null
    }
  })),
```

Then append these tests:

```tsx
  it("shows view for a draft thread that already has a final output", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.listChatThreads).mockResolvedValueOnce({
      success: true,
      threads: [
        {
          thread_id: "thread_done_draft",
          title: "프리미엄 뷰티살롱",
          status: "draft",
          brand_kit_id: null,
          project_id: null,
          final_brief: {},
          active_job_id: null,
          final_output_id: "output_done",
          has_final_output: true,
          resume_state: {
            action: "view_result",
            thread_id: "thread_done_draft",
            resume_job_id: "job_done",
            final_output_id: "output_done",
            latest_snapshot_id: "snapshot_waiting",
            snapshot_kind: "waiting_user_input",
            reason: "thread_has_final_output",
            current_question: null
          },
          last_message_at: "2026-06-17T03:37:45+00:00",
          archived_at: null,
          created_at: "2026-06-17T03:30:00+00:00",
          updated_at: "2026-06-17T03:37:45+00:00"
        }
      ],
      total: 1
    });
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="studio" />);

    await waitFor(() => expect(screen.getByText("프리미엄 뷰티살롱")).toBeTruthy());
    expect(screen.getByRole("button", { name: "보기" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "이어하기" })).toBeNull();
  });

  it("opens pending thread without creating a duplicate generation job", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.getChatThread).mockResolvedValueOnce({
      success: true,
      thread: {
        thread_id: "thread_pending",
        title: "뷰티살롱",
        status: "draft",
        brand_kit_id: null,
        project_id: null,
        final_brief: {},
        active_job_id: null,
        final_output_id: null,
        has_final_output: false,
        resume_state: {
          action: "answer_pending_job",
          thread_id: "thread_pending",
          resume_job_id: "job_waiting",
          final_output_id: null,
          latest_snapshot_id: "snapshot_waiting",
          snapshot_kind: "waiting_user_input",
          reason: "thread_has_waiting_job",
          current_question: { message: "어떤 업종의 광고인가요?" }
        },
        last_message_at: "2026-06-17T03:30:00+00:00",
        archived_at: null,
        created_at: "2026-06-17T03:30:00+00:00",
        updated_at: "2026-06-17T03:30:00+00:00"
      }
    });
    vi.mocked(api.getChatThreadResumeState).mockResolvedValueOnce({
      success: true,
      resume_state: {
        action: "answer_pending_job",
        thread_id: "thread_pending",
        resume_job_id: "job_waiting",
        final_output_id: null,
        latest_snapshot_id: "snapshot_waiting",
        snapshot_kind: "waiting_user_input",
        reason: "thread_has_waiting_job",
        current_question: { message: "어떤 업종의 광고인가요?" }
      }
    });
    vi.mocked(api.getChatThreadState).mockResolvedValueOnce({
      success: true,
      snapshot: {
        snapshot_id: "snapshot_waiting",
        thread_id: "thread_pending",
        job_id: "job_waiting",
        source_message_id: null,
        parent_snapshot_id: null,
        snapshot_version: 2,
        schema_version: 1,
        snapshot_kind: "waiting_user_input",
        state_payload: {
          status: "waiting_user_input",
          missing_fields: ["business_type"],
          context: { question: "어떤 업종의 광고인가요?" }
        },
        changed_fields: [],
        selected_reference_template_id: null,
        reference_template_snapshot: {},
        brand_kit_snapshot: {},
        metadata: {},
        created_at: "2026-06-17T03:30:00+00:00"
      }
    });
    vi.mocked(api.getChatThreadMessages).mockResolvedValueOnce({ success: true, messages: [], total: 0 });
    vi.mocked(api.getGenerationJob).mockResolvedValueOnce({
      success: true,
      job: {
        job_id: "job_waiting",
        thread_id: "thread_pending",
        status: "waiting_user_input",
        progress: { progress_percent: 50, current_stage: "waiting_user_input" },
        result_payload: {},
        metadata: {
          pending_interrupt: {
            type: "option_question",
            option_question: {
              field: "business_type",
              question: "어떤 업종의 광고인가요?",
              options: []
            }
          }
        },
        created_at: "2026-06-17T03:30:00+00:00",
        updated_at: "2026-06-17T03:30:00+00:00"
      }
    });
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialThreadId="thread_pending" />);

    await waitFor(() => expect(api.getChatThreadResumeState).toHaveBeenCalledWith("thread_pending"));
    await waitFor(() => expect(api.getGenerationJob).toHaveBeenCalledWith("job_waiting"));
    expect(api.createGenerationJob).not.toHaveBeenCalled();
  });
```

- [ ] **Step 2: Run tests and confirm missing frontend types/function**

Run:

```bash
cd apps/web && npx vitest run app/generate/chat/ChatGenerateClient.test.tsx
```

Expected: fail because `getChatThreadResumeState`, `final_output_id`, and `resume_state` are not typed or used.

- [ ] **Step 3: Add API client resume types**

In `apps/web/lib/api-client.ts`, replace `ChatThreadResponse` and add resume types:

```ts
export type ThreadResumeAction =
  | "view_result"
  | "answer_pending_job"
  | "retry_failed_job"
  | "continue_draft"
  | "locked_running";

export interface ChatThreadResumeState {
  action: ThreadResumeAction;
  thread_id: string;
  resume_job_id?: string | null;
  final_output_id?: string | null;
  latest_snapshot_id?: string | null;
  snapshot_kind?: string | null;
  reason: string;
  current_question?: Record<string, unknown> | null;
}

export interface ChatThreadResponse {
  thread_id: string;
  title?: string | null;
  status: string;
  brand_kit_id?: string | null;
  project_id?: string | null;
  final_brief: Record<string, unknown>;
  active_job_id?: string | null;
  final_output_id?: string | null;
  has_final_output: boolean;
  resume_state?: ChatThreadResumeState | null;
  last_message_at: string;
  archived_at?: string | null;
  created_at: string;
  updated_at: string;
}
```

Add response interface after `ChatThreadGetResponse`:

```ts
export interface ChatThreadResumeStateGetResponse {
  success: true;
  resume_state: ChatThreadResumeState;
  meta?: Record<string, unknown>;
}
```

Add API function after `getChatThread`:

```ts
export async function getChatThreadResumeState(threadId: string): Promise<ChatThreadResumeStateGetResponse> {
  const authHeaders = await getSupabaseAuthorizationHeader();
  return getJson<ChatThreadResumeStateGetResponse>(
    `/api/chat-threads/${encodeURIComponent(threadId)}/resume-state`,
    undefined,
    authHeaders
  );
}
```

Extend `GenerationJobCreateInput` with:

```ts
  continuationMode?: "new_thread" | "new_turn" | "retry_failed" | "regenerate_from_output";
```

- [ ] **Step 4: Use resume action for studio button labels**

In `apps/web/components/generate/StudioEntryStep.tsx`, add helper near the component:

```tsx
function getThreadPrimaryActionLabel(thread: ChatThreadResponse): string {
  if (thread.archived_at || thread.status === "archived") {
    return "보기";
  }
  const action = thread.resume_state?.action;
  if (action === "view_result") {
    return "보기";
  }
  if (action === "locked_running") {
    return "진행 보기";
  }
  if (action === "retry_failed_job") {
    return "다시 시도";
  }
  if (thread.has_final_output || thread.final_output_id) {
    return "보기";
  }
  return "이어하기";
}
```

Replace the inline label:

```tsx
{isArchived || thread.status === "completed" ? "보기" : "이어하기"}
```

with:

```tsx
{getThreadPrimaryActionLabel(thread)}
```

- [ ] **Step 5: Fetch resume state when opening a thread**

In `apps/web/app/generate/chat/ChatGenerateClient.tsx`, add `getChatThreadResumeState` to the existing import from `@/lib/api-client`. `getGenerationJob` is already imported in this file and will be reused for `view_result`.

Replace the `if (threadIdParam) { ... }` restore block's `Promise.all([...]).then(([threadResponse, stateResponse, messagesResponse]) => { ... })` body with this shape, preserving the surrounding `if (threadIdParam)` guard and `catch`:

```tsx
      Promise.all([
        getChatThread(threadIdParam).catch(() => null),
        getChatThreadResumeState(threadIdParam).catch(() => null),
        getChatThreadState(threadIdParam),
        getChatThreadMessages(threadIdParam, { limit: 120 }).catch(() => ({ success: true as const, messages: [], total: 0 }))
      ]).then(async ([threadResponse, resumeResponse, stateResponse, messagesResponse]) => {
        setCurrentThreadIsArchived(Boolean(threadResponse?.thread.archived_at));
        const resumeState = resumeResponse?.resume_state ?? threadResponse?.thread.resume_state ?? null;
        const restoreState = mapChatThreadSnapshotToRestoreState(stateResponse.snapshot);
        const transcript = mapChatMessagesToTranscript(messagesResponse.messages);

        if (resumeState?.action === "view_result") {
          const finalJobResponse = resumeState.resume_job_id
            ? await getGenerationJob(resumeState.resume_job_id).catch(() => null)
            : null;
          if (finalJobResponse?.job) {
            if (restoreState) {
              const turnResponse = generationJobToChatTurnResponse(finalJobResponse.job, restoreState.copyGenerationMode);
              dispatch({
                type: "restoreThreadSnapshot",
                ...restoreState,
                context: mergeContextFromTurnResponse(restoreState.context, turnResponse),
                generationJob: finalJobResponse.job,
                conversationMessages: transcript.length > 0 ? transcript : restoreState.conversationMessages
              });
            } else {
              dispatch({ type: "showResultShell" });
              dispatch({ type: "generationJobUpdated", generationJob: finalJobResponse.job });
            }
            setShowHistory(false);
            setGenerationStage("complete");
            lastPrimedStageRef.current = "complete";
            return;
          }
          showToast("완료된 결과를 불러오지 못했어요. 잠시 후 다시 시도해주세요.");
          return;
        }

        if (!restoreState) {
          const pendingTurn = readChatTurnSnapshot();
          if (chatTurnSnapshotMatchesThread(pendingTurn, threadIdParam)) {
            restoreChatTurnSnapshot(pendingTurn);
            return;
          }
          showToast("대화 기록을 불러왔지만 이어갈 정보가 비어 있어요.");
          return;
        }

        if (resumeState?.action === "answer_pending_job" && resumeState.resume_job_id) {
          const waitingJobResponse = await getGenerationJob(resumeState.resume_job_id).catch(() => null);
          if (waitingJobResponse?.job) {
            const turnResponse = generationJobToChatTurnResponse(waitingJobResponse.job, restoreState.copyGenerationMode);
            dispatch({
              type: "restoreThreadSnapshot",
              ...restoreState,
              context: mergeContextFromTurnResponse(restoreState.context, turnResponse),
              generationJob: waitingJobResponse.job,
              conversationMessages: transcript.length > 0 ? transcript : restoreState.conversationMessages
            });
            setShowHistory(false);
            const restoreIntake: InitialChatIntakeContext = {
              prompt: restoreState.prompt,
              copyGenerationMode: restoreState.copyGenerationMode,
              imageGenerationEngine: restoreState.selectedImageGenerationEngine,
              sourceAssetId: restoreState.sourceAssetId,
              sourceImagePath: restoreState.sourceImagePath,
              referenceImagePath: restoreState.referenceImagePath,
              selectedReferenceTemplateId: restoreState.selectedReferenceTemplateId,
              selectedReferenceTemplateTitle: restoreState.selectedReferenceTemplateTitle,
              userCustomHeadline: restoreState.userCustomHeadline,
              userCustomSubcopy: restoreState.userCustomSubcopy
            };
            if (stopForGenerationJobInterrupt(waitingJobResponse.job, restoreIntake)) {
              return;
            }
            setGenerationStage("jobQuestion");
            lastPrimedStageRef.current = "generating";
            return;
          }
        }

        dispatch({
          type: "restoreThreadSnapshot",
          ...restoreState,
          conversationMessages: transcript.length > 0 ? transcript : restoreState.conversationMessages
        });
        setShowHistory(false);
        const restoreIntake: InitialChatIntakeContext = {
          prompt: restoreState.prompt,
          copyGenerationMode: restoreState.copyGenerationMode,
          imageGenerationEngine: restoreState.selectedImageGenerationEngine,
          sourceAssetId: restoreState.sourceAssetId,
          sourceImagePath: restoreState.sourceImagePath,
          referenceImagePath: restoreState.referenceImagePath,
          selectedReferenceTemplateId: restoreState.selectedReferenceTemplateId,
          selectedReferenceTemplateTitle: restoreState.selectedReferenceTemplateTitle,
          userCustomHeadline: restoreState.userCustomHeadline,
          userCustomSubcopy: restoreState.userCustomSubcopy
        };
        if (
          restoreState.generationJob.status === "waiting_user_input" &&
          stopForGenerationJobInterrupt(restoreState.generationJob, restoreIntake)
        ) {
          return;
        }
        if (isTerminalGenerationJobStatus(restoreState.generationJob.status)) {
          setGenerationStage("complete");
          lastPrimedStageRef.current = "complete";
          return;
        }
        setGenerationStage(restoreState.currentQuestion ? "jobQuestion" : "brief");
        lastPrimedStageRef.current = restoreState.currentQuestion ? "generating" : "brief";
      }).catch(() => {
        showToast("대화 기록을 불러오는데 실패했습니다.");
      });
```

- [ ] **Step 6: Pass explicit continuationMode on create**

In every `createGenerationJob({ ... threadId: toGenerationJobThreadId(state.threadId), ... })` call in `ChatGenerateClient.tsx`, add:

```tsx
continuationMode: state.threadId ? "new_turn" : "new_thread",
```

For a retry button on a failed existing thread, use:

```tsx
continuationMode: "retry_failed",
```

For regeneration from an existing output id, use:

```tsx
continuationMode: "regenerate_from_output",
```

- [ ] **Step 7: Run focused frontend tests**

Run:

```bash
cd apps/web && npx vitest run app/generate/chat/ChatGenerateClient.test.tsx
```

Expected: all tests in the file pass. If unrelated existing tests fail because mocks lack `final_output_id` or `resume_state`, update those test fixtures with:

```ts
final_output_id: null,
resume_state: null,
```

- [ ] **Step 8: Type-check frontend**

Run:

```bash
cd apps/web && npx tsc --noEmit
```

Expected: TypeScript exits with code 0.

- [ ] **Step 9: Commit Task 4**

Run:

```bash
git add apps/web/lib/api-client.ts apps/web/components/generate/StudioEntryStep.tsx apps/web/app/generate/chat/ChatGenerateClient.tsx apps/web/app/generate/chat/ChatGenerateClient.test.tsx
git commit -m "fix: open generated threads from resume state"
```

Expected: commit succeeds with only listed frontend files staged.

---

### Task 5: Prevent Native Copy Length Validation Crashes

**Files:**

- Modify: `orchestrator/app/llm/native_copy_candidate_service.py`
- Modify: `orchestrator/tests/test_native_copy_candidates.py`

- [ ] **Step 1: Add failing long-copy test**

Append to `orchestrator/tests/test_native_copy_candidates.py`:

```python
def test_candidate_bundle_fits_overlong_candidate_before_schema_validation():
    evidence, product = _fixture()
    long_support = "강남에서 새롭게 만나는 프리미엄 뷰티 살롱의 섬세한 케어와 우아한 무드를 경험하세요"
    payload = {
        "candidates": [
            {
                "candidate_id": "too_long",
                "strategy": "brand_editorial",
                "headline": "프리미엄 뷰티살롱",
                "supporting_copy": long_support,
                "headline_basis_ids": product.product_name_evidence_ids,
            }
        ]
    }

    bundle = coerce_native_copy_strategy_bundle(payload, input_evidence=evidence, product_understanding=product)

    candidate = bundle.candidates[0]
    assert candidate.total_character_count <= 80
    assert len(candidate.headline) + len(candidate.supporting_copy or candidate.closing_copy or "") <= 80
```

- [ ] **Step 2: Run test and confirm validation failure**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_native_copy_candidates.py::test_candidate_bundle_fits_overlong_candidate_before_schema_validation -q
```

Expected: fail with a Pydantic validation error for `total_character_count` greater than 80.

- [ ] **Step 3: Add deterministic text fitting helper**

In `orchestrator/app/llm/native_copy_candidate_service.py`, after `STRATEGIES`, add:

```python
NATIVE_COPY_MAX_TOTAL_CHARACTERS = 80


def _trim_text_to_budget(text: str, budget: int) -> str | None:
    if budget <= 0:
        return None
    stripped = text.strip()
    if len(stripped) <= budget:
        return stripped
    if budget == 1:
        return stripped[:1]
    return stripped[: budget - 1].rstrip() + "…"


def _fit_candidate_text_blocks(
    *,
    headline: str,
    support: str | None,
    closing: str | None,
) -> tuple[str, str | None, str | None]:
    fitted_headline = _trim_text_to_budget(headline, NATIVE_COPY_MAX_TOTAL_CHARACTERS) or ""
    remaining = NATIVE_COPY_MAX_TOTAL_CHARACTERS - len(fitted_headline)
    if support:
        return fitted_headline, _trim_text_to_budget(support, remaining), None
    if closing:
        return fitted_headline, None, _trim_text_to_budget(closing, remaining)
    return fitted_headline, None, None
```

- [ ] **Step 4: Use fitting before constructing the schema**

In `_coerce_candidate`, after computing `strategy`, replace:

```python
    texts = [headline, support or closing or ""]
```

with:

```python
    headline, support, closing = _fit_candidate_text_blocks(
        headline=headline or product_name,
        support=support,
        closing=closing,
    )
    texts = [headline, support or closing or ""]
```

Replace `headline=headline or product_name,` in the `NativeCopyCandidate` constructor with:

```python
        headline=headline,
```

Replace:

```python
        closing_copy=closing if not support else None,
```

with:

```python
        closing_copy=closing if closing and not support else None,
```

Keep `total_character_count=sum(len(text) for text in texts if text)`.

- [ ] **Step 5: Run native copy tests**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_native_copy_candidates.py orchestrator/tests/test_native_candidate_capacity.py orchestrator/tests/test_native_campaign_copy_typography_v41.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 5**

Run:

```bash
git add orchestrator/app/llm/native_copy_candidate_service.py orchestrator/tests/test_native_copy_candidates.py
git commit -m "fix: fit native copy candidates before validation"
```

Expected: commit succeeds with only listed files staged.

---

### Task 6: End-to-End Regression and Manual Data Check

**Files:**

- Modify only if tests reveal a wiring issue in files already listed above.

- [ ] **Step 1: Run backend regression set**

Run:

```bash
PYTHONPATH=. uv run pytest \
  orchestrator/tests/test_chat_thread_resume_policy.py \
  orchestrator/tests/test_chat_thread_resume_api.py \
  orchestrator/tests/test_generation_jobs.py::test_create_generation_job_rejects_pending_thread_without_continuation_mode \
  orchestrator/tests/test_generation_jobs.py::test_restore_thread_state_for_generation_strips_waiting_transients \
  orchestrator/tests/test_native_copy_candidates.py \
  orchestrator/tests/test_native_candidate_capacity.py \
  -q
```

Expected: all tests pass.

- [ ] **Step 2: Run frontend regression set**

Run:

```bash
cd apps/web && npx vitest run app/generate/chat/ChatGenerateClient.test.tsx
```

Expected: all tests pass.

- [ ] **Step 3: Run frontend type check**

Run:

```bash
cd apps/web && npx tsc --noEmit
```

Expected: TypeScript exits with code 0.

- [ ] **Step 4: Verify the real problematic thread through the API**

Start the orchestrator if it is not already running:

```bash
uv run uvicorn orchestrator.app.main:app --host 0.0.0.0 --port 8010
```

Then query and assert the resume state:

```bash
curl -s "http://localhost:8010/api/v1/chat-threads/thread_40f80c2d7e5448d389f270abbaa533d3/resume-state" > /tmp/easyads-thread-resume.json
python - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("/tmp/easyads-thread-resume.json").read_text())
resume = payload["resume_state"]
assert payload["success"] is True
assert resume["action"] == "view_result"
assert resume["thread_id"] == "thread_40f80c2d7e5448d389f270abbaa533d3"
assert resume["resume_job_id"] == "job_a84b8d1c8120420a82380bbe183cb561"
assert resume["final_output_id"] == "output_c4b3e22ad71b4e48b4d2b4adda2c2647"
assert resume["reason"] == "thread_has_final_output"
print("resume_state_ok")
PY
```

Expected output: `resume_state_ok`

- [ ] **Step 5: Run git diff review**

Run:

```bash
git status --short
git diff --stat
git diff -- orchestrator/app/api/schemas/chat_threads.py orchestrator/app/chat_threads/resume_policy.py orchestrator/app/generation_jobs/service.py apps/web/app/generate/chat/ChatGenerateClient.tsx
```

Expected:

- Only files from this plan are staged or modified for this work.
- No unrelated user files are reverted.
- Resume-state decisions are server-owned.
- Frontend does not infer "보기" only from `thread.status`.
- `createGenerationJob` calls on existing threads include `continuationMode`.

- [ ] **Step 6: Final commit if Task 6 required fixes**

If Task 6 required additional code changes, commit them:

```bash
git add orchestrator apps/web
git commit -m "test: cover chat thread resume lifecycle"
```

If Task 6 required no code changes, do not create an empty commit.

---

## Risk Review

- **Risk: N+1 queries in thread list.** The first implementation computes resume state per listed thread. The list limit is 20 in the current studio UI, so this is acceptable for this fix. If it becomes slow, replace the per-thread lookups with one batched latest-waiting-job query and one batched latest-snapshot query.
- **Risk: legacy contaminated threads.** The policy intentionally prefers `view_result` for final-output threads unless the waiting job explicitly declares a continuation mode. This restores the missing-poster case without deleting legacy jobs.
- **Risk: existing clients without `continuationMode`.** Draft threads with no output and no pending job still work. Completed or pending threads reject ambiguous job creation so they cannot silently create duplicates.
- **Risk: frontend restore flow regression.** `ChatGenerateClient.tsx` is large. The plan reuses existing `dispatch`, `generationJobToChatTurnResponse`, `mergeContextFromTurnResponse`, `setGenerationStage`, and `lastPrimedStageRef` patterns so the new branch stays aligned with the existing `jobId` restore path.
- **Risk: copy truncation may reduce marketing nuance.** The helper trims support copy before headline. This is preferable to a failed job, and the renderer/native preflight can still reject weak copy later if needed.

## Self-Review

- Spec coverage: The plan covers completed-result opening, pending-job resumption, duplicate creation guard, snapshot transient stripping, frontend labels/open behavior, and native copy overflow.
- Ambiguity resolved: Final-output threads with accidental legacy waiting jobs open the result. Explicit future continuations can still resume waiting jobs because metadata carries `continuation_mode`.
- Type consistency: Backend uses snake_case API fields (`resume_state`, `final_output_id`) and frontend mirrors existing API style. Create request uses camelCase `continuationMode`, mapped by Pydantic alias to `continuation_mode`.
- Test coverage: Fast pure policy tests cover precedence, backend tests cover API/service wiring and guards, frontend tests cover UI regression, native-copy tests cover the 96-character crash class.
