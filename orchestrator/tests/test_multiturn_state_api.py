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
    from orchestrator.app.api.schemas.chat_threads import ChatThreadResponse
    from orchestrator.app.schemas.chat_state_snapshots import ChatStateSnapshotResponse

    captured = {}
    thread = ChatThreadResponse(
        thread_id="thread_1",
        title="카페 광고",
        status="generating",
        final_brief={},
        active_job_id=None,
        has_final_output=False,
        last_message_at="2026-06-06T00:00:00+00:00",
        created_at="2026-06-06T00:00:00+00:00",
        updated_at="2026-06-06T00:00:00+00:00",
    )
    mock_snapshot = ChatStateSnapshotResponse(
        snapshot_id="snap_1",
        thread_id="thread_1",
        job_id="job_1",
        snapshot_version=1,
        schema_version=1,
        snapshot_kind="input",
        state_payload={"test": "payload"},
        changed_fields=[],
        created_at="2026-06-06T00:00:00+00:00",
    )

    monkeypatch.setattr(chat_service, "get_chat_thread_with_workspace", lambda thread_id, user_id=None: (thread, "workspace_actual"))

    def fake_get_latest_thread_state_snapshot(**kwargs):
        captured.update(kwargs)
        return mock_snapshot

    monkeypatch.setattr(state_service, "get_latest_thread_state_snapshot", fake_get_latest_thread_state_snapshot)

    response = client.get("/api/v1/chat-threads/thread_1/state")

    assert response.status_code == 200
    assert response.json()["snapshot"]["snapshot_id"] == "snap_1"
    assert response.json()["snapshot"]["state_payload"]["test"] == "payload"
    assert captured["public_thread_id"] == "thread_1"
    assert captured["workspace_id"] == "workspace_actual"
