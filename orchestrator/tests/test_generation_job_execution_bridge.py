from pathlib import Path

import pytest
from PIL import Image

from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest
from orchestrator.app.generation_jobs.execution import execute_generation_job_immediate, get_generation_job_output_dir
from orchestrator.app.generation_jobs.service import (
    create_generation_job,
    get_generation_job,
    mark_generation_job_failed,
    reset_generation_job_store_for_tests,
)


@pytest.fixture(autouse=True)
def reset_store():
    reset_generation_job_store_for_tests()
    yield
    reset_generation_job_store_for_tests()


def test_queued_only_does_not_execute():
    request = GenerationJobCreateRequest(user_input="Create an ad", run_mode="queued_only")
    job = create_generation_job(request)

    assert job.status == "queued"
    assert job.progress.progress_percent == 0
    assert job.output_path is None
    assert job.result_payload is None


def test_mock_immediate_writes_artifacts_under_job_output_dir():
    request = GenerationJobCreateRequest(user_input="Create an ad", run_mode="mock_immediate", ad_format="instagram_feed")
    job = create_generation_job(request)
    done = execute_generation_job_immediate(job.job_id, request)

    assert done.status == "done"
    assert done.progress.progress_percent == 100
    assert done.progress.current_stage == "completed"
    assert done.output_path == f"data/outputs/{job.job_id}/final_0.png"
    assert done.result_payload is not None
    assert done.result_payload["schema_version"] == "result_artifact_v1"
    assert done.result_payload["download_url"] is None
    assert done.result_payload["final_image_url"] is None
    assert done.result_payload["prompt_summary"]
    assert done.result_payload["validation_summary"]["overall_pass"] is True
    assert done.metadata["requested_run_mode"] == "mock_immediate"
    assert done.metadata["effective_run_mode"] == "mock_immediate"
    assert done.metadata["execution_mode"] == "deterministic_mock"

    output_dir = Path(f"data/outputs/{job.job_id}")
    expected = [
        output_dir / "background_0.png",
        output_dir / "final_0.png",
        output_dir / "metadata.json",
        output_dir / "prompt.json",
        output_dir / "validation.json",
        output_dir / "copy.json",
        output_dir / "layout.json",
        output_dir / "render_result.json",
    ]
    for path in expected:
        assert path.exists()
        assert output_dir in path.parents

    with Image.open(output_dir / "final_0.png") as image:
        assert image.width == 1024
        assert image.height == 1024

    fetched = get_generation_job(job.job_id)
    assert fetched is not None
    assert fetched.status == "done"


def test_graph_job_pending_metadata_without_execution():
    request = GenerationJobCreateRequest(user_input="Create an ad", run_mode="graph_job")
    job = create_generation_job(request)

    assert job.status == "queued"
    assert job.output_path is None
    assert job.result_payload is None
    assert job.metadata["requested_run_mode"] == "graph_job"
    assert job.metadata["effective_run_mode"] == "graph_job"
    assert job.metadata["execution_mode"] == "pending_graph_execution"


def test_failed_job_sets_failed_stage():
    request = GenerationJobCreateRequest(user_input="Create an ad", run_mode="mock_immediate")
    job = create_generation_job(request)
    failed = mark_generation_job_failed(job.job_id, {"error_code": "mock_failed", "message": "Mock failed"})

    assert failed is not None
    assert failed.status == "failed"
    assert failed.progress.current_stage == "failed"
    assert failed.error is not None
    assert failed.error.error_code == "mock_failed"


def test_path_traversal_job_id_rejected():
    for job_id in ["job_../bad", "job_bad/path", "job_bad\\path", "bad_job"]:
        with pytest.raises(ValueError):
            get_generation_job_output_dir(job_id)
