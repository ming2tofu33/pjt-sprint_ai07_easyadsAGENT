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
