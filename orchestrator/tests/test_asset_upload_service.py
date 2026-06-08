import pytest
from shutil import copyfile

from PIL import Image

from orchestrator.app.api.schemas.assets import AssetPresignRequest
from orchestrator.app.assets import service
from orchestrator.app.assets.errors import PayloadTooLargeError, ServiceUnavailableError
from orchestrator.app.storage.errors import R2StorageUnavailableError


ASSET_ID = "asset_" + "a" * 32


def _null_transaction(*args, **kwargs):
    return __import__("contextlib").nullcontext()


def test_presign_success(monkeypatch):
    req = AssetPresignRequest(
        kind="source",
        filename="test.jpg",
        mimeType="image/jpeg",
        sizeBytes=1024,
        workspaceId="ws1",
    )
    monkeypatch.setattr("orchestrator.app.storage.settings.require_r2_ready", lambda: None)
    monkeypatch.setattr("orchestrator.app.storage.settings.get_r2_bucket", lambda: "b")
    monkeypatch.setattr("orchestrator.app.assets.service._resolve_workspace_id", lambda x, **kw: "ws1")
    monkeypatch.setattr("orchestrator.app.db.settings.get_demo_user_id", lambda: "user1")
    monkeypatch.setattr("orchestrator.app.assets.service.db_transaction", _null_transaction)

    class MockRepo:
        def create_asset(self, *args, **kwargs):
            self.created_by = kwargs.get("created_by")
            return {"id": "asset-uuid"}

    repo = MockRepo()
    monkeypatch.setattr("orchestrator.app.assets.service.asset_repo", repo)
    monkeypatch.setattr("orchestrator.app.assets.service.build_upload_object_key", lambda **k: "key")
    monkeypatch.setattr("orchestrator.app.assets.service.create_r2_client", lambda: object())
    monkeypatch.setattr("orchestrator.app.assets.service.create_presigned_put_url", lambda *a, **k: "http://url")

    res = service.presign_asset_upload(req, user_id="trusted-user-1")
    assert res.asset.status == "pending"
    assert res.upload.url == "http://url"
    assert repo.created_by == "trusted-user-1"


def test_presign_falls_back_to_demo_user(monkeypatch):
    req = AssetPresignRequest(
        kind="source",
        filename="test.jpg",
        mimeType="image/jpeg",
        sizeBytes=1024,
        workspaceId="ws1",
    )
    monkeypatch.setattr("orchestrator.app.storage.settings.require_r2_ready", lambda: None)
    monkeypatch.setattr("orchestrator.app.storage.settings.get_r2_bucket", lambda: "b")
    monkeypatch.setattr("orchestrator.app.assets.service._resolve_workspace_id", lambda x, **kw: "ws1")
    monkeypatch.setattr("orchestrator.app.db.settings.get_demo_user_id", lambda: "demo-user")
    monkeypatch.setattr("orchestrator.app.assets.service.db_transaction", _null_transaction)

    class MockRepo:
        def create_asset(self, *args, **kwargs):
            self.created_by = kwargs.get("created_by")
            return {"id": "asset-uuid"}

    repo = MockRepo()
    monkeypatch.setattr("orchestrator.app.assets.service.asset_repo", repo)
    monkeypatch.setattr("orchestrator.app.assets.service.build_upload_object_key", lambda **k: "key")
    monkeypatch.setattr("orchestrator.app.assets.service.create_r2_client", lambda: object())
    monkeypatch.setattr("orchestrator.app.assets.service.create_presigned_put_url", lambda *a, **k: "http://url")

    service.presign_asset_upload(req)
    assert repo.created_by == "demo-user"


def test_presign_client_unavailable_returns_structured_503(monkeypatch):
    req = AssetPresignRequest(
        kind="source",
        filename="test.jpg",
        mimeType="image/jpeg",
        sizeBytes=1024,
        workspaceId="ws1",
    )
    monkeypatch.setattr("orchestrator.app.storage.settings.require_r2_ready", lambda: None)
    monkeypatch.setattr("orchestrator.app.storage.settings.get_r2_bucket", lambda: "b")
    monkeypatch.setattr("orchestrator.app.assets.service._resolve_workspace_id", lambda x, **kw: "ws1")
    monkeypatch.setattr("orchestrator.app.db.settings.get_demo_user_id", lambda: "user1")
    monkeypatch.setattr("orchestrator.app.assets.service.db_transaction", _null_transaction)
    monkeypatch.setattr(
        "orchestrator.app.assets.service.create_r2_client",
        lambda: (_ for _ in ()).throw(R2StorageUnavailableError("credential detail")),
    )

    with pytest.raises(ServiceUnavailableError) as exc:
        service.presign_asset_upload(req)

    assert exc.value.error_code == "asset_storage_unavailable"
    assert "credential detail" not in exc.value.message


def test_presign_oversize(monkeypatch):
    req = AssetPresignRequest(
        kind="source",
        filename="test.jpg",
        mimeType="image/jpeg",
        sizeBytes=999999999,
        workspaceId="ws1",
    )
    monkeypatch.setattr("orchestrator.app.storage.settings.require_r2_ready", lambda: None)
    with pytest.raises(PayloadTooLargeError):
        service.presign_asset_upload(req)


def test_get_asset_no_signed_url_if_not_ready(monkeypatch):
    mock_row = {
        "public_asset_id": ASSET_ID,
        "kind": "source",
        "metadata": {"upload": {"status": "pending"}},
        "storage_provider": "r2",
        "bucket": "b",
        "object_key": "k",
    }
    monkeypatch.setattr("orchestrator.app.assets.service._resolve_workspace_id", lambda x, **kw: "ws1")
    monkeypatch.setattr("orchestrator.app.assets.service.db_transaction", _null_transaction)
    monkeypatch.setattr("orchestrator.app.db.settings.get_demo_user_id", lambda: "user1")

    class MockRepo:
        def get_asset_by_public_id(self, *args, **kwargs):
            return mock_row

    monkeypatch.setattr("orchestrator.app.assets.service.asset_repo", MockRepo())

    res = service.get_asset_response(ASSET_ID, workspace_id="ws1")
    assert res.status == "pending"
    assert res.image_url is None


def test_complete_idempotency(monkeypatch):
    mock_row = {
        "public_asset_id": ASSET_ID,
        "kind": "source",
        "metadata": {"upload": {"status": "ready"}},
        "storage_provider": "r2",
        "bucket": "b",
        "object_key": "k",
        "public_url": "http://existing",
    }
    monkeypatch.setattr("orchestrator.app.assets.service._resolve_workspace_id", lambda x, **kw: "ws1")
    monkeypatch.setattr("orchestrator.app.assets.service.db_transaction", _null_transaction)
    monkeypatch.setattr("orchestrator.app.db.settings.get_demo_user_id", lambda: "user1")

    class MockRepo:
        def get_asset_by_public_id(self, *args, **kwargs):
            return mock_row

    monkeypatch.setattr("orchestrator.app.assets.service.asset_repo", MockRepo())

    res = service.complete_asset_upload(ASSET_ID, workspace_id="ws1")
    assert res.status == "ready"
    assert res.image_url == "http://existing"


def test_ready_signed_url_failure_returns_ready_without_image_url(monkeypatch):
    mock_row = {
        "public_asset_id": ASSET_ID,
        "kind": "source",
        "metadata": {"upload": {"status": "ready"}},
        "storage_provider": "r2",
        "bucket": "b",
        "object_key": "k",
        "public_url": None,
    }
    monkeypatch.setattr("orchestrator.app.assets.service._resolve_workspace_id", lambda x, **kw: "ws1")
    monkeypatch.setattr("orchestrator.app.assets.service.db_transaction", _null_transaction)
    monkeypatch.setattr("orchestrator.app.db.settings.get_demo_user_id", lambda: "user1")

    class MockRepo:
        def get_asset_by_public_id(self, *args, **kwargs):
            return mock_row

    monkeypatch.setattr("orchestrator.app.assets.service.asset_repo", MockRepo())
    monkeypatch.setattr("orchestrator.app.storage.r2_service.create_r2_client", lambda: object())
    monkeypatch.setattr(
        "orchestrator.app.storage.url_policy.resolve_asset_urls",
        lambda **kw: (_ for _ in ()).throw(R2StorageUnavailableError("sign failed")),
    )

    res = service.get_asset_response(ASSET_ID, workspace_id="ws1")
    assert res.status == "ready"
    assert res.image_url is None


def test_complete_asset_upload_success(monkeypatch, tmp_path):
    pending_row = {
        "id": "internal-asset-uuid",
        "public_asset_id": ASSET_ID,
        "workspace_id": "ws1",
        "kind": "source",
        "storage_provider": "r2",
        "bucket": "bucket",
        "object_key": "uploads/source.png",
        "public_url": None,
        "created_at": "2026-06-08T00:00:00+00:00",
        "updated_at": "2026-06-08T00:00:00+00:00",
        "metadata": {
            "upload": {
                "status": "pending",
                "expected_mime_type": "image/png",
            }
        },
    }
    image_path = tmp_path / "source.png"
    Image.new("RGB", (32, 24)).save(image_path, format="PNG")
    size = image_path.stat().st_size
    pending_row["metadata"]["upload"]["expected_size_bytes"] = size
    calls = {"updates": []}

    class MockRepo:
        def get_asset_by_public_id(self, *args, **kwargs):
            assert kwargs.get("created_by") == "trusted-user-1"
            return pending_row

        def update_asset(self, *args, **kwargs):
            calls["updates"].append(kwargs)
            return {
                **pending_row,
                "mime_type": kwargs["mime_type"],
                "size_bytes": kwargs["size_bytes"],
                "width": kwargs["width"],
                "height": kwargs["height"],
                "checksum_sha256": kwargs["checksum_sha256"],
                "public_url": "http://image-url",
                "metadata": {
                    **pending_row["metadata"],
                    **kwargs["metadata_merge"],
                },
            }

    def fake_download(*, target_path, **kwargs):
        copyfile(image_path, target_path)

    monkeypatch.setattr(service, "asset_repo", MockRepo())
    monkeypatch.setattr(service, "_resolve_workspace_id", lambda *a, **k: "ws1")
    monkeypatch.setattr(service, "db_transaction", _null_transaction)
    monkeypatch.setattr(service, "create_r2_client", lambda: object())
    monkeypatch.setattr(
        service,
        "head_object",
        lambda **kwargs: {
            "ContentLength": size,
            "ContentType": "Image/PNG; charset=binary",
        },
    )
    monkeypatch.setattr(service, "download_file_from_r2", fake_download)

    result = service.complete_asset_upload(
        ASSET_ID,
        workspace_id="ws1",
        user_id="trusted-user-1",
    )

    assert result.status == "ready"
    assert result.mime_type == "image/png"
    assert result.width == 32
    assert result.height == 24
    update = calls["updates"][0]
    assert update["pending_only_upload_status"] is True
    assert update["metadata_merge"]["upload"]["status"] == "ready"
    assert update["metadata_merge"]["preprocess"]["mode"] == "exif_transpose_and_decode_validation"
    assert update["metadata_merge"]["preprocess"]["processed_width"] == 32
    assert update["metadata_merge"]["preprocess"]["processed_height"] == 24


def test_complete_client_unavailable_returns_503_without_failed_update(monkeypatch):
    pending_row = {
        "id": "internal-asset-uuid",
        "public_asset_id": ASSET_ID,
        "workspace_id": "ws1",
        "kind": "source",
        "storage_provider": "r2",
        "bucket": "bucket",
        "object_key": "uploads/source.png",
        "metadata": {"upload": {"status": "pending"}},
    }
    calls = {"updates": []}

    class MockRepo:
        def get_asset_by_public_id(self, *args, **kwargs):
            return pending_row

        def update_asset(self, *args, **kwargs):
            calls["updates"].append(kwargs)

    monkeypatch.setattr(service, "asset_repo", MockRepo())
    monkeypatch.setattr(service, "_resolve_workspace_id", lambda *a, **k: "ws1")
    monkeypatch.setattr(service, "db_transaction", _null_transaction)
    monkeypatch.setattr("orchestrator.app.db.settings.get_demo_user_id", lambda: None)
    monkeypatch.setattr(
        service,
        "create_r2_client",
        lambda: (_ for _ in ()).throw(R2StorageUnavailableError("credential detail")),
    )

    with pytest.raises(ServiceUnavailableError) as exc:
        service.complete_asset_upload(ASSET_ID, workspace_id="ws1")

    assert exc.value.error_code == "asset_storage_unavailable"
    assert "credential detail" not in exc.value.message
    assert calls["updates"] == []
