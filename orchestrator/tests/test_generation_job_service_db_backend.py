from datetime import datetime, timezone
from contextlib import contextmanager

import pytest

from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest
from orchestrator.app.generation_jobs import service


@pytest.fixture(autouse=True)
def reset_store(monkeypatch):
    service.reset_generation_job_store_for_tests()
    monkeypatch.delenv("EASYADS_DB_BACKEND", raising=False)
    yield
    service.reset_generation_job_store_for_tests()


def _row(public_job_id="job_db", status="queued", metadata=None, result_payload=None, error=None):
    now = datetime.now(timezone.utc)
    return {
        "public_job_id": public_job_id,
        "thread_id": "thread_uuid",
        "status": status,
        "current_stage": "completed" if status == "done" else status,
        "progress_percent": 100 if status == "done" else 0,
        "selected_reference_template_id": "seed_1",
        "output_path": "data/outputs/job_db/final_0.png" if status == "done" else None,
        "result_payload": result_payload,
        "error": error,
        "created_at": now,
        "updated_at": now,
        "metadata": metadata or {
            "public_thread_id": "thread_db",
            "requested_run_mode": "queued_only",
            "effective_run_mode": "queued_only",
            "execution_mode": "queued_only",
        },
    }


@contextmanager
def fake_db_transaction():
    yield object()


def test_memory_backend_uses_existing_store(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    request = GenerationJobCreateRequest(user_input="Create an ad", run_mode="queued_only")

    job = service.create_generation_job(request)

    assert job.job_id.startswith("job_")
    assert service.get_generation_job(job.job_id) == job


def test_postgres_backend_create_uses_repository_path(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction)
    monkeypatch.setattr(service.workspace_repo, "ensure_demo_workspace", lambda user_id=None, connection=None: {"id": "workspace_uuid"})
    monkeypatch.setattr(
        service.chat_thread_repo,
        "create_chat_thread",
        lambda **kwargs: {"id": "thread_uuid", "public_thread_id": "thread_db"},
    )

    captured = {}

    def fake_create_generation_job_row(**kwargs):
        captured.update(kwargs)
        metadata = dict(kwargs["metadata"])
        metadata["public_thread_id"] = "thread_db"
        return _row(public_job_id=kwargs["public_job_id"], metadata=metadata)

    monkeypatch.setattr(service.generation_job_repo, "create_generation_job_row", fake_create_generation_job_row)

    request = GenerationJobCreateRequest(user_input="Create an ad", run_mode="queued_only", selected_reference_template_id="seed_1")
    job = service.create_generation_job(request)

    assert job.job_id.startswith("job_")
    assert job.thread_id == "thread_db"
    assert job.status == "queued"
    assert job.selected_reference_template_id == "seed_1"
    assert captured["workspace_id"] == "workspace_uuid"
    assert captured["thread_id"] == "thread_uuid"
    assert captured["run_mode"] == "queued_only"
    assert captured["request_payload"]["user_input_preview"] == "Create an ad"


def test_postgres_backend_sanitizes_nested_metadata(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction)
    monkeypatch.setattr(service.workspace_repo, "ensure_demo_workspace", lambda user_id=None, connection=None: {"id": "workspace_uuid"})
    monkeypatch.setattr(service.chat_thread_repo, "create_chat_thread", lambda **kwargs: {"id": "thread_uuid", "public_thread_id": "thread_db"})

    captured = {}

    def fake_create_generation_job_row(**kwargs):
        captured.update(kwargs)
        metadata = dict(kwargs["metadata"])
        metadata["public_thread_id"] = "thread_db"
        return _row(public_job_id=kwargs["public_job_id"], metadata=metadata)

    monkeypatch.setattr(service.generation_job_repo, "create_generation_job_row", fake_create_generation_job_row)

    request = GenerationJobCreateRequest(
        user_input="Create an ad",
        run_mode="queued_only",
        metadata={"debug": {"api_key": "sk-should-not-leak", "safe": "visible"}},
    )
    job = service.create_generation_job(request)

    assert "sk-should-not-leak" not in str(job.model_dump(mode="json"))
    assert captured["metadata"]["debug"]["safe"] == "visible"
    assert "api_key" not in captured["metadata"]["debug"]


def test_postgres_backend_mark_done_and_failed_preserve_shape(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    state = {"row": _row(public_job_id="job_db")}
    monkeypatch.setattr(service.generation_job_repo, "get_generation_job_row", lambda job_id: state["row"])

    def fake_update(job_id, **fields):
        metadata = fields.get("metadata") or state["row"]["metadata"]
        state["row"] = {
            **state["row"],
            "status": fields.get("status", state["row"]["status"]),
            "current_stage": fields.get("current_stage", state["row"]["current_stage"]),
            "progress_percent": fields.get("progress_percent", state["row"]["progress_percent"]),
            "output_path": fields.get("output_path", state["row"]["output_path"]),
            "result_payload": fields.get("result_payload", state["row"]["result_payload"]),
            "error": fields.get("error", state["row"]["error"]),
            "metadata": metadata,
        }
        return state["row"]

    monkeypatch.setattr(service.generation_job_repo, "update_generation_job_row", fake_update)

    done = service.mark_generation_job_done("job_db", result_payload={"schema_version": "result_artifact_v1"}, output_path="data/outputs/job_db/final_0.png")
    assert done.status == "done"
    assert done.result_payload["schema_version"] == "result_artifact_v1"
    assert done.output_path.endswith("final_0.png")

    failed = service.mark_generation_job_failed("job_db", {"error_code": "x", "message": "failed"})
    assert failed.status == "failed"
    assert failed.error.error_code == "x"
    assert failed.progress.current_stage == "failed"
