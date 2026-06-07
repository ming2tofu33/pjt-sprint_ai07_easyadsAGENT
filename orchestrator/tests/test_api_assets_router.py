import pytest
from fastapi.testclient import TestClient
from orchestrator.app.main import app

client = TestClient(app)

VALID_ASSET_ID = "asset_" + "a" * 32

def test_presign_asset_api(monkeypatch):
    monkeypatch.setattr("orchestrator.app.storage.settings.require_r2_ready", lambda: None)
    monkeypatch.setattr("orchestrator.app.storage.settings.get_r2_bucket", lambda: "b")
    monkeypatch.setattr("orchestrator.app.assets.service._resolve_workspace_id", lambda x, **kw: "ws1")
    monkeypatch.setattr("orchestrator.app.db.settings.get_demo_user_id", lambda: "user1")
    monkeypatch.setattr("orchestrator.app.assets.service.db_transaction", lambda *a, **kw: __import__("contextlib").nullcontext())
    
    class MockRepo:
        def create_asset(self, *args, **kwargs):
            return {"id": "asset-uuid"}
            
    monkeypatch.setattr("orchestrator.app.assets.service.asset_repo", MockRepo())
    monkeypatch.setattr("orchestrator.app.assets.service.build_upload_object_key", lambda **k: "key")
    monkeypatch.setattr("orchestrator.app.assets.service.create_r2_client", lambda: None)
    monkeypatch.setattr("orchestrator.app.assets.service.create_presigned_put_url", lambda *a, **k: "http://url")

    resp = client.post(
        "/api/v1/assets/uploads/presign",
        params={"user_id": "user1"},
        json={
            "kind": "source",
            "filename": "test.jpg",
            "mimeType": "image/jpeg",
            "sizeBytes": 1024,
            "workspaceId": "ws1"
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["asset"]["status"] == "pending"
    assert data["upload"]["url"] == "http://url"

def test_complete_asset_api(monkeypatch):
    mock_row = {
        "id": "internal-uuid",
        "public_asset_id": VALID_ASSET_ID,
        "kind": "source",
        "metadata": {"upload": {"status": "pending"}},
        "bucket": "test-bucket",
        "object_key": "test-key"
    }
    
    class MockRepo:
        def get_asset_by_public_id(self, *args, **kwargs):
            return mock_row
        def update_asset(self, *args, **kwargs):
            mock_row["metadata"] = kwargs.get("metadata_merge")
            mock_row["public_url"] = kwargs.get("public_url")
            return mock_row
            
    monkeypatch.setattr("orchestrator.app.assets.service.asset_repo", MockRepo())
    monkeypatch.setattr("orchestrator.app.assets.service._resolve_workspace_id", lambda x, **kw: "ws1")
    monkeypatch.setattr("orchestrator.app.assets.service.db_transaction", lambda: __import__("contextlib").nullcontext())
    monkeypatch.setattr("orchestrator.app.assets.service.create_r2_client", lambda: None)
    
    from orchestrator.app.storage.errors import R2StorageUnavailableError
    def mock_head(*args, **kwargs):
        raise R2StorageUnavailableError("Not found")
        
    monkeypatch.setattr("orchestrator.app.assets.service.head_object", mock_head)
    
    resp = client.post(f"/api/v1/assets/uploads/{VALID_ASSET_ID}/complete", params={"workspace_id": "ws1", "user_id": "user1"})
    assert resp.status_code == 409
    assert "File not found" in resp.json()["detail"]["message"]

def test_get_asset_api(monkeypatch):
    mock_row = {
        "public_asset_id": VALID_ASSET_ID,
        "kind": "source",
        "metadata": {"upload": {"status": "ready"}},
        "storage_provider": "r2",
        "bucket": "b",
        "object_key": "k",
        "public_url": "http://image-url"
    }
    monkeypatch.setattr("orchestrator.app.assets.service._resolve_workspace_id", lambda x, **kw: "ws1")
    monkeypatch.setattr("orchestrator.app.assets.service.db_transaction", lambda *a, **kw: __import__("contextlib").nullcontext())
    
    class MockRepo:
        def get_asset_by_public_id(self, *args, **kwargs):
            return mock_row
    monkeypatch.setattr("orchestrator.app.assets.service.asset_repo", MockRepo())
    
    resp = client.get(f"/api/v1/assets/{VALID_ASSET_ID}", params={"workspace_id": "ws1", "user_id": "user1"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["asset"]["status"] == "ready"
    assert data["asset"]["imageUrl"] == "http://image-url"
