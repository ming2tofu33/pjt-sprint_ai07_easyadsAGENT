from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app
from orchestrator.app.api.schemas.generation_jobs import GenerationJobResponse, GenerationProgress
from orchestrator.app.chat_threads.errors import (
    ChatThreadArchivedError,
    ChatThreadHasActiveJobError,
    ChatThreadNotFoundError,
    ChatThreadServiceError,
)
from orchestrator.app.generation_jobs.service import reset_generation_job_store_for_tests


@pytest.fixture(autouse=True)
def reset_store():
    reset_generation_job_store_for_tests()
    yield
    reset_generation_job_store_for_tests()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


def test_openapi_registers_generation_jobs_and_existing_routes():
    schema = create_app().openapi()

    assert "/api/v1/references" in schema["paths"]
    assert "/api/v1/brand-kits" in schema["paths"]
    assert "/api/v1/generation-jobs" in schema["paths"]
    assert "/api/v1/generation-jobs/{job_id}" in schema["paths"]
    assert "/api/v1/generation-jobs/{job_id}/answer" in schema["paths"]


def test_create_generation_job_and_get_job(client):
    created = client.post(
        "/api/v1/generation-jobs",
        json={
            "user_input": "Create a cafe launch ad",
            "user_id": "user_1",
            "brand_kit_id": "bk_1",
            "selected_reference_template_id": "seed_cafe_strawberry_feed_001",
            "run_mode": "queued_only",
        },
    )

    assert created.status_code == 201
    job = created.json()["job"]
    assert job["job_id"].startswith("job_")
    assert job["thread_id"].startswith("thread_")
    assert job["status"] == "queued"
    assert job["progress"]["progress_percent"] == 0
    assert job["metadata"]["requested_run_mode"] == "queued_only"
    assert job["metadata"]["effective_run_mode"] == "queued_only"
    assert job["output_path"] is None

    fetched = client.get(f"/api/v1/generation-jobs/{job['job_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["job"]["job_id"] == job["job_id"]


def test_get_generation_job_marks_stale_running_planning_job_failed(client, monkeypatch):
    stale_job = GenerationJobResponse(
        job_id="job_stale_1",
        thread_id="thread_stale_1",
        user_id="user_1",
        status="running",
        progress=GenerationProgress(progress_percent=50, current_stage="planning", stage_order=[]),
        created_at=(datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(),
        updated_at=(datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(),
        metadata={"execution_mode": "graph_execution"},
    )
    failed_job = stale_job.model_copy(
        update={
            "status": "failed",
            "progress": GenerationProgress(progress_percent=50, current_stage="failed", stage_order=[]),
            "metadata": {"execution_mode": "stale_running_recovered"},
        }
    )
    calls = []

    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.get_generation_job", lambda job_id, **kwargs: stale_job)

    def fake_maybe_mark_stale_generation_job_failed(job):
        calls.append(job.job_id)
        return failed_job

    monkeypatch.setattr(
        "orchestrator.app.api.routers.generation_jobs.maybe_mark_stale_generation_job_failed",
        fake_maybe_mark_stale_generation_job_failed,
    )

    response = client.get("/api/v1/generation-jobs/job_stale_1")

    assert response.status_code == 200
    assert response.json()["job"]["status"] == "failed"
    assert response.json()["job"]["progress"]["current_stage"] == "failed"
    assert calls == ["job_stale_1"]


def test_create_generation_job_mock_immediate_completes(client):
    response = client.post(
        "/api/v1/generation-jobs",
        json={"user_input": "Create an ad", "run_mode": "mock_immediate"},
    )

    assert response.status_code == 201
    job = response.json()["job"]
    assert job["status"] == "done"
    assert job["progress"]["progress_percent"] == 100
    assert job["progress"]["current_stage"] == "completed"
    assert job["output_path"].endswith("/final_0.png")
    assert job["result_payload"]["schema_version"] == "result_artifact_v1"
    assert job["result_payload"]["final_image_path"] == job["output_path"]
    assert job["result_payload"]["download_url"] is None
    assert job["result_payload"]["final_image_url"] is None
    assert job["result_payload"]["prompt_summary"]
    assert job["result_payload"]["validation_summary"]["overall_pass"] is True
    assert job["metadata"]["effective_run_mode"] == "mock_immediate"
    assert job["metadata"]["execution_mode"] == "deterministic_mock"


def test_invalid_job_reference_and_request_errors(client):
    missing_job = client.get("/api/v1/generation-jobs/job_missing")
    assert missing_job.status_code == 404
    assert missing_job.json()["detail"]["error_code"] == "generation_job_not_found"

    missing_template = client.post(
        "/api/v1/generation-jobs",
        json={"user_input": "Create an ad", "selected_reference_template_id": "missing_template"},
    )
    assert missing_template.status_code == 404
    assert missing_template.json()["detail"]["error_code"] == "reference_template_not_found"

    invalid = client.post("/api/v1/generation-jobs", json={"user_input": " "})
    assert invalid.status_code == 400
    assert invalid.json()["error_code"] == "invalid_generation_job_request"

    legacy_run_mode = client.post(
        "/api/v1/generation-jobs",
        json={"user_input": "Create an ad", "run_mode": "graph_immediate"},
    )
    assert legacy_run_mode.status_code == 400
    assert legacy_run_mode.json()["error_code"] == "invalid_generation_job_request"


def test_graph_job_pending_metadata(client):
    response = client.post(
        "/api/v1/generation-jobs",
        json={
            "user_input": "카페 신메뉴 광고 만들어줘",
            "run_mode": "graph_job",
        },
    )

    assert response.status_code == 201
    body = response.json()
    job = body["job"]

    assert job["status"] in ("queued", "waiting_user_input")
    assert job["output_path"] is None
    assert job["result_payload"] is None
    assert job["metadata"]["requested_run_mode"] == "graph_job"
    assert job["metadata"]["effective_run_mode"] == "graph_job"
    assert job["metadata"]["execution_mode"] in ("pending_graph_execution", "graph_job")


def test_graph_job_routes_to_graph_executor_with_engine_metadata(client, monkeypatch):
    captured = {}

    def fake_execute_generation_job_graph(job_id, request):
        from orchestrator.app.generation_jobs.service import get_generation_job

        captured["job_id"] = job_id
        captured["run_mode"] = request.run_mode
        captured["metadata"] = request.metadata
        job = get_generation_job(job_id)
        assert job is not None
        return job

    monkeypatch.setattr(
        "orchestrator.app.api.routers.generation_jobs.execute_generation_job_graph",
        fake_execute_generation_job_graph,
    )

    response = client.post(
        "/api/v1/generation-jobs",
        json={
            "user_input": "카페 신메뉴 광고 만들어줘",
            "run_mode": "graph_job",
            "metadata": {
                "selected_engine": "flux_schnell",
                "requested_engine": "flux",
                "t2i_engine": "flux",
            },
        },
    )

    assert response.status_code == 201
    assert captured["run_mode"] == "graph_job"
    assert captured["metadata"]["selected_engine"] == "flux_schnell"
    assert captured["metadata"]["requested_engine"] == "flux"
    assert captured["metadata"]["t2i_engine"] == "flux"


def test_generation_job_answer_route_resumes_waiting_job(client, monkeypatch):
    captured = {}

    def fake_resume_generation_job_graph(job_id, answer, *, allow_running=False):
        from orchestrator.app.generation_jobs.service import get_generation_job, update_generation_job

        captured["job_id"] = job_id
        captured["allow_running"] = allow_running
        captured["payload"] = answer.to_resume_payload(job_id=job_id, thread_id="thread_1")
        updated = update_generation_job(
            job_id,
            status="done",
            metadata={"execution_mode": "graph_execution"},
        )
        return updated or get_generation_job(job_id)

    monkeypatch.setattr(
        "orchestrator.app.api.routers.generation_jobs.resume_generation_job_graph",
        fake_resume_generation_job_graph,
    )

    create_response = client.post(
        "/api/v1/generation-jobs",
        json={"user_input": "광고 만들어줘", "run_mode": "queued_only"},
    )
    job = create_response.json()["job"]
    from orchestrator.app.generation_jobs.service import update_generation_job
    update_generation_job(job["job_id"], status="waiting_user_input")

    answer_response = client.post(
        f"/api/v1/generation-jobs/{job['job_id']}/answer",
        json={"field": "business_type", "value": "cafe"},
    )

    assert answer_response.status_code == 200
    assert answer_response.json()["job"]["status"] == "running"
    assert captured["job_id"] == job["job_id"]
    assert captured["allow_running"] is True
    assert captured["payload"]["field"] == "business_type"
    assert captured["payload"]["value"] == "cafe"


def test_actual_lanes_default_disabled_return_failed_job(client, monkeypatch):
    monkeypatch.setenv("EASYADS_ENABLE_EXTERNAL_T2I", "false")
    monkeypatch.setenv("EASYADS_ENABLE_GPT_IMAGE_1", "false")
    monkeypatch.setenv("EASYADS_ENABLE_GPT_IMAGE_2", "false")
    monkeypatch.setenv("EASYADS_ENABLE_SD35_LOCAL", "false")
    monkeypatch.setenv("EASYADS_ENABLE_FLUX_LOCAL", "false")

    gpt = client.post("/api/v1/generation-jobs", json={"user_input": "Create an ad", "run_mode": "gpt_image_1_smoke"})
    sd35 = client.post("/api/v1/generation-jobs", json={"user_input": "Create an ad", "run_mode": "sd35_local_smoke"})
    flux = client.post("/api/v1/generation-jobs", json={"user_input": "Create an ad", "run_mode": "flux_local_smoke"})

    assert gpt.status_code == 201
    assert gpt.json()["job"]["status"] == "failed"
    assert gpt.json()["job"]["error"]["error_code"] == "t2i_engine_not_enabled"
    assert sd35.status_code == 201
    assert sd35.json()["job"]["status"] == "failed"
    assert sd35.json()["job"]["error"]["error_code"] == "t2i_engine_not_enabled"
    assert flux.status_code == 201
    assert flux.json()["job"]["status"] == "failed"
    assert flux.json()["job"]["error"]["error_code"] == "t2i_engine_not_enabled"
    assert flux.json()["job"]["metadata"]["t2i_engine"] == "flux"


def test_create_generation_job_accepts_camel_case_reference_alias(client):
    response = client.post(
        "/api/v1/generation-jobs",
        json={
            "userInput": "Create a cafe launch ad",
            "selectedReferenceTemplateId": "seed_cafe_strawberry_feed_001",
            "runMode": "queued_only",
        },
    )

    assert response.status_code == 201
    job = response.json()["job"]
    assert job["selected_reference_template_id"] == "seed_cafe_strawberry_feed_001"
    assert job["metadata"]["selected_reference_template_id"] == "seed_cafe_strawberry_feed_001"


def test_create_generation_job_accepts_snake_case_reference_id(client):
    response = client.post(
        "/api/v1/generation-jobs",
        json={
            "user_input": "Create a cafe launch ad",
            "selected_reference_template_id": "seed_cafe_strawberry_feed_001",
            "run_mode": "queued_only",
        },
    )

    assert response.status_code == 201
    job = response.json()["job"]
    assert job["selected_reference_template_id"] == "seed_cafe_strawberry_feed_001"


@pytest.mark.parametrize(
    ("exc", "status_code"),
    [
        (ChatThreadNotFoundError(), 404),
        (ChatThreadArchivedError(), 409),
        (ChatThreadHasActiveJobError(), 409),
        (ChatThreadServiceError("invalid_chat_thread_request", "Invalid thread."), 400),
    ],
)
def test_generation_job_chat_thread_errors_are_mapped(client, monkeypatch, exc, status_code):
    from orchestrator.app.api.routers import generation_jobs as router

    monkeypatch.setattr(router, "create_generation_job", lambda request: (_ for _ in ()).throw(exc))

    response = client.post(
        "/api/v1/generation-jobs",
        json={"user_input": "Create an ad", "thread_id": "thread_existing"},
    )

    assert response.status_code == status_code
    assert response.json()["detail"]["error_code"] == exc.error_code


def test_generation_job_actual_payload_preserves_quality_batch_metadata(client, monkeypatch):
    monkeypatch.setenv("EASYADS_ENABLE_EXTERNAL_T2I", "false")
    monkeypatch.setenv("EASYADS_ENABLE_GPT_IMAGE_2", "false")
    monkeypatch.setenv("EASYADS_QUALITY_BATCH_CONFIRM", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "")

    response = client.post(
        "/api/v1/generation-jobs",
        json={
            "user_input": "Create a quality batch ad background",
            "run_mode": "gpt_image_2_actual",
            "selected_reference_template_id": "seed_cafe_strawberry_feed_001",
            "ad_format": "instagram_feed",
            "metadata": {
                "quality_batch_id": "gpt_image2_quality_batch_v1",
                "case_id": "cafe_dessert_001",
            },
        },
    )

    assert response.status_code == 201
    job = response.json()["job"]
    assert job["selected_reference_template_id"] == "seed_cafe_strawberry_feed_001"
    assert job["metadata"]["quality_batch_id"] == "gpt_image2_quality_batch_v1"
    assert job["metadata"]["case_id"] == "cafe_dessert_001"
    assert job["status"] == "failed"
    assert job["error"]["error_code"] == "t2i_engine_not_enabled"

    assert response.status_code == 201
    job = response.json()["job"]
    assert job["selected_reference_template_id"] == "seed_cafe_strawberry_feed_001"
    assert job["metadata"]["quality_batch_id"] == "gpt_image2_quality_batch_v1"
    assert job["metadata"]["case_id"] == "cafe_dessert_001"
    assert job["status"] == "failed"
    assert job["error"]["error_code"] == "t2i_engine_not_enabled"
