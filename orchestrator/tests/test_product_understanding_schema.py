from __future__ import annotations

import pytest
from pydantic import ValidationError

from orchestrator.app.schemas.input_evidence import EvidenceItem
from orchestrator.app.schemas.product_understanding import ProductUnderstanding


def test_product_understanding_accepts_open_category_path():
    item = EvidenceItem(key="product_name", value="desk lamp", source="user_text", evidence_class="verified_fact", confidence=1.0, usable_for_copy=True)

    result = ProductUnderstanding(
        product_name="desk lamp",
        normalized_product_type="desk_lamp",
        broad_category="home_and_living",
        category_path=["home_and_living", "lighting", "desk_lamp"],
        verified_facts=[item],
        product_name_evidence_ids=[item.evidence_id],
        confidence=0.9,
    )

    assert result.category_path[-1] == "desk_lamp"


def test_product_understanding_rejects_product_as_broad_category():
    with pytest.raises(ValidationError):
        ProductUnderstanding(
            product_name="desk lamp",
            broad_category="desk_lamp",
            category_path=["desk_lamp"],
            confidence=0.9,
        )


def test_product_understanding_rejects_bad_category_path_and_claims():
    with pytest.raises(ValidationError):
        ProductUnderstanding(
            product_name="desk lamp",
            broad_category="home_and_living",
            category_path=["home_and_living", "Bad Path"],
            unsupported_claim_categories=["magic_claim"],
            confidence=0.9,
        )


def test_normalized_product_type_requires_letter():
    with pytest.raises(ValidationError):
        ProductUnderstanding(
            product_name="niacinamide 5%",
            normalized_product_type="5",
            broad_category="beauty_and_personal_care",
            category_path=["beauty_and_personal_care", "5"],
            confidence=0.8,
        )
