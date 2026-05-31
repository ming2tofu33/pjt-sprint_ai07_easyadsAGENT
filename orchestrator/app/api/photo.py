"""Photo-start API adapter for the marketing graph."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import Field

from orchestrator.app.api.chat import (
    CamelModel,
    ChatOptionQuestionResponse,
    ChatStartResponse,
    _copy_candidates_response,
    _interrupt_value,
    _option_question_response,
    _thread_config,
)
from orchestrator.app.api.marketing_graph import MARKETING_GRAPH

router = APIRouter(prefix="/v1/marketing/photo", tags=["marketing-photo"])
_GRAPH = MARKETING_GRAPH


class PhotoStartRequest(CamelModel):
    user_input: str = Field(alias="userInput", min_length=1)
    source_image_path: str = Field(alias="sourceImagePath", min_length=1)
    ad_format: str = Field(default="instagram_feed", alias="adFormat")
    render_profile: str = Field(default="premium_api", alias="renderProfile")
    vision_preprocess_mode: str = Field(default="resize_only", alias="visionPreprocessMode")


@router.post("/start", response_model=ChatStartResponse | ChatOptionQuestionResponse, response_model_by_alias=True)
def start_photo(request: PhotoStartRequest) -> ChatStartResponse | ChatOptionQuestionResponse:
    job_seed = f"{request.source_image_path}:{request.user_input}"
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
        "copy_generation_mode": "suggest_candidates",
        "context": {
            "extra": {
                "ad_format": request.ad_format,
                "source_image_path": request.source_image_path,
            }
        },
    }
    result = _GRAPH.invoke(state, config=_thread_config(thread_id))
    interrupt = _interrupt_value(result)

    if interrupt and interrupt.get("type") == "option_question":
        return _option_question_response(result, interrupt)

    return _copy_candidates_response(result, job_id=job_id, thread_id=thread_id, interrupt=interrupt)
