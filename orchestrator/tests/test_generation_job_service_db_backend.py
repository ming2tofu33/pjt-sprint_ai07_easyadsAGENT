from datetime import datetime, timezone
from contextlib import contextmanager

import pytest

from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest
from orchestrator.app.chat_threads.errors import ChatThreadHasActiveJobError
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
        "id": "job_uuid",
        "public_job_id": public_job_id,
        "workspace_id": "workspace_uuid",
        "thread_id": "thread_uuid",
        "requested_by": "demo_user",
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


from unittest.mock import MagicMock

@contextmanager
def fake_db_transaction():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    yield conn


def _patch_noop_side_effects(monkeypatch):
    monkeypatch.setattr(service.chat_thread_repo, "set_chat_thread_active_job", lambda *args, **kwargs: {"id": "thread_uuid"})
    monkeypatch.setattr(service.chat_message_repo, "append_chat_message", lambda **kwargs: {"id": "msg_uuid"})
    monkeypatch.setattr(service.state_service, "get_latest_thread_state_snapshot", lambda **kwargs: None)
    monkeypatch.setattr(service.state_service, "save_thread_state_snapshot", lambda **kwargs: {"snapshot_id": "snap_uuid"})
    monkeypatch.setattr(service.chat_thread_repo, "complete_chat_thread_generation", lambda **kwargs: {"id": "thread_uuid", **kwargs})
    monkeypatch.setattr(service.chat_message_repo, "append_chat_message", lambda **kwargs: {"id": "msg_uuid"})
    monkeypatch.setattr(service.state_service, "get_latest_thread_state_snapshot", lambda **kwargs: None)
    monkeypatch.setattr(service.state_service, "save_thread_state_snapshot", lambda **kwargs: {"snapshot_id": "snap_uuid"})
    monkeypatch.setattr(service.chat_thread_repo, "fail_chat_thread_generation", lambda **kwargs: {"id": "thread_uuid", **kwargs})
    monkeypatch.setattr(service.chat_message_repo, "append_chat_message", lambda **kwargs: {"id": "msg_uuid"})
    monkeypatch.setattr(service.state_service, "get_latest_thread_state_snapshot", lambda **kwargs: None)
    monkeypatch.setattr(service.state_service, "save_thread_state_snapshot", lambda **kwargs: {"snapshot_id": "snap_uuid"})
    monkeypatch.setattr(service.generation_job_event_repo, "record_generation_job_event", lambda **kwargs: {"id": "event_uuid", **kwargs})
    monkeypatch.setattr(service.chat_thread_repo, "get_chat_thread_by_public_id", lambda thread_id, **kwargs: {"id": "thread_uuid", "active_job_id": "job_uuid"})
    monkeypatch.setattr(service.chat_message_repo, "append_generation_job_chat_event", lambda **kwargs: {"id": "msg_uuid"})


def test_memory_backend_uses_existing_store(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    request = GenerationJobCreateRequest(user_input="Create an ad", run_mode="queued_only")

    job = service.create_generation_job(request)

    assert job.job_id.startswith("job_")
    assert service.get_generation_job(job.job_id) == job


def test_memory_backend_does_not_store_orphan_job_when_thread_claim_fails(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    monkeypatch.setattr(
        service.chat_thread_service,
        "set_thread_active_job",
        lambda *args, **kwargs: (_ for _ in ()).throw(ChatThreadHasActiveJobError()),
    )

    with pytest.raises(ChatThreadHasActiveJobError):
        service.create_generation_job(GenerationJobCreateRequest(user_input="Create an ad", run_mode="queued_only"))

    assert service._GENERATION_JOBS == {}


def test_postgres_backend_create_uses_repository_path(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction)
    _patch_noop_side_effects(monkeypatch)
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

    captured_thread = {}
    monkeypatch.setattr(
        service.chat_thread_repo,
        "create_chat_thread",
        lambda **kwargs: captured_thread.update(kwargs) or {"id": "thread_uuid", "public_thread_id": "thread_db"},
    )

    request = GenerationJobCreateRequest(
        user_input="Create an ad",
        run_mode="queued_only",
        selected_reference_template_id="seed_1",
        brand_kit_id="bk_public",
    )
    job = service.create_generation_job(request)

    assert job.job_id.startswith("job_")
    assert job.thread_id == "thread_db"
    assert job.status == "queued"
    assert job.selected_reference_template_id == "seed_1"
    assert captured["workspace_id"] == "workspace_uuid"
    assert captured["thread_id"] == "thread_uuid"
    assert captured_thread["brand_kit_id"] is None
    assert job.brand_kit_id == "bk_public"
    assert job.metadata["brand_kit_id"] == "bk_public"
    assert captured["run_mode"] == "queued_only"
    assert captured["request_payload"]["user_input_preview"] == "Create an ad"


def test_postgres_backend_create_uses_authenticated_user_workspace(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_DEMO_WORKSPACE_ID", "workspace_demo")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction)
    _patch_noop_side_effects(monkeypatch)
    monkeypatch.setattr(
        service.workspace_repo,
        "ensure_user_workspace",
        lambda user_id, connection=None: {"id": f"workspace_{user_id}"},
    )
    monkeypatch.setattr(
        service.workspace_repo,
        "ensure_demo_workspace",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("authenticated users must not use demo workspace")),
    )
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

    job = service.create_generation_job(
        GenerationJobCreateRequest(user_id="user_a", user_input="Create an ad", run_mode="queued_only")
    )

    assert job.user_id == "user_a"
    assert captured["workspace_id"] == "workspace_user_a"


def test_postgres_backend_sanitizes_nested_metadata(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction)
    _patch_noop_side_effects(monkeypatch)
    monkeypatch.setattr(service.workspace_repo, "ensure_demo_workspace", lambda user_id=None, connection=None: {"id": "workspace_uuid"})
    monkeypatch.setattr(service.chat_thread_repo, "create_chat_thread", lambda **kwargs: {"id": "thread_uuid", "public_thread_id": "thread_db"})
    monkeypatch.setattr(service.chat_message_repo, "append_chat_message", lambda **kwargs: {"id": "msg_uuid"})
    monkeypatch.setattr(service.state_service, "get_latest_thread_state_snapshot", lambda **kwargs: None)
    monkeypatch.setattr(service.state_service, "save_thread_state_snapshot", lambda **kwargs: {"snapshot_id": "snap_uuid"})

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
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction)
    _patch_noop_side_effects(monkeypatch)
    state = {"row": _row(public_job_id="job_db")}
    monkeypatch.setattr(service.generation_job_repo, "get_generation_job_row", lambda job_id, connection=None: state["row"])

    def fake_mark_done(job_id, result_payload, output_path=None, metadata=None, connection=None):
        metadata = metadata or state["row"]["metadata"]
        state["row"] = {
            **state["row"],
            "status": "done",
            "current_stage": "completed",
            "progress_percent": 100,
            "output_path": output_path,
            "result_payload": result_payload,
            "error": {},
            "metadata": metadata,
        }
        return state["row"]

    def fake_mark_failed(job_id, error, metadata=None, connection=None):
        state["row"] = {
            **state["row"],
            "status": "failed",
            "current_stage": "failed",
            "error": error,
            "metadata": metadata or state["row"]["metadata"],
        }
        return state["row"]

    monkeypatch.setattr(service.generation_job_repo, "mark_generation_job_done_row", fake_mark_done)
    monkeypatch.setattr(service.generation_job_repo, "mark_generation_job_failed_row", fake_mark_failed)
    monkeypatch.setattr(
        service.generation_job_repo,
        "update_generation_job_row",
        lambda job_id, connection=None, **fields: state["row"].update(fields) or state["row"],
    )
    monkeypatch.setattr(service.asset_repo, "create_asset", lambda **kwargs: {"id": "asset_uuid", **kwargs})
    monkeypatch.setattr(service.generation_output_repo, "create_generation_output", lambda **kwargs: {"id": "output_uuid", "asset_id": kwargs["asset_id"], **kwargs})
    monkeypatch.setattr(service.generation_output_repo, "mark_output_final", lambda output_id, *args, **kwargs: {"id": output_id})
    monkeypatch.setattr("orchestrator.app.archive.service.sync_archive_for_output", MagicMock())

    done = service.mark_generation_job_done("job_db", result_payload={"schema_version": "result_artifact_v1"}, output_path="data/outputs/job_db/final_0.png")
    assert done.status == "done"
    assert done.result_payload["schema_version"] == "result_artifact_v1"
    assert done.output_path.endswith("final_0.png")

    failed = service.mark_generation_job_failed("job_db", {"error_code": "x", "message": "failed"})
    assert failed.status == "failed"
    assert failed.error.error_code == "x"
    assert failed.progress.current_stage == "failed"
