"""Consolidated asset upload tests.

Merged from:
- orchestrator/tests/test_asset_upload_improvements.py
- orchestrator/tests/test_asset_upload_repository.py
- orchestrator/tests/test_asset_upload_service.py
"""



# ===== from test_asset_upload_improvements.py =====
"""Test asset upload improvements."""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from orchestrator.app.assets import service
from orchestrator.app.api.schemas.assets import AssetPresignRequest
from orchestrator.app.assets.errors import (
    AssetWorkspaceRequired,
    UnprocessableEntityError,
    UnsupportedMediaTypeError,
    PayloadTooLargeError,
    ConflictError,
    ServiceUnavailableError,
)
from orchestrator.tests.factories.storage_payloads import make_asset_row

ASSET_ID = "asset_" + "a" * 32

def test_presign_requires_workspace(monkeypatch):
    req = AssetPresignRequest(
        kind="source",
        filename="test.png",
        mimeType="image/png",
        sizeBytes=1024,
    )
    # Should raise AssetWorkspaceRequired in _resolve_workspace_id
    with pytest.raises(AssetWorkspaceRequired):
        service._resolve_workspace_id(req.workspace_id, user_id=None)

def test_presign_validates_mime_type(monkeypatch):
    req = AssetPresignRequest(
        kind="source",
        filename="test.txt",
        mimeType="text/plain",
        sizeBytes=1024,
        workspaceId="ws1"
    )
    monkeypatch.setattr("orchestrator.app.storage.settings.require_r2_ready", lambda: None)

    with pytest.raises(UnprocessableEntityError, match="Unsupported extension"):
        service.presign_asset_upload(req)

    req.filename = "test.png"
    with pytest.raises(UnsupportedMediaTypeError, match="File extension and MIME type do not match"):
        service.presign_asset_upload(req)

def test_complete_records_failed_status(monkeypatch):
    mock_row = make_asset_row(public_asset_id=ASSET_ID)

    class MockRepo:
        def __init__(self):
            self.last_update = None
        def get_asset_by_public_id(self, *args, **kwargs):
            return mock_row
        def update_asset(self, *args, **kwargs):
            self.last_update = kwargs.get("metadata_merge")

    mock_repo = MockRepo()
    monkeypatch.setattr("orchestrator.app.assets.service.asset_repo", mock_repo)
    monkeypatch.setattr("orchestrator.app.assets.service._resolve_workspace_id", lambda x, user_id=None, account_type=None: "ws1")
    monkeypatch.setattr("orchestrator.app.assets.service.db_transaction", lambda *a, **k: __import__("contextlib").nullcontext())

    from orchestrator.app.storage.errors import R2StorageUnavailableError
    def mock_head(*args, **kwargs):
        raise R2StorageUnavailableError("Not found")

    monkeypatch.setattr("orchestrator.app.assets.service.head_object", mock_head)
    monkeypatch.setattr("orchestrator.app.assets.service.create_r2_client", lambda: None)

    # 1. storage unavailable is retryable, should NOT update to failed
    with pytest.raises(ServiceUnavailableError):
        service.complete_asset_upload(ASSET_ID)
    assert mock_repo.last_update is None

    # 2. Mock a terminal error
    def mock_head_terminal(*args, **kwargs):
        return {"ContentLength": 9999999999, "ContentType": "image/png"} # Too large

    monkeypatch.setattr("orchestrator.app.assets.service.head_object", mock_head_terminal)
    monkeypatch.setattr(
        "orchestrator.app.assets.service.get_vision_settings",
        lambda: type("Settings", (), {"max_file_size_mb": 1, "max_pixel_count": 1_000_000})(),
    )

    with pytest.raises(PayloadTooLargeError):
        service.complete_asset_upload(ASSET_ID)

    assert mock_repo.last_update is not None
    assert mock_repo.last_update["upload"]["status"] == "failed"
    assert mock_repo.last_update["upload"]["error_code"] == "asset_too_large"


def test_complete_rejects_invalid_public_asset_id():
    with pytest.raises(UnprocessableEntityError):
        service.complete_asset_upload("asset_123", workspace_id="ws1")


# ===== from test_asset_upload_repository.py =====
import pytest
from unittest.mock import MagicMock
from orchestrator.app.db.repositories import assets as asset_repo

def test_create_asset_conflict(monkeypatch):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = {"id": "123"}

    res1 = asset_repo.create_asset(
        workspace_id="ws1",
        bucket="b",
        object_key="k",
        kind="source",
        connection=mock_conn
    )
    assert res1 is not None
    sql = mock_cursor.execute.call_args[0][0].lower()
    assert "insert into assets" in sql
    assert "returning *" in sql
    assert "on conflict" not in sql

def test_update_asset_with_workspace(monkeypatch):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = {"id": "123", "public_url": "http://new"}

    updated = asset_repo.update_asset(
        "123",
        workspace_id="ws1",
        public_url="http://new",
        connection=mock_conn
    )
    assert updated is not None
    assert "workspace_id = %s" in mock_cursor.execute.call_args[0][0]


def test_update_asset_can_require_pending_upload_status(monkeypatch):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = {"id": "123"}

    asset_repo.update_asset(
        "123",
        workspace_id="ws1",
        metadata_merge={"upload": {"status": "failed"}},
        pending_only_upload_status=True,
        connection=mock_conn,
    )
    sql, params = mock_cursor.execute.call_args.args
    assert "where id = %s and workspace_id = %s" in sql.lower()
    assert "metadata->'upload'->>'status' = 'pending'" in sql
    assert params[-2:] == ("123", "ws1")


# ===== from test_asset_upload_service.py =====
import pytest
from shutil import copyfile

from PIL import Image

from orchestrator.app.api.schemas.assets import AssetPresignRequest
from orchestrator.app.assets import service
from orchestrator.app.assets.errors import PayloadTooLargeError, ServiceUnavailableError
from orchestrator.app.storage.errors import R2StorageUnavailableError


ASSET_ID__test_asset_upload_service = "asset_" + "a" * 32


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
    mock_row = make_asset_row(
        public_asset_id=ASSET_ID__test_asset_upload_service,
        bucket="b",
        object_key="k",
    )
    monkeypatch.setattr("orchestrator.app.assets.service._resolve_workspace_id", lambda x, **kw: "ws1")
    monkeypatch.setattr("orchestrator.app.assets.service.db_transaction", _null_transaction)
    monkeypatch.setattr("orchestrator.app.db.settings.get_demo_user_id", lambda: "user1")

    class MockRepo:
        def get_asset_by_public_id(self, *args, **kwargs):
            return mock_row

    monkeypatch.setattr("orchestrator.app.assets.service.asset_repo", MockRepo())

    res = service.get_asset_response(ASSET_ID__test_asset_upload_service, workspace_id="ws1")
    assert res.status == "pending"
    assert res.image_url is None


def test_complete_idempotency(monkeypatch):
    mock_row = make_asset_row(
        public_asset_id=ASSET_ID__test_asset_upload_service,
        metadata={"upload": {"status": "ready"}},
        bucket="b",
        object_key="k",
        public_url="http://existing",
    )
    monkeypatch.setattr("orchestrator.app.assets.service._resolve_workspace_id", lambda x, **kw: "ws1")
    monkeypatch.setattr("orchestrator.app.assets.service.db_transaction", _null_transaction)
    monkeypatch.setattr("orchestrator.app.db.settings.get_demo_user_id", lambda: "user1")

    class MockRepo:
        def get_asset_by_public_id(self, *args, **kwargs):
            return mock_row

    monkeypatch.setattr("orchestrator.app.assets.service.asset_repo", MockRepo())

    res = service.complete_asset_upload(ASSET_ID__test_asset_upload_service, workspace_id="ws1")
    assert res.status == "ready"
    assert res.image_url == "http://existing"


def test_ready_signed_url_failure_returns_ready_without_image_url(monkeypatch):
    mock_row = {
        "public_asset_id": ASSET_ID__test_asset_upload_service,
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

    res = service.get_asset_response(ASSET_ID__test_asset_upload_service, workspace_id="ws1")
    assert res.status == "ready"
    assert res.image_url is None


def test_complete_asset_upload_success(monkeypatch, tmp_path):
    pending_row = {
        "id": "internal-asset-uuid",
        "public_asset_id": ASSET_ID__test_asset_upload_service,
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
        ASSET_ID__test_asset_upload_service,
        workspace_id="ws1",
        user_id="trusted-user-1",
    )

    assert result.status == "ready"
    assert result.mime_type == "image/png"
    assert result.width == 32
    assert result.height == 24
    public_payload = result.model_dump(by_alias=True)
    assert {"object_key", "bucket", "local_path", "raw_image", "base64"}.isdisjoint(public_payload)
    update = calls["updates"][0]
    assert update["pending_only_upload_status"] is True
    assert update["metadata_merge"]["upload"]["status"] == "ready"
    assert update["metadata_merge"]["preprocess"]["mode"] == "exif_transpose_and_decode_validation"
    assert update["metadata_merge"]["preprocess"]["processed_width"] == 32
    assert update["metadata_merge"]["preprocess"]["processed_height"] == 24


def test_complete_client_unavailable_returns_503_without_failed_update(monkeypatch):
    pending_row = {
        "id": "internal-asset-uuid",
        "public_asset_id": ASSET_ID__test_asset_upload_service,
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
        service.complete_asset_upload(ASSET_ID__test_asset_upload_service, workspace_id="ws1")

    assert exc.value.error_code == "asset_storage_unavailable"
    assert "credential detail" not in exc.value.message
    assert calls["updates"] == []


@pytest.mark.parametrize("head", [None, {}, {"ContentLength": 0, "ContentType": "image/png"}])
def test_validate_upload_head_rejects_missing_or_empty_objects(head):
    with pytest.raises(UnprocessableEntityError) as exc:
        service.validate_upload_head(
            asset={},
            head=head,
            expected_mime_type="image/png",
            expected_size_bytes=None,
        )
    assert exc.value.error_code == "asset_size_mismatch"


def test_validate_upload_head_rejects_size_mismatch():
    with pytest.raises(ConflictError) as exc:
        service.validate_upload_head(
            asset={},
            head={"ContentLength": 20, "ContentType": "image/png"},
            expected_mime_type="image/png",
            expected_size_bytes=10,
        )
    assert exc.value.error_code == "asset_size_mismatch"


def test_decode_image_metadata_accepts_png_without_exposing_path(tmp_path):
    image_path = tmp_path / "private.png"
    Image.new("RGB", (17, 13)).save(image_path, format="PNG")
    metadata = service.decode_image_metadata(local_path=image_path, mime_type="image/png")
    assert metadata["format"] == "PNG"
    assert (metadata["width"], metadata["height"]) == (17, 13)
    assert str(image_path) not in str(metadata)


def test_decode_image_metadata_rejects_invalid_bytes(tmp_path):
    image_path = tmp_path / "private.png"
    image_path.write_bytes(b"not-an-image")
    with pytest.raises(UnprocessableEntityError) as exc:
        service.decode_image_metadata(local_path=image_path, mime_type="image/png")
    assert exc.value.error_code == "invalid_image_asset"


def test_validate_image_constraints_rejects_unsupported_format():
    with pytest.raises(UnprocessableEntityError) as exc:
        service.validate_image_constraints(
            kind="reference",
            mime_type="image/gif",
            size_bytes=100,
            width=10,
            height=10,
            image_format="GIF",
            expected_mime_type="image/gif",
            storage_mime_type="image/gif",
        )
    assert exc.value.error_code == "unsupported_asset_media_type"
