from orchestrator.app.llm.native_copy_candidate_service import coerce_native_copy_strategy_bundle
from orchestrator.app.schemas.input_evidence import EvidenceItem, InputEvidenceBundle
from orchestrator.app.schemas.product_understanding import ProductUnderstanding


def _fixture():
    fact = EvidenceItem(key="product_name", value="된장찌개", source="user_text", evidence_class="verified_fact", confidence=1.0, usable_for_copy=True)
    evidence = InputEvidenceBundle(
        input_mode="text_only",
        user_text="고급진 된장찌개를 홍보하고 싶어",
        user_request_utterance="고급진 된장찌개를 홍보하고 싶어",
        campaign_intent="product_promotion",
        desired_positioning=["premium", "refined"],
        non_display_instruction_fragments=["홍보하고 싶어"],
        explicit_product_mentions=["된장찌개"],
        explicit_user_facts=[fact],
        overall_confidence=0.9,
    )
    product = ProductUnderstanding(
        product_name="된장찌개",
        normalized_product_type="doenjang_jjigae",
        broad_category="food_and_beverage",
        category_path=["food_and_beverage", "stew"],
        verified_facts=[fact],
        product_name_evidence_ids=[fact.evidence_id],
        confidence=0.9,
    )
    return evidence, product


def test_candidate_bundle_coerces_four_candidates_and_selects_unblocked():
    evidence, product = _fixture()
    payload = {
        "candidates": [
            {"candidate_id": "good", "strategy": "minimal_identity", "headline": "된장찌개", "supporting_copy": "구수한 한 그릇", "headline_basis_ids": product.product_name_evidence_ids},
            {"candidate_id": "bad", "strategy": "product_name_first", "headline": "품격 있게 즐기는 된장찌개", "headline_basis_ids": product.product_name_evidence_ids},
        ]
    }

    bundle = coerce_native_copy_strategy_bundle(payload, input_evidence=evidence, product_understanding=product)

    assert len(bundle.candidates) == 1
    assert bundle.effective_candidate_count == 1
    assert bundle.candidate_capacity == "single_minimal"
    assert bundle.recommended_candidate_id is not None
    selected = next(score for score in bundle.scorecards if score.candidate_id == bundle.recommended_candidate_id)
    assert selected.blocked is False


def test_candidate_bundle_strips_support_when_only_product_name_is_verified():
    fact = EvidenceItem(key="product_name", value="Product A", source="user_text", evidence_class="verified_fact", confidence=1.0, usable_for_copy=True)
    evidence = InputEvidenceBundle(
        input_mode="text_only",
        user_text="Promote Product A as premium",
        user_request_utterance="Promote Product A as premium",
        campaign_intent="product_promotion",
        desired_positioning=["premium"],
        explicit_product_mentions=["Product A"],
        explicit_user_facts=[fact],
        overall_confidence=0.9,
    )
    product = ProductUnderstanding(
        product_name="Product A",
        normalized_product_type="product",
        broad_category="other",
        category_path=["other"],
        verified_facts=[fact],
        product_name_evidence_ids=[fact.evidence_id],
        confidence=0.9,
    )

    bundle = coerce_native_copy_strategy_bundle(
        {
            "candidates": [
                {
                    "candidate_id": "candidate_1",
                    "strategy": "product_name_first",
                    "headline": "Product A",
                    "supporting_copy": "A calmer moment for every day",
                    "headline_basis_ids": [fact.evidence_id],
                }
            ]
        },
        input_evidence=evidence,
        product_understanding=product,
    )

    assert bundle.candidates[0].headline == "Product A"
    assert bundle.candidates[0].supporting_copy is None
    assert bundle.candidates[0].text_block_count == 1
