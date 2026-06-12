"""Photo-start API adapter for the marketing graph."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import Field

from orchestrator.app.api.chat import (
    CamelModel,
    ChatBriefReadyResponse,
    ChatOptionQuestionResponse,
    ChatStartResponse,
    CopyGenerationMode,
    _brief_ready_response,
    _clean_optional_text,
    _copy_candidates_response,
    _interrupt_value,
    _option_question_response,
    _require_custom_copy_headline,
    _selected_channel_id_for_ad_format,
    _thread_config,
    BRIEF_READY_COPY_MODES,
)
from orchestrator.app.api.marketing_graph import get_marketing_graph

router = APIRouter(prefix="/v1/marketing/photo", tags=["marketing-photo"])


class PhotoStartRequest(CamelModel):
    user_input: str = Field(alias="userInput", min_length=1)
    source_image_path: str = Field(alias="sourceImagePath", min_length=1)
    ad_format: str = Field(default="instagram_feed", alias="adFormat")
    render_profile: str = Field(default="premium_api", alias="renderProfile")
    vision_preprocess_mode: str = Field(default="resize_only", alias="visionPreprocessMode")
    copy_generation_mode: CopyGenerationMode = Field(default="suggest_candidates", alias="copyGenerationMode")
    user_custom_headline: str | None = Field(default=None, alias="userCustomHeadline")
    user_custom_subcopy: str | None = Field(default=None, alias="userCustomSubcopy")
    selected_reference_template_id: str | None = Field(default=None, alias="selectedReferenceTemplateId")
    reference_image_path: str | None = Field(default=None, alias="referenceImagePath")


@router.post("/start", response_model=ChatStartResponse | ChatOptionQuestionResponse | ChatBriefReadyResponse, response_model_by_alias=True)
def start_photo(request: PhotoStartRequest) -> ChatStartResponse | ChatOptionQuestionResponse | ChatBriefReadyResponse:
    _require_custom_copy_headline(request.copy_generation_mode, request.user_custom_headline)
    job_seed = ":".join(
        [
            request.source_image_path,
            request.user_input,
            request.ad_format,
            request.copy_generation_mode,
            _clean_optional_text(request.user_custom_headline) or "",
            _clean_optional_text(request.user_custom_subcopy) or "",
            _clean_optional_text(request.selected_reference_template_id) or "",
            _clean_optional_text(request.reference_image_path) or "",
        ]
    )
    job_id = f"photo_{abs(hash(job_seed))}"
    thread_id = f"{job_id}_thread"
    state = {
        "entry_mode": "photo_start",
        "user_input": request.user_input,
        "source_image_path": request.source_image_path,
        "job_id": job_id,
        "thread_id": thread_id,
        "render_profile": request.render_profile,
        "vision_preprocess_mode": request.vision_preprocess_mode,
        "copy_generation_mode": request.copy_generation_mode,
        "user_custom_headline": _clean_optional_text(request.user_custom_headline),
        "user_custom_subcopy": _clean_optional_text(request.user_custom_subcopy),
        "selected_reference_template_id": _clean_optional_text(request.selected_reference_template_id),
        "reference_image_path": _clean_optional_text(request.reference_image_path),
        "context": {
            "extra": {
                "ad_format": request.ad_format,
                "source_image_path": request.source_image_path,
                "selected_reference_template_id": _clean_optional_text(request.selected_reference_template_id),
                "reference_image_path": _clean_optional_text(request.reference_image_path),
            }
        },
    }
    result = get_marketing_graph().invoke(state, config=_thread_config(thread_id))
    interrupt = _interrupt_value(result)

    if interrupt and interrupt.get("type") == "option_question":
        return _option_question_response(result, interrupt)
    if result.get("copy_generation_mode") in BRIEF_READY_COPY_MODES and result.get("status") == "done":
        return _brief_ready_response(result, job_id=job_id, thread_id=thread_id, selected_channel_id=_selected_channel_id_for_ad_format(request.ad_format))

    return _copy_candidates_response(result, job_id=job_id, thread_id=thread_id, interrupt=interrupt)
