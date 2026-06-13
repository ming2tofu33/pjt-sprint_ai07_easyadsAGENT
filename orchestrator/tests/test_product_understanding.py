"""Consolidated product understanding tests.

Merged from:
- orchestrator/tests/test_open_domain_product_understanding.py
- orchestrator/tests/test_product_understanding_actual_contract.py
- orchestrator/tests/test_product_understanding_node.py
- orchestrator/tests/test_product_understanding_policy.py
- orchestrator/tests/test_product_understanding_schema.py
"""

from __future__ import annotations



# ===== from test_open_domain_product_understanding.py =====
from orchestrator.app.llm.nodes.input_evidence_normalizer import build_input_evidence_bundle
from orchestrator.app.llm.nodes.product_understanding import product_understanding_node
from scripts import _actual_creative_pipeline as pipeline


def test_open_domain_holdout_products_do_not_require_product_enum():
    cases = [
        ("desk lamp", "home_and_living"),
        ("car detailing service", "local_service"),
        ("language course", "education"),
        ("wireless keyboard", "technology"),
        ("flower bouquet", "other"),
    ]
    for product, broad_category in cases:
        bundle = build_input_evidence_bundle({"user_input": f"promote {product}", "context": {"item_or_service": product}})
        fact = bundle.explicit_user_facts[0]
        update = product_understanding_node(
            {
                "input_evidence_bundle": bundle.model_dump(),
                "product_understanding_llm_response": {
                    "product_name": product,
                    "normalized_product_type": product.replace(" ", "_"),
                    "broad_category": broad_category,
                    "category_path": [broad_category, product.replace(" ", "_")],
                    "verified_facts": [fact.model_dump()],
                    "product_name_evidence_ids": [fact.evidence_id],
                    "confidence": 0.8,
                },
            }
        )

        assert update["product_understanding_status"] == "completed"
        assert update["product_understanding"]["product_name"] == product


def test_korean_food_product_type_uses_general_taxonomy_not_other():
    evidence = {
        "explicit_product_mentions": ["된장찌개 메뉴"],
        "explicit_user_facts": [
            {
                "evidence_id": "evidence_food",
                "key": "product_name",
                "value": "된장찌개 메뉴",
                "normalized_value": "된장찌개 메뉴",
                "source": "user_text",
                "evidence_class": "verified_fact",
                "confidence": 1.0,
                "usable_for_copy": True,
            }
        ],
        "visual_observations": [],
        "asset_metadata_evidence": [],
        "brand_profile_evidence": [],
        "reference_evidence": [],
        "creative_inferences": [],
        "input_conflicts": [],
        "unknown_fields": [],
    }

    data = pipeline._coerce_product_understanding_candidate(
        {"product_name": "된장찌개 메뉴", "broad_category": "other"},
        evidence,
    )

    assert data["normalized_product_type"] == "doenjang_jjigae"
    assert data["broad_category"] == "food_and_beverage"
    assert data["category_path"] == ["food_and_beverage", "doenjang_jjigae"]
    assert data["product_name_evidence_ids"] == ["evidence_food"]


def test_korean_food_product_name_separates_campaign_modifier():
    evidence = {
        "explicit_product_mentions": ["된장찌개 메뉴"],
        "explicit_user_facts": [
            {
                "evidence_id": "evidence_food",
                "key": "product_name",
                "value": "된장찌개 메뉴",
                "normalized_value": "된장찌개 메뉴",
                "source": "user_text",
                "evidence_class": "verified_fact",
                "confidence": 1.0,
                "usable_for_copy": True,
            }
        ],
        "visual_observations": [],
        "asset_metadata_evidence": [],
        "brand_profile_evidence": [],
        "reference_evidence": [],
        "creative_inferences": [],
        "input_conflicts": [],
        "unknown_fields": [],
    }

    data = pipeline._coerce_product_understanding_candidate(
        {"product_name": "된장찌개 메뉴", "broad_category": "other"},
        evidence,
    )

    assert data["product_name"] == "된장찌개"
    assert data["campaign_modifiers"] == ["메뉴 홍보"]
    assert data["normalized_product_type"] == "doenjang_jjigae"


def test_korean_serum_product_type_does_not_collapse_to_numeric():
    evidence = {
        "explicit_product_mentions": ["나이아신아마이드 5% 세럼"],
        "explicit_user_facts": [
            {
                "evidence_id": "evidence_serum",
                "key": "product_name",
                "value": "나이아신아마이드 5% 세럼",
                "normalized_value": "나이아신아마이드 5% 세럼",
                "source": "user_text",
                "evidence_class": "verified_fact",
                "confidence": 1.0,
                "usable_for_copy": True,
            }
        ],
        "visual_observations": [],
        "asset_metadata_evidence": [],
        "brand_profile_evidence": [],
        "reference_evidence": [],
        "creative_inferences": [],
        "input_conflicts": [],
        "unknown_fields": [],
    }

    data = pipeline._coerce_product_understanding_candidate(
        {"product_name": "5", "normalized_product_type": "5", "broad_category": "other"},
        evidence,
    )

    assert data["product_name"] == "나이아신아마이드 5% 세럼"
    assert data["normalized_product_type"] == "niacinamide_5_serum"
    assert data["broad_category"] == "beauty_and_personal_care"


# ===== from test_product_understanding_actual_contract.py =====
import argparse
import json
from types import SimpleNamespace

from scripts import run_final_composite_quality_actual as runner


def test_product_understanding_benchmark_stop_after_writes_artifacts(monkeypatch, tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "desk_lamp",
                        "input_mode": "text_only",
                        "user_text": "promote a desk lamp",
                        "expected_broad_category": "home_and_living",
                        "expected_category_prefix": ["home_and_living"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    class Adapter:
        def normalize_input_evidence(self, *, request, model):
            return {
                "input_mode": request.input_mode,
                "user_text": request.user_text,
                "explicit_product_mentions": ["desk lamp"],
                "explicit_user_facts": [
                    {"key": "product_name", "value": "desk lamp", "source": "user_text", "evidence_class": "verified_fact", "confidence": 1.0, "usable_for_copy": True}
                ],
                "visual_observations": [],
                "unknown_fields": [],
                "unresolved_questions": [],
                "input_conflicts": [],
                "overall_confidence": 0.95,
                "provider_metadata": {"normalizer": {"provider": "openai", "model": "gpt-5.4", "fallback_used": False, "token_usage": {"input_tokens": 1, "output_tokens": 1}}},
            }

        def understand_product(self, *, request, evidence, model):
            fact = evidence["explicit_user_facts"][0]
            return {
                "product_understanding": {
                    "product_name": "desk lamp",
                    "normalized_product_type": "desk_lamp",
                    "broad_category": "home_and_living",
                    "category_path": ["home_and_living", "lighting", "desk_lamp"],
                    "verified_facts": [fact],
                    "product_name_evidence_ids": [fact["evidence_id"]],
                    "confidence": 0.9,
                },
                "provider_metadata": {"provider": "openai", "model": model, "fallback_used": False, "token_usage": {"input_tokens": 1, "output_tokens": 1}},
            }

    monkeypatch.setattr(
        runner,
        "_canonical_runtime",
        lambda args: SimpleNamespace(copy_model="gpt-5.4", vision_model="gpt-5.4", openai_adapter=Adapter(), call_budget=None),
    )
    args = argparse.Namespace(benchmark_manifest=str(manifest), seed=62, copy_model="gpt-5.4", vlm_model="gpt-5.4", stop_after="product_understanding")

    summary = runner.run_product_understanding_benchmark(args=args, output_dir=tmp_path / "out")

    assert summary["status"] == "completed"
    assert (tmp_path / "out" / "cases" / "desk_lamp" / "product_understanding.json").exists()
    assert summary["image_generation_performed"] is False


# ===== from test_product_understanding_node.py =====
from orchestrator.app.llm.nodes.input_evidence_normalizer import build_input_evidence_bundle
from orchestrator.app.llm.nodes.product_understanding import product_understanding_node


def test_product_understanding_node_preserves_context_and_writes_understanding_state():
    bundle = build_input_evidence_bundle({"user_input": "promote a desk lamp", "context": {"item_or_service": "desk lamp"}})

    update = product_understanding_node({"input_evidence_bundle": bundle.model_dump(), "context": {}})

    assert update["product_understanding_status"] == "completed"
    assert update["product_understanding"]["product_name"] == "desk lamp"
    assert "context" not in update


def test_product_understanding_node_uses_llm_response_without_copy_fields():
    bundle = build_input_evidence_bundle({"user_input": "promote a language course", "context": {"item_or_service": "language course"}})
    fact = bundle.explicit_user_facts[0]

    update = product_understanding_node(
        {
            "input_evidence_bundle": bundle.model_dump(),
            "product_understanding_llm_response": {
                "product_name": "language course",
                "normalized_product_type": "language_course",
                "broad_category": "education",
                "category_path": ["education", "language_learning", "language_course"],
                "verified_facts": [fact.model_dump()],
                "product_name_evidence_ids": [fact.evidence_id],
                "confidence": 0.9,
            },
        }
    )

    assert update["product_understanding_status"] == "completed"
    assert "headline" not in update["product_understanding"]


def test_product_understanding_node_recovers_numeric_korean_brand_name():
    bundle = build_input_evidence_bundle(
        {
            "user_input": '"82고기" 고깃집 오픈 홍보 광고 만들어줘',
            "context": {"item_or_service": "82고기"},
            "user_plan": "free",
        }
    )

    update = product_understanding_node({"input_evidence_bundle": bundle.model_dump(), "user_plan": "free"})

    assert update["product_understanding_status"] != "failed"
    assert update["product_understanding"]["product_name"] == "82고기"
    assert update["product_understanding"]["normalized_product_type"] == "82_meat"
    assert update["product_understanding"]["broad_category"] == "food_and_beverage"


# ===== from test_product_understanding_policy.py =====
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


# ===== from test_product_understanding_schema.py =====
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
