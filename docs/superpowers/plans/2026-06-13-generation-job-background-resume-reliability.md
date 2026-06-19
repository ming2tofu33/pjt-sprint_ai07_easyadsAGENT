# Generation Job Background Resume Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make generation job create/resume background execution observable and recoverable so a custom copy answer cannot disappear into a long `running/planning` state followed by a generic image failure.

**Architecture:** Keep the existing FastAPI `BackgroundTasks` execution model for this pass, but add explicit lifecycle events around enqueue/start/delegate/failure and classify stale jobs from those events. Backend changes live in the generation job service/router boundary; frontend changes only translate the new backend failure codes into clear user-facing notices.

**Tech Stack:** FastAPI, LangGraph, Pydantic, Postgres repositories via psycopg, pytest, Next.js/React, Vitest.

---

## Current Evidence

- Latest `origin/develop` is `dc3bbc46`.
- The exact local graph path `suggest_candidates -> Command(resume={"user_custom_headline": ...})` succeeds.
- Production DB shows jobs such as `job_1189414b4fd84c648f00f8ffd628cad3` moving `queued -> running/planning -> stale failed` with no graph progress events between.
- The current UI switches final-generation answers to `stage="generating"` immediately; if the backend task stalls, the copy input disappears and the user later sees a generic failed image notice.

## File Structure

- Modify `orchestrator/app/generation_jobs/service.py`
  - Owns generation job lifecycle state transitions.
  - Add public lifecycle event helper.
  - Add stale failure classification based on lifecycle events.
- Modify `orchestrator/app/api/routers/generation_jobs.py`
  - Owns API scheduling of create/resume background graph work.
  - Add small wrapper functions that record enqueue/start and delegate to the existing execution functions.
- Modify `orchestrator/tests/test_generation_jobs.py`
  - Unit tests for lifecycle event helper, stale classification, and exact direct-custom-copy graph path.
- Modify `orchestrator/tests/test_api_routers.py`
  - Unit tests for route-level background enqueue/start wrapper behavior.
- Modify `apps/web/lib/generation-result-utils.ts`
  - Map new backend error codes to clearer notices.
- Modify `apps/web/lib/generation-result-utils.test.ts`
  - Vitest coverage for new stale/background failure notices.

---

### Task 1: Add Generation Job Lifecycle Event Helper

**Files:**
- Modify: `orchestrator/app/generation_jobs/service.py`
- Test: `orchestrator/tests/test_generation_jobs.py`

- [ ] **Step 1: Write the failing test**

Add this test near `test_postgres_mark_failed_updates_row_thread_and_event` in `orchestrator/tests/test_generation_jobs.py`:

```python
def test_postgres_record_generation_job_lifecycle_event_records_scoped_event(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction__test_generation_job_persistence_db_backend)
    events = []
    row = _row__test_generation_job_persistence_db_backend()

    monkeypatch.setattr(
        service,
        "_resolve_db_workspace_for_public_access",
        lambda requested_workspace_id=None, user_id=None, connection=None: "workspace_uuid",
    )
    monkeypatch.setattr(
        service.generation_job_repo,
        "get_generation_job_scoped_by_public_id",
        lambda job_id, workspace_id, connection=None, for_update=False: row,
    )
    monkeypatch.setattr(
        service.generation_job_event_repo,
        "record_generation_job_event",
        lambda **kwargs: events.append(kwargs) or {"id": "event_uuid"},
    )

    service.record_generation_job_lifecycle_event(
        "job_db",
        "background_enqueued",
        message="graph_resume",
        payload={"task": "graph_resume", "source": "answer_route"},
        workspace_id="workspace_uuid",
        user_id="user_uuid",
    )

    assert events == [
        {
            "workspace_id": "workspace_uuid",
            "thread_id": "thread_uuid",
            "job_id": "job_uuid",
            "event_type": "background_enqueued",
            "message": "graph_resume",
            "payload": {"task": "graph_resume", "source": "answer_route"},
            "connection": events[0]["connection"],
        }
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_generation_jobs.py::test_postgres_record_generation_job_lifecycle_event_records_scoped_event -q
```

Expected: FAIL with `AttributeError: module 'orchestrator.app.generation_jobs.service' has no attribute 'record_generation_job_lifecycle_event'`.

- [ ] **Step 3: Implement the helper**

In `orchestrator/app/generation_jobs/service.py`, add this public helper just above `_record_generation_job_event_db`:

```python
def record_generation_job_lifecycle_event(
    job_id: str,
    event_type: str,
    *,
    message: str | None = None,
    payload: dict | None = None,
    workspace_id: str | None = None,
    user_id: str | None = None,
) -> None:
    if not _use_postgres_backend():
        return
    with db_transaction() as conn:
        if workspace_id is not None or user_id is not None:
            resolved_workspace_id = _resolve_db_workspace_for_public_access(
                requested_workspace_id=workspace_id,
                user_id=user_id,
                connection=conn,
            )
            row = generation_job_repo.get_generation_job_scoped_by_public_id(
                job_id,
                workspace_id=resolved_workspace_id,
                connection=conn,
            )
        else:
            row = generation_job_repo.get_generation_job_row(job_id, connection=conn)
        if not row:
            return
        _record_generation_job_event_db(
            row,
            event_type,
            message=message,
            payload=payload or {},
            connection=conn,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_generation_jobs.py::test_postgres_record_generation_job_lifecycle_event_records_scoped_event -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add orchestrator/app/generation_jobs/service.py orchestrator/tests/test_generation_jobs.py
git commit -m "feat(orchestrator): record generation job lifecycle events"
```

---

### Task 2: Wrap Background Graph Create/Resume Tasks With Lifecycle Events

**Files:**
- Modify: `orchestrator/app/api/routers/generation_jobs.py`
- Test: `orchestrator/tests/test_api_routers.py`

- [ ] **Step 1: Write failing wrapper tests**

Add these tests near other generation job router tests in `orchestrator/tests/test_api_routers.py`:

```python
def test_run_graph_job_background_records_start_and_delegates(monkeypatch):
    from orchestrator.app.api.routers import generation_jobs as router

    events = []
    calls = []

    monkeypatch.setattr(
        router,
        "record_generation_job_lifecycle_event",
        lambda job_id, event_type, **kwargs: events.append({"job_id": job_id, "event_type": event_type, **kwargs}),
    )
    monkeypatch.setattr(
        router,
        "execute_generation_job_graph",
        lambda job_id, request: calls.append((job_id, request)) or "done",
    )

    request = GenerationJobCreateRequest(userInput="Create an ad", runMode="graph_job")

    result = router._run_graph_job_background("job_bg", request)

    assert result == "done"
    assert calls == [("job_bg", request)]
    assert events == [
        {
            "job_id": "job_bg",
            "event_type": "background_started",
            "message": "graph_execute",
            "payload": {"task": "graph_execute"},
        }
    ]


def test_resume_graph_job_background_records_start_and_delegates(monkeypatch):
    from orchestrator.app.api.routers import generation_jobs as router

    events = []
    calls = []

    monkeypatch.setattr(
        router,
        "record_generation_job_lifecycle_event",
        lambda job_id, event_type, **kwargs: events.append({"job_id": job_id, "event_type": event_type, **kwargs}),
    )
    monkeypatch.setattr(
        router,
        "resume_generation_job_graph",
        lambda job_id, request, **kwargs: calls.append((job_id, request, kwargs)) or "resumed",
    )

    request = GenerationJobAnswerRequest(userCustomHeadline="직접 쓴 문구", displayText="직접 쓴 문구")

    result = router._resume_graph_job_background(
        "job_resume",
        request,
        workspace_id="workspace_uuid",
        user_id="user_uuid",
    )

    assert result == "resumed"
    assert calls == [
        (
            "job_resume",
            request,
            {
                "allow_running": True,
                "workspace_id": "workspace_uuid",
                "user_id": "user_uuid",
            },
        )
    ]
    assert events == [
        {
            "job_id": "job_resume",
            "event_type": "background_started",
            "message": "graph_resume",
            "payload": {"task": "graph_resume"},
            "workspace_id": "workspace_uuid",
            "user_id": "user_uuid",
        }
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_api_routers.py::test_run_graph_job_background_records_start_and_delegates orchestrator/tests/test_api_routers.py::test_resume_graph_job_background_records_start_and_delegates -q
```

Expected: FAIL with missing `_run_graph_job_background` and `_resume_graph_job_background`.

- [ ] **Step 3: Add imports**

In `orchestrator/app/api/routers/generation_jobs.py`, extend the service import block:

```python
from orchestrator.app.generation_jobs.service import (
    create_generation_job,
    get_generation_job,
    get_generation_job_internal_with_scope,
    get_generation_job_scoped,
    mark_generation_job_failed,
    mark_generation_job_running,
    maybe_mark_stale_generation_job_failed,
    maybe_poll_generation_job_from_modal,
    maybe_submit_generation_job_to_modal,
    record_generation_job_lifecycle_event,
    resolve_generation_job_scope_from_existing_job,
    resolve_scoped_workspace_id,
    should_route_generation_job_to_modal,
)
```

- [ ] **Step 4: Add wrapper functions**

In `orchestrator/app/api/routers/generation_jobs.py`, add these functions below `_chat_thread_error`:

```python
def _run_graph_job_background(job_id: str, request: GenerationJobCreateRequest):
    record_generation_job_lifecycle_event(
        job_id,
        "background_started",
        message="graph_execute",
        payload={"task": "graph_execute"},
    )
    try:
        return execute_generation_job_graph(job_id, request)
    except Exception as exc:
        mark_generation_job_failed(
            job_id,
            {
                "error_code": "generation_job_background_task_failed",
                "message": "Generation job background task failed before graph completion.",
                "detail": str(exc),
            },
            metadata={"execution_mode": "graph_background_failed", "background_task": "graph_execute"},
        )
        return None


def _resume_graph_job_background(
    job_id: str,
    request: GenerationJobAnswerRequest,
    *,
    workspace_id: str | None,
    user_id: str | None,
):
    record_generation_job_lifecycle_event(
        job_id,
        "background_started",
        message="graph_resume",
        payload={"task": "graph_resume"},
        workspace_id=workspace_id,
        user_id=user_id,
    )
    try:
        return resume_generation_job_graph(
            job_id,
            request,
            allow_running=True,
            workspace_id=workspace_id,
            user_id=user_id,
        )
    except Exception as exc:
        mark_generation_job_failed(
            job_id,
            {
                "error_code": "generation_job_background_task_failed",
                "message": "Generation job background task failed before graph completion.",
                "detail": str(exc),
            },
            metadata={"execution_mode": "graph_background_failed", "background_task": "graph_resume"},
            workspace_id=workspace_id,
            user_id=user_id,
        )
        return None
```

- [ ] **Step 5: Run wrapper tests to verify they pass**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_api_routers.py::test_run_graph_job_background_records_start_and_delegates orchestrator/tests/test_api_routers.py::test_resume_graph_job_background_records_start_and_delegates -q
```

Expected: PASS.

- [ ] **Step 6: Write failing route enqueue tests**

Add these tests to `orchestrator/tests/test_api_routers.py`:

```python
def test_create_graph_job_route_records_background_enqueue(monkeypatch):
    from fastapi import BackgroundTasks
    from orchestrator.app.api.routers import generation_jobs as router

    events = []
    scheduled = []
    job = GenerationJobResponse(
        job_id="job_created_graph",
        thread_id="thread_created_graph",
        user_id="user_a",
        status="queued",
        progress=GenerationProgress(progress_percent=0, current_stage="queued", stage_order=[]),
        created_at="2026-06-13T00:00:00+00:00",
        updated_at="2026-06-13T00:00:00+00:00",
        metadata={},
    )

    class CapturingBackgroundTasks(BackgroundTasks):
        def add_task(self, func, *args, **kwargs):
            scheduled.append((func, args, kwargs))

    monkeypatch.setattr(router, "_forced_user_plan", lambda: None)
    monkeypatch.setattr(router, "get_reference_template", lambda template_id: {"template_id": template_id})
    monkeypatch.setattr(router, "create_generation_job", lambda request: job)
    monkeypatch.setattr(router, "should_route_generation_job_to_modal", lambda request: False)
    monkeypatch.setattr(
        router,
        "record_generation_job_lifecycle_event",
        lambda job_id, event_type, **kwargs: events.append({"job_id": job_id, "event_type": event_type, **kwargs}),
    )

    response = router.create_generation_job_route(
        GenerationJobCreateRequest(userInput="Create an ad", runMode="graph_job"),
        CapturingBackgroundTasks(),
        router.RequestPrincipal(user_id="user_a", workspace_id=None, account_type="user"),
    )

    assert response.job.job_id == "job_created_graph"
    assert events == [
        {
            "job_id": "job_created_graph",
            "event_type": "background_enqueued",
            "message": "graph_execute",
            "payload": {"task": "graph_execute", "source": "create_generation_job_route"},
        }
    ]
    assert scheduled[0][0] is router._run_graph_job_background
    assert scheduled[0][1][0] == "job_created_graph"


def test_answer_graph_job_route_records_background_enqueue(monkeypatch):
    from fastapi import BackgroundTasks
    from orchestrator.app.api.routers import generation_jobs as router

    events = []
    scheduled = []
    job = GenerationJobResponse(
        job_id="job_answer_graph",
        thread_id="thread_answer_graph",
        user_id="user_a",
        status="waiting_user_input",
        progress=GenerationProgress(progress_percent=50, current_stage="waiting_user_input", stage_order=[]),
        created_at="2026-06-13T00:00:00+00:00",
        updated_at="2026-06-13T00:00:00+00:00",
        metadata={},
    )
    running = job.model_copy(
        update={
            "status": "running",
            "progress": GenerationProgress(progress_percent=50, current_stage="planning", stage_order=[]),
        }
    )

    class CapturingBackgroundTasks(BackgroundTasks):
        def add_task(self, func, *args, **kwargs):
            scheduled.append((func, args, kwargs))

    monkeypatch.setattr(router, "resolve_generation_job_scope_from_existing_job", lambda job_id: ("workspace_uuid", "user_a"))
    monkeypatch.setattr(router, "resolve_scoped_workspace_id", lambda workspace_id, user_id, account_type=None: "workspace_uuid")
    monkeypatch.setattr(router, "get_generation_job_scoped", lambda job_id, **kwargs: job)
    monkeypatch.setattr(router, "mark_generation_job_running", lambda job_id, **kwargs: running)
    monkeypatch.setattr(
        router,
        "record_generation_job_lifecycle_event",
        lambda job_id, event_type, **kwargs: events.append({"job_id": job_id, "event_type": event_type, **kwargs}),
    )

    request = GenerationJobAnswerRequest(userCustomHeadline="직접 쓴 문구", displayText="직접 쓴 문구")
    response = router.answer_generation_job_route(
        "job_answer_graph",
        request,
        CapturingBackgroundTasks(),
        principal=router.RequestPrincipal(user_id="user_a", workspace_id=None, account_type="user"),
    )

    assert response.job.status == "running"
    assert events == [
        {
            "job_id": "job_answer_graph",
            "event_type": "background_enqueued",
            "message": "graph_resume",
            "payload": {"task": "graph_resume", "source": "answer_generation_job_route"},
            "workspace_id": "workspace_uuid",
            "user_id": "user_a",
        }
    ]
    assert scheduled[0][0] is router._resume_graph_job_background
    assert scheduled[0][1][:2] == ("job_answer_graph", request)
    assert scheduled[0][2] == {"workspace_id": "workspace_uuid", "user_id": "user_a"}
```

- [ ] **Step 7: Run route enqueue tests to verify they fail**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_api_routers.py::test_create_graph_job_route_records_background_enqueue orchestrator/tests/test_api_routers.py::test_answer_graph_job_route_records_background_enqueue -q
```

Expected: FAIL because routes still schedule the raw graph functions and do not record `background_enqueued`.

- [ ] **Step 8: Update route scheduling**

In `create_generation_job_route`, replace:

```python
background_tasks.add_task(execute_generation_job_graph, job.job_id, request)
```

with:

```python
record_generation_job_lifecycle_event(
    job.job_id,
    "background_enqueued",
    message="graph_execute",
    payload={"task": "graph_execute", "source": "create_generation_job_route"},
)
background_tasks.add_task(_run_graph_job_background, job.job_id, request)
```

In `answer_generation_job_route`, replace the current `background_tasks.add_task(...)` block with:

```python
record_generation_job_lifecycle_event(
    job_id,
    "background_enqueued",
    message="graph_resume",
    payload={"task": "graph_resume", "source": "answer_generation_job_route"},
    workspace_id=resolved_workspace_id,
    user_id=resolved_user_id,
)
background_tasks.add_task(
    _resume_graph_job_background,
    job_id,
    request,
    workspace_id=resolved_workspace_id,
    user_id=resolved_user_id,
)
```

- [ ] **Step 9: Run router tests**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_api_routers.py::test_run_graph_job_background_records_start_and_delegates orchestrator/tests/test_api_routers.py::test_resume_graph_job_background_records_start_and_delegates orchestrator/tests/test_api_routers.py::test_create_graph_job_route_records_background_enqueue orchestrator/tests/test_api_routers.py::test_answer_graph_job_route_records_background_enqueue -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add orchestrator/app/api/routers/generation_jobs.py orchestrator/tests/test_api_routers.py
git commit -m "fix(orchestrator): trace graph background task lifecycle"
```

---

### Task 3: Classify Stale Running Jobs by Lifecycle Evidence

**Files:**
- Modify: `orchestrator/app/generation_jobs/service.py`
- Test: `orchestrator/tests/test_generation_jobs.py`

- [ ] **Step 1: Write failing pure classifier tests**

Add these tests to `orchestrator/tests/test_generation_jobs.py` near the existing stale job tests:

```python
def test_stale_running_payload_detects_background_never_started():
    job = GenerationJobResponse(
        job_id="job_bg_never_started",
        status="running",
        progress=GenerationProgress(progress_percent=50, current_stage="planning", stage_order=[]),
        created_at="2026-06-13T00:00:00+00:00",
        updated_at="2026-06-13T00:00:00+00:00",
        metadata={"execution_mode": "graph_execution"},
    )

    error, metadata = service._stale_running_failure_payload(
        job,
        [{"event_type": "background_enqueued", "payload": {"task": "graph_resume"}}],
    )

    assert error["error_code"] == "generation_job_background_not_started"
    assert error["message"] == "Generation job worker did not start."
    assert "no background_started event" in error["detail"]
    assert metadata["execution_mode"] == "background_not_started_recovered"
    assert metadata["background_task"] == "graph_resume"


def test_stale_running_payload_detects_background_started_but_stalled():
    job = GenerationJobResponse(
        job_id="job_bg_stalled",
        status="running",
        progress=GenerationProgress(progress_percent=50, current_stage="planning", stage_order=[]),
        created_at="2026-06-13T00:00:00+00:00",
        updated_at="2026-06-13T00:00:00+00:00",
        metadata={"execution_mode": "graph_execution"},
    )

    error, metadata = service._stale_running_failure_payload(
        job,
        [
            {"event_type": "background_enqueued", "payload": {"task": "graph_resume"}},
            {"event_type": "background_started", "payload": {"task": "graph_resume"}},
        ],
    )

    assert error["error_code"] == "generation_job_background_stalled"
    assert error["message"] == "Generation job stalled while preparing the request."
    assert "background_started event was recorded" in error["detail"]
    assert metadata["execution_mode"] == "background_stalled_recovered"
    assert metadata["background_task"] == "graph_resume"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_generation_jobs.py::test_stale_running_payload_detects_background_never_started orchestrator/tests/test_generation_jobs.py::test_stale_running_payload_detects_background_started_but_stalled -q
```

Expected: FAIL with missing `_stale_running_failure_payload`.

- [ ] **Step 3: Implement classifier helpers**

In `orchestrator/app/generation_jobs/service.py`, add these helpers above `maybe_mark_stale_generation_job_failed`:

```python
def _event_payload_task(events: list[dict]) -> str | None:
    for event in events:
        payload = event.get("payload") or {}
        task = payload.get("task") if isinstance(payload, dict) else None
        if task:
            return str(task)
    return None


def _stale_running_failure_payload(job: GenerationJobResponse, events: list[dict]) -> tuple[dict, dict]:
    event_types = {str(event.get("event_type")) for event in events}
    background_task = _event_payload_task(events)
    base_metadata = {
        **(job.metadata or {}),
        "stale_running_stage": job.progress.current_stage,
    }
    if "background_enqueued" in event_types and "background_started" not in event_types:
        return (
            {
                "error_code": "generation_job_background_not_started",
                "message": "Generation job worker did not start.",
                "detail": "The job was queued for background execution, but no background_started event was recorded before the stale threshold.",
            },
            {
                **base_metadata,
                "execution_mode": "background_not_started_recovered",
                "background_task": background_task,
            },
        )
    if "background_started" in event_types:
        return (
            {
                "error_code": "generation_job_background_stalled",
                "message": "Generation job stalled while preparing the request.",
                "detail": "A background_started event was recorded, but no completion, interrupt, or Modal handoff was recorded before the stale threshold.",
            },
            {
                **base_metadata,
                "execution_mode": "background_stalled_recovered",
                "background_task": background_task,
            },
        )
    return (
        {
            "error_code": "generation_job_stale_running",
            "message": "Generation job stopped while preparing the request.",
            "detail": "The job stayed in running/planning longer than the allowed stale threshold.",
        },
        {
            **base_metadata,
            "execution_mode": "stale_running_recovered",
        },
    )
```

- [ ] **Step 4: Run classifier tests to verify they pass**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_generation_jobs.py::test_stale_running_payload_detects_background_never_started orchestrator/tests/test_generation_jobs.py::test_stale_running_payload_detects_background_started_but_stalled -q
```

Expected: PASS.

- [ ] **Step 5: Write failing integration test for stale recovery using events**

Add this test near `test_maybe_mark_stale_generation_job_failed_fails_old_running_job`:

```python
def test_maybe_mark_stale_generation_job_failed_uses_background_lifecycle_events(monkeypatch):
    now = datetime(2026, 6, 13, 9, 0, tzinfo=timezone.utc)
    stale_job = GenerationJobResponse(
        job_id="job_stale_background",
        status="running",
        progress=GenerationProgress(progress_percent=50, current_stage="planning", stage_order=[]),
        created_at=(now - timedelta(minutes=30)).isoformat(),
        updated_at=(now - timedelta(minutes=30)).isoformat(),
        metadata={"execution_mode": "graph_execution"},
    )
    captured = {}

    monkeypatch.setattr(
        service.generation_job_event_repo,
        "list_generation_job_events_by_public_job_id",
        lambda job_id, limit=20: [{"event_type": "background_enqueued", "payload": {"task": "graph_resume"}}],
    )

    def fake_mark_failed(job_id, error, metadata=None, **kwargs):
        captured.update({"job_id": job_id, "error": error, "metadata": metadata, "kwargs": kwargs})
        return stale_job.model_copy(
            update={
                "status": "failed",
                "progress": GenerationProgress(progress_percent=50, current_stage="failed", stage_order=[]),
            }
        )

    monkeypatch.setattr(service, "mark_generation_job_failed", fake_mark_failed)

    result = service.maybe_mark_stale_generation_job_failed(
        stale_job,
        workspace_id="workspace_uuid",
        user_id="user_uuid",
        now=now,
    )

    assert result.status == "failed"
    assert captured["job_id"] == "job_stale_background"
    assert captured["error"]["error_code"] == "generation_job_background_not_started"
    assert captured["metadata"]["execution_mode"] == "background_not_started_recovered"
    assert captured["metadata"]["background_task"] == "graph_resume"
    assert captured["kwargs"] == {"workspace_id": "workspace_uuid", "user_id": "user_uuid"}
```

- [ ] **Step 6: Run integration test to verify it fails**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_generation_jobs.py::test_maybe_mark_stale_generation_job_failed_uses_background_lifecycle_events -q
```

Expected: FAIL because `maybe_mark_stale_generation_job_failed` still emits `generation_job_stale_running`.

- [ ] **Step 7: Update stale recovery to read lifecycle events**

Replace the `failed = mark_generation_job_failed(...)` block inside `maybe_mark_stale_generation_job_failed` with:

```python
    events: list[dict] = []
    try:
        events = generation_job_event_repo.list_generation_job_events_by_public_job_id(job.job_id, limit=20)
    except Exception:
        events = []
    error_payload, metadata_payload = _stale_running_failure_payload(job, events)

    failed = mark_generation_job_failed(
        job.job_id,
        error_payload,
        metadata=metadata_payload,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    return failed or job
```

- [ ] **Step 8: Run stale tests**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_generation_jobs.py::test_maybe_mark_stale_generation_job_failed_keeps_fresh_running_job orchestrator/tests/test_generation_jobs.py::test_maybe_mark_stale_generation_job_failed_fails_old_running_job orchestrator/tests/test_generation_jobs.py::test_maybe_mark_stale_generation_job_failed_uses_background_lifecycle_events -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add orchestrator/app/generation_jobs/service.py orchestrator/tests/test_generation_jobs.py
git commit -m "fix(orchestrator): classify stale background graph jobs"
```

---

### Task 4: Preserve the Exact Custom Copy Candidate Resume Path

**Files:**
- Modify: `orchestrator/tests/test_marketing_graph.py`

- [ ] **Step 1: Add regression coverage for the observed UI path**

Add this test after `test_suggest_candidates_interrupt_then_resume_to_mock` in `orchestrator/tests/test_marketing_graph.py`:

```python
def test_suggest_candidates_interrupt_accepts_manual_copy_without_selected_id_to_mock():
    graph = build_marketing_graph()
    config = {"configurable": {"thread_id": "copy-mode-suggest-manual"}}
    first = graph.invoke(_request("suggest_candidates", "copy-mode-suggest-manual"), config=config)
    payload = first["__interrupt__"][0].value

    assert payload["type"] == "copy_candidate_selection"

    result = graph.invoke(
        Command(
            resume={
                "user_custom_headline": "직접 쓴 딸기라떼 광고",
                "user_custom_subcopy": "오늘 오후 한정",
                "selected_channel_id": "instagram-feed",
                "selected_ad_format": "instagram_feed",
                "selected_tone": "감성적인",
            }
        ),
        config=config,
    )

    assert result["status"] == "done"
    assert result["marketing_copy"]["headline"] == "직접 쓴 딸기라떼 광고"
    assert result["marketing_copy"]["subcopy"] == "오늘 오후 한정"
    assert result["marketing_copy"]["metadata"]["copy_resolution"] == "manual_edit"
    assert result["copy_spec"]["items"][0]["text"] == "직접 쓴 딸기라떼 광고"
    assert result["t2i_result"]["engine"] == "mock"
```

- [ ] **Step 2: Run regression test**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_marketing_graph.py::test_suggest_candidates_interrupt_accepts_manual_copy_without_selected_id_to_mock -q
```

Expected: PASS. If this fails, stop and fix `orchestrator/app/llm/nodes/copy_candidates.py` before continuing because the graph cannot handle the UI path.

- [ ] **Step 3: Commit**

```bash
git add orchestrator/tests/test_marketing_graph.py
git commit -m "test(orchestrator): cover manual copy from candidate interrupt"
```

---

### Task 5: Show Specific Frontend Notices for Background Stale Failures

**Files:**
- Modify: `apps/web/lib/generation-result-utils.ts`
- Test: `apps/web/lib/generation-result-utils.test.ts`

- [ ] **Step 1: Write failing Vitest coverage**

Add these tests near the existing failed job notice tests in `apps/web/lib/generation-result-utils.test.ts`:

```typescript
  it("explains when a background job never started", () => {
    expect(
      getGenerationResultNotice({
        job_id: "job_background_not_started",
        status: "failed",
        error: {
          error_code: "generation_job_background_not_started",
          message: "Generation job worker did not start.",
          detail: "The job was queued for background execution, but no background_started event was recorded before the stale threshold."
        }
      }).message
    ).toBe("생성 작업이 서버에서 시작되지 않았어요. 잠시 후 다시 시도해주세요.");
  });

  it("explains when a background job started but stalled", () => {
    expect(
      getGenerationResultNotice({
        job_id: "job_background_stalled",
        status: "failed",
        error: {
          error_code: "generation_job_background_stalled",
          message: "Generation job stalled while preparing the request.",
          detail: "A background_started event was recorded, but no completion, interrupt, or Modal handoff was recorded before the stale threshold."
        }
      }).message
    ).toBe("생성 작업이 중간에 멈췄어요. 같은 요청으로 다시 시도해주세요.");
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
npm --prefix apps/web test -- lib/generation-result-utils.test.ts
```

Expected: FAIL because the notice still falls back to raw error text.

- [ ] **Step 3: Implement notice mapping**

In `apps/web/lib/generation-result-utils.ts`, add this helper above `getErrorMessage`:

```typescript
function getKnownGenerationErrorMessage(error: unknown): string | null {
  if (!error || typeof error !== "object") {
    return null;
  }
  const errorCode = (error as { error_code?: unknown }).error_code;
  if (errorCode === "generation_job_background_not_started") {
    return "생성 작업이 서버에서 시작되지 않았어요. 잠시 후 다시 시도해주세요.";
  }
  if (errorCode === "generation_job_background_stalled") {
    return "생성 작업이 중간에 멈췄어요. 같은 요청으로 다시 시도해주세요.";
  }
  return null;
}
```

Then update the start of `getErrorMessage`:

```typescript
function getErrorMessage(error: unknown): string | null {
  const knownMessage = getKnownGenerationErrorMessage(error);
  if (knownMessage) {
    return knownMessage;
  }
  if (!error || typeof error !== "object") {
    return typeof error === "string" ? error : null;
  }
```

- [ ] **Step 4: Run frontend tests**

Run:

```bash
npm --prefix apps/web test -- lib/generation-result-utils.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/lib/generation-result-utils.ts apps/web/lib/generation-result-utils.test.ts
git commit -m "fix(web): explain stalled background generation failures"
```

---

### Task 6: Final Verification

**Files:**
- No new files.

- [ ] **Step 1: Run backend targeted tests**

Run:

```bash
PYTHONPATH=. uv run pytest \
  orchestrator/tests/test_generation_jobs.py::test_postgres_record_generation_job_lifecycle_event_records_scoped_event \
  orchestrator/tests/test_generation_jobs.py::test_stale_running_payload_detects_background_never_started \
  orchestrator/tests/test_generation_jobs.py::test_stale_running_payload_detects_background_started_but_stalled \
  orchestrator/tests/test_generation_jobs.py::test_maybe_mark_stale_generation_job_failed_keeps_fresh_running_job \
  orchestrator/tests/test_generation_jobs.py::test_maybe_mark_stale_generation_job_failed_fails_old_running_job \
  orchestrator/tests/test_generation_jobs.py::test_maybe_mark_stale_generation_job_failed_uses_background_lifecycle_events \
  orchestrator/tests/test_api_routers.py::test_run_graph_job_background_records_start_and_delegates \
  orchestrator/tests/test_api_routers.py::test_resume_graph_job_background_records_start_and_delegates \
  orchestrator/tests/test_api_routers.py::test_create_graph_job_route_records_background_enqueue \
  orchestrator/tests/test_api_routers.py::test_answer_graph_job_route_records_background_enqueue \
  orchestrator/tests/test_marketing_graph.py::test_suggest_candidates_interrupt_accepts_manual_copy_without_selected_id_to_mock \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend targeted tests**

Run:

```bash
npm --prefix apps/web test -- lib/generation-result-utils.test.ts app/generate/chat/ChatGenerateClient.test.tsx
```

Expected: PASS.

- [ ] **Step 3: Run Docker import guard**

Run:

```bash
docker build -f Dockerfile.orchestrator -t easyads-orchestrator-background-lifecycle-check .
docker run --rm easyads-orchestrator-background-lifecycle-check python -c "import langgraph.checkpoint.postgres; import psycopg_pool; print('runtime-ok')"
docker rmi easyads-orchestrator-background-lifecycle-check
```

Expected: the container prints `runtime-ok`, and the image is removed.

- [ ] **Step 4: Inspect status**

Run:

```bash
git status --short --branch
git log --oneline --decorate -6
```

Expected: working tree is clean after the final commit, and the latest commits match the task commit messages.

---

## Self-Review

**Spec coverage:** The plan covers the user-visible bug by addressing the actual observed failure mode: final-generation answers move the UI to generating, but backend background graph work can remain in `running/planning` until stale recovery. Task 2 records background enqueue/start, Task 3 classifies stale recovery by those events, Task 4 protects the custom copy graph path, and Task 5 replaces the generic failed image notice for the new backend failure codes.

**Placeholder scan:** The plan contains no deferred implementation steps and no unspecified test instructions.

**Type consistency:** Backend function names are consistent across tasks: `record_generation_job_lifecycle_event`, `_run_graph_job_background`, `_resume_graph_job_background`, and `_stale_running_failure_payload`. Frontend error codes match backend classifier output: `generation_job_background_not_started` and `generation_job_background_stalled`.
