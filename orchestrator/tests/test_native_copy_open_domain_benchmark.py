import json
from pathlib import Path

from orchestrator.app.llm.native_copy_candidate_service import coerce_native_copy_strategy_bundle
from orchestrator.app.llm.native_copy_policy import contains_request_intent, direct_positioning_terms_used
from orchestrator.app.schemas.input_evidence import EvidenceItem, InputEvidenceBundle
from orchestrator.app.schemas.product_understanding import ProductUnderstanding


def test_open_domain_native_copy_v3_fixture_contract():
    cases = json.loads(Path("orchestrator/tests/fixtures/native_copy_open_domain_v3.json").read_text(encoding="utf-8"))

    for case in cases:
        fact = EvidenceItem(key="product_name", value=case["product_name"], source="user_text", evidence_class="verified_fact", confidence=1.0, usable_for_copy=True)
        evidence = InputEvidenceBundle(
            input_mode="text_only",
            user_text=case["user_text"],
            user_request_utterance=case["user_text"],
            campaign_intent="product_promotion",
            desired_positioning=case["positioning"],
            non_display_instruction_fragments=["홍보하고 싶어"] if "홍보하고 싶어" in case["user_text"] else [],
            explicit_product_mentions=[case["product_name"]],
            explicit_user_facts=[fact],
            overall_confidence=0.9,
        )
        product = ProductUnderstanding(
            product_name=case["product_name"],
            normalized_product_type="open_domain_product",
            broad_category="other",
            category_path=["other", "open_domain_product"],
            verified_facts=[fact],
            product_name_evidence_ids=[fact.evidence_id],
            confidence=0.9,
        )
        payload = {
            "candidates": [
                {"candidate_id": "product", "strategy": "minimal_identity", "headline": case["product_name"], "headline_basis_ids": [fact.evidence_id]},
                {"candidate_id": "support", "strategy": "product_name_first", "headline": case["product_name"], "supporting_copy": "감각을 담은 한 순간", "headline_basis_ids": [fact.evidence_id]},
            ]
        }

        bundle = coerce_native_copy_strategy_bundle(payload, input_evidence=evidence, product_understanding=product)
        selected = next(item for item in bundle.candidates if item.candidate_id == bundle.recommended_candidate_id)
        score = next(item for item in bundle.scorecards if item.candidate_id == selected.candidate_id)

        assert selected.headline != case["user_text"]
        assert not contains_request_intent(selected.headline)
        assert not direct_positioning_terms_used(selected.headline)
        assert score.blocked is False
        assert score.product_centeredness >= 0.8
        assert selected.action_cta is None
