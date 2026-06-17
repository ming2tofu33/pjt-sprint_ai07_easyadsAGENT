"""Helpers for copy recommendation lineage and stage snapshots."""

from __future__ import annotations

from typing import Any


def build_copy_input_projection(state: dict[str, Any]) -> dict[str, Any]:
    context = _dict(state.get("context"))
    return {
        "user_input_present": bool((state.get("user_input") or "").strip()),
        "business_type": _string_or_none(context.get("business_type")),
        "item_or_service": _string_or_none(context.get("item_or_service")),
        "promotion_goal": _string_or_none(context.get("promotion_goal")),
        "brand_tone": _string_or_none(context.get("brand_tone")),
        "target_persona": _string_or_none(context.get("target_persona")),
        "time_context": _string_or_none(context.get("time_context")),
        "price_or_discount": _string_or_none(context.get("price_or_discount")),
        "location_text": _string_or_none(context.get("location_text")),
        "contact_or_order_method": _string_or_none(context.get("contact_or_order_method")),
        "requested_ad_format": _requested_ad_format(state),
        "copy_generation_mode": _string_or_none(state.get("copy_generation_mode")),
    }


def build_copy_prompt_projection(metadata_contract: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    available_state = _dict(metadata_contract.get("available_state"))
    context = _dict(available_state.get("context") or state.get("context"))
    constraints = _dict(metadata_contract.get("constraints"))
    return {
        "service_name_present": bool(_string_or_none(context.get("item_or_service"))),
        "target_audience_present": bool(_string_or_none(context.get("target_persona"))),
        "explicit_fact_count": len(_explicit_fact_refs(state)),
        "campaign_role_present": bool(_string_or_none(context.get("promotion_goal"))),
        "ad_format_present": bool(_requested_ad_format(state)),
        "copy_tone_profile_present": bool(_dict(available_state.get("tone_binding_output"))),
        "required_fact_refs": _explicit_fact_refs(state),
        "candidate_count_requested": int(_dict(available_state.get("plan_policy")).get("max_candidates") or 3),
        "diversity_instruction_present": True,
        "forbidden_claim_count": len(list(constraints.get("forbidden_claims") or [])),
        "do_not_invent_enabled": bool(constraints.get("do_not_invent") or constraints.get("no_user_unprovided_claims")),
    }


def build_copy_stage_snapshots(
    candidates: list[dict[str, Any]],
    *,
    stage: str,
    source: str,
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
                "grounded_fact_refs": candidate_grounded_fact_refs(candidate),
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
    provider = _string_or_none(result.get("provider")) or _string_or_none(selection.get("provider")) or "unknown"
    model = (
        _string_or_none(result.get("model_name"))
        or _string_or_none(selection.get("model_name"))
        or _string_or_none(selection.get("provider_profile"))
        or _string_or_none(selection.get("selected_model_class"))
        or "unknown"
    )
    call_id = _string_or_none(_dict(result.get("metadata")).get("provider_request_id")) or (
        f"{_string_or_none(state.get('thread_id')) or 'thread'}:{_string_or_none(state.get('job_id')) or 'job'}:"
        f"{_string_or_none(selection.get('node_name')) or 'copy_candidate_generation'}"
    )
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
        "model": model,
        "adapter": adapter_name_for_provider(provider),
        "provider_request_id": _string_or_none(_dict(result.get("metadata")).get("provider_request_id")),
        "call_id": call_id,
        "input_tokens": _int_or_none(usage.get("input_tokens")),
        "output_tokens": _int_or_none(usage.get("output_tokens")),
        "cached_input_tokens": _int_or_none(usage.get("cached_input_tokens") or usage.get("cached_tokens")),
        "latency_ms": result.get("latency_ms"),
        "copy_source_mode": copy_source_mode,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
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


def candidate_grounded_fact_refs(candidate: dict[str, Any]) -> list[str]:
    text = " ".join(
        value.strip()
        for value in (
            _string_or_none(candidate.get("headline")),
            _string_or_none(candidate.get("subcopy")),
            _string_or_none(candidate.get("cta")),
        )
        if value and value.strip()
    ).lower()
    refs: list[str] = []
    markers = (
        ("item_or_service", text),
        ("contact_or_order_method", text),
        ("price_or_discount", text),
        ("location_text", text),
        ("time_context", text),
    )
    for name, haystack in markers:
        if name in str(candidate.get("metadata", {})):
            refs.append(name)
        elif name == "price_or_discount" and any(token in haystack for token in ("%", "원", "$")):
            refs.append(name)
        elif name == "contact_or_order_method" and any(token in haystack for token in ("문의", "예약", "주문", "call", "dm")):
            refs.append(name)
    return refs


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
