"""Guarded brief interpretation helper."""

from __future__ import annotations

import re
from typing import Any

from orchestrator.app.graph.state import MarketingState
from orchestrator.app.llm.metadata_builders import metadata_contract_to_prompt_json
from orchestrator.app.llm.node_runner import run_structured_node
from orchestrator.app.llm.settings import get_llm_settings
from orchestrator.app.schemas.brief_llm import BriefInterpreterOutput


ALLOWED_BRIEF_LLM_PLANS = {"economic", "premium", "internal_benchmark"}
BRIEF_INTERPRETER_CONFIDENCE_THRESHOLD = 0.65

BUSINESS_TYPE_MAP = {
    "cafe": "cafe",
    "restaurant": "restaurant",
    "beauty": "beauty_salon",
    "fitness": "fitness",
}

PROMOTION_GOAL_MAP = {
    "new_launch": "new_launch",
    "discount_event": "discount_event",
    "brand_awareness": "brand_awareness",
    "reservation": "reservation_cta",
    "visit_increase": "reservation_cta",
    "seasonal_campaign": "seasonal_campaign",
    "product_detail": "product_detail",
}

COPY_GENERATION_MODES = {"suggest_candidates", "auto_pilot", "no_copy", "custom_input"}

INVENTED_FACT_PATTERNS = [
    re.compile(r"\b010[-\s]?\d{3,4}[-\s]?\d{4}\b"),
    re.compile(r"\b\d{2,3}[-\s]?\d{3,4}[-\s]?\d{4}\b"),
    re.compile(r"\b\d{1,3}(?:,\d{3})+\s*원\b"),
    re.compile(r"\d+\s*%"),
    re.compile(r"(?:무료|공짜|1\+1|반값|최저가|주소|영업시간|오시는 길)"),
]


def interpret_brief_with_llm(state: MarketingState, text: str) -> tuple[BriefInterpreterOutput | None, dict[str, Any]]:
    if not should_attempt_brief_interpreter_llm(state):
        return None, {"llm_attempted": False, "fallback_used": True, "fallback_reason": "brief_interpreter_not_enabled"}
    metadata = build_brief_interpreter_metadata(state, text)
    output, llm_metadata = run_structured_node(
        state,
        node_name="validator",
        output_schema=BriefInterpreterOutput,
        prompt=build_brief_interpreter_prompt(state, text, metadata),
        fallback_fn=lambda: None,
        risk_level="low",
        confidence=0.4,
        latency_budget="interactive",
        metadata=metadata,
    )
    if not isinstance(output, BriefInterpreterOutput):
        return None, {**llm_metadata, "fallback_used": True, "fallback_reason": "invalid_brief_interpreter_output"}
    if output.confidence < BRIEF_INTERPRETER_CONFIDENCE_THRESHOLD:
        return None, {**llm_metadata, "fallback_used": True, "fallback_reason": "low_brief_interpreter_confidence"}
    return output, llm_metadata


def should_attempt_brief_interpreter_llm(state: MarketingState) -> bool:
    if str(state.get("user_plan") or "free") not in ALLOWED_BRIEF_LLM_PLANS:
        return False
    settings = get_llm_settings()
    return settings.enable_api_call is True


def build_brief_interpreter_metadata(state: MarketingState, text: str) -> dict[str, Any]:
    context = state.get("context") or {}
    return {
        "node": "brief_interpreter",
        "user_plan": state.get("user_plan"),
        "text_preview": text[:240],
        "context": {
            "business_type": context.get("business_type") if isinstance(context, dict) else None,
            "item_or_service": context.get("item_or_service") if isinstance(context, dict) else None,
            "promotion_goal": context.get("promotion_goal") if isinstance(context, dict) else None,
        },
        "allowed_output_fields": [
            "business_type",
            "item_or_service",
            "promotion_goal",
            "target_persona",
            "tone",
            "copy_generation_mode",
            "missing_fields",
            "confidence",
            "warnings",
            "unverifiable_claims",
        ],
    }


def build_brief_interpreter_prompt(state: MarketingState, text: str, metadata: dict[str, Any]) -> str:
    return (
        "Interpret a Korean small-business advertising brief into BriefInterpreterOutput. "
        "Use only facts present in the user brief. Do not invent phone numbers, addresses, prices, "
        "discounts, dates, medical claims, or performance guarantees. "
        f"User brief: {text[:800]}. "
        f"metadata_contract={metadata_contract_to_prompt_json(metadata)}."
    )


def build_context_updates_from_brief_interpreter(
    output: BriefInterpreterOutput,
    source_text: str = "",
) -> tuple[dict[str, Any], list[str]]:
    updates: dict[str, Any] = {}
    warnings: list[str] = []

    business_type = BUSINESS_TYPE_MAP.get(str(output.business_type or ""))
    if business_type:
        updates["business_type"] = business_type

    promotion_goal = PROMOTION_GOAL_MAP.get(str(output.promotion_goal or ""))
    if promotion_goal:
        updates["promotion_goal"] = promotion_goal

    if output.item_or_service:
        if has_invented_fact_risk(output.item_or_service, source_text):
            warnings.append("item_or_service ignored because it may contain unverifiable commercial facts")
        else:
            updates["item_or_service"] = output.item_or_service.strip()[:80]

    if output.target_persona:
        if has_invented_fact_risk(output.target_persona, source_text):
            warnings.append("target_persona ignored because it may contain unverifiable commercial facts")
        else:
            updates["target_persona"] = output.target_persona.strip()[:80]

    if output.tone and output.tone != "unknown":
        updates["brand_tone"] = output.tone

    if output.copy_generation_mode in COPY_GENERATION_MODES:
        updates["copy_generation_mode"] = output.copy_generation_mode

    for claim in output.unverifiable_claims:
        if claim and has_invented_fact_risk(claim, source_text):
            warnings.append(f"unverifiable_claim: {claim[:80]}")
    return updates, warnings


def has_invented_fact_risk(value: str, source_text: str = "") -> bool:
    if not value:
        return False
    normalized_source = normalize_fact_text(source_text)
    for pattern in INVENTED_FACT_PATTERNS:
        for match in pattern.finditer(value):
            matched = match.group(0)
            if matched and normalize_fact_text(matched) not in normalized_source:
                return True
    return False


def normalize_fact_text(value: str) -> str:
    return "".join(str(value or "").split()).lower()
