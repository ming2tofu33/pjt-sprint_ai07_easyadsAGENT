from orchestrator.app.llm.native_copy_brief_service import generate_approved_native_copy_brief
from orchestrator.app.llm.native_copy_policy import plan_gpt_image2_native_single_shot
from orchestrator.app.schemas.input_evidence import InputEvidenceBundle
from orchestrator.app.schemas.product_understanding import ProductUnderstanding


def test_native_copy_brief_service_rejects_invalid_adapter_copy():
    class Adapter:
        def generate_native_copy_brief(self, **kwargs):
            return {
                "headline": "고급진 된장찌개 9,000원",
                "language": "korean",
                "message_role": "headline_only",
                "allowed_texts": ["고급진 된장찌개 9,000원"],
                "forbidden_texts": [],
                "max_text_blocks": 1,
                "max_total_characters": 48,
                "verified_evidence_ids": [],
                "unsupported_claim_categories": [],
                "compliance_status": "approved",
                "rejection_reasons": [],
            }

    evidence = InputEvidenceBundle(input_mode="text_only", user_text="된장찌개", explicit_product_mentions=["된장찌개"], overall_confidence=0.9)
    product = ProductUnderstanding(product_name="된장찌개", normalized_product_type="doenjang_jjigae", broad_category="food_and_beverage", category_path=["food_and_beverage", "doenjang_jjigae"], confidence=0.9)

    brief = generate_approved_native_copy_brief(input_evidence=evidence, product_understanding=product, execution_plan=plan_gpt_image2_native_single_shot(), source_visual_analysis=None, state={"native_copy_adapter": Adapter()})

    assert brief.compliance_status == "rejected"
    assert "exact_operational_text_detected" in brief.rejection_reasons


def test_native_copy_brief_service_does_not_fallback_to_product_name_when_headline_missing():
    class Adapter:
        def generate_native_copy_brief(self, **kwargs):
            return {
                "language": "korean",
                "message_role": "headline_only",
                "allowed_texts": [],
                "forbidden_texts": [],
                "max_text_blocks": 1,
                "max_total_characters": 48,
                "verified_evidence_ids": ["e1"],
                "unsupported_claim_categories": [],
                "compliance_status": "approved",
                "rejection_reasons": [],
            }

    evidence = InputEvidenceBundle(input_mode="text_only", user_text="고급진 된장찌개를 홍보하고 싶어", user_request_utterance="고급진 된장찌개를 홍보하고 싶어", campaign_intent="product_promotion", desired_positioning=["premium", "refined"], non_display_instruction_fragments=["홍보하고 싶어"], explicit_product_mentions=["된장찌개"], overall_confidence=0.9)
    product = ProductUnderstanding(product_name="된장찌개", normalized_product_type="doenjang_jjigae", broad_category="food_and_beverage", category_path=["food_and_beverage", "doenjang_jjigae"], product_name_evidence_ids=["e1"], confidence=0.9)

    brief = generate_approved_native_copy_brief(input_evidence=evidence, product_understanding=product, execution_plan=plan_gpt_image2_native_single_shot(), source_visual_analysis=None, state={"native_copy_adapter": Adapter()})

    assert brief.headline is None
    assert brief.compliance_status == "rejected"
    assert "headline_missing" in brief.rejection_reasons


def test_native_copy_brief_service_rejects_raw_user_request_headline():
    class Adapter:
        def generate_native_copy_brief(self, **kwargs):
            return {
                "headline": "고급진 된장찌개를 홍보하고 싶어",
                "language": "korean",
                "message_role": "headline_only",
                "allowed_texts": ["고급진 된장찌개를 홍보하고 싶어"],
                "forbidden_texts": [],
                "max_text_blocks": 1,
                "max_total_characters": 48,
                "verified_evidence_ids": ["e1"],
                "unsupported_claim_categories": [],
                "compliance_status": "approved",
                "rejection_reasons": [],
            }

    evidence = InputEvidenceBundle(input_mode="text_only", user_text="고급진 된장찌개를 홍보하고 싶어", user_request_utterance="고급진 된장찌개를 홍보하고 싶어", campaign_intent="product_promotion", desired_positioning=["premium", "refined"], non_display_instruction_fragments=["홍보하고 싶어"], explicit_product_mentions=["된장찌개"], overall_confidence=0.9)
    product = ProductUnderstanding(product_name="된장찌개", normalized_product_type="doenjang_jjigae", broad_category="food_and_beverage", category_path=["food_and_beverage", "doenjang_jjigae"], product_name_evidence_ids=["e1"], confidence=0.9)

    brief = generate_approved_native_copy_brief(input_evidence=evidence, product_understanding=product, execution_plan=plan_gpt_image2_native_single_shot(), source_visual_analysis=None, state={"native_copy_adapter": Adapter()})

    assert brief.compliance_status == "rejected"
    assert "user_request_copied_as_headline" in brief.rejection_reasons
