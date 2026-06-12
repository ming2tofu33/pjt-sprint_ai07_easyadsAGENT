"""Consolidated r2 storage tests.

Merged from:
- orchestrator/tests/test_r2_client.py
- orchestrator/tests/test_r2_object_keys.py
- orchestrator/tests/test_r2_service.py
- orchestrator/tests/test_r2_storage_settings.py
- orchestrator/tests/test_r2_usage_tracking.py
"""



# ===== from test_r2_client.py =====
import sys
import types

from orchestrator.app.storage import r2_client


def test_create_r2_client_uses_s3v4_signature(monkeypatch):
    captured = {}

    boto3_module = types.ModuleType("boto3")

    def fake_client(service_name, **kwargs):
        captured["service_name"] = service_name
        captured.update(kwargs)
        return object()

    boto3_module.client = fake_client

    botocore_module = types.ModuleType("botocore")
    config_module = types.ModuleType("botocore.config")

    class FakeConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    config_module.Config = FakeConfig

    monkeypatch.setitem(sys.modules, "boto3", boto3_module)
    monkeypatch.setitem(sys.modules, "botocore", botocore_module)
    monkeypatch.setitem(sys.modules, "botocore.config", config_module)

    monkeypatch.setenv("EASYADS_ENABLE_R2_UPLOAD", "true")
    monkeypatch.setenv("EASYADS_R2_BUCKET", "easyads-dev")
    monkeypatch.setenv("EASYADS_R2_ENDPOINT_URL", "https://example.r2.cloudflarestorage.com")
    monkeypatch.setenv("EASYADS_R2_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("EASYADS_R2_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("EASYADS_R2_REGION", "auto")

    client = r2_client.create_r2_client()

    assert client is not None
    assert captured["service_name"] == "s3"
    assert captured["endpoint_url"] == "https://example.r2.cloudflarestorage.com"
    assert captured["config"].kwargs["signature_version"] == "s3v4"


# ===== from test_r2_object_keys.py =====
import pytest

from orchestrator.app.storage.object_keys import build_generation_object_key, safe_object_key_part


def test_build_generation_object_key_uses_expected_convention():
    key = build_generation_object_key(
        workspace_id="workspace_1",
        thread_id="thread_1",
        job_id="job_1",
        filename="final_0.png",
    )

    assert key == "workspaces/workspace_1/threads/thread_1/jobs/job_1/final_0.png"


def test_safe_object_key_part_sanitizes_traversal_and_backslashes():
    assert safe_object_key_part(r"..\unsafe/name.png") == "name.png"
    assert safe_object_key_part(" spaced value ") == "spaced_value"


def test_build_generation_object_key_uses_filename_basename():
    key = build_generation_object_key(
        workspace_id="workspace_1",
        thread_id="thread_1",
        job_id="job_1",
        filename="nested/path/final_0.png",
    )

    assert key.endswith("/final_0.png")


def test_safe_object_key_part_rejects_empty_values():
    with pytest.raises(ValueError):
        safe_object_key_part("..")


# ===== from test_r2_service.py =====
from pathlib import Path

import pytest
from PIL import Image

from orchestrator.app.storage.errors import R2StorageUnavailableError, R2UploadError
from orchestrator.app.storage.r2_service import upload_file_to_r2


class FakeR2Client:
    def __init__(self):
        self.upload_calls = []
        self.presign_calls = []

    def upload_file(self, filename, bucket, object_key, ExtraArgs=None):
        self.upload_calls.append(
            {
                "filename": filename,
                "bucket": bucket,
                "object_key": object_key,
                "extra_args": ExtraArgs,
            }
        )

    def generate_presigned_url(self, operation_name, Params=None, ExpiresIn=None):
        self.presign_calls.append(
            {
                "operation_name": operation_name,
                "params": Params,
                "expires_in": ExpiresIn,
            }
        )
        return f"https://signed.example/{Params['Key']}?expires={ExpiresIn}"


def _configure_signed_env(monkeypatch):
    monkeypatch.setenv("EASYADS_ENABLE_R2_UPLOAD", "true")
    monkeypatch.setenv("EASYADS_R2_BUCKET", "easyads-dev")
    monkeypatch.setenv("EASYADS_R2_ENDPOINT_URL", "https://example.r2.cloudflarestorage.com")
    monkeypatch.setenv("EASYADS_R2_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("EASYADS_R2_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("EASYADS_R2_URL_MODE", "signed")
    monkeypatch.setenv("EASYADS_R2_SIGNED_URL_TTL_SECONDS", "3600")


def _write_png(path: Path):
    Image.new("RGB", (64, 32), color=(255, 0, 0)).save(path)


def test_upload_file_to_r2_returns_signed_urls(tmp_path, monkeypatch):
    _configure_signed_env(monkeypatch)
    image_path = tmp_path / "final_0.png"
    _write_png(image_path)
    client = FakeR2Client()

    uploaded = upload_file_to_r2(
        local_path=image_path,
        object_key="workspaces/ws/threads/th/jobs/job/final_0.png",
        client=client,
    )

    assert client.upload_calls[0]["bucket"] == "easyads-dev"
    assert uploaded.bucket == "easyads-dev"
    assert uploaded.object_key.endswith("final_0.png")
    assert uploaded.final_image_url.startswith("https://signed.example/")
    assert uploaded.download_url == uploaded.final_image_url
    assert uploaded.signed_url_expires_at is not None
    assert uploaded.mime_type == "image/png"
    assert uploaded.width == 64
    assert uploaded.height == 32


def test_upload_file_to_r2_returns_public_url_in_public_mode(tmp_path, monkeypatch):
    _configure_signed_env(monkeypatch)
    monkeypatch.setenv("EASYADS_R2_URL_MODE", "public")
    monkeypatch.setenv("EASYADS_R2_PUBLIC_BASE_URL", "https://cdn.example.com/")
    image_path = tmp_path / "final_0.png"
    _write_png(image_path)
    client = FakeR2Client()

    uploaded = upload_file_to_r2(
        local_path=image_path,
        object_key="workspaces/ws/threads/th/jobs/job/final_0.png",
        client=client,
    )

    assert uploaded.public_url == "https://cdn.example.com/workspaces/ws/threads/th/jobs/job/final_0.png"
    assert uploaded.final_image_url == uploaded.public_url
    assert uploaded.download_url == uploaded.public_url
    assert uploaded.signed_url_expires_at is None


def test_upload_file_to_r2_raises_for_missing_local_file(monkeypatch, tmp_path):
    _configure_signed_env(monkeypatch)

    with pytest.raises(R2UploadError):
        upload_file_to_r2(
            local_path=tmp_path / "missing.png",
            object_key="workspaces/ws/threads/th/jobs/job/final_0.png",
            client=FakeR2Client(),
        )


def test_upload_file_to_r2_raises_when_client_creation_is_unavailable(monkeypatch, tmp_path):
    _configure_signed_env(monkeypatch)
    image_path = tmp_path / "final_0.png"
    _write_png(image_path)
    monkeypatch.setattr(
        "orchestrator.app.storage.r2_service.create_r2_client",
        lambda: (_ for _ in ()).throw(R2StorageUnavailableError("boto3 is unavailable for R2 upload.")),
    )

    with pytest.raises(R2StorageUnavailableError):
        upload_file_to_r2(
            local_path=image_path,
            object_key="workspaces/ws/threads/th/jobs/job/final_0.png",
        )


# ===== from test_r2_storage_settings.py =====
from orchestrator.app.storage import settings


def test_r2_settings_default_to_local_dev(monkeypatch):
    monkeypatch.delenv("EASYADS_ASSET_STORAGE_BACKEND", raising=False)
    monkeypatch.delenv("EASYADS_ENABLE_R2_UPLOAD", raising=False)
    readiness = settings.get_r2_readiness()

    assert settings.get_asset_storage_backend() == "local_dev"
    assert settings.is_r2_upload_enabled() is False
    assert readiness["enabled"] is False
    assert readiness["access_key_id_present"] is False
    assert readiness["secret_access_key_present"] is False


def test_r2_readiness_reports_missing_requirements_without_secret_values(monkeypatch):
    monkeypatch.setenv("EASYADS_ENABLE_R2_UPLOAD", "true")
    monkeypatch.delenv("EASYADS_R2_BUCKET", raising=False)
    monkeypatch.delenv("EASYADS_R2_ENDPOINT_URL", raising=False)
    monkeypatch.setenv("EASYADS_R2_ACCESS_KEY_ID", "key-value")
    monkeypatch.setenv("EASYADS_R2_SECRET_ACCESS_KEY", "secret-value")

    readiness = settings.get_r2_readiness()

    assert readiness["enabled"] is True
    assert "EASYADS_R2_BUCKET" in readiness["missing_requirements"]
    assert "EASYADS_R2_ENDPOINT_URL" in readiness["missing_requirements"]
    assert "key-value" not in str(readiness)
    assert "secret-value" not in str(readiness)


def test_public_url_mode_requires_public_base(monkeypatch):
    monkeypatch.setenv("EASYADS_ENABLE_R2_UPLOAD", "true")
    monkeypatch.setenv("EASYADS_R2_BUCKET", "easyads-dev")
    monkeypatch.setenv("EASYADS_R2_ENDPOINT_URL", "https://example.r2.cloudflarestorage.com")
    monkeypatch.setenv("EASYADS_R2_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("EASYADS_R2_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("EASYADS_R2_URL_MODE", "public")
    monkeypatch.delenv("EASYADS_R2_PUBLIC_BASE_URL", raising=False)

    readiness = settings.get_r2_readiness()

    assert readiness["url_mode"] == "public"
    assert "EASYADS_R2_PUBLIC_BASE_URL" in readiness["missing_requirements"]


def test_signed_url_mode_does_not_require_public_base(monkeypatch):
    monkeypatch.setenv("EASYADS_ENABLE_R2_UPLOAD", "true")
    monkeypatch.setenv("EASYADS_R2_BUCKET", "easyads-dev")
    monkeypatch.setenv("EASYADS_R2_ENDPOINT_URL", "https://example.r2.cloudflarestorage.com")
    monkeypatch.setenv("EASYADS_R2_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("EASYADS_R2_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("EASYADS_R2_URL_MODE", "signed")
    monkeypatch.delenv("EASYADS_R2_PUBLIC_BASE_URL", raising=False)

    readiness = settings.get_r2_readiness()

    assert readiness["url_mode"] == "signed"
    assert "EASYADS_R2_PUBLIC_BASE_URL" not in readiness["missing_requirements"]


# ===== from test_r2_usage_tracking.py =====
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
