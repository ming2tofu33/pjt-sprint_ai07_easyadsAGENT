from contextlib import contextmanager
from datetime import datetime, timezone

from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest
from orchestrator.app.generation_jobs import service


@contextmanager
def fake_db_transaction():
    yield object()


def _row(status="queued", metadata=None, error=None):
    now = datetime.now(timezone.utc)
    return {
        "id": "job_uuid",
        "public_job_id": "job_db",
        "workspace_id": "workspace_uuid",
        "thread_id": "thread_uuid",
        "requested_by": "demo_user",
        "status": status,
        "current_stage": status,
        "progress_percent": 50 if status == "running" else 0,
        "selected_reference_template_id": "seed_1",
        "output_path": None,
        "result_payload": None,
        "error": error or {},
        "created_at": now,
        "updated_at": now,
        "metadata": metadata or {
            "public_thread_id": "thread_db",
            "requested_run_mode": "queued_only",
            "effective_run_mode": "queued_only",
            "execution_mode": "queued_only",
        },
    }


def test_postgres_create_records_queued_event_and_active_thread(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction)
    events = []
    thread_updates = []
    captured = {}

    monkeypatch.setattr(service.workspace_repo, "ensure_demo_workspace", lambda user_id=None, connection=None: {"id": "workspace_uuid"})
    monkeypatch.setattr(service.chat_thread_repo, "create_chat_thread", lambda **kwargs: {"id": "thread_uuid", "public_thread_id": "thread_db"})
    monkeypatch.setattr(service.chat_thread_repo, "set_chat_thread_active_job", lambda *args, **kwargs: thread_updates.append((args, kwargs)) or {"id": "thread_uuid"})
    monkeypatch.setattr(service.generation_job_event_repo, "record_generation_job_event", lambda **kwargs: events.append(kwargs) or {"id": "event_uuid"})

    def create_row(**kwargs):
        captured.update(kwargs)
        metadata = dict(kwargs["metadata"])
        metadata["public_thread_id"] = "thread_db"
        return _row(metadata=metadata)

    monkeypatch.setattr(service.generation_job_repo, "create_generation_job_row", create_row)

    job = service.create_generation_job(
        GenerationJobCreateRequest(user_input="Create an ad", run_mode="queued_only", selected_reference_template_id="seed_1")
    )

    assert job.job_id == "job_db"
    assert job.thread_id == "thread_db"
    assert job.status == "queued"
    assert captured["workspace_id"] == "workspace_uuid"
    assert captured["thread_id"] == "thread_uuid"
    assert events[0]["event_type"] == "queued"
    assert thread_updates[0][1]["status"] == "generating"

    assert captured["engine"] is None
    assert captured["model_provider"] is None
    assert captured["model_name"] is None


def test_postgres_get_converts_db_row_to_response(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(service.generation_job_repo, "get_generation_job_row", lambda job_id: _row())

    job = service.get_generation_job("job_db")

    assert job.job_id == "job_db"
    assert job.thread_id == "thread_db"
    assert job.selected_reference_template_id == "seed_1"
    assert job.metadata["requested_run_mode"] == "queued_only"


def test_postgres_mark_running_updates_row_and_records_event(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction)
    events = []
    thread_updates = []

    def mark_running(job_id, current_stage=None, connection=None):
        row = _row(status="running")
        row["current_stage"] = current_stage
        return row

    monkeypatch.setattr(service.generation_job_repo, "mark_generation_job_running_row", mark_running)
    monkeypatch.setattr(service.generation_job_event_repo, "record_generation_job_event", lambda **kwargs: events.append(kwargs) or {"id": "event_uuid"})
    monkeypatch.setattr(service.chat_thread_repo, "update_chat_thread_status", lambda *args, **kwargs: thread_updates.append((args, kwargs)) or {"id": "thread_uuid"})

    job = service.mark_generation_job_running("job_db", "t2i_running")

    assert job.status == "running"
    assert job.progress.current_stage == "t2i_running"
    assert job.progress.progress_percent == 50
    assert events[0]["event_type"] == "running"
    assert events[0]["payload"]["current_stage"] == "t2i_running"
    assert thread_updates[0][1]["status"] == "generating"


def test_postgres_mark_failed_updates_row_thread_and_event(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction)
    events = []
    thread_updates = []
    state = _row()

    def mark_failed(job_id, error, metadata=None, connection=None):
        state.update({"status": "failed", "current_stage": "failed", "error": error, "metadata": metadata or state["metadata"]})
        return state

    monkeypatch.setattr(service.generation_job_repo, "get_generation_job_row", lambda job_id, connection=None: state)
    monkeypatch.setattr(service.generation_job_repo, "mark_generation_job_failed_row", mark_failed)
    monkeypatch.setattr(service.generation_job_event_repo, "record_generation_job_event", lambda **kwargs: events.append(kwargs) or {"id": "event_uuid"})
    monkeypatch.setattr(service.chat_thread_repo, "fail_chat_thread_generation", lambda **kwargs: thread_updates.append(kwargs) or {"id": "thread_uuid"})

    failed = service.mark_generation_job_failed("job_db", {"error_code": "x", "message": "failed"})

    assert failed.status == "failed"
    assert failed.error.error_code == "x"
    assert events[0]["event_type"] == "failed"
    assert events[0]["payload"]["error_code"] == "x"
    assert thread_updates[0]["expected_active_job_id"] == "job_uuid"
