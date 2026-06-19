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
    _forced_user_plan,
    _interrupt_value,
    _selected_channel_id_from_result,
    _option_question_response,
    _require_custom_copy_headline,
    _thread_config,
    BRIEF_READY_COPY_MODES,
)
from orchestrator.app.api.marketing_graph import get_marketing_graph
from orchestrator.app.t2i.contracts import normalize_t2i_engine

router = APIRouter(prefix="/v1/marketing/photo", tags=["marketing-photo"])

def _normalize_image_engine(*values: str | None) -> str | None:
    for value in values:
        cleaned = _clean_optional_text(value)
        if not cleaned:
            continue
        normalized = normalize_t2i_engine(cleaned)
        if normalized:
            return normalized.value
    return None


class PhotoStartRequest(CamelModel):
    user_input: str = Field(alias="userInput", min_length=1)
    source_asset_id: str = Field(alias="sourceAssetId", min_length=1)
    ad_format: str = Field(default="instagram_feed", alias="adFormat")
    render_profile: str = Field(default="premium_api", alias="renderProfile")
    vision_preprocess_mode: str = Field(default="resize_only", alias="visionPreprocessMode")
    copy_generation_mode: CopyGenerationMode = Field(default="suggest_candidates", alias="copyGenerationMode")
    user_custom_headline: str | None = Field(default=None, alias="userCustomHeadline")
    user_custom_subcopy: str | None = Field(default=None, alias="userCustomSubcopy")
    selected_reference_template_id: str | None = Field(default=None, alias="selectedReferenceTemplateId")
    reference_asset_id: str | None = Field(default=None, alias="referenceAssetId")
    image_generation_engine: str | None = Field(default=None, alias="imageGenerationEngine")
    requested_engine: str | None = Field(default=None, alias="requestedEngine")
    t2i_engine: str | None = Field(default=None, alias="t2iEngine")
    selected_engine_label: str | None = Field(default=None, alias="selectedEngineLabel")


@router.post("/start", response_model=ChatStartResponse | ChatOptionQuestionResponse | ChatBriefReadyResponse, response_model_by_alias=True)
def start_photo(request: PhotoStartRequest) -> ChatStartResponse | ChatOptionQuestionResponse | ChatBriefReadyResponse:
    _require_custom_copy_headline(request.copy_generation_mode, request.user_custom_headline)
    job_seed = ":".join(
        [
            request.source_asset_id,
            request.user_input,
            request.ad_format,
            request.copy_generation_mode,
            _clean_optional_text(request.user_custom_headline) or "",
            _clean_optional_text(request.user_custom_subcopy) or "",
            _clean_optional_text(request.selected_reference_template_id) or "",
            _clean_optional_text(request.reference_asset_id) or "",
            _normalize_image_engine(request.requested_engine, request.t2i_engine, request.image_generation_engine) or "",
        ]
    )
    job_id = f"photo_{abs(hash(job_seed))}"
    thread_id = f"{job_id}_thread"
    selected_engine = _normalize_image_engine(request.requested_engine, request.t2i_engine, request.image_generation_engine)
    state = {
        "entry_mode": "photo_start",
        "user_input": request.user_input,
        "source_asset_id": request.source_asset_id,
        "job_id": job_id,
        "thread_id": thread_id,
        "render_profile": request.render_profile,
        "vision_preprocess_mode": request.vision_preprocess_mode,
        "copy_generation_mode": request.copy_generation_mode,
        "user_custom_headline": _clean_optional_text(request.user_custom_headline),
        "user_custom_subcopy": _clean_optional_text(request.user_custom_subcopy),
        "selected_reference_template_id": _clean_optional_text(request.selected_reference_template_id),
        "reference_asset_id": _clean_optional_text(request.reference_asset_id),
        "context": {
            "extra": {
                "ad_format": request.ad_format,
                "source_asset_id": request.source_asset_id,
                "selected_reference_template_id": _clean_optional_text(request.selected_reference_template_id),
                "reference_asset_id": _clean_optional_text(request.reference_asset_id),
            }
        },
    }
    if selected_engine:
        state.update(
            {
                "engine": selected_engine,
                "image_generation_engine": selected_engine,
                "requested_engine": selected_engine,
                "t2i_engine": selected_engine,
                "selected_engine_label": _clean_optional_text(request.selected_engine_label),
            }
        )
        state["context"]["extra"].update(
            {
                "requested_engine": selected_engine,
                "t2i_engine": selected_engine,
                "selected_engine_label": _clean_optional_text(request.selected_engine_label),
            }
        )
    forced_plan = _forced_user_plan()
    if forced_plan:
        state["user_plan"] = forced_plan
    result = get_marketing_graph().invoke(state, config=_thread_config(thread_id))
    interrupt = _interrupt_value(result)

    if interrupt and interrupt.get("type") == "option_question":
        return _option_question_response(result, interrupt, fallback_ad_format=request.ad_format)
    if result.get("copy_generation_mode") in BRIEF_READY_COPY_MODES and result.get("status") == "done":
        return _brief_ready_response(
            result,
            job_id=job_id,
            thread_id=thread_id,
            selected_channel_id=_selected_channel_id_from_result(result, fallback_ad_format=request.ad_format) or "instagram-feed",
        )

    return _copy_candidates_response(result, job_id=job_id, thread_id=thread_id, interrupt=interrupt, fallback_ad_format=request.ad_format)
