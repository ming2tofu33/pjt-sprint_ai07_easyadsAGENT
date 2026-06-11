from __future__ import annotations

from orchestrator.app.llm.nodes.input_evidence_normalizer import build_input_evidence_bundle
from orchestrator.app.llm.nodes.product_understanding import product_understanding_node


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
