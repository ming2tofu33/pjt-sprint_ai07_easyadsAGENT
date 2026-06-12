from __future__ import annotations

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
