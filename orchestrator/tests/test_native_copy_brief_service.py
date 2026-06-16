from orchestrator.app.llm.native_copy_brief_service import (
    generate_approved_native_copy_brief,
    resolve_approved_primary_copy,
)
from orchestrator.app.llm.native_copy_policy import plan_gpt_image2_native_single_shot
from orchestrator.app.schemas.input_evidence import InputEvidenceBundle
from orchestrator.app.schemas.native_creative import ApprovedNativeCopyBrief
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


def test_native_copy_brief_service_rejects_restaurant_meta_instruction():
    class Adapter:
        def generate_native_copy_brief(self, **kwargs):
            return {
                "headline": "삼겹살집 회식 손님 많이 오게 포스터 만들어줘",
                "supporting_copy": "예약/방문 유도",
                "language": "korean",
                "message_role": "headline_plus_support",
                "allowed_texts": ["삼겹살집 회식 손님 많이 오게 포스터 만들어줘", "예약/방문 유도"],
                "forbidden_texts": [],
                "max_text_blocks": 2,
                "max_total_characters": 48,
                "verified_evidence_ids": ["e1"],
                "unsupported_claim_categories": [],
                "compliance_status": "approved",
                "rejection_reasons": [],
                "product_identity": "삼겹살집",
            }

    evidence = InputEvidenceBundle(input_mode="text_only", user_text="삼겹살집 회식 손님 많이 오게 포스터 만들어줘", user_request_utterance="삼겹살집 회식 손님 많이 오게 포스터 만들어줘", campaign_intent="product_promotion", desired_positioning=[], non_display_instruction_fragments=["만들어줘", "손님 많이 오게"], explicit_product_mentions=["삼겹살"], overall_confidence=0.9)
    product = ProductUnderstanding(product_name="삼겹살집", normalized_product_type="restaurant", broad_category="food_and_beverage", category_path=["food_and_beverage", "restaurant"], product_name_evidence_ids=["e1"], confidence=0.9)

    brief = generate_approved_native_copy_brief(input_evidence=evidence, product_understanding=product, execution_plan=plan_gpt_image2_native_single_shot(), source_visual_analysis=None, state={"native_copy_adapter": Adapter()})

    assert brief.compliance_status == "rejected"
    assert "meta_instruction_leakage_detected" in brief.rejection_reasons
    assert "user_request_copied_as_headline" in brief.rejection_reasons


def test_native_copy_brief_service_approves_clean_restaurant_copy():
    class Adapter:
        def generate_native_copy_brief(self, **kwargs):
            return {
                "headline": "회식은 삼겹살집에서",
                "supporting_copy": "함께 즐기는 따뜻한 한 상",
                "language": "korean",
                "message_role": "headline_plus_support",
                "allowed_texts": ["회식은 삼겹살집에서", "함께 즐기는 따뜻한 한 상"],
                "forbidden_texts": [],
                "max_text_blocks": 2,
                "max_total_characters": 48,
                "verified_evidence_ids": ["e1", "e2"],
                "copy_claim_evidence_ids": ["e1", "e2"],
                "unsupported_claim_categories": [],
                "compliance_status": "approved",
                "rejection_reasons": [],
                "product_identity": "삼겹살집",
                "support_basis_type": "aesthetic_expression",
            }

    evidence = InputEvidenceBundle(input_mode="text_only", user_text="삼겹살집 회식 손님 많이 오게 포스터 만들어줘", user_request_utterance="삼겹살집 회식 손님 많이 오게 포스터 만들어줘", campaign_intent="product_promotion", desired_positioning=[], non_display_instruction_fragments=["만들어줘", "손님 많이 오게"], explicit_product_mentions=["삼겹살"], overall_confidence=0.9)
    product = ProductUnderstanding(product_name="삼겹살집", normalized_product_type="restaurant", broad_category="food_and_beverage", category_path=["food_and_beverage", "restaurant"], product_name_evidence_ids=["e1"], confidence=0.9)

    brief = generate_approved_native_copy_brief(input_evidence=evidence, product_understanding=product, execution_plan=plan_gpt_image2_native_single_shot(), source_visual_analysis=None, state={"native_copy_adapter": Adapter()})

    assert brief.rejection_reasons == []
    assert brief.compliance_status == "approved"
    assert brief.headline == "회식은 삼겹살집에서"


def _approved_adapter():
    class Adapter:
        def generate_native_copy_brief(self, **kwargs):
            return {
                "headline": "자동 생성 헤드라인",
                "supporting_copy": "자동 생성 서브카피",
                "language": "korean",
                "message_role": "headline_plus_support",
                "allowed_texts": ["자동 생성 헤드라인", "자동 생성 서브카피"],
                "forbidden_texts": [],
                "max_text_blocks": 2,
                "max_total_characters": 48,
                "verified_evidence_ids": ["e1"],
                "unsupported_claim_categories": [],
                "compliance_status": "approved",
                "rejection_reasons": [],
            }

    return Adapter()


def _serum_inputs():
    evidence = InputEvidenceBundle(input_mode="text_only", user_text="시카 세럼 상세페이지", explicit_product_mentions=["시카 세럼"], overall_confidence=0.9)
    product = ProductUnderstanding(product_name="시카 세럼", normalized_product_type="cica_serum", broad_category="beauty_and_personal_care", category_path=["beauty_and_personal_care", "cica_serum"], product_name_evidence_ids=["e1"], confidence=0.9)
    return evidence, product


def test_resolve_approved_primary_copy_prefers_exact_custom_fields():
    brief = ApprovedNativeCopyBrief(headline="자동 헤드라인", supporting_copy="자동 서브카피", language="korean", message_role="headline_plus_support", allowed_texts=["자동 헤드라인", "자동 서브카피"], max_text_blocks=2, max_total_characters=48, compliance_status="approved")
    state = {"user_custom_headline": "시카 진정 세럼", "user_custom_subcopy": "민감한 피부를 편안하게 감싸는 진정 케어"}

    headline, supporting, mode = resolve_approved_primary_copy(state=state, approved_copy=brief)

    assert headline == "시카 진정 세럼"
    assert supporting == "민감한 피부를 편안하게 감싸는 진정 케어"
    assert mode == "user_exact"


def test_resolve_approved_primary_copy_falls_back_to_generated_copy():
    brief = ApprovedNativeCopyBrief(headline="자동 헤드라인", supporting_copy="자동 서브카피", language="korean", message_role="headline_plus_support", allowed_texts=["자동 헤드라인", "자동 서브카피"], max_text_blocks=2, max_total_characters=48, compliance_status="approved")

    headline, supporting, mode = resolve_approved_primary_copy(state={}, approved_copy=brief)

    assert headline == "자동 헤드라인"
    assert supporting == "자동 서브카피"
    assert mode == "generated"


def test_brief_preserves_exact_custom_headline_and_subcopy():
    evidence, product = _serum_inputs()
    state = {
        "native_copy_adapter": _approved_adapter(),
        "user_custom_headline": "시카 진정 세럼",
        "user_custom_subcopy": "민감한 피부를 편안하게 감싸는 진정 케어",
    }

    brief = generate_approved_native_copy_brief(input_evidence=evidence, product_understanding=product, execution_plan=plan_gpt_image2_native_single_shot(), source_visual_analysis=None, state=state)

    assert brief.headline == "시카 진정 세럼"
    assert brief.supporting_copy == "민감한 피부를 편안하게 감싸는 진정 케어"
    assert brief.copy_source_mode == "user_exact"
    assert brief.allowed_texts[:2] == ["시카 진정 세럼", "민감한 피부를 편안하게 감싸는 진정 케어"]


def test_brief_uses_generated_copy_when_no_custom_fields():
    evidence, product = _serum_inputs()
    state = {"native_copy_adapter": _approved_adapter()}

    brief = generate_approved_native_copy_brief(input_evidence=evidence, product_understanding=product, execution_plan=plan_gpt_image2_native_single_shot(), source_visual_analysis=None, state=state)

    assert brief.headline == "자동 생성 헤드라인"
    assert brief.supporting_copy == "자동 생성 서브카피"
