from orchestrator.app.generation_jobs import service as generation_service
from orchestrator.app.assets import service as asset_service


def test_generation_job_r2_upload_records_usage(monkeypatch):
    calls = []
    row = {
        "id": "job_uuid",
        "public_job_id": "job_public",
        "workspace_id": "ws_uuid",
        "thread_id": "thread_uuid",
        "requested_by": "user1",
        "metadata": {"user_plan": "premium", "public_thread_id": "thread_public"},
    }

    monkeypatch.setattr(generation_service.usage_service, "record_r2_upload_usage", lambda **kwargs: calls.append(kwargs))

    generation_service._record_r2_usage_for_uploaded_asset(
        row=row,
        uploaded_size_bytes=2048,
        asset_id="asset_uuid",
        connection=object(),
    )

    assert calls[0]["workspace_id"] == "ws_uuid"
    assert calls[0]["quantity"] == 2048
    assert calls[0]["provider"] == "cloudflare_r2"
    assert calls[0]["idempotency_key"] == "r2_upload:job_public:asset_uuid"
    assert "bucket" not in calls[0]["metadata"]
    assert "object_key" not in calls[0]["metadata"]


def test_asset_upload_complete_records_r2_usage(monkeypatch):
    calls = []
    row = {
        "id": "asset_uuid",
        "public_asset_id": "asset_public",
        "workspace_id": "ws_uuid",
        "thread_id": "thread_uuid",
        "created_by": "user1",
        "kind": "source",
        "storage_provider": "r2",
        "mime_type": "image/png",
        "width": 40,
        "height": 30,
    }
    monkeypatch.setattr(asset_service.usage_service, "record_r2_upload_usage", lambda **kwargs: calls.append(kwargs))

    asset_service._record_r2_upload_usage_for_asset(
        row,
        512,
        "checksum",
        connection=object(),
    )

    assert calls[0]["workspace_id"] == "ws_uuid"
    assert calls[0]["quantity"] == 512
    assert calls[0]["provider"] == "cloudflare_r2"
    assert calls[0]["idempotency_key"] == "r2_upload:asset_public:checksum"
    assert "bucket" not in calls[0]["metadata"]
    assert "object_key" not in calls[0]["metadata"]


def test_r2_usage_failure_does_not_rollback_asset_ready(monkeypatch):
    row = {"id": "asset_uuid", "workspace_id": "ws_uuid", "kind": "source", "storage_provider": "r2"}
    monkeypatch.setattr(asset_service.usage_service, "record_r2_upload_usage", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    asset_service._record_r2_upload_usage_for_asset(row, 512, "checksum", connection=None)


def test_r2_usage_failure_does_not_rollback_generation_output(monkeypatch):
    payload = {"workspace_id": "ws_uuid", "quantity": 512, "provider": "cloudflare_r2"}
    monkeypatch.setattr(generation_service.usage_service, "record_r2_upload_usage", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    generation_service._safe_record_r2_usage(payload)
