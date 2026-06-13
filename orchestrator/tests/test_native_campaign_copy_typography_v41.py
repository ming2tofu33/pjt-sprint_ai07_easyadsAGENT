from orchestrator.app.llm.native_campaign_message_service import (
    has_meaningful_support_basis,
    plan_native_campaign_message,
    plan_native_typography_expression,
)
from orchestrator.app.llm.native_copy_candidate_service import coerce_native_copy_strategy_bundle
from orchestrator.app.llm.native_copy_policy import build_native_prompt_package, score_native_copy_candidate
from orchestrator.app.llm.nodes.input_evidence_normalizer import build_input_evidence_bundle
from orchestrator.app.schemas.native_creative import ApprovedNativeCopyBrief, NativeCopyCandidate
from orchestrator.app.schemas.product_understanding import ProductUnderstanding


DOENJANG = "\ub41c\uc7a5\ucc0c\uac1c"
NEW_MENU = "\uc2e0\uba54\ub274"
INTRODUCE = "\uc18c\uac1c\ud558\uace0 \uc2f6\uc5b4"


def _product(bundle) -> ProductUnderstanding:
    product_id = bundle.explicit_user_facts[0].evidence_id
    return ProductUnderstanding(
        product_name=bundle.explicit_product_mentions[0],
        campaign_status=bundle.campaign_status,
        campaign_intent=bundle.campaign_intent,
        desired_positioning=bundle.desired_positioning,
        broad_category="food_and_beverage",
        category_path=["food_and_beverage", "restaurant_food", "stew"],
        normalized_product_type="stew",
        verified_facts=list(bundle.explicit_user_facts),
        product_name_evidence_ids=[product_id],
        confidence=0.9,
    )


def test_product_identity_separates_new_menu_campaign_status():
    bundle = build_input_evidence_bundle({"user_input": f"{DOENJANG} {NEW_MENU}\ub97c {INTRODUCE}"})

    assert bundle.explicit_product_mentions == [DOENJANG]
    assert bundle.campaign_status == "new_menu"
    assert bundle.campaign_intent == "new_product_launch"
    assert any(item.key == "campaign_status" and item.value == "new_menu" for item in bundle.explicit_user_facts)


def test_generic_introduction_alone_does_not_create_launch_role():
    bundle = build_input_evidence_bundle({"user_input": f"{DOENJANG}\ub97c {INTRODUCE}"})
    product = _product(bundle)

    plan = plan_native_campaign_message(
        input_evidence=bundle,
        product_understanding=product,
        placement="restaurant_poster",
        promotion_goal=bundle.campaign_intent or "product_promotion",
        source_visual_analysis=None,
        state={},
    )

    assert plan.campaign_role != "new_product_introduction"
    assert plan.launch_visibility_policy == "implicit"
    assert plan.campaign_context_is_display_copy is False


def test_launch_role_does_not_force_launch_headline():
    bundle = build_input_evidence_bundle({"user_input": f"{DOENJANG} {NEW_MENU}\ub97c {INTRODUCE}"})
    product = _product(bundle)

    plan = plan_native_campaign_message(
        input_evidence=bundle,
        product_understanding=product,
        placement="restaurant_poster",
        promotion_goal=bundle.campaign_intent or "new_product_launch",
        source_visual_analysis=None,
        state={},
    )

    assert plan.campaign_role == "new_product_introduction"
    assert plan.headline_function == "product_identity"
    assert plan.launch_visibility_policy == "implicit"
    assert plan.campaign_context_is_display_copy is False


def test_product_name_only_is_not_meaningful_support_basis():
    bundle = build_input_evidence_bundle({"user_input": DOENJANG})
    product = _product(bundle)

    assert has_meaningful_support_basis(input_evidence=bundle, product_understanding=product) is False


def test_generic_launch_support_is_removed_not_hardcoded():
    bundle = build_input_evidence_bundle({"user_input": f"{DOENJANG} {NEW_MENU}\ub97c {INTRODUCE}"})
    product = _product(bundle)
    payload = {
        "campaign_message_plan": {
            "campaign_role": "new_product_introduction",
            "primary_communication_goal": "new_product_launch",
            "funnel_stage": "awareness",
            "image_explanatory_power": 0.7,
            "verified_information_density": "low",
            "visible_copy_mode": "headline_plus_support",
            "headline_function": "product_identity",
            "support_function": "sensory_detail",
            "confidence": 0.8,
        },
        "candidates": [
            {
                "candidate_id": "c1",
                "strategy": "campaign_context",
                "headline": DOENJANG,
                "supporting_copy": "\uc0c8\ub86d\uac8c \uc120\ubcf4\uc774\ub294 \uba54\ub274\uc785\ub2c8\ub2e4",
                "headline_basis_ids": product.product_name_evidence_ids,
                "support_basis_ids": [],
            }
        ],
    }

    bundle_result = coerce_native_copy_strategy_bundle(payload, input_evidence=bundle, product_understanding=product)

    assert all(candidate.supporting_copy != "\uc0c8\ub86d\uac8c \uc120\ubcf4\uc774\ub294 \uba54\ub274\uc785\ub2c8\ub2e4" for candidate in bundle_result.candidates)


def test_generic_launch_support_penalty_and_product_contamination():
    candidate = NativeCopyCandidate(
        candidate_id="c1",
        strategy="campaign_context",
        headline=f"{DOENJANG} {NEW_MENU}",
        supporting_copy="\uc0c8\ub86d\uac8c \uc120\ubcf4\uc774\ub294 \uba54\ub274\uc785\ub2c8\ub2e4",
        headline_basis_ids=["e1"],
        support_basis_ids=[],
        language="korean",
        positioning_realization_mode="implicit",
        text_block_count=2,
        total_character_count=30,
    )

    score = score_native_copy_candidate(candidate, product_identity=DOENJANG, campaign_message_plan={"campaign_role": "new_product_introduction"})

    assert score.generic_launch_copy_penalty > 0
    assert score.product_identity_contamination_penalty > 0
    assert "generic_launch_support_detected" in score.blocking_reasons


def test_typography_expression_reference_changes_plan_and_prompt_sections():
    bundle = build_input_evidence_bundle({"user_input": f"{DOENJANG} {NEW_MENU}\ub97c {INTRODUCE}"})
    product = _product(bundle)
    campaign = plan_native_campaign_message(
        input_evidence=bundle,
        product_understanding=product,
        placement="restaurant_poster",
        promotion_goal="new_product_launch",
        source_visual_analysis=None,
        state={},
    )
    expression = plan_native_typography_expression(
        campaign_plan=campaign,
        input_evidence=bundle,
        product_understanding=product,
        reference_typography_analysis={"style_family": "modern_minimal", "style_summary": ["clean reference rhythm"]},
    )
    brief = ApprovedNativeCopyBrief(
        headline=DOENJANG,
        language="korean",
        message_role="headline_only",
        allowed_texts=[DOENJANG],
        forbidden_texts=[],
        max_text_blocks=1,
        max_total_characters=48,
        verified_evidence_ids=product.product_name_evidence_ids,
        unsupported_claim_categories=[],
        compliance_status="approved",
        product_identity=DOENJANG,
        product_evidence_ids=product.product_name_evidence_ids,
    )
    package = build_native_prompt_package(
        product_understanding=product.model_dump(),
        copy_brief=brief,
        input_evidence=bundle.model_dump(),
        campaign_message_plan=campaign.model_dump(),
        typography_expression_plan=expression.model_dump(),
        reference_typography_analysis={"style_summary": ["clean reference rhythm"]},
    )

    assert expression.reference_style_source == "reference_image"
    assert "PRODUCT IDENTITY" in package.final_prompt
    assert "CAMPAIGN CONTEXT - NON-DISPLAY BY DEFAULT" in package.final_prompt
    assert "TYPOGRAPHY EXPRESSION" in package.final_prompt
    assert "REFERENCE TYPOGRAPHY STYLE" in package.final_prompt
