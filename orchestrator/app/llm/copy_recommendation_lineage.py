"""Helpers for copy recommendation lineage and stage snapshots."""

from __future__ import annotations

import re
from typing import Any

from orchestrator.app.llm.copy_fallbacks import build_message_strategy
from orchestrator.app.llm.copy_grounding import evaluate_copy_grounding
from orchestrator.app.schemas.llm_marketing import CopyCandidate, MarketingContext

def build_copy_input_projection(state: dict[str, Any]) -> dict[str, Any]:
    context = _dict(state.get("context"))
    current_brief = _dict(state.get("current_brief"))
    campaign_context = _dict(state.get("campaign_context"))
    return {
        "user_input_present": bool((state.get("user_input") or "").strip()),
        "business_type": _string_or_none(context.get("business_type")),
        "item_or_service": _string_or_none(context.get("item_or_service")),
        "promotion_goal": _string_or_none(context.get("promotion_goal")),
        "campaign_intent": _string_or_none(current_brief.get("campaign_intent")) or _string_or_none(campaign_context.get("campaign_intent")),
        "brand_tone": _string_or_none(context.get("brand_tone")),
        "target_persona": _string_or_none(context.get("target_persona")),
        "time_context": _string_or_none(context.get("time_context")),
        "price_or_discount": _string_or_none(context.get("price_or_discount")),
        "location_text": _string_or_none(context.get("location_text")),
        "contact_or_order_method": _string_or_none(context.get("contact_or_order_method")),
        "requested_ad_format": _requested_ad_format(state),
        "copy_generation_mode": _string_or_none(state.get("copy_generation_mode")),
    }


def build_copy_prompt_projection(metadata_contract: dict[str, Any], state: dict[str, Any], *, prompt: str | None = None) -> dict[str, Any]:
    available_state = _dict(metadata_contract.get("available_state"))
    context = _dict(available_state.get("context") or state.get("context"))
    constraints = _dict(metadata_contract.get("constraints"))
    prompt_text = str(prompt or "")
    return {
        "service_name_present": bool(_string_or_none(context.get("item_or_service"))),
        "target_audience_present": bool(_string_or_none(context.get("target_persona"))),
        "explicit_fact_count": len(_explicit_fact_refs(state)),
        "campaign_role_present": bool(_string_or_none(context.get("promotion_goal"))),
        "ad_format_present": bool(_requested_ad_format(state)),
        "copy_tone_profile_present": bool(_dict(available_state.get("tone_binding_output"))),
        "required_fact_refs": _explicit_fact_refs(state),
        "candidate_count_requested": int(_dict(available_state.get("plan_policy")).get("max_candidates") or 3),
        "diversity_instruction_present": any(
            phrase in prompt_text
            for phrase in (
                "Return exactly three distinct candidates",
                "different message angle",
                "different persuasion angle",
                "avoid repeating the same sentence structure",
            )
        ),
        "forbidden_claim_count": len(list(constraints.get("forbidden_claims") or [])),
        "do_not_invent_enabled": bool(constraints.get("do_not_invent") or constraints.get("no_user_unprovided_claims")),
    }


def build_copy_stage_snapshots(
    candidates: list[dict[str, Any]],
    *,
    stage: str,
    source: str,
    input_projection: dict[str, Any] | None = None,
    compliance_records: list[dict[str, Any]] | None = None,
    ranked_ids: list[str] | None = None,
    parent_candidate_ids: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    compliance_by_id = {
        str(item.get("candidate_id") or ""): str(item.get("status") or "")
        for item in (compliance_records or [])
        if item.get("candidate_id")
    }
    rank_by_id = {candidate_id: index + 1 for index, candidate_id in enumerate(ranked_ids or [])}
    snapshots: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_id = str(candidate.get("id") or "")
        snapshots.append(
            {
                "candidate_id": candidate_id,
                "parent_candidate_id": _string_or_none((parent_candidate_ids or {}).get(candidate_id)),
                "stage": stage,
                "headline": _string_or_none(candidate.get("headline")) or "",
                "supporting_copy": _string_or_none(candidate.get("subcopy")),
                "source": source,
                "grounded_fact_refs": candidate_grounded_fact_refs(candidate, input_projection=input_projection),
                "compliance_status": compliance_by_id.get(candidate_id) or None,
                "rewrite_reason": _rewrite_reason(candidate),
                "rank": rank_by_id.get(candidate_id),
            }
        )
    return snapshots


def build_copy_llm_call_lineage(
    state: dict[str, Any],
    llm_metadata: dict[str, Any],
    *,
    raw_candidate_count: int,
    parsed_candidate_count: int,
    final_candidate_count: int,
) -> dict[str, Any]:
    selection = _dict(llm_metadata.get("model_selection"))
    result = _dict(llm_metadata.get("llm_call_result"))
    usage = _dict(result.get("token_usage"))
    llm_attempted = bool(llm_metadata.get("llm_attempted"))
    selected_provider = _string_or_none(selection.get("provider"))
    executed_provider = _string_or_none(result.get("provider")) if llm_attempted else None
    provider = executed_provider or selected_provider or "unknown"
    selected_model = (
        _string_or_none(selection.get("model_name"))
        or _string_or_none(selection.get("provider_profile"))
        or _string_or_none(selection.get("selected_model_class"))
    )
    executed_model = _string_or_none(result.get("model_name")) if llm_attempted else None
    model = executed_model or selected_model or "unknown"
    call_id = _string_or_none(_dict(result.get("metadata")).get("provider_request_id")) or (
        f"{_string_or_none(state.get('thread_id')) or 'thread'}:{_string_or_none(state.get('job_id')) or 'job'}:"
        f"{_string_or_none(selection.get('node_name')) or 'copy_candidate_generation'}"
    )
    metadata_available = llm_attempted and (bool(_dict(result.get("metadata"))) or bool(usage))
    fallback_used = bool(llm_metadata.get("fallback_used"))
    fallback_reason = _string_or_none(llm_metadata.get("fallback_reason"))
    copy_source_mode = "llm"
    if fallback_used:
        if provider == "mock" or fallback_reason == "provider_mock_fallback":
            copy_source_mode = "mock"
        elif fallback_reason == "free_plan_deterministic_fallback":
            copy_source_mode = "rule_based"
        else:
            copy_source_mode = "fallback"
    status = "success" if result.get("success") and not fallback_used else "fallback" if fallback_used else "failed"
    return {
        "trace_id": _string_or_none(state.get("thread_id")) or _string_or_none(state.get("job_id")) or "copy_trace",
        "thread_id": _string_or_none(state.get("thread_id")),
        "job_id": _string_or_none(state.get("job_id")),
        "stage": _string_or_none(selection.get("node_name")) or "copy_candidate_generation",
        "provider": provider,
        "selected_provider": selected_provider,
        "executed_provider": executed_provider,
        "model": model,
        "adapter": adapter_name_for_provider(provider),
        "selected_model": selected_model,
        "executed_model": executed_model,
        "selected_adapter": adapter_name_for_provider(selected_provider),
        "executed_adapter": adapter_name_for_provider(executed_provider),
        "provider_request_id": _string_or_none(_dict(result.get("metadata")).get("provider_request_id")),
        "call_id": call_id,
        "input_tokens": _int_or_none(usage.get("input_tokens")),
        "output_tokens": _int_or_none(usage.get("output_tokens")),
        "cached_input_tokens": _int_or_none(usage.get("cached_input_tokens") or usage.get("cached_tokens")),
        "latency_ms": result.get("latency_ms"),
        "copy_source_mode": copy_source_mode,
        "call_attempted": llm_attempted,
        "call_succeeded": bool(result.get("success")) and not fallback_used,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "metadata_available": metadata_available,
        "raw_candidate_count": raw_candidate_count,
        "parsed_candidate_count": parsed_candidate_count,
        "final_candidate_count": final_candidate_count,
        "status": status,
        "error_code": _string_or_none(result.get("error")) or fallback_reason,
    }


def adapter_name_for_provider(provider: str | None) -> str:
    names = {
        "openai": "OpenAIAdapter",
        "openai_compatible": "OpenAICompatibleLLMAdapter",
        "local_openai_compat": "LocalOpenAICompatAdapter",
        "mock": "MockLLMAdapter",
    }
    return names.get((provider or "").strip().lower(), "UnknownAdapter")


def candidate_grounded_fact_refs(candidate: dict[str, Any], *, input_projection: dict[str, Any] | None = None) -> list[str]:
    text = _candidate_text(candidate)
    refs: list[str] = []
    projection = input_projection or {}
    fact_values = {
        "item_or_service": _string_or_none(projection.get("item_or_service")),
        "target_persona": _string_or_none(projection.get("target_persona")),
        "time_context": _string_or_none(projection.get("time_context")),
        "contact_or_order_method": _string_or_none(projection.get("contact_or_order_method")),
        "price_or_discount": _string_or_none(projection.get("price_or_discount")),
        "location_text": _string_or_none(projection.get("location_text")),
    }
    for field_name, field_value in fact_values.items():
        if field_value and _matches_fact_value(text, field_name, field_value):
            refs.append(field_name)
    return refs


def build_candidate_quality_metrics(
    candidates: list[dict[str, Any]],
    *,
    input_projection: dict[str, Any],
    context: MarketingContext,
) -> dict[str, Any]:
    explicit_facts = [
        (field_name, _string_or_none(input_projection.get(field_name)))
        for field_name in (
            "item_or_service",
            "target_persona",
            "time_context",
            "contact_or_order_method",
            "price_or_discount",
            "location_text",
        )
        if _string_or_none(input_projection.get(field_name))
    ]
    fact_hits: dict[str, int] = {field_name: 0 for field_name, _ in explicit_facts}
    generic_only_candidate_count = 0
    unsupported_claim_count = 0
    angle_labels: set[str] = set()
    duplicate_pairs = 0
    seen_texts: set[str] = set()
    grounded_candidates = 0
    strategy = build_message_strategy(context)

    for candidate in candidates:
        text = _candidate_text(candidate)
        if text in seen_texts:
            duplicate_pairs += 1
        seen_texts.add(text)
        metadata = _dict(candidate.get("metadata"))
        score = _dict(metadata.get("copy_quality_v2_score"))
        grounded_refs = candidate_grounded_fact_refs(candidate, input_projection=input_projection)
        if _is_generic_only_candidate(text) and not grounded_refs:
            generic_only_candidate_count += 1
        angle = _string_or_none(candidate.get("angle"))
        if angle:
            angle_labels.add(angle)
        if any(str(warning).startswith("unsupported_claim:") for warning in list(score.get("warnings") or [])):
            unsupported_claim_count += 1
        grounding = evaluate_copy_grounding(_to_candidate_model(candidate), context=context, strategy=strategy)
        if grounding.grounded:
            grounded_candidates += 1
        for field_name, field_value in explicit_facts:
            if _matches_fact_value(text, field_name, field_value or ""):
                fact_hits[field_name] += 1

    covered_fact_count = sum(1 for count in fact_hits.values() if count > 0)
    explicit_fact_count = len(explicit_facts)
    return {
        "candidate_count": len(candidates),
        "explicit_fact_count": explicit_fact_count,
        "fact_hits_by_field": fact_hits,
        "lexical_fact_coverage": round(covered_fact_count / explicit_fact_count, 3) if explicit_fact_count else 0.0,
        "grounded_fact_coverage": round(covered_fact_count / explicit_fact_count, 3) if explicit_fact_count else 0.0,
        "grounded_candidate_count": grounded_candidates,
        "generic_only_candidate_count": generic_only_candidate_count,
        "unsupported_claim_count": unsupported_claim_count,
        "distinct_angle_count": len(angle_labels),
        "duplicate_candidate_count": duplicate_pairs,
    }


def _candidate_text(candidate: dict[str, Any]) -> str:
    return " ".join(
        value.strip()
        for value in (
            _string_or_none(candidate.get("headline")),
            _string_or_none(candidate.get("subcopy")),
            _string_or_none(candidate.get("cta")),
        )
        if value and value.strip()
    ).lower()


def _requested_ad_format(state: dict[str, Any]) -> str | None:
    current_brief = _dict(state.get("current_brief"))
    context = _dict(state.get("context"))
    extra = _dict(context.get("extra"))
    return (
        _string_or_none(current_brief.get("requested_ad_format"))
        or _string_or_none(current_brief.get("requestedAdFormat"))
        or _string_or_none(extra.get("ad_format"))
        or _string_or_none(extra.get("adFormat"))
        or _string_or_none(state.get("ad_format"))
    )


def _explicit_fact_refs(state: dict[str, Any]) -> list[str]:
    context = _dict(state.get("context"))
    refs: list[str] = []
    for field in (
        "item_or_service",
        "promotion_goal",
        "target_persona",
        "time_context",
        "price_or_discount",
        "location_text",
        "contact_or_order_method",
        "brand_tone",
    ):
        if _string_or_none(context.get(field)):
            refs.append(field)
    return refs


def _rewrite_reason(candidate: dict[str, Any]) -> str | None:
    metadata = _dict(candidate.get("metadata"))
    copy_tone_policy = _dict(metadata.get("copy_tone_policy"))
    applied = list(_dict(copy_tone_policy).get("applied_fixes") or [])
    if applied:
        return ",".join(str(item) for item in applied)
    return None


def _matches_fact_value(text: str, field_name: str, field_value: str) -> bool:
    normalized_text = re.sub(r"\s+", "", text.lower())
    normalized_value = re.sub(r"\s+", "", field_value.lower())
    if not normalized_value:
        return False
    if normalized_value in normalized_text:
        return True
    aliases = {
        "contact_or_order_method": ("문의", "상담", "전화", "예약", "call", "dm"),
        "time_context": ("평일", "저녁", "야간", "주말", "오전", "오후"),
        "target_persona": ("직장인", "강남", "학생", "사장님", "자영업자"),
        "price_or_discount": ("%", "원", "$"),
    }
    return any(token in normalized_text and token in normalized_value for token in aliases.get(field_name, ()))


def _is_generic_only_candidate(text: str) -> bool:
    generic_markers = ("한계없는시간", "감성을더하다", "당신을위한선택", "새로운경험", "일상을바꾸는", "지금만나보세요")
    normalized = re.sub(r"\s+", "", text.lower())
    return any(marker in normalized for marker in generic_markers)


def _to_candidate_model(candidate: dict[str, Any]) -> CopyCandidate:
    return CopyCandidate(
        id=str(candidate.get("id") or "copy_1"),
        headline=str(candidate.get("headline") or ""),
        subcopy=_string_or_none(candidate.get("subcopy")),
        cta=_string_or_none(candidate.get("cta")),
        angle=_string_or_none(candidate.get("angle")),
        metadata=_dict(candidate.get("metadata")),
    )


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
