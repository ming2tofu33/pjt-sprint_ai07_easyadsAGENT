"""Default provider for format-specific approved native-copy plans.

The provider proposes structured fields only. Grounding, operational-text
authorization, schema validation, and the final decision remain deterministic in
``format_approved_plan_service``.
"""

from __future__ import annotations

import json
import time
from typing import Any

from orchestrator.app.schemas.input_evidence import InputEvidenceBundle
from orchestrator.app.schemas.native_creative import ApprovedNativeCopyBrief
from orchestrator.app.schemas.product_understanding import ProductUnderstanding


class DefaultFormatApprovedPlanProvider:
    """Production provider used when graph state has no explicit test adapter."""

    def generate_format_approved_plan(
        self,
        *,
        ad_format: str,
        input_evidence: InputEvidenceBundle,
        product_understanding: ProductUnderstanding,
        approved_copy: ApprovedNativeCopyBrief,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        if ad_format not in {"flyer", "product_detail"}:
            raise ValueError(f"unsupported_format_plan:{ad_format}")
        return _call_openai_format_plan(
            ad_format=ad_format,
            input_evidence=input_evidence,
            product_understanding=product_understanding,
            approved_copy=approved_copy,
        )


def get_default_format_approved_plan_provider() -> DefaultFormatApprovedPlanProvider:
    """Return the lazy production provider.

    Construction performs no external call. Tests monkeypatch this factory, so
    production graph coverage stays fully offline.
    """
    return DefaultFormatApprovedPlanProvider()


def _call_openai_format_plan(
    *,
    ad_format: str,
    input_evidence: InputEvidenceBundle,
    product_understanding: ProductUnderstanding,
    approved_copy: ApprovedNativeCopyBrief,
) -> dict[str, Any]:
    from openai import OpenAI  # type: ignore
    from orchestrator.app.t2i.settings import get_openai_api_key

    started = time.perf_counter()
    prompt = _build_format_plan_prompt(
        ad_format=ad_format,
        input_evidence=input_evidence,
        product_understanding=product_understanding,
        approved_copy=approved_copy,
    )
    response = OpenAI(timeout=90).responses.create(
        model="gpt-5.4",
        input=prompt,
        temperature=0,
    )
    raw_text = getattr(response, "output_text", None) or ""
    payload = json.loads(raw_text)
    if not isinstance(payload, dict):
        raise ValueError("format_plan_payload_not_object")
    metadata = dict(payload.get("provider_metadata") or {})
    metadata.update({
        "provider": "openai",
        "model": "gpt-5.4",
        "latency_ms": max(0, round((time.perf_counter() - started) * 1000)),
    })
    payload["provider_metadata"] = metadata
    return payload


def _build_format_plan_prompt(
    *,
    ad_format: str,
    input_evidence: InputEvidenceBundle,
    product_understanding: ProductUnderstanding,
    approved_copy: ApprovedNativeCopyBrief,
) -> str:
    common = (
        "Return one JSON object only. You propose format-specific approved-copy fields; "
        "a deterministic validator will reject anything not grounded in the supplied evidence. "
        "Never rewrite headline or supporting_copy. Never invent prices, discounts, dates, "
        "phone numbers, addresses, calls to action, benefits, efficacy claims, or operational facts. "
        "If evidence is insufficient or ambiguous, return decision=manual_review with reason_codes. "
    )
    if ad_format == "product_detail":
        format_rules = (
            "Schema: {decision, reason_codes, plan:{feature_labels}}. "
            "feature_labels must contain 2 to 4 short labels copied or tightly extracted from explicit "
            "user input or verified product evidence. Do not infer unverified effects."
        )
    else:
        format_rules = (
            "Schema: {decision, reason_codes, flyer_mode, plan}. "
            "flyer_mode is editorial or promotional. Use promotional only when opening, recruitment, "
            "discount, inquiry, reservation, location, or operating information is explicit. "
            "Editorial plan keys: subtitle, body_copy, info_cards, bottom_notice. "
            "Promotional plan keys: promo_badge, subheadline, offer_line, info_items, contact_line, "
            "location_line, notice_line. Operational values must be copied exactly from user evidence; "
            "omit absent optional fields."
        )
    evidence = {
        "input_evidence": input_evidence.model_dump(),
        "product_understanding": product_understanding.model_dump(),
        "approved_primary_copy": {
            "headline": approved_copy.headline,
            "supporting_copy": approved_copy.supporting_copy,
        },
    }
    return f"{common}{format_rules}\nFORMAT: {ad_format}\nEVIDENCE: {json.dumps(evidence, ensure_ascii=False)}"
