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

def test_create_generation_job_db_asset_integration(monkeypatch):
    from orchestrator.app.generation_jobs.service import _create_generation_job_db
    from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest
    import uuid
    
    req = GenerationJobCreateRequest(
        source_asset_id="asset_" + "a"*32,
        reference_asset_id="asset_" + "b"*32,
        user_input="Test",
        workspace_id="ws1",
    )
    
    def fake_resolve(*, public_asset_id, expected_kind, **kwargs):
        if expected_kind == "source":
            return {"id": "int-src"}
        return {"id": "int-ref"}
        
    monkeypatch.setattr("orchestrator.app.generation_jobs.service._resolve_generation_input_asset", fake_resolve)
    
    class MockJobRepo:
        def create_generation_job_row(self, **kwargs):
            self.kwargs = kwargs
            return {
                "id": uuid.uuid4(),
                "public_job_id": "job_123",
                "status": "queued",
                "request_payload": kwargs.get("request_payload")
            }
    mock_repo = MockJobRepo()
    monkeypatch.setattr("orchestrator.app.generation_jobs.service.generation_job_repo", mock_repo)
    monkeypatch.setattr("orchestrator.app.generation_jobs.service.db_transaction", lambda: __import__("contextlib").nullcontext())
    monkeypatch.setattr("orchestrator.app.db.settings.get_demo_user_id", lambda: "demo")
    monkeypatch.setattr("orchestrator.app.db.settings.get_db_backend", lambda: "postgres")
    monkeypatch.setattr("orchestrator.app.generation_jobs.service.workspace_repo", type("W", (), {"get_workspace": lambda *a, **k: {"id": "ws1", "owner_user_id": None}})())
    monkeypatch.setattr("orchestrator.app.generation_jobs.service.chat_thread_repo", type("T", (), {"get_chat_thread_by_public_id": lambda *a, **k: {"id": "t1"}, "create_chat_thread": lambda *a, **k: {"id": "t1"}, "set_chat_thread_active_job": lambda *a, **k: True})())
    monkeypatch.setattr("orchestrator.app.generation_jobs.service.chat_message_repo", type("M", (), {"append_chat_message": lambda *a, **k: {"id": "m1"}, "append_generation_job_chat_event": lambda *a, **k: {"id": "m2"}})())
    monkeypatch.setattr("orchestrator.app.generation_jobs.service.state_service", type("S", (), {"save_thread_state_snapshot": lambda *a, **k: None, "get_latest_thread_state_snapshot": lambda *a, **k: None, "restore_thread_state": lambda *a, **k: {}})())

    _create_generation_job_db(req)

    assert mock_repo.kwargs["input_asset_id"] == "int-src"
    assert mock_repo.kwargs["reference_asset_id"] == "int-ref"
    assert mock_repo.kwargs["request_payload"]["source_asset_id"] == req.source_asset_id
    assert mock_repo.kwargs["request_payload"]["reference_asset_id"] == req.reference_asset_id
