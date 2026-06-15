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


# ===== Task 7: format-specific extended-plan isolation resolver =====
from orchestrator.app.llm.native_copy_policy import resolve_visible_text_source_by_format
from orchestrator.app.schemas.native_creative import (
    FlyerApprovedCopyPlan,
    FlyerPromotionalApprovedCopyPlan,
    ProductDetailApprovedFeaturePlan,
)


def _pd_plan():
    return ProductDetailApprovedFeaturePlan(
        headline="시카 세럼", supporting_copy="피부 진정 케어",
        feature_labels=["피부 진정", "수분 충전"],
        allowed_texts=["시카 세럼", "피부 진정 케어", "피부 진정", "수분 충전"],
    ).model_dump()


def _flyer_editorial_plan():
    return FlyerApprovedCopyPlan(
        headline="독서 모임", subtitle="함께 읽는 즐거움", info_cards=["토요일 모임", "자유 토론"],
        allowed_texts=["독서 모임", "함께 읽는 즐거움", "토요일 모임", "자유 토론"],
    ).model_dump()


def _flyer_promo_plan():
    return FlyerPromotionalApprovedCopyPlan(
        promo_badge="GRAND OPEN", headline="헬스장 오픈",
        info_items=["PT 상담", "웨이트존", "초보 지도"],
        contact_line="문의 000-0000-0000",
        allowed_texts=["GRAND OPEN", "헬스장 오픈", "PT 상담", "웨이트존", "초보 지도", "문의 000-0000-0000", "오픈"],
    ).model_dump()


# 1-2: banner/poster fail closed on any extended plan
@pytest.mark.parametrize("fmt", ["banner", "poster"])
def test_brief_only_format_rejects_flyer_plan(fmt):
    res = resolve_visible_text_source_by_format(ad_format=fmt, flyer_approved_copy_plan=_flyer_editorial_plan())
    assert res.status == "fail"
    assert "extended_plan_not_allowed_for_format" in res.failure_codes


@pytest.mark.parametrize("fmt", ["banner", "poster"])
def test_brief_only_format_rejects_product_detail_plan(fmt):
    res = resolve_visible_text_source_by_format(ad_format=fmt, product_detail_approved_feature_plan=_pd_plan())
    assert res.status == "fail"
    assert "extended_plan_not_allowed_for_format" in res.failure_codes


# 3: product_detail with flyer plan fails closed
def test_product_detail_rejects_flyer_plan():
    res = resolve_visible_text_source_by_format(ad_format="product_detail", flyer_approved_copy_plan=_flyer_editorial_plan())
    assert res.status == "fail"
    assert "flyer_plan_used_for_product_detail" in res.failure_codes


# 4: flyer with product_detail plan fails closed
def test_flyer_rejects_product_detail_plan():
    res = resolve_visible_text_source_by_format(ad_format="flyer", product_detail_approved_feature_plan=_pd_plan())
    assert res.status == "fail"
    assert "product_detail_plan_used_for_flyer" in res.failure_codes


# 5: both flyer plans present fails closed
def test_flyer_rejects_multiple_flyer_plans():
    res = resolve_visible_text_source_by_format(ad_format="flyer", flyer_approved_copy_plan=_flyer_editorial_plan(), flyer_promotional_approved_copy_plan=_flyer_promo_plan())
    assert res.status == "fail"
    assert "multiple_flyer_plans_present" in res.failure_codes


# 6: product_detail extended mode without plan fails closed
def test_product_detail_missing_plan_fails_closed():
    res = resolve_visible_text_source_by_format(ad_format="product_detail")
    assert res.status == "fail"
    assert res.decision == "manual_review"
    assert "missing_required_extended_plan" in res.failure_codes


# 7: flyer extended mode without plan fails closed
def test_flyer_missing_plan_fails_closed():
    res = resolve_visible_text_source_by_format(ad_format="flyer")
    assert res.status == "fail"
    assert "missing_required_extended_plan" in res.failure_codes


# 8: valid product_detail selected as source
def test_product_detail_plan_selected_as_source():
    res = resolve_visible_text_source_by_format(ad_format="product_detail", product_detail_approved_feature_plan=_pd_plan())
    assert res.status == "ok"
    assert res.source_kind == "product_detail"


# 9: valid editorial flyer selected as source
def test_flyer_editorial_plan_selected_as_source():
    res = resolve_visible_text_source_by_format(ad_format="flyer", flyer_approved_copy_plan=_flyer_editorial_plan())
    assert res.status == "ok"
    assert res.source_kind == "flyer_editorial"


# 10: valid promotional flyer selected as source
def test_flyer_promotional_plan_selected_as_source():
    res = resolve_visible_text_source_by_format(ad_format="flyer", flyer_promotional_approved_copy_plan=_flyer_promo_plan())
    assert res.status == "ok"
    assert res.source_kind == "flyer_promotional"


# 11: banner/poster normal case uses two-block brief only
@pytest.mark.parametrize("fmt", ["banner", "poster"])
def test_brief_only_format_uses_brief_source(fmt):
    res = resolve_visible_text_source_by_format(ad_format=fmt)
    assert res.status == "ok"
    assert res.source_kind == "brief"


@pytest.mark.parametrize("fmt", ["instagram_feed", "instagram_story"])
def test_instagram_brief_only_formats_reject_extended_plans(fmt):
    for plan_field, plan in (
        ("flyer_approved_copy_plan", _flyer_editorial_plan()),
        ("flyer_promotional_approved_copy_plan", _flyer_promo_plan()),
        ("product_detail_approved_feature_plan", _pd_plan()),
    ):
        res = resolve_visible_text_source_by_format(ad_format=fmt, **{plan_field: plan})
        assert res.status == "fail"
        assert res.decision == "rejected"
        assert "extended_plan_not_allowed_for_format" in res.failure_codes
