from orchestrator.app.llm.nodes.native_creative_preflight import native_creative_preflight_node
from orchestrator.tests.test_native_copy_policy import _brief


def test_native_preflight_builds_prompt_package_when_approved():
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
