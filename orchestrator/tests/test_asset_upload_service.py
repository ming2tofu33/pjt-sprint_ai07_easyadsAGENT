import pytest
from datetime import datetime, timezone
from orchestrator.app.assets import service
from orchestrator.app.api.schemas.assets import AssetPresignRequest
from orchestrator.app.assets.errors import (
    UnprocessableEntityError,
    UnsupportedMediaTypeError,
    PayloadTooLargeError,
    ConflictError,
    AssetServiceError,
)

ASSET_ID = "asset_" + "a" * 32

def test_presign_success(monkeypatch):
    req = AssetPresignRequest(
        kind="source",
        filename="test.jpg",
        mimeType="image/jpeg",
        sizeBytes=1024,
        workspaceId="ws1"
    )
    monkeypatch.setattr("orchestrator.app.storage.settings.require_r2_ready", lambda: None)
    monkeypatch.setattr("orchestrator.app.storage.settings.get_r2_bucket", lambda: "b")
    monkeypatch.setattr("orchestrator.app.assets.service._resolve_workspace_id", lambda x, **kw: "ws1")
    monkeypatch.setattr("orchestrator.app.db.settings.get_demo_user_id", lambda: "user1")
    monkeypatch.setattr("orchestrator.app.assets.service.db_transaction", lambda *a, **kw: __import__("contextlib").nullcontext())
    
    class MockRepo:
        def create_asset(self, *args, **kwargs):
            self.created_by = kwargs.get("created_by")
            return {"id": "asset-uuid"}
    
    repo = MockRepo()
    monkeypatch.setattr("orchestrator.app.assets.service.asset_repo", repo)
    monkeypatch.setattr("orchestrator.app.assets.service.build_upload_object_key", lambda **k: "key")
    monkeypatch.setattr("orchestrator.app.assets.service.create_r2_client", lambda: None)
    monkeypatch.setattr("orchestrator.app.assets.service.create_presigned_put_url", lambda *a, **k: "http://url")
    
    res = service.presign_asset_upload(req)
    assert res.asset.status == "pending"
    assert res.upload.url == "http://url"
    assert repo.created_by is not None

def test_presign_oversize(monkeypatch):
    req = AssetPresignRequest(
        kind="source",
        filename="test.jpg",
        mimeType="image/jpeg",
        sizeBytes=999999999,
        workspaceId="ws1"
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
        "object_key": "k"
    }
    monkeypatch.setattr("orchestrator.app.assets.service._resolve_workspace_id", lambda x, **kw: "ws1")
    monkeypatch.setattr("orchestrator.app.assets.service.db_transaction", lambda *a, **kw: __import__("contextlib").nullcontext())
    
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
        "public_url": "http://existing"
    }
    monkeypatch.setattr("orchestrator.app.assets.service._resolve_workspace_id", lambda x, **kw: "ws1")
    monkeypatch.setattr("orchestrator.app.assets.service.db_transaction", lambda *a, **kw: __import__("contextlib").nullcontext())
    
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
    monkeypatch.setattr("orchestrator.app.assets.service.db_transaction", lambda *a, **kw: __import__("contextlib").nullcontext())

    class MockRepo:
        def get_asset_by_public_id(self, *args, **kwargs):
            return mock_row
    monkeypatch.setattr("orchestrator.app.assets.service.asset_repo", MockRepo())
    monkeypatch.setattr("orchestrator.app.storage.r2_service.create_r2_client", lambda: object())
    monkeypatch.setattr("orchestrator.app.storage.url_policy.resolve_asset_urls", lambda **kw: (_ for _ in ()).throw(RuntimeError("sign failed")))

    res = service.get_asset_response(ASSET_ID, workspace_id="ws1")
    assert res.status == "ready"
    assert res.image_url is None
