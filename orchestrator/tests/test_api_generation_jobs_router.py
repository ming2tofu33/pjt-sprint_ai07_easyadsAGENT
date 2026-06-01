import pytest
from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app
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


def test_graph_immediate_degrades_to_queued_only(client):
    response = client.post(
        "/api/v1/generation-jobs",
        json={
            "user_input": "카페 신메뉴 광고 만들어줘",
            "run_mode": "graph_immediate",
        },
    )

    assert response.status_code == 201
    body = response.json()
    job = body["job"]

    assert job["status"] == "queued"
    assert job["output_path"] is None
    assert job["result_payload"] is None
    assert job["metadata"]["requested_run_mode"] == "graph_immediate"
    assert job["metadata"]["effective_run_mode"] == "queued_only"
    assert job["metadata"]["execution_mode"] == "degraded_no_graph_execution"


def test_actual_lanes_default_disabled_return_failed_job(client, monkeypatch):
    monkeypatch.delenv("EASYADS_ENABLE_EXTERNAL_T2I", raising=False)
    monkeypatch.delenv("EASYADS_ENABLE_GPT_IMAGE_2", raising=False)
    monkeypatch.delenv("EASYADS_ENABLE_SD35_LOCAL", raising=False)

    gpt = client.post("/api/v1/generation-jobs", json={"user_input": "Create an ad", "run_mode": "gpt_image_2_smoke"})
    sd35 = client.post("/api/v1/generation-jobs", json={"user_input": "Create an ad", "run_mode": "sd35_local_smoke"})

    assert gpt.status_code == 201
    assert gpt.json()["job"]["status"] == "failed"
    assert gpt.json()["job"]["error"]["error_code"] == "t2i_engine_not_enabled"
    assert sd35.status_code == 201
    assert sd35.json()["job"]["status"] == "failed"
    assert sd35.json()["job"]["error"]["error_code"] == "t2i_engine_not_enabled"


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
