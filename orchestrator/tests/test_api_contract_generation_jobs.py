from pydantic import ValidationError

from orchestrator.app.api.schemas.generation_jobs import (
    GenerationJobAnswerRequest,
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


def test_generation_job_create_request_accepts_ad_format_and_renderer_mode_aliases():
    request = GenerationJobCreateRequest.model_validate(
        {
            "userInput": "포스터 만들어줘",
            "adFormat": "poster",
            "rendererMode": "simple_text",
        }
    )

    assert request.ad_format == "poster"
    assert request.renderer_mode == "simple_text"


def test_generation_job_answer_request_builds_option_resume_payload():
    request = GenerationJobAnswerRequest(
        field="business_type",
        value="cafe",
        custom_text=None,
    )

    payload = request.to_resume_payload(job_id="job_1", thread_id="thread_1")

    assert payload == {
        "job_id": "job_1",
        "thread_id": "thread_1",
        "field": "business_type",
        "value": "cafe",
    }


def test_generation_job_answer_request_supports_camel_case_custom_text():
    request = GenerationJobAnswerRequest.model_validate(
        {
            "field": "item_or_service",
            "value": "custom",
            "customText": "딸기라떼",
            "displayText": "딸기라떼",
        }
    )

    payload = request.to_resume_payload(job_id="job_1", thread_id="thread_1")

    assert payload["custom_text"] == "딸기라떼"
    assert payload["display_text"] == "딸기라떼"


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
