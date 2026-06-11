from __future__ import annotations

import pytest
from pydantic import ValidationError

from orchestrator.app.schemas.input_evidence import EvidenceItem, InputEvidenceBundle


def test_input_evidence_bundle_serializes_canonical_fields():
    bundle = InputEvidenceBundle(
        input_mode="text_only",
        user_text="카페 신메뉴 치즈케이크 홍보",
        explicit_product_mentions=["치즈케이크"],
        explicit_user_facts=[
            EvidenceItem(key="product_name", value="치즈케이크", source="user_text", evidence_class="verified_fact", confidence=1.0, usable_for_copy=True)
        ],
        unknown_fields=["price"],
        overall_confidence=0.9,
    )

    data = bundle.model_dump()

    assert data["schema_version"] == "input_evidence_bundle_v1"
    assert data["explicit_user_facts"][0]["evidence_class"] == "verified_fact"
    assert "image_b64" not in str(data)
    assert "image_bytes" not in str(data)


def test_evidence_confidence_is_bounded():
    with pytest.raises(ValidationError):
        EvidenceItem(key="product_name", value="cake", source="user_text", evidence_class="verified_fact", confidence=1.5, usable_for_copy=True)


def test_image_only_rejects_user_text_facts():
    with pytest.raises(ValidationError):
        InputEvidenceBundle(
            input_mode="image_only",
            explicit_user_facts=[
                EvidenceItem(key="product_name", value="치즈케이크", source="user_text", evidence_class="verified_fact", confidence=1.0, usable_for_copy=True)
            ],
            overall_confidence=0.8,
        )


def test_runtime_paths_are_not_valid_evidence_values():
    with pytest.raises(ValidationError):
        InputEvidenceBundle(
            input_mode="text_only",
            explicit_user_facts=[
                EvidenceItem(key="product_name", value="data/outputs/job/final.png", source="user_text", evidence_class="verified_fact", confidence=1.0, usable_for_copy=True)
            ],
            overall_confidence=0.8,
        )
