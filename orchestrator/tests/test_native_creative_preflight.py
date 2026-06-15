from orchestrator.app.llm.nodes.native_creative_preflight import native_creative_preflight_node
from orchestrator.app.schemas.native_creative import NativeCreativePreflightReview
from orchestrator.tests.test_native_copy_policy import _brief


def test_native_preflight_builds_prompt_package_when_approved(monkeypatch):
    monkeypatch.setattr(
        "orchestrator.app.llm.nodes.native_creative_preflight.review_native_creative_preflight",
        lambda **kwargs: NativeCreativePreflightReview(
            decision="approved",
            copy_grounded=True,
            claims_supported=True,
            language_natural=True,
            generic_cta_absent=True,
            text_budget_valid=True,
            native_typography_suitable=True,
            product_visual_direction_valid=True,
            consumer_facing_copy=True,
            meta_instruction_absent=True,
            user_request_transformed=True,
            product_identity_clean=True,
            copy_relevance_score=0.9,
            headline_quality_score=0.8,
            positioning_alignment_score=0.8,
            failure_reasons=[],
            revision_instructions=[],
        ),
    )
    update = native_creative_preflight_node(
        {
            "approved_native_copy_brief": _brief().model_dump(),
            "product_understanding": {"product_name": "된장찌개"},
            "ad_format_spec": {"ad_format": "restaurant_poster"},
        }
    )

    assert update["native_creative_preflight_review"]["decision"] == "approved"
    assert update["native_creative_prompt_package"]["image_model"] == "gpt-image-2"
    assert update["native_creative_prompt_package"]["image_call_limit"] == 1


# ===== Task 7: preflight node fails closed on format contamination =====
from orchestrator.tests.test_native_copy_policy import _pd_plan, _flyer_editorial_plan


def test_preflight_node_fails_closed_when_banner_has_extended_plan():
    update = native_creative_preflight_node(
        {
            "approved_native_copy_brief": _brief().model_dump(),
            "product_understanding": {"product_name": "된장찌개"},
            "selected_ad_format": "banner",
            "product_detail_approved_feature_plan": _pd_plan(),
        }
    )
    assert update["native_generation_status"] == "rejected"
    assert update["native_creative_preflight_review"]["decision"] == "rejected"
    assert "extended_plan_not_allowed_for_format" in update["native_creative_preflight_review"]["failure_reasons"]


def test_preflight_node_fails_closed_on_flyer_plan_in_product_detail():
    update = native_creative_preflight_node(
        {
            "approved_native_copy_brief": _brief().model_dump(),
            "product_understanding": {"product_name": "된장찌개"},
            "selected_ad_format": "product_detail",
            "flyer_approved_copy_plan": _flyer_editorial_plan(),
        }
    )
    assert update["native_generation_status"] == "rejected"
    assert "flyer_plan_used_for_product_detail" in update["native_creative_preflight_review"]["failure_reasons"]


def test_preflight_node_manual_review_when_required_product_detail_plan_missing():
    update = native_creative_preflight_node(
        {
            "approved_native_copy_brief": _brief().model_dump(),
            "product_understanding": {"product_name": "된장찌개"},
            "selected_ad_format": "product_detail",
        }
    )
    assert update["native_generation_status"] == "manual_review"
    assert "missing_required_extended_plan" in update["native_creative_preflight_review"]["failure_reasons"]


# ===== Task 8: 4-format prompt package integration =====
import pytest
from orchestrator.app.schemas.native_creative import NativeCreativePromptPackage
from orchestrator.tests.test_native_copy_policy import _flyer_promo_plan


def _custom_pd_plan(headline="시카 진정 세럼", subcopy="민감한 피부를 편안하게 감싸는 진정 케어"):
    return {
        "schema_version": "product_detail_approved_feature_plan_v1",
        "source_mode": "controlled_approved",
        "headline": headline,
        "supporting_copy": subcopy,
        "feature_labels": ["피부 진정", "수분 충전", "산뜻한 흡수"],
        "allowed_texts": [headline, subcopy, "피부 진정", "수분 충전", "산뜻한 흡수"],
        "max_text_blocks": 6,
        "max_total_characters": 120,
    }


@pytest.fixture
def _approved_review(monkeypatch):
    monkeypatch.setattr(
        "orchestrator.app.llm.nodes.native_creative_preflight.review_native_creative_preflight",
        lambda **kwargs: NativeCreativePreflightReview(
            decision="approved", copy_grounded=True, claims_supported=True, language_natural=True,
            generic_cta_absent=True, text_budget_valid=True, native_typography_suitable=True,
            product_visual_direction_valid=True, failure_reasons=[], revision_instructions=[],
        ),
    )


def _run(state):
    return native_creative_preflight_node(state)


def _pkg(update):
    return update["native_creative_prompt_package"]


def test_prompt_package_banner_two_block_only(_approved_review):
    update = _run({
        "approved_native_copy_brief": _brief().model_dump(),
        "product_understanding": {"product_name": "된장찌개"},
        "selected_ad_format": "banner",
    })
    pkg = _pkg(update)
    assert pkg["exact_allowed_texts"] == ["된장찌개", "구수한 한 그릇"]
    assert "FORMAT PROFILE: banner" in pkg["final_prompt"]
    assert "FORMAT PROFILE: product_detail" not in pkg["final_prompt"]
    assert "FORMAT PROFILE: flyer_editorial" not in pkg["final_prompt"]
    assert "feature label cards" not in pkg["final_prompt"]
    assert pkg["product_detail_approved_feature_plan"] is None
    assert pkg["flyer_approved_copy_plan"] is None


def test_prompt_package_poster_two_block_only(_approved_review):
    update = _run({
        "approved_native_copy_brief": _brief().model_dump(),
        "product_understanding": {"product_name": "된장찌개"},
        "selected_ad_format": "poster",
    })
    pkg = _pkg(update)
    assert pkg["exact_allowed_texts"] == ["된장찌개", "구수한 한 그릇"]
    assert "FORMAT PROFILE: poster" in pkg["final_prompt"]
    assert "FORMAT PROFILE: flyer_promotional" not in pkg["final_prompt"]
    assert pkg["product_detail_approved_feature_plan"] is None


def test_prompt_package_product_detail_includes_feature_labels(_approved_review):
    update = _run({
        "approved_native_copy_brief": _brief().model_dump(),
        "product_understanding": {"product_name": "시카 세럼"},
        "selected_ad_format": "product_detail",
        "product_detail_approved_feature_plan": _custom_pd_plan(),
    })
    pkg = _pkg(update)
    # headline + supporting + 2-4 feature labels; custom copy byte-for-byte first.
    assert pkg["exact_allowed_texts"] == ["시카 진정 세럼", "민감한 피부를 편안하게 감싸는 진정 케어", "피부 진정", "수분 충전", "산뜻한 흡수"]
    assert "FORMAT PROFILE: product_detail" in pkg["final_prompt"]
    assert "FORMAT PROFILE: flyer_editorial" not in pkg["final_prompt"]
    assert "FORMAT PROFILE: banner" not in pkg["final_prompt"]
    assert pkg["product_detail_approved_feature_plan"] is not None
    assert pkg["flyer_approved_copy_plan"] is None


def test_prompt_package_editorial_flyer_blocks_only(_approved_review):
    update = _run({
        "approved_native_copy_brief": _brief().model_dump(),
        "product_understanding": {"product_name": "독서 모임"},
        "selected_ad_format": "flyer",
        "flyer_approved_copy_plan": _flyer_editorial_plan(),
    })
    pkg = _pkg(update)
    assert 4 <= len(pkg["exact_allowed_texts"]) <= 6
    assert pkg["exact_allowed_texts"] == ["독서 모임", "함께 읽는 즐거움", "토요일 모임", "자유 토론"]
    assert "FORMAT PROFILE: flyer_editorial" in pkg["final_prompt"]
    assert "FORMAT PROFILE: flyer_promotional" not in pkg["final_prompt"]
    assert "feature label cards" not in pkg["final_prompt"]
    assert pkg["product_detail_approved_feature_plan"] is None
    assert pkg["flyer_promotional_approved_copy_plan"] is None


def test_prompt_package_promotional_flyer_blocks_only(_approved_review):
    update = _run({
        "approved_native_copy_brief": _brief().model_dump(),
        "product_understanding": {"product_name": "헬스장"},
        "selected_ad_format": "flyer",
        "flyer_promotional_approved_copy_plan": _flyer_promo_plan(),
    })
    pkg = _pkg(update)
    assert 7 <= len(pkg["exact_allowed_texts"]) <= 10
    # approved operational text present.
    assert "문의 000-0000-0000" in pkg["exact_allowed_texts"]
    assert "FORMAT PROFILE: flyer_promotional" in pkg["final_prompt"]
    assert "FORMAT PROFILE: flyer_editorial" not in pkg["final_prompt"]
    assert "feature label cards" not in pkg["final_prompt"]
    assert pkg["product_detail_approved_feature_plan"] is None
    assert pkg["flyer_approved_copy_plan"] is None


@pytest.mark.parametrize(
    "ad_format,profile,native_size",
    [
        ("instagram_feed", "instagram_feed", (1080, 1080)),
        ("instagram_story", "instagram_story", (1080, 1920)),
    ],
)
def test_prompt_package_instagram_formats_use_two_block_native_profiles(_approved_review, ad_format, profile, native_size):
    update = _run({
        "approved_native_copy_brief": _brief().model_dump(),
        "product_understanding": {"product_name": "된장찌개"},
        "selected_ad_format": ad_format,
    })
    pkg = _pkg(update)
    assert pkg["exact_allowed_texts"] == ["된장찌개", "구수한 한 그릇"]
    assert f"FORMAT PROFILE: {profile}" in pkg["final_prompt"]
    assert "Do not invent hashtags" in pkg["final_prompt"]
    assert (pkg["native_width"], pkg["native_height"]) == native_size
    assert pkg["product_detail_approved_feature_plan"] is None
    assert pkg["flyer_approved_copy_plan"] is None
    assert pkg["flyer_promotional_approved_copy_plan"] is None


@pytest.mark.parametrize("ad_format", ["instagram_feed", "instagram_story"])
def test_preflight_instagram_rejects_extended_plan_contamination(_approved_review, ad_format):
    update = _run({
        "approved_native_copy_brief": _brief().model_dump(),
        "product_understanding": {"product_name": "된장찌개"},
        "selected_ad_format": ad_format,
        "product_detail_approved_feature_plan": _custom_pd_plan(),
    })
    assert update["native_generation_status"] == "rejected"
    assert "extended_plan_not_allowed_for_format" in update["native_creative_preflight_review"]["failure_reasons"]
