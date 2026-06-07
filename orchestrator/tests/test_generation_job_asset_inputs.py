import pytest
from orchestrator.app.generation_jobs.service import _resolve_generation_input_asset
from orchestrator.app.generation_jobs.errors import (
    GenerationJobAssetKindInvalid,
    GenerationJobAssetNotFound,
    GenerationJobAssetNotReady,
)

def test_resolve_input_asset_not_found(monkeypatch):
    class MockRepo:
        def get_asset_by_public_id(self, *a, **k):
            return None
    monkeypatch.setattr("orchestrator.app.db.repositories.assets.get_asset_by_public_id", MockRepo().get_asset_by_public_id)
    
    with pytest.raises(GenerationJobAssetNotFound):
        _resolve_generation_input_asset(
            public_asset_id="asset_123",
            workspace_id="ws1",
            expected_kind="source",
            connection=None
        )

def test_resolve_input_asset_invalid_kind(monkeypatch):
    class MockRepo:
        def get_asset_by_public_id(self, *a, **k):
            return {"kind": "reference"}
    monkeypatch.setattr("orchestrator.app.db.repositories.assets.get_asset_by_public_id", MockRepo().get_asset_by_public_id)
    
    with pytest.raises(GenerationJobAssetKindInvalid):
        _resolve_generation_input_asset(
            public_asset_id="asset_123",
            workspace_id="ws1",
            expected_kind="source",
            connection=None
        )

def test_resolve_input_asset_not_ready(monkeypatch):
    class MockRepo:
        def get_asset_by_public_id(self, *a, **k):
            return {"kind": "source", "metadata": {"upload": {"status": "pending"}}}
    monkeypatch.setattr("orchestrator.app.db.repositories.assets.get_asset_by_public_id", MockRepo().get_asset_by_public_id)
    
    with pytest.raises(GenerationJobAssetNotReady):
        _resolve_generation_input_asset(
            public_asset_id="asset_123",
            workspace_id="ws1",
            expected_kind="source",
            connection=None
        )

def test_resolve_input_asset_success(monkeypatch):
    class MockRepo:
        def get_asset_by_public_id(self, *a, **k):
            return {"id": "internal-uuid", "kind": "source", "metadata": {"upload": {"status": "ready"}}}
    monkeypatch.setattr("orchestrator.app.db.repositories.assets.get_asset_by_public_id", MockRepo().get_asset_by_public_id)
    
    row = _resolve_generation_input_asset(
        public_asset_id="asset_123",
        workspace_id="ws1",
        expected_kind="source",
        connection=None
    )
    assert row["id"] == "internal-uuid"
