"""Chat-start API adapter for the marketing graph."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field

from orchestrator.app.api.marketing_graph import MARKETING_GRAPH
from orchestrator.app.llm.option_registry import option_label_for_value

router = APIRouter(prefix="/v1/marketing/chat", tags=["marketing-chat"])
_GRAPH = MARKETING_GRAPH


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


class PartialChatContext(CamelModel):
    business_type: str | None = Field(default=None, alias="businessType")
    item_or_service: str | None = Field(default=None, alias="itemOrService")
    promotion_goal: str | None = Field(default=None, alias="promotionGoal")


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
    render_profile: str = Field(default="fast", alias="renderProfile")


class ChatStartResponse(CamelModel):
    type: Literal["copy_candidates"] = "copy_candidates"
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


class ChatAnswerRequest(CamelModel):
    job_id: str = Field(alias="jobId", min_length=1)
    thread_id: str = Field(alias="threadId", min_length=1)
    field: str = Field(min_length=1)
    value: str
    custom_text: str | None = Field(default=None, alias="customText")


class ChatBriefResponse(CamelModel):
    job_id: str = Field(alias="jobId")
    thread_id: str = Field(alias="threadId")
    status: str
    brief: ChatBrief


class ChatOptionQuestionResponse(CamelModel):
    type: Literal["option_question"] = "option_question"
    job_id: str = Field(alias="jobId")
    thread_id: str = Field(alias="threadId")
    status: str = "waiting_user_selection"
    context: PartialChatContext
    question: dict[str, Any]
    missing_fields: list[str] = Field(default_factory=list, alias="missingFields")


def _thread_config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _label(mapping: dict[str, str], value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    return mapping.get(value, value)


def _item_or_service_label(value: str | None) -> str:
    if not value:
        return "대표 메뉴"
    label = option_label_for_value("item_or_service", value)
    if label:
        return label
    if "_" in value and value.isascii():
        return "상품/서비스"
    return value


def _tone_summary(selected_tone: str | None) -> str:
    tone = _clean_optional_text(selected_tone)
    if not tone:
        return "브랜드에 맞춘 분위기"
    return f"{tone} 분위기"


def _image_direction_summary(context: ChatContext, selected_tone: str | None, custom_direction: str | None) -> str:
    if custom_direction:
        return custom_direction
    item = context.item_or_service or "상품/서비스"
    tone_prefix = f"{selected_tone} 분위기를 살려 " if _clean_optional_text(selected_tone) else ""
    if "예약" in item or item.endswith("서비스"):
        return f"{tone_prefix}{item} 안내가 잘 보이도록 깔끔한 배경과 읽기 쉬운 여백을 구성해요."
    return f"{tone_prefix}{item} 중심의 깔끔한 광고 배경과 문구 여백을 구성해요."


def _context_from_state(state: dict[str, Any]) -> ChatContext:
    context = state.get("context") or {}
    return ChatContext(
        businessType=_label(BUSINESS_LABELS, context.get("business_type"), "카페"),
        itemOrService=_item_or_service_label(context.get("item_or_service")),
        promotionGoal=_label(GOAL_LABELS, context.get("promotion_goal"), "광고 홍보"),
    )


def _partial_context_from_state(state: dict[str, Any]) -> PartialChatContext:
    context = state.get("context") or {}
    return PartialChatContext(
        businessType=_label(BUSINESS_LABELS, context.get("business_type"), "") or None,
        itemOrService=_item_or_service_label(context.get("item_or_service")) if context.get("item_or_service") else None,
        promotionGoal=_label(GOAL_LABELS, context.get("promotion_goal"), "") or None,
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


def _option_question_response(result: dict[str, Any], interrupt: dict[str, Any]) -> ChatOptionQuestionResponse:
    return ChatOptionQuestionResponse(
        jobId=result.get("job_id") or interrupt.get("job_id"),
        threadId=result.get("thread_id") or interrupt.get("thread_id"),
        status=result.get("status") or "waiting_user_selection",
        context=_partial_context_from_state(result),
        question=interrupt.get("option_question") or {},
        missingFields=result.get("missing_fields") or [],
    )


def _copy_candidates_response(
    result: dict[str, Any],
    *,
    job_id: str,
    thread_id: str,
    interrupt: dict[str, Any] | None = None,
) -> ChatStartResponse:
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


def _brief_resume_payload(request: ChatBriefRequest) -> dict[str, str]:
    payload = {
        "selected_copy_id": request.selected_copy_id,
        "selected_channel_id": request.selected_channel_id,
    }
    selected_ad_format = AD_FORMAT_BY_CHANNEL.get(request.selected_channel_id)
    if selected_ad_format:
        payload["selected_ad_format"] = selected_ad_format
    selected_tone = _clean_optional_text(request.selected_tone)
    if selected_tone:
        payload["selected_tone"] = selected_tone
    custom_direction = _clean_optional_text(request.custom_direction)
    if custom_direction:
        payload["custom_direction"] = custom_direction
    return payload


@router.post("/start", response_model=ChatStartResponse | ChatOptionQuestionResponse, response_model_by_alias=True)
def start_chat(request: ChatStartRequest) -> ChatStartResponse | ChatOptionQuestionResponse:
    job_id = f"chat_{abs(hash(request.user_input))}"
    thread_id = f"{job_id}_thread"
    state = {
        "entry_mode": "chat_start",
        "user_input": request.user_input,
        "job_id": job_id,
        "thread_id": thread_id,
        "render_profile": request.render_profile,
        "copy_generation_mode": "suggest_candidates",
        "context": {"extra": {"ad_format": request.ad_format}},
    }
    result = _GRAPH.invoke(state, config=_thread_config(thread_id))
    interrupt = _interrupt_value(result)

    if interrupt and interrupt.get("type") == "option_question":
        return _option_question_response(result, interrupt)

    return _copy_candidates_response(result, job_id=job_id, thread_id=thread_id, interrupt=interrupt)


@router.post("/answer", response_model=ChatStartResponse | ChatOptionQuestionResponse, response_model_by_alias=True)
def answer_chat_question(request: ChatAnswerRequest) -> ChatStartResponse | ChatOptionQuestionResponse:
    resume_payload = {
        "job_id": request.job_id,
        "thread_id": request.thread_id,
        "field": request.field,
        "value": request.value,
    }
    if request.custom_text:
        resume_payload["custom_text"] = request.custom_text

    result = _GRAPH.invoke(Command(resume=resume_payload), config=_thread_config(request.thread_id))
    interrupt = _interrupt_value(result)
    if interrupt and interrupt.get("type") == "option_question":
        return _option_question_response(result, interrupt)

    return _copy_candidates_response(result, job_id=request.job_id, thread_id=request.thread_id, interrupt=interrupt)


@router.post("/brief", response_model=ChatBriefResponse, response_model_by_alias=True)
def create_brief(request: ChatBriefRequest) -> ChatBriefResponse:
    result = _GRAPH.invoke(Command(resume=_brief_resume_payload(request)), config=_thread_config(request.thread_id))
    if result.get("status") == "failed":
        raise HTTPException(status_code=422, detail=result.get("error_message") or "graph failed")

    context = _context_from_state(result)
    marketing_copy = result.get("marketing_copy") or {}
    current_brief = result.get("current_brief") or {}
    selected_channel_id = current_brief.get("selected_channel_id") or request.selected_channel_id
    selected_tone = current_brief.get("selected_tone") or request.selected_tone or "감성적인"
    custom_direction = current_brief.get("custom_direction") or _clean_optional_text(request.custom_direction)
    image_direction = _image_direction_summary(context, selected_tone, custom_direction)
    brief = ChatBrief(
        purpose=context.promotion_goal,
        item=context.item_or_service,
        copy=marketing_copy.get("headline") or "봄을 닮은 한 잔, 딸기라떼 출시",
        tone=_tone_summary(selected_tone),
        channel=CHANNEL_LABELS.get(selected_channel_id, selected_channel_id),
        imageDirection=image_direction,
        finalImagePath=result.get("final_image_path"),
    )
    return ChatBriefResponse(
        jobId=result.get("job_id") or request.job_id,
        threadId=result.get("thread_id") or request.thread_id,
        status=result.get("status") or "done",
        brief=brief,
    )
