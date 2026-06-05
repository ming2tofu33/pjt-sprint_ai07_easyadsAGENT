import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from orchestrator.app.api.app import create_app

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)

def test_list_generation_outputs(client, monkeypatch):
    mock_service = MagicMock()
    mock_service.return_value = ([], 0)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_outputs.list_generation_outputs", mock_service)
    
    mock_scope = MagicMock()
    mock_scope.return_value = "ws1"
    monkeypatch.setattr("orchestrator.app.db.workspace_scope.resolve_workspace_scope", mock_scope)
    
    resp = client.get("/api/v1/generation-outputs?workspace_id=ws1")
    assert resp.status_code == 200
    assert resp.json()["items"] == []

def test_select_final_generation_output(client, monkeypatch):
    mock_service = MagicMock()
    
    from orchestrator.app.api.schemas.generation_outputs import GenerationOutputResponse
    
    mock_service.return_value = GenerationOutputResponse(
        output_id="out1", is_final=True, variant_index=0, output_type="final_image", created_at="2026-06-06T00:00:00Z", updated_at="2026-06-06T00:00:00Z"
    )
    monkeypatch.setattr("orchestrator.app.api.routers.generation_outputs.select_final_generation_output", mock_service)
    
    mock_scope = MagicMock()
    mock_scope.return_value = "ws1"
    monkeypatch.setattr("orchestrator.app.db.workspace_scope.resolve_workspace_scope", mock_scope)
    
    resp = client.post("/api/v1/generation-outputs/out1/select-final?workspace_id=ws1")
    assert resp.status_code == 200
    assert resp.json()["output_id"] == "out1"
