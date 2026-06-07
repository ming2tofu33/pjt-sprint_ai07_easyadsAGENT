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
    mock_row = {
        "id": "internal-uuid",
        "public_asset_id": "asset_123",
        "metadata": {"upload": {"status": "pending"}},
        "bucket": "test-bucket",
        "object_key": "test-key"
    }
    
    class MockRepo:
        def __init__(self):
            self.last_update = None
        def get_asset_by_public_id(self, *args, **kwargs):
            return mock_row
        def update_asset(self, *args, **kwargs):
            self.last_update = kwargs.get("metadata_merge")
            
    mock_repo = MockRepo()
    monkeypatch.setattr("orchestrator.app.assets.service.asset_repo", mock_repo)
    monkeypatch.setattr("orchestrator.app.assets.service._resolve_workspace_id", lambda x, user_id: "ws1")
    monkeypatch.setattr("orchestrator.app.assets.service.db_transaction", lambda *a, **k: __import__("contextlib").nullcontext())
    
    from orchestrator.app.storage.errors import R2StorageUnavailableError
    def mock_head(*args, **kwargs):
        raise R2StorageUnavailableError("Not found")
        
    monkeypatch.setattr("orchestrator.app.assets.service.head_object", mock_head)
    monkeypatch.setattr("orchestrator.app.assets.service.create_r2_client", lambda: None)
    
    # 1. file_not_found is retryable, should NOT update to failed
    with pytest.raises(ConflictError):
        service.complete_asset_upload("asset_123")
    assert mock_repo.last_update is None
    
    # 2. Mock a terminal error
    def mock_head_terminal(*args, **kwargs):
        return {"ContentLength": 9999999999, "ContentType": "image/png"} # Too large
        
    monkeypatch.setattr("orchestrator.app.assets.service.head_object", mock_head_terminal)
    monkeypatch.setattr("orchestrator.app.vision.settings.get_vision_settings", lambda: type("Settings", (), {"max_file_size_mb": 1})())
    
    with pytest.raises(PayloadTooLargeError):
        service.complete_asset_upload("asset_123")
        
    assert mock_repo.last_update is not None
    assert mock_repo.last_update["upload"]["status"] == "failed"
    assert mock_repo.last_update["upload"]["error_code"] == "asset_too_large"
