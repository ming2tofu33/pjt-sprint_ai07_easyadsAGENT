from contextlib import contextmanager

from orchestrator.app.generation_jobs import service
from orchestrator.app.storage.errors import R2UploadError


@contextmanager
def fake_db_transaction():
    yield object()


def _base_row():
    return {
        "id": "job_uuid",
        "public_job_id": "job_db",
        "workspace_id": "workspace_uuid",
        "thread_id": "thread_uuid",
        "requested_by": "demo_user",
        "status": "queued",
        "current_stage": "queued",
        "progress_percent": 0,
        "selected_reference_template_id": None,
        "output_path": None,
        "result_payload": None,
        "error": {},
        "metadata": {"public_thread_id": "thread_db"},
        "created_at": "2026-06-02T00:00:00+00:00",
        "updated_at": "2026-06-02T00:00:00+00:00",
    }


def _patch_mark_done(monkeypatch, row):
    def mark_done(job_id, result_payload, output_path=None, metadata=None, connection=None):
        row.update(
            {
                "status": "done",
                "current_stage": "completed",
                "progress_percent": 100,
                "result_payload": result_payload,
                "output_path": output_path,
                "error": {},
                "metadata": metadata or row["metadata"],
            }
        )
        return row

    monkeypatch.setattr(service.generation_job_repo, "mark_generation_job_done_row", mark_done)


def test_mark_done_r2_disabled_keeps_local_dev_placeholder(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.delenv("EASYADS_ENABLE_R2_UPLOAD", raising=False)
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction)
    events = []
    assets = []
    outputs = []
    row = _base_row()

    monkeypatch.setattr(service.generation_job_repo, "get_generation_job_row", lambda job_id, connection=None: row)
    monkeypatch.setattr(service.generation_job_repo, "update_generation_job_row", lambda job_id, connection=None, **fields: row.update(fields) or row)
    _patch_mark_done(monkeypatch, row)
    monkeypatch.setattr(service.asset_repo, "create_asset", lambda **kwargs: assets.append({"id": "asset_uuid", **kwargs}) or assets[-1])
    monkeypatch.setattr(service.generation_output_repo, "create_generation_output", lambda **kwargs: outputs.append({"id": "output_uuid", "asset_id": kwargs["asset_id"], **kwargs}) or outputs[-1])
    monkeypatch.setattr(service.generation_output_repo, "mark_output_final", lambda output_id, connection=None: {"id": output_id, "asset_id": "asset_uuid", "is_final": True})
    thread_updates = []
    monkeypatch.setattr(service.chat_thread_repo, "complete_chat_thread_generation", lambda **kwargs: thread_updates.append(kwargs) or {"id": "thread_uuid"})
    monkeypatch.setattr(service.generation_job_event_repo, "record_generation_job_event", lambda **kwargs: events.append(kwargs) or {"id": "event_uuid"})

    done = service.mark_generation_job_done(
        "job_db",
        result_payload={"schema_version": "result_artifact_v1", "final_image_path": "data/outputs/job_db/final_0.png"},
        output_path="data/outputs/job_db/final_0.png",
    )

    assert done.status == "done"
    assert assets[0]["storage_provider"] == "local_dev"
    assert done.result_payload["final_asset_id"] == "asset_uuid"
    assert done.result_payload["storage_provider"] == "local_dev"
    assert done.result_payload["bucket"] == "local-dev"
    assert done.result_payload["object_key"] == "data/outputs/job_db/final_0.png"
    assert done.result_payload.get("final_image_url") is None
    assert done.result_payload.get("download_url") is None
    assert "r2_upload_started" not in [event["event_type"] for event in events]
    assert thread_updates[0]["expected_active_job_id"] == "job_uuid"
    assert thread_updates[0]["final_output_id"] == "output_uuid"

def test_mark_done_r2_success_persists_r2_asset_and_urls(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_ENABLE_R2_UPLOAD", "true")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction)
    events = []
    assets = []
    outputs = []
    state = {"row": _base_row()}

    def get_row(job_id, connection=None):
        return state["row"]

    def update_row(job_id, connection=None, **fields):
        state["row"] = {**state["row"], **fields}
        return state["row"]

    monkeypatch.setattr(service.generation_job_repo, "get_generation_job_row", get_row)
    monkeypatch.setattr(service.generation_job_repo, "update_generation_job_row", update_row)
    _patch_mark_done(monkeypatch, state["row"])
    monkeypatch.setattr(
        service,
        "upload_file_to_r2",
        lambda **kwargs: type(
            "Uploaded",
            (),
            {
                "bucket": "easyads-dev",
                "object_key": "workspaces/workspace_uuid/threads/thread_db/jobs/job_db/final_0.png",
                "storage_provider": "r2",
                "mime_type": "image/png",
                "size_bytes": 123,
                "public_url": None,
                "final_image_url": "https://signed.example/final_0.png",
                "download_url": "https://signed.example/final_0.png",
                "signed_url_expires_at": "2026-06-03T00:00:00+00:00",
                "metadata": {"public_serving": True, "url_mode": "signed", "source": "generation_job_r2_upload"},
                "width": 1200,
                "height": 1200,
            },
        )(),
    )
    monkeypatch.setattr(service.asset_repo, "create_asset", lambda **kwargs: assets.append({"id": "asset_r2_uuid", **kwargs}) or assets[-1])
    monkeypatch.setattr(service.generation_output_repo, "create_generation_output", lambda **kwargs: outputs.append({"id": "output_uuid", "asset_id": kwargs["asset_id"], **kwargs}) or outputs[-1])
    monkeypatch.setattr(service.generation_output_repo, "mark_output_final", lambda output_id, connection=None: {"id": output_id, "asset_id": "asset_r2_uuid", "is_final": True})
    thread_updates = []
    monkeypatch.setattr(service.chat_thread_repo, "complete_chat_thread_generation", lambda **kwargs: thread_updates.append(kwargs) or {"id": "thread_uuid"})
    monkeypatch.setattr(service.generation_job_event_repo, "record_generation_job_event", lambda **kwargs: events.append(kwargs) or {"id": "event_uuid"})

    done = service.mark_generation_job_done(
        "job_db",
        result_payload={"schema_version": "result_artifact_v1", "final_image_path": "data/outputs/job_db/final_0.png"},
        output_path="data/outputs/job_db/final_0.png",
    )

    assert done.status == "done"
    assert assets[0]["storage_provider"] == "r2"
    assert outputs[0]["asset_id"] == "asset_r2_uuid"
    assert done.result_payload["final_image_url"] == "https://signed.example/final_0.png"
    assert done.result_payload["download_url"] == "https://signed.example/final_0.png"
    assert done.result_payload["final_asset_id"] == "asset_r2_uuid"
    assert [event["event_type"] for event in events] == ["r2_upload_started", "r2_upload_completed", "done", "output_created"]
    assert thread_updates[0]["expected_active_job_id"] == "job_uuid"
    assert thread_updates[0]["final_output_id"] == "output_uuid"


def test_mark_done_r2_failure_falls_back_to_local_dev_when_not_required(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_ENABLE_R2_UPLOAD", "true")
    monkeypatch.setenv("EASYADS_R2_UPLOAD_REQUIRED", "false")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction)
    events = []
    assets = []
    state = {"row": _base_row()}

    monkeypatch.setattr(service.generation_job_repo, "get_generation_job_row", lambda job_id, connection=None: state["row"])
    monkeypatch.setattr(service.generation_job_repo, "update_generation_job_row", lambda job_id, connection=None, **fields: state["row"].update(fields) or state["row"])
    _patch_mark_done(monkeypatch, state["row"])
    monkeypatch.setattr(service, "upload_file_to_r2", lambda **kwargs: (_ for _ in ()).throw(R2UploadError("R2 upload failed.")))
    monkeypatch.setattr(service.asset_repo, "create_asset", lambda **kwargs: assets.append({"id": "asset_local_uuid", **kwargs}) or assets[-1])
    monkeypatch.setattr(service.generation_output_repo, "create_generation_output", lambda **kwargs: {"id": "output_uuid", "asset_id": kwargs["asset_id"], **kwargs})
    monkeypatch.setattr(service.generation_output_repo, "mark_output_final", lambda output_id, connection=None: {"id": output_id, "asset_id": "asset_local_uuid", "is_final": True})
    thread_updates = []
    monkeypatch.setattr(service.chat_thread_repo, "complete_chat_thread_generation", lambda **kwargs: thread_updates.append(kwargs) or {"id": "thread_uuid"})
    monkeypatch.setattr(service.generation_job_event_repo, "record_generation_job_event", lambda **kwargs: events.append(kwargs) or {"id": "event_uuid"})

    done = service.mark_generation_job_done(
        "job_db",
        result_payload={"schema_version": "result_artifact_v1", "final_image_path": "data/outputs/job_db/final_0.png"},
        output_path="data/outputs/job_db/final_0.png",
    )

    assert done.status == "done"
    assert assets[0]["storage_provider"] == "local_dev"
    assert done.result_payload.get("final_image_url") is None
    assert done.result_payload.get("download_url") is None
    assert done.metadata["storage_warning"] == "r2_upload_failed_local_dev_fallback"
    assert [event["event_type"] for event in events] == ["r2_upload_started", "r2_upload_failed", "done", "output_created"]
    assert done.result_payload["final_asset_id"] == "asset_local_uuid"
    assert done.result_payload["storage_provider"] == "local_dev"
    assert done.result_payload["bucket"] == "local-dev"
    assert done.result_payload["object_key"] == "data/outputs/job_db/final_0.png"
    assert thread_updates[0]["expected_active_job_id"] == "job_uuid"
    assert thread_updates[0]["final_output_id"] == "output_uuid"

def test_mark_done_r2_failure_required_marks_job_failed(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_ENABLE_R2_UPLOAD", "true")
    monkeypatch.setenv("EASYADS_R2_UPLOAD_REQUIRED", "true")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction)
    events = []
    state = {"row": _base_row()}

    def get_row(job_id, connection=None):
        return state["row"]

    def update_row(job_id, connection=None, **fields):
        state["row"] = {**state["row"], **fields}
        return state["row"]

    def mark_failed(job_id, error, metadata=None, connection=None):
        state["row"] = {
            **state["row"],
            "status": "failed",
            "current_stage": "failed",
            "error": error,
            "metadata": metadata or state["row"]["metadata"],
        }
        return state["row"]

    monkeypatch.setattr(service.generation_job_repo, "get_generation_job_row", get_row)
    monkeypatch.setattr(service.generation_job_repo, "update_generation_job_row", update_row)
    monkeypatch.setattr(service.generation_job_repo, "mark_generation_job_failed_row", mark_failed)
    _patch_mark_done(monkeypatch, state["row"])
    monkeypatch.setattr(service, "upload_file_to_r2", lambda **kwargs: (_ for _ in ()).throw(R2UploadError("R2 upload failed.")))
    monkeypatch.setattr(service.asset_repo, "create_asset", lambda **kwargs: (_ for _ in ()).throw(AssertionError("local asset fallback should not run")))
    monkeypatch.setattr(service.generation_output_repo, "create_generation_output", lambda **kwargs: (_ for _ in ()).throw(AssertionError("output should not be created")))
    monkeypatch.setattr(service.chat_thread_repo, "fail_chat_thread_generation", lambda **kwargs: {"id": "thread_uuid"})
    monkeypatch.setattr(service.generation_job_event_repo, "record_generation_job_event", lambda **kwargs: events.append(kwargs) or {"id": "event_uuid"})

    failed = service.mark_generation_job_done(
        "job_db",
        result_payload={"schema_version": "result_artifact_v1", "final_image_path": "data/outputs/job_db/final_0.png"},
        output_path="data/outputs/job_db/final_0.png",
    )

    assert failed.status == "failed"
    assert failed.error.error_code == "r2_upload_failed"
    assert [event["event_type"] for event in events] == ["r2_upload_started", "r2_upload_failed", "failed"]
