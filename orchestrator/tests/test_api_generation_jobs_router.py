import pytest
from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app
from orchestrator.app.generation_jobs.service import reset_generation_job_store_for_tests


@pytest.fixture(autouse=True)
def reset_store():
    reset_generation_job_store_for_tests()
    yield
    reset_generation_job_store_for_tests()


def client() -> TestClient:
    return TestClient(create_app())


def test_openapi_registers_generation_jobs_and_existing_routes():
    schema = create_app().openapi()

    assert "/api/v1/references" in schema["paths"]
    assert "/api/v1/brand-kits" in schema["paths"]
    assert "/api/v1/generation-jobs" in schema["paths"]
    assert "/api/v1/generation-jobs/{job_id}" in schema["paths"]


def test_create_generation_job_and_get_job():
    http = client()
    created = http.post(
        "/api/v1/generation-jobs",
        json={
            "user_input": "Create a cafe launch ad",
            "user_id": "user_1",
            "brand_kit_id": "bk_1",
            "selected_reference_template_id": "seed_cafe_strawberry_feed_001",
            "run_mode": "mock_immediate",
        },
    )

    assert created.status_code == 201
    payload = created.json()
    assert payload["success"] is True
    job = payload["job"]
    assert job["job_id"].startswith("job_")
    assert job["thread_id"].startswith("thread_")
    assert job["status"] == "queued"
    assert job["progress"]["progress_percent"] == 0
    assert job["progress"]["current_stage"] == "queued"
    assert job["selected_reference_template_id"] == "seed_cafe_strawberry_feed_001"
    assert job["metadata"]["requested_run_mode"] == "mock_immediate"
    assert job["metadata"]["effective_run_mode"] == "queued_only"
    assert job["output_path"] is None
    assert job["result_payload"] is None

    fetched = http.get(f"/api/v1/generation-jobs/{job['job_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["job"]["job_id"] == job["job_id"]


def test_create_generation_job_accepts_graph_immediate_without_running_graph():
    response = client().post(
        "/api/v1/generation-jobs",
        json={"user_input": "Create an ad", "run_mode": "graph_immediate"},
    )

    assert response.status_code == 201
    job = response.json()["job"]
    assert job["status"] == "queued"
    assert job["metadata"]["requested_run_mode"] == "graph_immediate"
    assert job["metadata"]["effective_run_mode"] == "queued_only"


def test_invalid_job_id_returns_structured_404():
    response = client().get("/api/v1/generation-jobs/job_missing")

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["success"] is False
    assert detail["error_code"] == "generation_job_not_found"


def test_invalid_reference_template_id_returns_structured_404():
    response = client().post(
        "/api/v1/generation-jobs",
        json={"user_input": "Create an ad", "selected_reference_template_id": "missing_template"},
    )

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["success"] is False
    assert detail["error_code"] == "reference_template_not_found"


def test_empty_user_input_returns_structured_400():
    response = client().post("/api/v1/generation-jobs", json={"user_input": " "})

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["error_code"] == "invalid_generation_job_request"
