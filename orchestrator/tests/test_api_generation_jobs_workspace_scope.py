from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app
from orchestrator.app.api.schemas.generation_jobs import GenerationJobResponse, GenerationProgress
from orchestrator.app.generation_jobs.service import reset_generation_job_store_for_tests


WORKSPACE_A = "11111111-1111-1111-1111-111111111111"
WORKSPACE_B = "22222222-2222-2222-2222-222222222222"


def test_generation_job_get_route_rejects_missing_scope(monkeypatch):
    response = TestClient(create_app()).get("/api/v1/generation-jobs/job_scoped")

    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "workspace_required"


def test_generation_job_get_route_does_not_trust_query_user_id(monkeypatch):
    captured = {}

    def fake_get_generation_job(job_id, *, workspace_id=None, user_id=None):
        captured.update({"workspace_id": workspace_id, "user_id": user_id})
        return None

    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.get_generation_job_scoped", fake_get_generation_job)

    response = TestClient(create_app()).get(
        f"/api/v1/generation-jobs/job_scoped?workspace_id={WORKSPACE_A}&user_id=user_a"
    )

    assert response.status_code == 404
    assert captured == {"workspace_id": WORKSPACE_A, "user_id": None}


def test_generation_job_get_route_recovers_scope_from_existing_job_without_header(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_ALLOW_DEMO_WORKSPACE_FALLBACK", "false")
    captured = {}
    stale_scope = {}
    modal_scope = {}
    job = GenerationJobResponse(
        job_id="job_polling",
        thread_id="thread_polling",
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

    def fake_mark_stale(current_job, **kwargs):
        stale_scope.update(kwargs)
        return current_job

    def fake_poll_modal(current_job, **kwargs):
        modal_scope.update(kwargs)
        return current_job

    monkeypatch.setattr(
        "orchestrator.app.api.routers.generation_jobs.resolve_generation_job_scope_from_existing_job",
        lambda job_id: (WORKSPACE_A, "user_a"),
    )
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.get_generation_job_scoped", fake_get_generation_job)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.maybe_mark_stale_generation_job_failed", fake_mark_stale)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.maybe_poll_generation_job_from_modal", fake_poll_modal)

    response = TestClient(create_app()).get("/api/v1/generation-jobs/job_polling")

    assert response.status_code == 200
    assert captured == {"job_id": "job_polling", "workspace_id": WORKSPACE_A, "user_id": "user_a"}
    assert stale_scope == {"workspace_id": WORKSPACE_A, "user_id": "user_a"}
    assert modal_scope == {"workspace_id": WORKSPACE_A, "user_id": "user_a"}


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
        return job if workspace_id == WORKSPACE_A else None

    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.get_generation_job_scoped", fake_get_generation_job)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.maybe_mark_stale_generation_job_failed", lambda job, **kwargs: job)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.maybe_poll_generation_job_from_modal", lambda job, **kwargs: job)

    response = TestClient(create_app()).get(
        f"/api/v1/generation-jobs/job_scoped?workspace_id={WORKSPACE_A}",
        headers={"X-EasyAds-User-Id": "user_a"},
    )

    assert response.status_code == 200
    assert captured == {"job_id": "job_scoped", "workspace_id": WORKSPACE_A, "user_id": "user_a"}


def test_generation_job_get_route_resolves_workspace_from_user_header(monkeypatch):
    # B1: HITL polling only carries the authenticated user (no workspace id).
    # The route must resolve a workspace instead of raising "workspaceId is required.".
    captured = {}

    def fake_get_generation_job(job_id, *, workspace_id=None, user_id=None):
        captured.update({"job_id": job_id, "workspace_id": workspace_id, "user_id": user_id})
        return None

    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.get_generation_job_scoped", fake_get_generation_job)

    response = TestClient(create_app()).get(
        "/api/v1/generation-jobs/job_scoped",
        headers={"X-EasyAds-User-Id": "user_a"},
    )

    # Memory backend resolves to the shared mem workspace; no 400 workspace_required.
    assert response.status_code == 404
    assert captured == {"job_id": "job_scoped", "workspace_id": "mem_workspace", "user_id": "user_a"}


def test_generation_job_get_route_returns_404_for_cross_workspace(monkeypatch):
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.get_generation_job_scoped", lambda job_id, **kwargs: None)

    response = TestClient(create_app()).get(
        f"/api/v1/generation-jobs/job_scoped?workspace_id={WORKSPACE_B}",
        headers={"X-EasyAds-User-Id": "user_a"},
    )

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

    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.get_generation_job_scoped", fake_get_generation_job)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.mark_generation_job_running", lambda job_id, stage="planning", **kwargs: job)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.resume_generation_job_graph", lambda *args, **kwargs: job)

    response = TestClient(create_app()).post(
        f"/api/v1/generation-jobs/job_waiting/answer?workspace_id={WORKSPACE_A}",
        headers={"X-EasyAds-User-Id": "user_a"},
        json={"field": "business_type", "value": "cafe"},
    )

    assert response.status_code == 200
    assert captured == {"job_id": "job_waiting", "workspace_id": WORKSPACE_A, "user_id": "user_a"}


def test_generation_job_answer_route_recovers_scope_from_existing_job_without_header(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_ALLOW_DEMO_WORKSPACE_FALLBACK", "false")
    captured = {}
    running_scope = {}
    resume_scope = {}
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

    def fake_mark_running(job_id, stage="planning", **kwargs):
        running_scope.update(kwargs)
        return job

    def fake_resume(job_id, answer, *, allow_running=False, **kwargs):
        resume_scope.update(kwargs)
        return job

    monkeypatch.setattr(
        "orchestrator.app.api.routers.generation_jobs.resolve_generation_job_scope_from_existing_job",
        lambda job_id: (WORKSPACE_A, "user_a"),
    )
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.get_generation_job_scoped", fake_get_generation_job)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.mark_generation_job_running", fake_mark_running)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.resume_generation_job_graph", fake_resume)

    response = TestClient(create_app()).post(
        "/api/v1/generation-jobs/job_waiting/answer",
        json={"field": "business_type", "value": "cafe"},
    )

    assert response.status_code == 200
    assert captured == {"job_id": "job_waiting", "workspace_id": WORKSPACE_A, "user_id": "user_a"}
    assert running_scope == {"workspace_id": WORKSPACE_A, "user_id": "user_a"}
    assert resume_scope == {"workspace_id": WORKSPACE_A, "user_id": "user_a"}
