import pytest
from orchestrator.app.vision.nodes import _resolve_asset_to_local_file

def test_resolve_and_download_asset_not_found(monkeypatch):
    class MockRepo:
        def get_asset_by_public_id(self, *a, **k):
            return None
    monkeypatch.setattr("orchestrator.app.db.repositories.assets.get_asset_by_public_id", MockRepo().get_asset_by_public_id)
    
    state = {
        "workspace_id": "ws1",
        "source_asset_id": "asset_123"
    }
    
    with pytest.raises(ValueError, match="Asset not found"):
        _resolve_asset_to_local_file(
            state=state,
            asset_key="source_asset_id",
            image_key="source_image_path"
        )

def test_resolve_and_download_asset_success(monkeypatch):
    mock_row = {
        "id": "internal-uuid",
        "kind": "source",
        "metadata": {"upload": {"status": "ready"}},
        "bucket": "b",
        "object_key": "k",
        "storage_provider": "r2",
        "public_asset_id": "asset_123"
    }
    class MockRepo:
        def get_asset_by_public_id(self, *a, **k):
            return mock_row
    monkeypatch.setattr("orchestrator.app.db.repositories.assets.get_asset_by_public_id", MockRepo().get_asset_by_public_id)
    monkeypatch.setattr("orchestrator.app.storage.r2_service.download_file_from_r2", lambda **k: None)
    
    state = {
        "workspace_id": "ws1",
        "source_asset_id": "asset_123",
        "job_id": "job_123"
    }
    
    local_path = _resolve_asset_to_local_file(
        state=state,
        asset_key="source_asset_id",
        image_key="source_image_path"
    )
    assert local_path is not None
