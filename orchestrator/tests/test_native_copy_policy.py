import pytest

from orchestrator.app.llm.native_copy_policy import decide_native_typography_eligibility, validate_approved_native_copy_brief
from orchestrator.app.schemas.native_creative import ApprovedNativeCopyBrief


def _brief(**overrides):
    data = {
        "headline": "된장찌개",
        "supporting_copy": "구수한 한 그릇",
        "closing_copy": None,
        "action_cta": None,
        "language": "korean",
        "message_role": "headline_plus_support",
        "allowed_texts": ["된장찌개", "구수한 한 그릇"],
        "forbidden_texts": [],
        "max_text_blocks": 2,
        "max_total_characters": 48,
        "verified_evidence_ids": ["e1"],
        "unsupported_claim_categories": [],
        "compliance_status": "approved",
        "rejection_reasons": [],
        "source_user_request": "고급진 된장찌개를 홍보하고 싶어",
        "product_identity": "된장찌개",
        "campaign_intent": "product_promotion",
        "desired_positioning": ["premium", "refined"],
        "transformation_performed": True,
        "product_evidence_ids": ["e1"],
        "creative_direction_evidence_ids": ["e2"],
    }
    data.update(overrides)
    return ApprovedNativeCopyBrief(**data)


def test_native_typography_allows_short_headline_and_support():
    brief = _brief()

    assert validate_approved_native_copy_brief(brief) == []
    assert decide_native_typography_eligibility(brief).eligible is True


def test_native_typography_blocks_price_and_generic_cta():
    brief = _brief(headline="된장찌개 9,000원", supporting_copy=None, action_cta="Learn More", allowed_texts=["된장찌개 9,000원", "Learn More"])

    failures = validate_approved_native_copy_brief(brief)

    assert "generic_cta_detected" in failures
    assert "exact_operational_text_detected" in failures


def test_closing_copy_is_not_action_cta():
    brief = _brief(supporting_copy=None, closing_copy="오늘의 식탁에 구수함을", allowed_texts=["된장찌개", "오늘의 식탁에 구수함을"], message_role="headline_plus_closing")

    assert "action_cta_requires_verified_destination" not in validate_approved_native_copy_brief(brief)


@pytest.mark.parametrize(
    ("overrides", "expected_failures"),
    [
        pytest.param(
            {
                "headline": "고급진 된장찌개를 홍보하고 싶어",
                "supporting_copy": None,
                "allowed_texts": ["고급진 된장찌개를 홍보하고 싶어"],
                "message_role": "headline_only",
                "transformation_performed": False,
            },
            {
                "copy_transformation_missing",
                "meta_instruction_leakage_detected",
                "positioning_literalization",
                "product_centeredness_too_low",
                "user_request_copied_as_headline",
            },
            id="user-request-copied-headline",
        ),
        pytest.param(
            {
                "headline": "된장찌개를 홍보하고 싶어",
                "supporting_copy": None,
                "allowed_texts": ["된장찌개를 홍보하고 싶어"],
                "message_role": "headline_only",
            },
            {"user_request_copied_as_headline", "meta_instruction_leakage_detected"},
            id="meta-instruction-headline",
        ),
        pytest.param(
            {
                "headline": "깊고 구수한 한 그릇",
                "supporting_copy": None,
                "allowed_texts": ["깊고 구수한 한 그릇"],
                "message_role": "headline_only",
            },
            {"product_centeredness_too_low", "product_identity_missing"},
            id="consumer-facing-transform",
        ),
    ],
)
def test_native_copy_validation_exact_failure_set(overrides, expected_failures):
    brief = _brief(**overrides)
    assert set(validate_approved_native_copy_brief(brief)) == expected_failures


def test_user_exact_copy_can_be_preserved():
    brief = _brief(headline="고급진 된장찌개", supporting_copy=None, allowed_texts=["고급진 된장찌개"], message_role="headline_only", copy_source_mode="user_exact", transformation_performed=False)

    assert "copy_transformation_missing" not in validate_approved_native_copy_brief(brief)
