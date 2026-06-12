from __future__ import annotations

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
