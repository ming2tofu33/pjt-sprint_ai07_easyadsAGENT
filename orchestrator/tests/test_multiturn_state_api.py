from fastapi.testclient import TestClient
from orchestrator.app.main import app
import pytest

@pytest.fixture
def client():
    return TestClient(app)

def test_get_chat_thread_state_not_found(client):
    response = client.get("/api/v1/chat-threads/non_existent_thread_for_state/state")
    assert response.status_code == 404

def test_get_chat_thread_state_success(client, monkeypatch):
    from orchestrator.app.chat_threads import service as chat_service
    from orchestrator.app.chat_threads import state_service
    from orchestrator.app.api.schemas.chat_threads import ChatThreadGetResponse
    from orchestrator.app.schemas.chat_state_snapshots import ChatStateSnapshotResponse

    monkeypatch.setattr(chat_service, "get_chat_thread", lambda *args, **kwargs: {"thread_id": "thread_1", "public_thread_id": "thread_1"})
    monkeypatch.setattr(chat_service, "_use_postgres", lambda: False)
    
    mock_snapshot = ChatStateSnapshotResponse(
        snapshot_id="snap_1",
        thread_id="thread_1",
        snapshot_version=1,
        schema_version=1,
        snapshot_kind="input",
        state_payload={"test": "payload"},
        changed_fields=[],
        created_at="2026-06-05T00:00:00Z",
        job_id="job",
        source_message_id="msg",
        parent_snapshot_id="snap",
        selected_reference_template_id="ref",
        reference_template_snapshot={},
        brand_kit_snapshot={},
        metadata={},
        snapshot_key="key"
    )
    
    monkeypatch.setattr(state_service, "get_latest_thread_state_snapshot", lambda *args, **kwargs: mock_snapshot)
    
    response = client.get("/api/v1/chat-threads/thread_1/state")
    assert response.status_code == 200
    assert response.json()["snapshot"]["snapshot_id"] == "snap_1"
    assert response.json()["snapshot"]["state_payload"]["test"] == "payload"
