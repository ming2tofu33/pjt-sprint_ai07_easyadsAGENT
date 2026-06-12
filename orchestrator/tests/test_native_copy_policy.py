from orchestrator.app.llm.native_copy_policy import decide_native_typography_eligibility, validate_approved_native_copy_brief
from orchestrator.app.schemas.native_creative import ApprovedNativeCopyBrief


def _brief(**overrides):
    data = {
        "headline": "고급진 된장찌개",
        "supporting_copy": "진한 구수함 한 그릇",
        "closing_copy": None,
        "action_cta": None,
        "language": "korean",
        "message_role": "headline_plus_support",
        "allowed_texts": ["고급진 된장찌개", "진한 구수함 한 그릇"],
        "forbidden_texts": [],
        "max_text_blocks": 2,
        "max_total_characters": 48,
        "verified_evidence_ids": ["e1"],
        "unsupported_claim_categories": [],
        "compliance_status": "approved",
        "rejection_reasons": [],
    }
    data.update(overrides)
    return ApprovedNativeCopyBrief(**data)


def test_native_typography_allows_short_headline_and_support():
    brief = _brief()

    assert validate_approved_native_copy_brief(brief) == []
    assert decide_native_typography_eligibility(brief).eligible is True


def test_native_typography_blocks_price_and_generic_cta():
    brief = _brief(headline="고급진 된장찌개 9,000원", supporting_copy=None, action_cta="Learn More", allowed_texts=["고급진 된장찌개 9,000원", "Learn More"])

    failures = validate_approved_native_copy_brief(brief)

    assert "generic_cta_detected" in failures
    assert "exact_operational_text_detected" in failures


def test_closing_copy_is_not_action_cta():
    brief = _brief(supporting_copy=None, closing_copy="오늘의 식탁에 구수함을", allowed_texts=["고급진 된장찌개", "오늘의 식탁에 구수함을"], message_role="headline_plus_closing")

    assert "action_cta_requires_verified_destination" not in validate_approved_native_copy_brief(brief)
