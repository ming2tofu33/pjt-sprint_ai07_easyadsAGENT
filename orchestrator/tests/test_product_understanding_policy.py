from __future__ import annotations

import pytest

from orchestrator.app.llm.product_understanding_policy import validate_product_understanding
from orchestrator.app.schemas.input_evidence import EvidenceItem, InputEvidenceBundle
from orchestrator.app.schemas.product_understanding import ProductUnderstanding


def _bundle() -> InputEvidenceBundle:
    fact = EvidenceItem(key="product_name", value="desk lamp", source="user_text", evidence_class="verified_fact", confidence=1.0, usable_for_copy=True)
    return InputEvidenceBundle(input_mode="text_only", user_text="promote a desk lamp", explicit_product_mentions=["desk lamp"], explicit_user_facts=[fact], overall_confidence=0.95)


def test_validate_product_understanding_recomputes_confidence():
    bundle = _bundle()
    fact = bundle.explicit_user_facts[0]
    result = ProductUnderstanding(
        product_name="desk lamp",
        normalized_product_type="desk_lamp",
        broad_category="home_and_living",
        category_path=["home_and_living", "lighting", "desk_lamp"],
        verified_facts=[fact],
        product_name_evidence_ids=[fact.evidence_id],
        confidence=0.1,
    )

    validated = validate_product_understanding(result, bundle)

    assert validated.confidence > 0.8
    assert validated.clarification_required is False


def test_verified_fact_must_reference_bundle_evidence():
    bundle = _bundle()
    external = EvidenceItem(key="product_name", value="desk lamp", source="user_text", evidence_class="verified_fact", confidence=1.0, usable_for_copy=True)
    result = ProductUnderstanding(
        product_name="desk lamp",
        normalized_product_type="desk_lamp",
        broad_category="home_and_living",
        category_path=["home_and_living", "lighting", "desk_lamp"],
        verified_facts=[external],
        product_name_evidence_ids=[external.evidence_id],
        confidence=0.9,
    )

    with pytest.raises(ValueError):
        validate_product_understanding(result, bundle)

