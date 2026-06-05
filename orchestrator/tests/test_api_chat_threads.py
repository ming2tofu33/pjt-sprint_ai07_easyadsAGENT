from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app
from orchestrator.app.chat_threads.service import reset_chat_thread_store_for_tests


@pytest.fixture(autouse=True)
def memory_backend(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    reset_chat_thread_store_for_tests()
    yield
    reset_chat_thread_store_for_tests()


def test_chat_thread_api_create_append_list_flow():
    client = TestClient(create_app())

    created = client.post("/api/v1/chat-threads", json={"userId": "user_a", "title": "Campaign"}).json()
    thread_id = created["thread"]["thread_id"]

    msg = client.post(
        f"/api/v1/chat-threads/{thread_id}/messages?userId=user_a",
        json={"role": "user", "content": "hello", "payload": {"apiKey": "sk-secret", "safe": "visible"}},
    )
    listed = client.get(f"/api/v1/chat-threads/{thread_id}/messages?userId=user_a")

    assert msg.status_code == 201
    assert msg.json()["message"]["payload"] == {"safe": "visible"}
    assert listed.json()["total"] == 1


def test_chat_thread_api_owner_scope_returns_not_found():
    client = TestClient(create_app())

    created = client.post("/api/v1/chat-threads", json={"userId": "user_a", "title": "Campaign"}).json()
    response = client.get(f"/api/v1/chat-threads/{created['thread']['thread_id']}?userId=user_b")

    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "chat_thread_not_found"


def test_generation_job_rejects_invalid_thread_id_prefix():
    client = TestClient(create_app())

    response = client.post("/api/v1/generation-jobs", json={"userInput": "Create ad", "threadId": "bad"})

    assert response.status_code == 400
    assert response.json()["error_code"] == "invalid_generation_job_request"
