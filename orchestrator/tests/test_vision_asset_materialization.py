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
    def fake_download(*args, **kwargs):
        from pathlib import Path
        target = kwargs.get('target_path') or kwargs.get('local_path')
        Path(target).write_bytes(b"fake")
        
    monkeypatch.setattr("orchestrator.app.storage.r2_service.download_file_from_r2", fake_download)

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
    assert "downloaded.k" in local_path or "asset_123" in local_path or local_path.endswith(".k") or local_path.endswith(".tmp") or "source_asset_id" in local_path
    from pathlib import Path
    assert Path(local_path).exists()
