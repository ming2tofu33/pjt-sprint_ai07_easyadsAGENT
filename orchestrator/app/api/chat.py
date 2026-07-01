"""Chat-start API adapter for the marketing graph."""

from __future__ import annotations

import os
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field

from orchestrator.app.api.marketing_graph import get_marketing_graph
from orchestrator.app.core.config import _get_env
from orchestrator.app.graph.runtime_config import graph_thread_config
from orchestrator.app.graph.state import resolve_requested_ad_format
from orchestrator.app.llm.campaign_semantics import campaign_intent_label
from orchestrator.app.llm.option_registry import option_label_for_value

router = APIRouter(prefix="/v1/marketing/chat", tags=["marketing-chat"])


BUSINESS_LABELS = {
    "cafe": "카페",
    "restaurant": "음식점",
    "beauty_salon": "뷰티",
    "beauty_nail": "네일샵",
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
    "seasonal_limited": "시즌 한정 홍보",
    "seasonal_campaign": "시즌 한정 홍보",
}

CAMPAIGN_INTENT_LABELS = {
    "store_opening": "신규 오픈 홍보",
    "grand_opening": "그랜드 오픈 홍보",
    "student_recruitment": "수강생 모집",
    "brand_awareness": "브랜드 인지도",
    "product_promotion": "상품 홍보",
    "local_business_promotion": "매장 홍보",
    "business_introduction": "매장 소개",
    "organization_promotion": "기관 홍보",
}

CHANNEL_LABELS = {
    "instagram-feed": "인스타 피드 (1:1)",
    "instagram-story": "인스타 스토리 (9:16)",
    "poster": "포스터 (4:5)",
    "flyer": "전단지 (A4)",
    "banner": "배너 (16:9)",
    "product_detail": "상세페이지 (가로형)",
}

AD_FORMAT_BY_CHANNEL = {
    "instagram-feed": "instagram_feed",
    "instagram-story": "instagram_story",
    "poster": "poster",
    "flyer": "flyer",
    "banner": "banner",
    "product_detail": "product_detail",
}

CHANNEL_BY_AD_FORMAT = {value: key for key, value in AD_FORMAT_BY_CHANNEL.items()}
CopyGenerationMode = Literal["suggest_candidates", "auto_pilot", "custom_input", "no_copy"]
BRIEF_READY_COPY_MODES = {"auto_pilot", "custom_input", "no_copy"}


class CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class ChatContext(CamelModel):
    business_type: str | None = Field(default=None, alias="businessType")
    item_or_service: str | None = Field(default=None, alias="itemOrService")
    promotion_goal: str | None = Field(default=None, alias="promotionGoal")
    advertised_subject: str | None = Field(default=None, alias="advertisedSubject")
    advertised_subject_type: str | None = Field(default=None, alias="advertisedSubjectType")
    campaign_intent: str | None = Field(default=None, alias="campaignIntent")


class PartialChatContext(CamelModel):
    business_type: str | None = Field(default=None, alias="businessType")
    item_or_service: str | None = Field(default=None, alias="itemOrService")
    promotion_goal: str | None = Field(default=None, alias="promotionGoal")
    advertised_subject: str | None = Field(default=None, alias="advertisedSubject")
    advertised_subject_type: str | None = Field(default=None, alias="advertisedSubjectType")
    campaign_intent: str | None = Field(default=None, alias="campaignIntent")


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
    selected_channel_id: str | None = Field(default=None, alias="selectedChannelId")
    image_direction: str = Field(alias="imageDirection")
    final_image_path: str | None = Field(default=None, alias="finalImagePath")


class ChatStartRequest(CamelModel):
    user_input: str = Field(alias="userInput", min_length=1)
    ad_format: str | None = Field(default=None, alias="adFormat")
    render_profile: str = Field(default="fast", alias="renderProfile")
    copy_generation_mode: CopyGenerationMode = Field(default="suggest_candidates", alias="copyGenerationMode")
    user_custom_headline: str | None = Field(default=None, alias="userCustomHeadline")
    user_custom_subcopy: str | None = Field(default=None, alias="userCustomSubcopy")
    selected_reference_template_id: str | None = Field(default=None, alias="selectedReferenceTemplateId")
    reference_image_path: str | None = Field(default=None, alias="referenceImagePath")


class ChatStartResponse(CamelModel):
    type: Literal["copy_candidates"] = "copy_candidates"
    job_id: str = Field(alias="jobId")
    thread_id: str = Field(alias="threadId")
    status: str
    context: ChatContext
    copy_candidates: list[CopyCandidate] = Field(alias="copyCandidates")
    recommended_copy_id: str | None = Field(default=None, alias="recommendedCopyId")
    copy_generation_mode: CopyGenerationMode | None = Field(default=None, alias="copyGenerationMode")
    copy_candidate_origin: Literal["llm", "rule_based", "fallback", "mock", "unknown"] = Field(default="unknown", alias="copyCandidateOrigin")
    copy_fallback_used: bool = Field(default=False, alias="copyFallbackUsed")
    copy_fallback_reason: str | None = Field(default=None, alias="copyFallbackReason")
    selected_channel_id: str | None = Field(default=None, alias="selectedChannelId")


class ChatBriefRequest(CamelModel):
    job_id: str = Field(alias="jobId", min_length=1)
    thread_id: str = Field(alias="threadId", min_length=1)
    selected_copy_id: str = Field(alias="selectedCopyId", min_length=1)
    selected_channel_id: str | None = Field(default=None, alias="selectedChannelId")
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
    selected_channel_id: str | None = Field(default=None, alias="selectedChannelId")


class ChatBriefReadyResponse(CamelModel):
    type: Literal["brief_ready"] = "brief_ready"
    job_id: str = Field(alias="jobId")
    thread_id: str = Field(alias="threadId")
    status: str
    context: ChatContext
    brief: ChatBrief
    copy_generation_mode: CopyGenerationMode = Field(alias="copyGenerationMode")
    selected_channel_id: str | None = Field(default=None, alias="selectedChannelId")


class ChatOptionQuestionResponse(CamelModel):
    type: Literal["option_question"] = "option_question"
    job_id: str = Field(alias="jobId")
    thread_id: str = Field(alias="threadId")
    status: str = "waiting_user_selection"
    context: PartialChatContext
    question: dict[str, Any]
    missing_fields: list[str] = Field(default_factory=list, alias="missingFields")
    selected_channel_id: str | None = Field(default=None, alias="selectedChannelId")


def _thread_config(thread_id: str) -> dict[str, Any]:
    return graph_thread_config(thread_id)


_FORCEABLE_USER_PLANS = {"free", "economic", "premium", "internal_benchmark"}


def _forced_user_plan() -> str | None:
    """Return a user_plan to force-inject at the API boundary, or None.

    MVP policy: premium is the default in every (non-test) environment so all
    generation runs on the GPT-5.4 models instead of falling back to local
    Gemma. EASYADS_FORCE_USER_PLAN can override this to a lower plan
    (free|economic|premium|internal_benchmark) per deployment if needed.

    Skipped under pytest (returns None) so the suite keeps its deterministic
    free-plan/mock behavior and never hits a real API.
    """
    if "PYTEST_CURRENT_TEST" in os.environ:
        return None
    forced = _get_env("EASYADS_FORCE_USER_PLAN", "").strip().lower()
    if forced in _FORCEABLE_USER_PLANS:
        return forced
    return "premium"


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _label(mapping: dict[str, str], value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    return mapping.get(value, value)


def _campaign_intent_label(value: str | None) -> str | None:
    return campaign_intent_label(value)


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
    current_brief = state.get("current_brief") or {}
    campaign_context = state.get("campaign_context") or {}
    return ChatContext(
        businessType=_clean_optional_text(context.get("business_type")),
        itemOrService=_clean_optional_text(context.get("item_or_service")),
        promotionGoal=_clean_optional_text(context.get("promotion_goal")),
        advertisedSubject=_clean_optional_text(current_brief.get("advertised_subject")),
        advertisedSubjectType=_clean_optional_text(current_brief.get("advertised_subject_type")),
        campaignIntent=_clean_optional_text(current_brief.get("campaign_intent") or campaign_context.get("campaign_intent")),
    )


def _partial_context_from_state(state: dict[str, Any]) -> PartialChatContext:
    context = state.get("context") or {}
    current_brief = state.get("current_brief") or {}
    campaign_context = state.get("campaign_context") or {}
    return PartialChatContext(
        businessType=_clean_optional_text(context.get("business_type")),
        itemOrService=_clean_optional_text(context.get("item_or_service")),
        promotionGoal=_clean_optional_text(context.get("promotion_goal")),
        advertisedSubject=_clean_optional_text(current_brief.get("advertised_subject")),
        advertisedSubjectType=_clean_optional_text(current_brief.get("advertised_subject_type")),
        campaignIntent=_clean_optional_text(current_brief.get("campaign_intent") or campaign_context.get("campaign_intent")),
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


def _option_question_response(
    result: dict[str, Any],
    interrupt: dict[str, Any],
    *,
    fallback_ad_format: str | None = None,
) -> ChatOptionQuestionResponse:
    return ChatOptionQuestionResponse(
        jobId=result.get("job_id") or interrupt.get("job_id"),
        threadId=result.get("thread_id") or interrupt.get("thread_id"),
        status=result.get("status") or "waiting_user_selection",
        context=_partial_context_from_state(result),
        question=interrupt.get("option_question") or {},
        missingFields=result.get("missing_fields") or [],
        selectedChannelId=_selected_channel_id_from_result(result, fallback_ad_format=fallback_ad_format),
    )


def _copy_candidates_response(
    result: dict[str, Any],
    *,
    job_id: str,
    thread_id: str,
    interrupt: dict[str, Any] | None = None,
    fallback_ad_format: str | None = None,
) -> ChatStartResponse:
    candidates = result.get("copy_candidates") or []
    recommended_copy_id = None
    copy_candidate_origin = str(result.get("copy_candidate_origin") or "unknown")
    copy_fallback_used, copy_fallback_reason = _copy_fallback_status(result)
    if interrupt and interrupt.get("type") == "copy_candidate_selection":
        candidates = interrupt.get("candidates") or candidates
        recommended_copy_id = interrupt.get("recommended_candidate_id")
        copy_candidate_origin = str(interrupt.get("copy_candidate_origin") or copy_candidate_origin)

    if not candidates:
        raise HTTPException(status_code=422, detail={"message": "copy candidates were not generated", "state": result.get("status")})

    return ChatStartResponse(
        jobId=result.get("job_id") or job_id,
        threadId=result.get("thread_id") or thread_id,
        status=result.get("status") or "waiting_copy_selection",
        context=_context_from_state(result),
        copyCandidates=[_candidate_from_raw(candidate) for candidate in candidates],
        recommendedCopyId=recommended_copy_id or candidates[0].get("id"),
        copyGenerationMode=result.get("copy_generation_mode"),
        copyCandidateOrigin=copy_candidate_origin if copy_candidate_origin in {"llm", "rule_based", "fallback", "mock"} else "unknown",
        copyFallbackUsed=copy_fallback_used or copy_candidate_origin in {"fallback", "mock"},
        copyFallbackReason=copy_fallback_reason,
        selectedChannelId=_selected_channel_id_from_result(result, fallback_ad_format=fallback_ad_format),
    )


def _copy_fallback_status(result: dict[str, Any]) -> tuple[bool, str | None]:
    trace = result.get("copy_generation_trace") or {}
    lineage = trace.get("lineage") if isinstance(trace, dict) else {}
    if not isinstance(lineage, dict):
        lineage = {}
    fallback_used = bool(lineage.get("fallback_used") or result.get("copy_candidate_origin") in {"fallback", "mock"})
    fallback_reason = _clean_optional_text(str(lineage.get("fallback_reason"))) if lineage.get("fallback_reason") is not None else None
    return fallback_used, fallback_reason


def _normalize_selected_channel_id(value: str | None) -> str | None:
    cleaned = _clean_optional_text(value)
    if not cleaned:
        return None
    if cleaned in CHANNEL_LABELS:
        return cleaned
    if cleaned in CHANNEL_BY_AD_FORMAT:
        return CHANNEL_BY_AD_FORMAT[cleaned]
    return None


def _selected_channel_id_for_ad_format(ad_format: str | None) -> str | None:
    return _normalize_selected_channel_id(ad_format)


def _selected_channel_id_from_result(
    result: dict[str, Any],
    *,
    fallback_selected_channel_id: str | None = None,
    fallback_ad_format: str | None = None,
) -> str | None:
    current_brief = result.get("current_brief") or {}
    context_extra = ((result.get("context") or {}).get("extra")) or {}
    return (
        _normalize_selected_channel_id(current_brief.get("selected_channel_id"))
        or _normalize_selected_channel_id(current_brief.get("selectedChannelId"))
        or _selected_channel_id_for_ad_format(resolve_requested_ad_format(result))
        or _selected_channel_id_for_ad_format(current_brief.get("requested_ad_format"))
        or _selected_channel_id_for_ad_format(current_brief.get("requestedAdFormat"))
        or _selected_channel_id_for_ad_format(result.get("ad_format"))
        or _normalize_selected_channel_id(context_extra.get("selected_channel_id"))
        or _normalize_selected_channel_id(context_extra.get("selectedChannelId"))
        or _selected_channel_id_for_ad_format(context_extra.get("ad_format"))
        or _selected_channel_id_for_ad_format(context_extra.get("adFormat"))
        or _normalize_selected_channel_id(fallback_selected_channel_id)
        or _selected_channel_id_for_ad_format(fallback_ad_format)
    )


def _brief_from_result(
    result: dict[str, Any],
    *,
    selected_channel_id: str | None = None,
    selected_tone: str | None = None,
    custom_direction: str | None = None,
) -> ChatBrief:
    context = _context_from_state(result)
    marketing_copy = result.get("marketing_copy") or {}
    current_brief = result.get("current_brief") or {}
    final_channel_id = _selected_channel_id_from_result(result, fallback_selected_channel_id=selected_channel_id) or "instagram-feed"
    final_tone = current_brief.get("selected_tone") or selected_tone
    final_custom_direction = current_brief.get("custom_direction") or _clean_optional_text(custom_direction)
    image_direction = _image_direction_summary(context, final_tone, final_custom_direction)
    headline = marketing_copy.get("headline")
    subcopy = marketing_copy.get("subcopy")
    if headline and subcopy:
        copy_text = f"{headline}\n{subcopy}"
    elif headline:
        copy_text = headline
    else:
        copy_text = "문구 없이 이미지로만" if result.get("copy_generation_mode") == "no_copy" else "봄을 닮은 한 잔, 딸기라떼 출시"
    brief_purpose = context.promotion_goal or _campaign_intent_label(context.campaign_intent) or "확인 필요"
    brief_item = context.item_or_service or context.advertised_subject or "확인 필요"
    return ChatBrief(
        purpose=brief_purpose,
        item=brief_item,
        copy=copy_text,
        tone=_tone_summary(final_tone),
        channel=CHANNEL_LABELS.get(final_channel_id, final_channel_id),
        selected_channel_id=final_channel_id,
        imageDirection=image_direction,
        finalImagePath=result.get("final_image_path"),
    )


def _brief_ready_response(result: dict[str, Any], *, job_id: str, thread_id: str, selected_channel_id: str | None = None) -> ChatBriefReadyResponse:
    final_channel_id = _selected_channel_id_from_result(result, fallback_selected_channel_id=selected_channel_id)
    return ChatBriefReadyResponse(
        jobId=result.get("job_id") or job_id,
        threadId=result.get("thread_id") or thread_id,
        status=result.get("status") or "done",
        context=_context_from_state(result),
        brief=_brief_from_result(result, selected_channel_id=selected_channel_id),
        copyGenerationMode=result.get("copy_generation_mode") or "no_copy",
        selectedChannelId=final_channel_id,
    )


def _require_custom_copy_headline(copy_generation_mode: str | None, user_custom_headline: str | None) -> None:
    if copy_generation_mode == "custom_input" and not _clean_optional_text(user_custom_headline):
        raise HTTPException(status_code=400, detail={"message": "userCustomHeadline is required for custom_input"})


def _brief_resume_payload(request: ChatBriefRequest) -> dict[str, str]:
    payload = {"selected_copy_id": request.selected_copy_id}
    selected_channel_id = _normalize_selected_channel_id(request.selected_channel_id)
    if selected_channel_id:
        payload["selected_channel_id"] = selected_channel_id
        selected_ad_format = AD_FORMAT_BY_CHANNEL.get(selected_channel_id)
        if selected_ad_format:
            payload["selected_ad_format"] = selected_ad_format
    selected_tone = _clean_optional_text(request.selected_tone)
    if selected_tone:
        payload["selected_tone"] = selected_tone
    custom_direction = _clean_optional_text(request.custom_direction)
    if custom_direction:
        payload["custom_direction"] = custom_direction
    return payload


@router.post("/start", response_model=ChatStartResponse | ChatOptionQuestionResponse | ChatBriefReadyResponse, response_model_by_alias=True)
def start_chat(request: ChatStartRequest) -> ChatStartResponse | ChatOptionQuestionResponse | ChatBriefReadyResponse:
    _require_custom_copy_headline(request.copy_generation_mode, request.user_custom_headline)
    job_seed = ":".join(
        [
            request.user_input,
            request.ad_format or "",
            request.copy_generation_mode,
            _clean_optional_text(request.user_custom_headline) or "",
            _clean_optional_text(request.user_custom_subcopy) or "",
            _clean_optional_text(request.selected_reference_template_id) or "",
            _clean_optional_text(request.reference_image_path) or "",
        ]
    )
    job_id = f"chat_{abs(hash(job_seed))}"
    thread_id = f"{job_id}_thread"
    state = {
        "entry_mode": "chat_start",
        "user_input": request.user_input,
        "job_id": job_id,
        "thread_id": thread_id,
        "render_profile": request.render_profile,
        "copy_generation_mode": request.copy_generation_mode,
        "user_custom_headline": _clean_optional_text(request.user_custom_headline),
        "user_custom_subcopy": _clean_optional_text(request.user_custom_subcopy),
        "selected_reference_template_id": _clean_optional_text(request.selected_reference_template_id),
        "reference_image_path": _clean_optional_text(request.reference_image_path),
        "context": {
            "extra": {
                "ad_format": request.ad_format,
                "selected_reference_template_id": _clean_optional_text(request.selected_reference_template_id),
                "reference_image_path": _clean_optional_text(request.reference_image_path),
            }
        },
    }
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


@router.post("/answer", response_model=ChatStartResponse | ChatOptionQuestionResponse | ChatBriefReadyResponse, response_model_by_alias=True)
def answer_chat_question(request: ChatAnswerRequest) -> ChatStartResponse | ChatOptionQuestionResponse | ChatBriefReadyResponse:
    resume_payload = {
        "job_id": request.job_id,
        "thread_id": request.thread_id,
        "field": request.field,
        "value": request.value,
    }
    if request.custom_text:
        resume_payload["custom_text"] = request.custom_text

    result = get_marketing_graph().invoke(Command(resume=resume_payload), config=_thread_config(request.thread_id))
    interrupt = _interrupt_value(result)
    if interrupt and interrupt.get("type") == "option_question":
        return _option_question_response(result, interrupt)
    if result.get("copy_generation_mode") in BRIEF_READY_COPY_MODES and result.get("status") == "done":
        return _brief_ready_response(
            result,
            job_id=request.job_id,
            thread_id=request.thread_id,
            selected_channel_id=_selected_channel_id_from_result(result) or "instagram-feed",
        )

    return _copy_candidates_response(result, job_id=request.job_id, thread_id=request.thread_id, interrupt=interrupt)


@router.post("/brief", response_model=ChatBriefResponse, response_model_by_alias=True)
def create_brief(request: ChatBriefRequest) -> ChatBriefResponse:
    result = get_marketing_graph().invoke(Command(resume=_brief_resume_payload(request)), config=_thread_config(request.thread_id))
    if result.get("status") == "failed":
        raise HTTPException(status_code=422, detail=result.get("error_message") or "graph failed")

    brief = _brief_from_result(
        result,
        selected_channel_id=_normalize_selected_channel_id(request.selected_channel_id) or request.selected_channel_id,
        selected_tone=request.selected_tone or "감성적인",
        custom_direction=request.custom_direction,
    )
    return ChatBriefResponse(
        jobId=result.get("job_id") or request.job_id,
        threadId=result.get("thread_id") or request.thread_id,
        status=result.get("status") or "done",
        brief=brief,
        selectedChannelId=brief.selected_channel_id,
    )
