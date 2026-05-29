"""Chat-start API adapter for the marketing graph."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field

from orchestrator.app.graph.builder import build_marketing_graph

router = APIRouter(prefix="/v1/marketing/chat", tags=["marketing-chat"])
_GRAPH = build_marketing_graph()


BUSINESS_LABELS = {
    "cafe": "카페",
    "restaurant": "음식점",
    "beauty_salon": "뷰티",
    "fitness": "피트니스",
    "flower_shop": "꽃집",
    "store": "매장",
}

GOAL_LABELS = {
    "new_launch": "신메뉴 출시",
    "discount_event": "할인 이벤트",
    "reservation_cta": "예약/방문 유도",
    "review_event": "리뷰 이벤트",
    "brand_awareness": "브랜드 인지도",
    "retention": "재방문 유도",
}

CHANNEL_LABELS = {
    "instagram-feed": "인스타 피드 (1:1)",
    "instagram-story": "인스타 스토리 (9:16)",
    "poster": "포스터 (4:5)",
    "flyer": "전단지 (A4)",
}

AD_FORMAT_BY_CHANNEL = {
    "instagram-feed": "instagram_feed",
    "instagram-story": "instagram_story",
    "poster": "poster",
    "flyer": "flyer",
}


class CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class ChatContext(CamelModel):
    business_type: str = Field(alias="businessType")
    item_or_service: str = Field(alias="itemOrService")
    promotion_goal: str = Field(alias="promotionGoal")


class CopyCandidate(CamelModel):
    id: str
    headline: str
    subcopy: str | None = None
    cta: str | None = None


class ChatBrief(CamelModel):
    purpose: str
    item: str
    copy_text: str = Field(alias="copy")
    tone: str
    channel: str
    image_direction: str = Field(alias="imageDirection")
    final_image_path: str | None = Field(default=None, alias="finalImagePath")


class ChatStartRequest(CamelModel):
    user_input: str = Field(alias="userInput", min_length=1)
    ad_format: str = Field(default="instagram_feed", alias="adFormat")


class ChatStartResponse(CamelModel):
    job_id: str = Field(alias="jobId")
    thread_id: str = Field(alias="threadId")
    status: str
    context: ChatContext
    copy_candidates: list[CopyCandidate] = Field(alias="copyCandidates")
    recommended_copy_id: str | None = Field(default=None, alias="recommendedCopyId")


class ChatBriefRequest(CamelModel):
    job_id: str = Field(alias="jobId", min_length=1)
    thread_id: str = Field(alias="threadId", min_length=1)
    selected_copy_id: str = Field(alias="selectedCopyId", min_length=1)
    selected_channel_id: str = Field(default="instagram-feed", alias="selectedChannelId")
    selected_tone: str | None = Field(default=None, alias="selectedTone")
    custom_direction: str | None = Field(default=None, alias="customDirection")


class ChatBriefResponse(CamelModel):
    job_id: str = Field(alias="jobId")
    thread_id: str = Field(alias="threadId")
    status: str
    brief: ChatBrief


def _thread_config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def _label(mapping: dict[str, str], value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    return mapping.get(value, value)


def _context_from_state(state: dict[str, Any]) -> ChatContext:
    context = state.get("context") or {}
    return ChatContext(
        businessType=_label(BUSINESS_LABELS, context.get("business_type"), "카페"),
        itemOrService=context.get("item_or_service") or "대표 메뉴",
        promotionGoal=_label(GOAL_LABELS, context.get("promotion_goal"), "광고 홍보"),
    )


def _candidate_from_raw(candidate: dict[str, Any]) -> CopyCandidate:
    return CopyCandidate(
        id=candidate.get("id") or "copy_1",
        headline=candidate.get("headline") or "",
        subcopy=candidate.get("subcopy"),
        cta=candidate.get("cta"),
    )


def _interrupt_value(state: dict[str, Any]) -> dict[str, Any] | None:
    interrupts = state.get("__interrupt__") or []
    if not interrupts:
        return None
    return getattr(interrupts[0], "value", None)


@router.post("/start", response_model=ChatStartResponse, response_model_by_alias=True)
def start_chat(request: ChatStartRequest) -> ChatStartResponse:
    job_id = f"chat_{abs(hash(request.user_input))}"
    thread_id = f"{job_id}_thread"
    state = {
        "entry_mode": "chat_start",
        "user_input": request.user_input,
        "job_id": job_id,
        "thread_id": thread_id,
        "render_profile": "fast",
        "copy_generation_mode": "suggest_candidates",
        "context": {"extra": {"ad_format": request.ad_format}},
    }
    result = _GRAPH.invoke(state, config=_thread_config(thread_id))
    interrupt = _interrupt_value(result)

    candidates = result.get("copy_candidates") or []
    recommended_copy_id = None
    if interrupt and interrupt.get("type") == "copy_candidate_selection":
        candidates = interrupt.get("candidates") or candidates
        recommended_copy_id = interrupt.get("recommended_candidate_id")

    if not candidates:
        raise HTTPException(status_code=422, detail={"message": "copy candidates were not generated", "state": result.get("status")})

    return ChatStartResponse(
        jobId=result.get("job_id") or job_id,
        threadId=result.get("thread_id") or thread_id,
        status=result.get("status") or "waiting_copy_selection",
        context=_context_from_state(result),
        copyCandidates=[_candidate_from_raw(candidate) for candidate in candidates],
        recommendedCopyId=recommended_copy_id or candidates[0].get("id"),
    )


@router.post("/brief", response_model=ChatBriefResponse, response_model_by_alias=True)
def create_brief(request: ChatBriefRequest) -> ChatBriefResponse:
    result = _GRAPH.invoke(Command(resume={"selected_copy_id": request.selected_copy_id}), config=_thread_config(request.thread_id))
    if result.get("status") == "failed":
        raise HTTPException(status_code=422, detail=result.get("error_message") or "graph failed")

    context = _context_from_state(result)
    marketing_copy = result.get("marketing_copy") or {}
    image_prompt_spec = result.get("image_prompt_spec") or {}
    image_direction = (
        request.custom_direction
        or image_prompt_spec.get("scene_description")
        or f"크림톤 배경, {context.item_or_service}를 중앙에 크게 배치하고 우측 여백에 카피 배치"
    )
    tone = request.selected_tone or "감성적인"
    brief = ChatBrief(
        purpose=context.promotion_goal,
        item=context.item_or_service,
        copy=marketing_copy.get("headline") or "봄을 닮은 한 잔, 딸기라떼 출시",
        tone=f"{tone}이고 상큼한 카페 무드",
        channel=CHANNEL_LABELS.get(request.selected_channel_id, request.selected_channel_id),
        imageDirection=image_direction,
        finalImagePath=result.get("final_image_path"),
    )
    return ChatBriefResponse(
        jobId=result.get("job_id") or request.job_id,
        threadId=result.get("thread_id") or request.thread_id,
        status=result.get("status") or "done",
        brief=brief,
    )
