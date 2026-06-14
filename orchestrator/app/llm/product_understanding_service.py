"""Shared ProductUnderstanding generation service."""

from __future__ import annotations

import json
from typing import Any

from orchestrator.app.llm.node_runner import run_structured_node
from orchestrator.app.llm.nodes.product_understanding import build_minimal_product_understanding
from orchestrator.app.llm.product_understanding_policy import validate_product_understanding
from orchestrator.app.schemas.input_evidence import InputEvidenceBundle
from orchestrator.app.schemas.product_understanding import ProductUnderstanding


def generate_product_understanding(bundle: InputEvidenceBundle, *, state: dict[str, Any]) -> ProductUnderstanding:
    prompt = (
        "You receive a canonical InputEvidenceBundle. Generate ProductUnderstanding only. "
        "Do not generate advertising copy, headline, CTA, slogan, offer, or visual style. "
        "Keep verified facts separate from visual observations and inferences. "
        "Every verified fact must reference an existing evidence item. "
        "Do not invent price, discounts, ingredients, origin, manufacturing method, certification, efficacy, health effects, beauty effects, numeric claims, scarcity, or social proof. "
        "product_name is the product identity only; put launch/campaign words in campaign_modifiers. "
        "Keep product_name verbatim in the user's original characters; for Korean names keep the Korean (e.g. '돌반지' stays '돌반지', never romanized as 'dolphinji'). "
        "normalized_product_type must be a valid English snake_case product type when the product identity is known, including for non-English product names. "
        "If an explicit product mention exists and there is no identity conflict, classify it into the provided top-level broad-category taxonomy using general category knowledge. "
        "Do not return broad_category='other' for a clearly named food, beverage, beauty, fashion, home, technology, education, hospitality, automotive, or local service product. "
        "category_path is open vocabulary, first item must be broad_category, and must include hierarchy when product identity is known. "
        "If evidence is insufficient, set clarification_required/manual_review_required instead of guessing. "
        f"InputEvidenceBundle: {json.dumps(bundle.model_dump(), ensure_ascii=False)}"
    )
    fallback = lambda: build_minimal_product_understanding(bundle)
    output, metadata = run_structured_node(
        state,
        node_name="product_understanding",
        output_schema=ProductUnderstanding,
        prompt=prompt,
        fallback_fn=fallback,
        risk_level="medium",
        confidence=bundle.overall_confidence,
        latency_budget="interactive",
        metadata={"task": "product_understanding_v1"},
    )
    result = validate_product_understanding(output, bundle)
    provider_metadata = dict(result.provider_metadata or {})
    provider_metadata.update(metadata or {})
    return result.model_copy(update={"provider_metadata": provider_metadata})
