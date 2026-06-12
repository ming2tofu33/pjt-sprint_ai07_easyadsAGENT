"""Suggest-candidates copy branch nodes."""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from orchestrator.app.graph.state import MarketingState, context_to_model
from orchestrator.app.llm.ad_format_presets import build_ad_format_spec
from orchestrator.app.llm.copy_quality import apply_candidate_quality_policy, apply_copy_quality_policy
from orchestrator.app.llm.copy_quality_v2 import annotate_and_rank_candidate_output, generate_copy_candidates_v2
from orchestrator.app.llm.copy_tone_policy import normalize_copy_for_business
from orchestrator.app.llm.metadata_builders import build_copy_generation_metadata, metadata_contract_to_prompt_json
from orchestrator.app.llm.node_runner import run_structured_node
from orchestrator.app.llm.nodes.format_planner import build_layout_spec
from orchestrator.app.llm.option_registry import option_label_for_value
from orchestrator.app.schemas.llm_marketing import CopyCandidate, CopyCandidateListOutput, MarketingCopy


CHANNEL_TO_AD_FORMAT = {
    "instagram-feed": "instagram_feed",
    "instagram-story": "instagram_story",
    "poster": "poster",
    "flyer": "flyer",
}


def copy_candidate_generation_node(state: MarketingState) -> dict[str, Any]:
    metadata_contract = build_copy_generation_metadata(
        state,
        node_name="copy_candidate_generation",
        output_schema=CopyCandidateListOutput,
    )
    output, llm_metadata = run_structured_node(
        state,
        node_name="copy_candidate_generation",
        output_schema=CopyCandidateListOutput,
        prompt=build_candidate_prompt(state, metadata_contract),
        fallback_fn=lambda: build_rule_based_candidate_output(state),
        risk_level="medium",
        confidence=0.5,
        latency_budget="interactive",
        metadata=metadata_contract,
    )
    if not isinstance(output, CopyCandidateListOutput) or not output.candidates:
        output = build_rule_based_candidate_output(state)
        llm_metadata = {**llm_metadata, "fallback_used": True, "fallback_reason": "invalid_candidate_output"}
    max_candidates = int((state.get("plan_policy") or {}).get("max_candidates") or 3)
    output, llm_metadata = validate_or_fallback_candidate_output(state, output, llm_metadata)
    output = annotate_and_rank_candidate_output(output, state=state, max_candidates=max_candidates)
    candidates = [apply_candidate_quality_policy(candidate) for candidate in normalize_candidate_ids(output.candidates[: max(1, max_candidates)])]
    recommended_candidate_id = output.recommended_candidate_id or candidates[0].id
    output = CopyCandidateListOutput(
        candidates=candidates,
        recommended_candidate_id=recommended_candidate_id,
        metadata={**output.metadata, "source_node": "copy_candidate_generation", "llm_metadata": llm_metadata},
    )
    candidate_origin = classify_copy_candidate_origin(output.metadata, llm_metadata)
    serialized = [candidate.model_dump() for candidate in candidates]
    serialized, compliance_records, compliance_status, compliance_ready = _attach_compliance_badges(
        serialized, state
    )
    return {
        "copy_candidates": serialized,
        "copy_compliance": compliance_records,
        "copy_compliance_status": compliance_status,
        "copy_compliance_publication_ready": compliance_ready,
        "copy_candidate_origin": candidate_origin,
        "copywriting_output": output.model_dump(),
        "copy_generation_mode": "suggest_candidates",
        "copy_required": True,
        "text_overlay_pending": True,
        "model_selections": state.get("model_selections", []),
        "llm_call_results": state.get("llm_call_results", []),
        "status": "generating_copy_candidates",
    }


def build_rule_based_candidate_output(state: MarketingState) -> CopyCandidateListOutput:
    max_candidates = int((state.get("plan_policy") or {}).get("max_candidates") or 3)
    output = generate_copy_candidates_v2(state, max_candidates=max_candidates)
    return CopyCandidateListOutput(
        candidates=output.candidates,
        recommended_candidate_id=output.recommended_candidate_id,
        metadata={
            "source_node": "copy_candidate_generation",
            "fallback": "rule_based_v2",
            "message_strategy": output.message_strategy.model_dump(),
            "copy_quality_v2_ranking": output.ranking.model_dump(),
        },
    )


def classify_copy_candidate_origin(metadata: dict[str, Any], llm_metadata: dict[str, Any]) -> str:
    if not llm_metadata:
        return "unknown"
    if not llm_metadata.get("fallback_used"):
        return "llm"
    fallback_reason = llm_metadata.get("fallback_reason")
    if fallback_reason == "free_plan_deterministic_fallback":
        return "rule_based"
    if metadata.get("fallback") == "rule_based" and not fallback_reason:
        return "rule_based"
    return "fallback"


def validate_or_fallback_candidate_output(
    state: MarketingState,
    output: CopyCandidateListOutput,
    llm_metadata: dict[str, Any],
) -> tuple[CopyCandidateListOutput, dict[str, Any]]:
    blocked: list[str] = []
    normalized: list[CopyCandidate] = []
    context = context_to_model(state.get("context"))
    for candidate in output.candidates:
        reason = hallucinated_fact_reason(candidate, state)
        if reason:
            blocked.append(reason)
            continue
        policy = normalize_copy_for_business(
            {"headline": candidate.headline, "subcopy": candidate.subcopy, "cta": candidate.cta},
            context.business_type,
            mode="generated",
        )
        copy = policy["normalized_copy"]
        normalized.append(
            candidate.model_copy(
                update={
                    "headline": copy["headline"],
                    "subcopy": copy["subcopy"],
                    "cta": copy["cta"],
                    "metadata": {**candidate.metadata, "copy_tone_policy": policy},
                }
            )
        )
    if not normalized:
        fallback = build_rule_based_candidate_output(state)
        return fallback, {**llm_metadata, "fallback_used": True, "fallback_reason": "llm_candidate_validation_failed", "blocked_claims": sorted(set(blocked))}
    return output.model_copy(update={"candidates": normalized}), {**llm_metadata, "blocked_claims": sorted(set(blocked))}


def hallucinated_fact_reason(candidate: CopyCandidate, state: MarketingState) -> str | None:
    context = context_to_model(state.get("context"))
    provided = " ".join(
        str(value or "")
        for value in (
            context.price_or_discount,
            context.location_text,
            context.contact_or_order_method,
            state.get("user_input"),
        )
    )
    text = " ".join(str(value or "") for value in (candidate.headline, candidate.subcopy, candidate.cta))
    if re_search_phone(text) and not re_search_phone(provided):
        return "invented_phone_number"
    if "%" in text and "%" not in provided:
        return "invented_discount_rate"
    if re_search_price(text) and not re_search_price(provided):
        return "invented_price"
    for marker in ("주소", "강남구", "서울", "부산", "대구", "인천"):
        if marker in text and marker not in provided:
            return "invented_address"
    return None


def re_search_phone(text: str) -> bool:
    import re

    return bool(re.search(r"0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}", text or ""))


def re_search_price(text: str) -> bool:
    import re

    return bool(re.search(r"(₩\s*\d|[0-9][0-9,]*\s*원)", text or ""))


def build_restaurant_candidates(item: str) -> list[CopyCandidate]:
    return [
        CopyCandidate(
            id="copy_1",
            headline=f"오늘 저녁, 따뜻한 {item} 한 판",
            subcopy="함께 모이기 좋은 시간",
            cta="예약 문의하기",
            tone_label="emotional",
            rationale="Warm emotional version.",
        ),
        CopyCandidate(
            id="copy_2",
            headline=f"회식은 역시 {item}",
            subcopy="든든하게 즐기는 우리 가게 대표 메뉴",
            cta="지금 예약하기",
            tone_label="direct",
            rationale="Direct benefit-first version.",
        ),
        CopyCandidate(
            id="copy_3",
            headline="오늘 자리, 미리 잡아두세요",
            subcopy=f"{item} 모임은 편하게 예약하고 즐기세요",
            cta="예약 문의하기",
            tone_label="cta",
            rationale="Action-oriented version.",
        ),
    ]


def build_cafe_candidates(item: str, promotion_goal: str | None) -> list[CopyCandidate]:
    if promotion_goal == "discount_event":
        return [
            CopyCandidate(
                id="copy_1",
                headline=f"{item}, 오늘 더 달콤하게",
                subcopy="놓치기 아쉬운 혜택을 준비했어요",
                cta="혜택 확인하기",
                tone_label="fresh",
                rationale="Cafe discount version without restaurant gathering wording.",
            ),
            CopyCandidate(
                id="copy_2",
                headline=f"달콤한 {item} 혜택",
                subcopy="가볍게 들러 즐기기 좋은 카페 이벤트",
                cta="오늘 혜택 보기",
                tone_label="bright",
                rationale="Benefit-first cafe version.",
            ),
            CopyCandidate(
                id="copy_3",
                headline=f"오늘의 카페 타임은 {item}",
                subcopy="기분 좋은 한 잔에 혜택까지 더했어요",
                cta="지금 확인하기",
                tone_label="emotional",
                rationale="Soft cafe visit CTA version.",
            ),
        ]
    if promotion_goal == "new_launch":
        return [
            CopyCandidate(
                id="copy_1",
                headline=f"새롭게 만나는 {item}",
                subcopy="카페에서 준비한 새로운 한 잔을 만나보세요",
                cta="신메뉴 보기",
                tone_label="fresh",
                rationale="Cafe new-launch version.",
            ),
            CopyCandidate(
                id="copy_2",
                headline=f"첫 한 잔의 설렘, {item}",
                subcopy="오늘 가장 먼저 맛보고 싶은 신메뉴",
                cta="지금 맛보기",
                tone_label="emotional",
                rationale="Emotional cafe launch version.",
            ),
            CopyCandidate(
                id="copy_3",
                headline=f"{item} 출시",
                subcopy="달콤한 메뉴가 새롭게 준비됐어요",
                cta="메뉴 확인하기",
                tone_label="clear",
                rationale="Direct cafe launch version.",
            ),
        ]
    return [
        CopyCandidate(
            id="copy_1",
            headline=f"{item} 한 잔의 여유",
            subcopy="잠깐의 휴식이 필요한 순간에 어울리는 메뉴",
            cta="메뉴 확인하기",
            tone_label="emotional",
            rationale="Default cafe version.",
        ),
        CopyCandidate(
            id="copy_2",
            headline=f"오늘은 {item} 어때요?",
            subcopy="가볍게 들러 즐기기 좋은 카페 메뉴",
            cta="지금 확인하기",
            tone_label="friendly",
            rationale="Friendly cafe visit version.",
        ),
        CopyCandidate(
            id="copy_3",
            headline=f"달콤하게 쉬어가는 {item}",
            subcopy="카페에서 준비한 기분 좋은 한 잔",
            cta="방문해보기",
            tone_label="warm",
            rationale="Warm cafe version.",
        ),
    ]


def build_generic_candidates(item: str, promotion_goal: str | None) -> list[CopyCandidate]:
    if promotion_goal == "discount_event":
        return [
            CopyCandidate(
                id="copy_1",
                headline=f"{item} 혜택을 지금 확인하세요",
                subcopy="필요한 정보를 간결하게 담은 이벤트 안내",
                cta="혜택 확인하기",
                tone_label="direct",
                rationale="Generic discount version.",
            ),
            CopyCandidate(
                id="copy_2",
                headline=f"놓치기 아쉬운 {item} 이벤트",
                subcopy="오늘 확인하면 좋은 혜택을 준비했어요",
                cta="자세히 보기",
                tone_label="benefit",
                rationale="Benefit-first generic version.",
            ),
            CopyCandidate(
                id="copy_3",
                headline=f"지금 만나는 {item}",
                subcopy="상품/서비스의 장점을 쉽게 확인해보세요",
                cta="지금 확인하기",
                tone_label="clear",
                rationale="Clear generic version.",
            ),
        ]
    return [
        CopyCandidate(
            id="copy_1",
            headline=f"{item}을 지금 확인하세요",
            subcopy="필요한 정보를 간결하게 담은 안내",
            cta="자세히 보기",
            tone_label="clear",
            rationale="Default generic version.",
        ),
        CopyCandidate(
            id="copy_2",
            headline=f"새롭게 만나는 {item}",
            subcopy="우리 가게가 준비한 내용을 확인해보세요",
            cta="지금 확인하기",
            tone_label="friendly",
            rationale="Friendly generic version.",
        ),
        CopyCandidate(
            id="copy_3",
            headline=f"{item}이 필요한 순간",
            subcopy="간결하고 명확하게 전하는 광고 메시지",
            cta="문의하기",
            tone_label="direct",
            rationale="Action-oriented generic version.",
        ),
    ]


def build_reservation_service_candidates(item: str) -> list[CopyCandidate]:
    return [
        CopyCandidate(
            id="copy_1",
            headline=f"방문 전, {item}로 편하게",
            subcopy="기다림은 줄이고 원하는 시간에 맞춰요",
            cta="지금 예약하기",
            tone_label="clear",
            rationale="Reservation-service version without product-only wording.",
        ),
        CopyCandidate(
            id="copy_2",
            headline="오늘 일정, 미리 잡아두세요",
            subcopy=f"{item}로 더 여유롭게 방문하세요",
            cta="예약 문의하기",
            tone_label="direct",
            rationale="Direct reservation CTA version.",
        ),
        CopyCandidate(
            id="copy_3",
            headline="원하는 시간에 편하게 방문하세요",
            subcopy="예약하고 오시면 더 빠르게 안내해드려요",
            cta="방문 예약하기",
            tone_label="cta",
            rationale="Action-oriented reservation version.",
        ),
    ]


def display_item_or_service(value: str | None) -> str:
    if not value:
        return "상품"
    label = option_label_for_value("item_or_service", value)
    if label:
        return label
    if "_" in value and value.isascii():
        return "상품/서비스"
    return value


def is_reservation_service_item(raw_value: str | None, display_value: str, extra: dict[str, Any]) -> bool:
    option_value = extra.get("item_or_service_option_value")
    return option_value == "reservation_service" or raw_value == "reservation_service" or "예약" in display_value or display_value.endswith("서비스")


def normalize_candidate_ids(candidates: list[CopyCandidate]) -> list[CopyCandidate]:
    normalized: list[CopyCandidate] = []
    for index, candidate in enumerate(candidates, start=1):
        normalized.append(candidate.model_copy(update={"id": candidate.id or f"copy_{index}"}))
    return normalized


def build_candidate_prompt(state: MarketingState, metadata_contract: dict[str, Any] | None = None) -> str:
    context = context_to_model(state.get("context"))
    tone = state.get("tone_binding_output") or {}
    metadata_contract = metadata_contract or build_copy_generation_metadata(
        state,
        node_name="copy_candidate_generation",
        output_schema=CopyCandidateListOutput,
    )
    return (
        "Generate structured Korean ad copy candidates. "
        f"business_type={context.business_type}, item_or_service={context.item_or_service}, "
        f"promotion_goal={context.promotion_goal}, brand_tone={context.brand_tone}, "
        f"forbidden_claims={tone.get('forbidden_claims', [])}. "
        "Do not invent phone numbers, addresses, prices, discounts, or event periods. "
        f"metadata_contract={metadata_contract_to_prompt_json(metadata_contract)}."
    )


def copy_candidate_selection_interrupt_node(state: MarketingState) -> dict[str, Any]:
    candidates = list(state.get("copy_candidates", []))
    output = state.get("copywriting_output") or {}
    payload = {
        "type": "copy_candidate_selection",
        "job_id": state["job_id"],
        "thread_id": state["thread_id"],
        "candidates": candidates,
        "recommended_candidate_id": output.get("recommended_candidate_id") or _recommended_candidate_id_from_candidates(candidates),
        "copy_candidate_origin": state.get("copy_candidate_origin") or "unknown",
    }
    resume_payload = interrupt(payload)
    return {"copy_selection": resume_payload, "status": "waiting_copy_selection"}


def state_update_selected_copy_node(state: MarketingState) -> dict[str, Any]:
    selection = dict(state.get("copy_selection") or {})
    selection.setdefault("selected_copy_id", state.get("selected_copy_id"))
    selection.setdefault("selected_channel_id", state.get("selected_channel_id"))
    selection.setdefault("selected_ad_format", state.get("selected_ad_format"))
    selection.setdefault("selected_tone", state.get("selected_tone"))
    selection.setdefault("custom_direction", state.get("custom_direction"))
    selection.setdefault("user_custom_headline", state.get("user_custom_headline"))
    selection.setdefault("user_custom_subcopy", state.get("user_custom_subcopy"))
    recommended_id = _recommended_candidate_id_from_state(state)
    selected_id = selection.get("selected_copy_id") or recommended_id
    candidates = list(state.get("copy_candidates", []))
    candidate = next((item for item in candidates if item.get("id") == selected_id), None)
    warnings: list[str] = []
    custom_headline = clean_optional_text(selection.get("user_custom_headline"))
    custom_subcopy = clean_optional_text(selection.get("user_custom_subcopy"))
    if custom_headline:
        if candidate is None and selected_id:
            warnings.append("Invalid selected_copy_id; custom copy applied without a matching base candidate.")
        copy = apply_copy_quality_policy(MarketingCopy(
            headline=custom_headline,
            subcopy=custom_subcopy,
            cta=None,
            hashtags=[],
            metadata={
                "selected_copy_id": selected_id,
                "copy_resolution": "manual_edit",
                "warnings": warnings,
                "source_node": "state_update_selected_copy",
            },
        ))
        selection_update = build_frontend_selection_state_update(state, selection)
        return {
            "marketing_copy": copy.model_dump(),
            "selected_copy_id": selected_id,
            "user_custom_headline": custom_headline,
            "user_custom_subcopy": custom_subcopy,
            **selection_update,
            "copy_required": True,
            "text_overlay_pending": True,
            "status": "applying_selected_copy",
        }
    if candidate is None:
        candidate = next((item for item in candidates if item.get("id") == recommended_id), None)
        selected_id = recommended_id
        warnings.append("Invalid selected_copy_id; recommended candidate fallback applied.")
    if candidate is None:
        return {"status": "failed", "error_message": "No copy candidate available for selection."}
    copy = apply_copy_quality_policy(MarketingCopy(
        headline=candidate["headline"],
        subcopy=candidate.get("subcopy"),
        cta=candidate.get("cta"),
        hashtags=candidate.get("hashtags", []),
        metadata={"selected_copy_id": selected_id, "warnings": warnings, "source_node": "state_update_selected_copy"},
    ))
    selection_update = build_frontend_selection_state_update(state, selection)
    return {
        "marketing_copy": copy.model_dump(),
        "selected_copy_id": selected_id,
        **selection_update,
        "copy_required": True,
        "text_overlay_pending": True,
        "status": "applying_selected_copy",
    }


def _recommended_candidate_id_from_state(state: MarketingState) -> str:
    output = state.get("copywriting_output") or {}
    return str(output.get("recommended_candidate_id") or _recommended_candidate_id_from_candidates(list(state.get("copy_candidates", []))))


def _recommended_candidate_id_from_candidates(candidates: list[dict[str, Any]]) -> str:
    if not candidates:
        return "copy_1"
    for candidate in candidates:
        metadata = candidate.get("metadata") or {}
        score = metadata.get("copy_quality_v2_score") or {}
        if score and not score.get("hard_blocked"):
            return str(candidate.get("id") or "copy_1")
    return str(candidates[0].get("id") or "copy_1")


def build_frontend_selection_state_update(state: MarketingState, selection: dict[str, Any]) -> dict[str, Any]:
    selected_channel_id = clean_optional_text(selection.get("selected_channel_id"))
    selected_ad_format = clean_optional_text(selection.get("selected_ad_format"))
    if not selected_ad_format and selected_channel_id:
        selected_ad_format = CHANNEL_TO_AD_FORMAT.get(selected_channel_id)
    selected_tone = clean_optional_text(selection.get("selected_tone"))
    custom_direction = clean_optional_text(selection.get("custom_direction"))

    current_brief = dict(state.get("current_brief") or {})
    context = context_to_model(state.get("context")).model_dump()
    context_extra = dict(context.get("extra") or {})
    update: dict[str, Any] = {}

    if selected_channel_id:
        update["selected_channel_id"] = selected_channel_id
        current_brief["selected_channel_id"] = selected_channel_id
        context_extra["selected_channel_id"] = selected_channel_id
    if selected_ad_format:
        update["selected_ad_format"] = selected_ad_format
        current_brief["requested_ad_format"] = selected_ad_format
        context_extra["ad_format"] = selected_ad_format
        context_extra["selected_ad_format"] = selected_ad_format
        ad_format_spec = build_ad_format_spec(selected_ad_format)
        update["ad_format_spec"] = ad_format_spec.model_dump()
        update["layout_spec"] = build_layout_spec(selected_ad_format).model_dump()
    if selected_tone:
        update["selected_tone"] = selected_tone
        current_brief["selected_tone"] = selected_tone
        context["brand_tone"] = selected_tone
        context_extra["selected_tone"] = selected_tone
    if custom_direction:
        update["custom_direction"] = custom_direction
        current_brief["custom_direction"] = custom_direction
        context_extra["custom_direction"] = custom_direction

    if update:
        context["extra"] = context_extra
        update["context"] = context
        update["current_brief"] = current_brief
    return update


def clean_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


_COMPLIANCE_STATUS_RANK: dict[str, int] = {
    "pass": 0,
    "warn": 1,
    "evidence_required": 2,
    "blocked": 3,
}


def _attach_compliance_badges(
    candidates: list[dict[str, Any]],
    state: MarketingState,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str, bool]:
    """각 후보 dict에 metadata.compliance 배지를 삽입하고 집계 상태를 반환한다.

    Returns:
        (updated_candidates, compliance_records, worst_status, all_publication_ready)
    """
    from orchestrator.app.compliance.service import get_compliance_service

    context = context_to_model(state.get("context"))
    svc = get_compliance_service()

    compliance_records: list[dict[str, Any]] = []
    worst_status = "pass"
    all_publication_ready = True

    for candidate in candidates:
        copy_dict: dict[str, Any] = {
            "headline": candidate.get("headline") or "",
            "subcopy": candidate.get("subcopy") or "",
            "cta": candidate.get("cta") or "",
        }
        result = svc.check_copy(copy_dict, context.business_type)
        candidate.setdefault("metadata", {})["compliance"] = {
            "status": result.status,
            "finding_count": len(result.findings),
            "disabled": not result.publication_ready,
        }
        compliance_records.append({
            "candidate_id": candidate.get("id"),
            "status": result.status,
            "finding_count": len(result.findings),
            "publication_ready": result.publication_ready,
            "findings": [f.model_dump() for f in result.findings],
        })
        if _COMPLIANCE_STATUS_RANK.get(result.status, 0) > _COMPLIANCE_STATUS_RANK.get(worst_status, 0):
            worst_status = result.status
        if not result.publication_ready:
            all_publication_ready = False

    return candidates, compliance_records, worst_status, all_publication_ready
