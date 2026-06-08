from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app


def test_validation_detail_api_returns_public_contract(monkeypatch):
    monkeypatch.setattr("orchestrator.app.api.routers.validation_feedback.resolve_workspace_scope", lambda workspace_id, user_id=None: "ws")
    monkeypatch.setattr(
        "orchestrator.app.api.routers.validation_feedback.get_latest_validation_for_output",
        lambda **kwargs: {
            "reportId": "validation_1",
            "outputId": "output_1",
            "jobId": "job_1",
            "status": "fail",
            "decision": "retry_image",
            "failureTypes": ["fake_text"],
            "suggestedActions": [{"code": "remove_fake_text", "scope": "image", "priority": 90, "reason": "remove text", "parameters": {}}],
            "retryRecommended": True,
            "requiresManualReview": False,
            "schemaVersion": "validation_feedback_v1",
            "createdAt": "2026-06-08T00:00:00Z",
        },
    )

    response = TestClient(create_app()).get("/api/v1/generation-outputs/output_1/validation?workspace_id=ws")

    assert response.status_code == 200
    body = response.json()
    assert body["validation"]["reportId"] == "validation_1"
    assert "object_key" not in str(body)

