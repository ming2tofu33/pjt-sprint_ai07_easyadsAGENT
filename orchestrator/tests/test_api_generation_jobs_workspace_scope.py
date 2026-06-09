from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app
from orchestrator.app.api.schemas.generation_jobs import GenerationJobResponse, GenerationProgress
from orchestrator.app.generation_jobs.service import reset_generation_job_store_for_tests


def test_generation_job_get_route_passes_workspace_scope(monkeypatch):
    reset_generation_job_store_for_tests()
    captured = {}
    job = GenerationJobResponse(
        job_id="job_scoped",
        thread_id="thread_scoped",
        user_id="user_a",
        status="queued",
        progress=GenerationProgress(progress_percent=0, current_stage="queued", stage_order=[]),
        created_at="2026-06-09T00:00:00+00:00",
        updated_at="2026-06-09T00:00:00+00:00",
        metadata={},
    )

    def fake_get_generation_job(job_id, *, workspace_id=None, user_id=None):
        captured.update({"job_id": job_id, "workspace_id": workspace_id, "user_id": user_id})
        return job if workspace_id == "workspace_a" else None

    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.get_generation_job", fake_get_generation_job)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.maybe_mark_stale_generation_job_failed", lambda job: job)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.maybe_poll_generation_job_from_modal", lambda job: job)

    response = TestClient(create_app()).get("/api/v1/generation-jobs/job_scoped?workspace_id=workspace_a&user_id=user_a")

    assert response.status_code == 200
    assert captured == {"job_id": "job_scoped", "workspace_id": "workspace_a", "user_id": "user_a"}


def test_generation_job_get_route_returns_404_for_cross_workspace(monkeypatch):
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.get_generation_job", lambda job_id, **kwargs: None)

    response = TestClient(create_app()).get("/api/v1/generation-jobs/job_scoped?workspace_id=workspace_b&user_id=user_a")

    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "generation_job_not_found"


def test_generation_job_answer_route_passes_workspace_scope(monkeypatch):
    captured = {}
    job = GenerationJobResponse(
        job_id="job_waiting",
        thread_id="thread_waiting",
        user_id="user_a",
        status="waiting_user_input",
        progress=GenerationProgress(progress_percent=50, current_stage="waiting_user_input", stage_order=[]),
        created_at="2026-06-09T00:00:00+00:00",
        updated_at="2026-06-09T00:00:00+00:00",
        metadata={},
    )

    def fake_get_generation_job(job_id, *, workspace_id=None, user_id=None):
        captured.update({"job_id": job_id, "workspace_id": workspace_id, "user_id": user_id})
        return job

    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.get_generation_job", fake_get_generation_job)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.mark_generation_job_running", lambda job_id, stage="planning": job)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.resume_generation_job_graph", lambda *args, **kwargs: job)

    response = TestClient(create_app()).post(
        "/api/v1/generation-jobs/job_waiting/answer?workspace_id=workspace_a&user_id=user_a",
        json={"field": "business_type", "value": "cafe"},
    )

    assert response.status_code == 200
    assert captured == {"job_id": "job_waiting", "workspace_id": "workspace_a", "user_id": "user_a"}
