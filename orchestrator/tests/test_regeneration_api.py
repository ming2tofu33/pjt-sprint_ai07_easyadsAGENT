from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app


def test_regeneration_api_returns_accepted_job(monkeypatch):
    monkeypatch.setattr("orchestrator.app.api.routers.validation_feedback.resolve_workspace_scope", lambda workspace_id, user_id=None: "ws")
    monkeypatch.setattr(
        "orchestrator.app.api.routers.validation_feedback.regenerate_output",
        lambda **kwargs: (
            202,
            {
                "jobId": "job_new",
                "threadId": "thread_1",
                "parentJobId": "job_old",
                "previousOutputId": "output_old",
                "depth": 1,
                "status": "queued",
                "appliedActions": ["remove_fake_text"],
                "idempotentReplay": False,
            },
        ),
    )

    response = TestClient(create_app()).post(
        "/api/v1/generation-outputs/output_old/regenerate?workspace_id=ws",
        json={"suggestedActions": ["remove_fake_text"], "scope": "image", "idempotencyKey": "idem-123456"},
    )

    assert response.status_code == 202
    assert response.json()["regeneration"]["jobId"] == "job_new"


def test_regeneration_api_dispatches_created_graph_job(monkeypatch):
    calls = []
    monkeypatch.setattr("orchestrator.app.api.routers.validation_feedback.resolve_workspace_scope", lambda workspace_id, user_id=None: "ws")
    monkeypatch.setattr(
        "orchestrator.app.api.routers.validation_feedback.regenerate_output",
        lambda **kwargs: (
            202,
            {
                "jobId": "job_new",
                "threadId": "thread_1",
                "parentJobId": "job_old",
                "previousOutputId": "output_old",
                "depth": 1,
                "status": "queued",
                "appliedActions": ["remove_fake_text"],
                "idempotentReplay": False,
                "_dispatch": {
                    "jobId": "job_new",
                    "runMode": "graph_job",
                    "request": {"userInput": "regenerate", "threadId": "thread_1", "runMode": "graph_job", "metadata": {"regeneration_patch": {"scope": "image", "patches": {}}}},
                },
            },
        ),
    )
    monkeypatch.setattr(
        "orchestrator.app.api.routers.validation_feedback.execute_generation_job_graph",
        lambda job_id, request: calls.append((job_id, request.run_mode, request.metadata)),
    )

    response = TestClient(create_app()).post(
        "/api/v1/generation-outputs/output_old/regenerate?workspace_id=ws",
        json={"suggestedActions": ["remove_fake_text"], "idempotencyKey": "idem-123456"},
    )

    assert response.status_code == 202
    assert calls == [("job_new", "graph_job", {"regeneration_patch": {"scope": "image", "patches": {}}})]
    assert "_dispatch" not in str(response.json())


def test_regeneration_api_dispatches_gpt_image_1_job(monkeypatch):
    calls = []
    monkeypatch.setattr("orchestrator.app.api.routers.validation_feedback.resolve_workspace_scope", lambda workspace_id, user_id=None: "ws")
    monkeypatch.setattr(
        "orchestrator.app.api.routers.validation_feedback.regenerate_output",
        lambda **kwargs: (
            202,
            {
                "jobId": "job_gpt1",
                "threadId": "thread_1",
                "parentJobId": "job_old",
                "previousOutputId": "output_old",
                "depth": 1,
                "status": "queued",
                "appliedActions": ["remove_fake_text"],
                "idempotentReplay": False,
                "_dispatch": {
                    "jobId": "job_gpt1",
                    "runMode": "gpt_image_1_actual",
                    "request": {
                        "userInput": "regenerate",
                        "threadId": "thread_1",
                        "runMode": "gpt_image_1_actual",
                        "metadata": {"regeneration_patch": {"scope": "image", "patches": {}}},
                    },
                },
            },
        ),
    )
    monkeypatch.setattr(
        "orchestrator.app.api.routers.validation_feedback.execute_generation_job_t2i",
        lambda job_id, request, engine_name: calls.append((job_id, request.run_mode, engine_name, request.metadata)),
    )

    response = TestClient(create_app()).post(
        "/api/v1/generation-outputs/output_old/regenerate?workspace_id=ws",
        json={"suggestedActions": ["remove_fake_text"], "idempotencyKey": "idem-gpt1"},
    )

    assert response.status_code == 202
    assert calls == [("job_gpt1", "gpt_image_1_actual", "gpt_image_1", {"regeneration_patch": {"scope": "image", "patches": {}}})]
    assert "_dispatch" not in str(response.json())
