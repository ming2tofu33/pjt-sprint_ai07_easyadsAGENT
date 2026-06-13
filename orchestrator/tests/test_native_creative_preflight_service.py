from orchestrator.app.llm.native_copy_policy import build_native_prompt_package
from orchestrator.app.llm.native_creative_preflight_service import review_native_creative_preflight
from orchestrator.app.schemas.input_evidence import EvidenceItem, InputEvidenceBundle
from orchestrator.app.schemas.native_creative import ApprovedNativeCopyBrief
from orchestrator.app.schemas.product_understanding import ProductUnderstanding


def _evidence():
    fact = EvidenceItem(key="product_name", value="된장찌개", source="user_text", evidence_class="verified_fact", confidence=1.0, usable_for_copy=True)
    return InputEvidenceBundle(
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


def _product(evidence):
    return ProductUnderstanding(
        product_name="된장찌개",
        normalized_product_type="doenjang_jjigae",
        broad_category="food_and_beverage",
        category_path=["food_and_beverage", "doenjang_jjigae"],
        verified_facts=evidence.explicit_user_facts,
        product_name_evidence_ids=[evidence.explicit_user_facts[0].evidence_id],
        confidence=0.9,
    )


def _brief(evidence, product, headline="깊고 구수한 한 그릇"):
    return ApprovedNativeCopyBrief(
        headline=headline,
        supporting_copy=None,
        closing_copy=None,
        action_cta=None,
        language="korean",
        message_role="headline_only",
        allowed_texts=[headline],
        forbidden_texts=[],
        max_text_blocks=1,
        max_total_characters=48,
        verified_evidence_ids=list(product.product_name_evidence_ids),
        unsupported_claim_categories=[],
        compliance_status="approved",
        rejection_reasons=[],
        source_user_request=evidence.user_request_utterance,
        non_display_instructions=evidence.non_display_instruction_fragments,
        product_identity=product.product_name,
        desired_positioning=evidence.desired_positioning,
        campaign_intent=evidence.campaign_intent,
        transformation_performed=True,
        product_evidence_ids=list(product.product_name_evidence_ids),
        creative_direction_evidence_ids=[],
        copy_claim_evidence_ids=[],
    )


def test_semantic_preflight_rejects_meta_instruction_leakage():
    evidence = _evidence()
    product = _product(evidence)
    brief = _brief(evidence, product, headline="고급진 된장찌개를 홍보하고 싶어")
    package = build_native_prompt_package(product_understanding=product.model_dump(), copy_brief=brief, input_evidence=evidence.model_dump())

    review = review_native_creative_preflight(input_evidence=evidence, product_understanding=product, copy_brief=brief, prompt_package=package, state={})

    assert review.decision == "rejected"
    assert "meta_instruction_leakage_detected" in review.failure_reasons


def test_semantic_preflight_passes_adapter_approved_review(monkeypatch):
    evidence = _evidence()
    product = _product(evidence)
    brief = _brief(evidence, product)
    package = build_native_prompt_package(product_understanding=product.model_dump(), copy_brief=brief, input_evidence=evidence.model_dump())

    approved = {
        "decision": "approved",
        "copy_grounded": True,
        "claims_supported": True,
        "language_natural": True,
        "generic_cta_absent": True,
        "text_budget_valid": True,
        "native_typography_suitable": True,
        "product_visual_direction_valid": True,
        "consumer_facing_copy": True,
        "meta_instruction_absent": True,
        "user_request_transformed": True,
        "product_identity_clean": True,
        "copy_relevance_score": 0.9,
        "headline_quality_score": 0.85,
        "positioning_alignment_score": 0.8,
        "failure_reasons": [],
        "revision_instructions": [],
    }

    def fake_run_structured_node(*args, **kwargs):
        return kwargs["output_schema"](**approved), {"fallback_used": False, "llm_call_result": {"provider": "openai", "model_name": "gpt-5.4", "token_usage": {"input_tokens": 1, "output_tokens": 1}}}

    monkeypatch.setattr("orchestrator.app.llm.native_creative_preflight_service.run_structured_node", fake_run_structured_node)

    review = review_native_creative_preflight(input_evidence=evidence, product_understanding=product, copy_brief=brief, prompt_package=package, state={"user_plan": "premium"})

    assert review.decision == "approved"
    assert review.provider_metadata["provider"] == "openai"
    assert review.provider_metadata["model"] == "gpt-5.4"
