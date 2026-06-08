from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app
from orchestrator.app.usage import service


def setup_function():
    service.reset_usage_store_for_tests()


def teardown_function():
    service.reset_usage_store_for_tests()


def test_openapi_registers_usage_summary():
    schema = create_app().openapi()

    assert "/api/v1/usage/summary" in schema["paths"]


def test_usage_summary_api_returns_memory_totals(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    monkeypatch.setattr("orchestrator.app.api.routers.usage.resolve_workspace_scope", lambda workspace_id, user_id: "ws1")
    service.record_llm_usage(
        workspace_id="ws1",
        provider="openai",
        model_name="gpt-4.1-mini",
        input_tokens=10,
        output_tokens=5,
        plan="premium",
    )

    response = TestClient(create_app()).get(
        "/api/v1/usage/summary",
        params={
            "workspaceId": "ws1",
            "plan": "premium",
            "startAt": "2026-01-01T00:00:00Z",
            "endAt": "2027-01-01T00:00:00Z",
        },
    )

    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["scope"] == "workspace"
    assert summary["totals"]["llmCalls"] == 1
    assert summary["totals"]["llmInputTokens"] == 10
    assert summary["totals"]["llmOutputTokens"] == 5
    assert summary["totals"]["unpricedEventCount"] == 1
