"""GPT-5.4 native copy brief service."""

from __future__ import annotations

import json
import time
from typing import Any

from orchestrator.app.llm.native_copy_policy import validate_approved_native_copy_brief
from orchestrator.app.schemas.input_evidence import InputEvidenceBundle
from orchestrator.app.schemas.native_creative import ApprovedNativeCopyBrief, CreativeExecutionPlan
from orchestrator.app.schemas.product_understanding import ProductUnderstanding


def generate_approved_native_copy_brief(
    *,
    input_evidence: InputEvidenceBundle,
    product_understanding: ProductUnderstanding,
    execution_plan: CreativeExecutionPlan,
    source_visual_analysis: dict | None,
    state: dict[str, Any],
) -> ApprovedNativeCopyBrief:
    adapter = state.get("native_copy_adapter")
    if adapter:
        payload = adapter.generate_native_copy_brief(input_evidence=input_evidence, product_understanding=product_understanding, execution_plan=execution_plan, source_visual_analysis=source_visual_analysis, state=state)
    else:
        payload = _call_openai_native_copy(input_evidence=input_evidence, product_understanding=product_understanding, execution_plan=execution_plan)
    brief = ApprovedNativeCopyBrief(**_coerce_native_copy_payload(payload.get("approved_native_copy_brief") or payload, product_name=product_understanding.product_name))
    failures = validate_approved_native_copy_brief(brief)
    if failures:
        return brief.model_copy(update={"compliance_status": "rejected", "rejection_reasons": sorted(set([*brief.rejection_reasons, *failures]))})
    return brief


def _coerce_native_copy_payload(payload: dict[str, Any], *, product_name: str) -> dict[str, Any]:
    data = dict(payload or {})
    if data.get("language") == "ko":
        data["language"] = "korean"
    data.setdefault("language", "korean")
    headline = _clean(data.get("headline") or data.get("title") or product_name)
    support = _clean(data.get("supporting_copy") or data.get("support") or data.get("subcopy"))
    closing = _clean(data.get("closing_copy") or data.get("closing"))
    action = _clean(data.get("action_cta") or data.get("cta"))
    data["headline"] = headline
    data["supporting_copy"] = support
    data["closing_copy"] = closing if not support else None
    data["action_cta"] = action
    if not data.get("message_role"):
        data["message_role"] = "headline_plus_support" if support else ("headline_plus_closing" if closing else "headline_only")
    texts = [text for text in (headline, support, closing if not support else None) if text]
    data["allowed_texts"] = list(data.get("allowed_texts") or texts)
    data.setdefault("forbidden_texts", [])
    data["max_text_blocks"] = int(data.get("max_text_blocks") or len(texts) or 1)
    data["max_total_characters"] = int(data.get("max_total_characters") or 48)
    data.setdefault("verified_evidence_ids", [])
    data.setdefault("unsupported_claim_categories", [])
    data.setdefault("compliance_status", "approved")
    data.setdefault("rejection_reasons", [])
    return data


def _clean(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _call_openai_native_copy(*, input_evidence: InputEvidenceBundle, product_understanding: ProductUnderstanding, execution_plan: CreativeExecutionPlan) -> dict[str, Any]:
    from openai import OpenAI  # type: ignore

    started = time.perf_counter()
    prompt = (
        "Return JSON only for approved_native_copy_brief_v1. Generate Korean native typography copy for one GPT Image 2 poster. "
        "Use only verified evidence and ProductUnderstanding. Max two text blocks. No action CTA unless a verified destination exists; default action_cta null. "
        "No price, discount, date, address, phone, ingredient amount, efficacy, guarantee, generic CTA, or unsupported claim. "
        "For doenjang jjigae, prefer natural Korean headline and at most one support/closing line. "
        f"ExecutionPlan: {execution_plan.model_dump_json()} InputEvidenceBundle: {input_evidence.model_dump_json()} ProductUnderstanding: {product_understanding.model_dump_json()}"
    )
    response = OpenAI(timeout=90).responses.create(model="gpt-5.4", input=prompt, temperature=0)
    payload = json.loads(getattr(response, "output_text", "") or "{}")
    payload.setdefault("provider_metadata", {"provider": "openai", "model": "gpt-5.4", "fallback_used": False, "token_usage": _usage_dict(response), "latency_ms": int((time.perf_counter() - started) * 1000)})
    return payload


def _usage_dict(response: Any) -> dict[str, int] | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    return {
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
    }
