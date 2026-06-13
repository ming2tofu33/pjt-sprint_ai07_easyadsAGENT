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
