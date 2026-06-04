from pydantic import ValidationError

from orchestrator.app.api.schemas.generation_jobs import (
    GenerationJobCreateRequest,
    GenerationJobCreateResponse,
    GenerationJobResponse,
    GenerationProgress,
)


def test_generation_job_create_request_validation():
    request = GenerationJobCreateRequest(
        user_input="Create an Instagram ad for a strawberry cake launch.",
        selected_reference_template_id="seed_cafe_strawberry_feed_001",
    )

    assert request.run_mode == "queued_only"
    assert request.user_plan == "free"

    try:
        GenerationJobCreateRequest(user_input=" ")
    except ValidationError:
        pass
    else:
        raise AssertionError("blank user_input should fail validation")


def test_generation_progress_percent_validation():
    progress = GenerationProgress(progress_percent=100, current_stage="completed")
    assert progress.progress_percent == 100

    try:
        GenerationProgress(progress_percent=101)
    except ValidationError:
        pass
    else:
        raise AssertionError("progress_percent > 100 should fail validation")


def test_generation_job_create_response_json_dump():
    job = GenerationJobResponse(
        job_id="job_001",
        status="queued",
        progress=GenerationProgress(),
        created_at="2026-05-29T00:00:00Z",
        updated_at="2026-05-29T00:00:00Z",
    )
    response = GenerationJobCreateResponse(job=job)

    dumped = response.model_dump(mode="json")

    assert dumped["success"] is True
    assert dumped["job"]["job_id"] == "job_001"
