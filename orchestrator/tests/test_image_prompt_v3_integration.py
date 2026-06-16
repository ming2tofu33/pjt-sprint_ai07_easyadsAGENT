import os
import pytest
from orchestrator.app.graph.builder import build_marketing_graph


@pytest.fixture(autouse=True)
def disable_external_apis():
    vars_to_clear = [
        "EASYADS_ENABLE_EXTERNAL_T2I",
        "EASYADS_ENABLE_GPT_IMAGE_2",
        "EASYADS_ENABLE_SD35_LOCAL",
        "EASYADS_ENABLE_FLUX_LOCAL",
        "EASYADS_QUALITY_BATCH_CONFIRM",
        "OPENAI_API_KEY",
    ]
    old_values = {}
    for var in vars_to_clear:
        if var in os.environ:
            old_values[var] = os.environ[var]
            del os.environ[var]
    yield
    for var, val in old_values.items():
        os.environ[var] = val


def _base_request(job_id: str, **extra):
    request = {
        "user_input": "신선한 딸기 음료 출시 광고 배경 제작해줘",
        "job_id": job_id,
        "thread_id": job_id,
        "copy_generation_mode": "auto_pilot",
        "context": {
            "business_type": "cafe",
            "item_or_service": "딸기 요거트 스무디",
            "promotion_goal": "reservation_cta",
            "extra": {"ad_format": "instagram_feed"},
        },
    }
    request.update(extra)
    return request


def test_image_prompt_v3_integration_flow():
    template_id = "seed_cafe_strawberry_feed_001"

    result = build_marketing_graph().invoke(
        _base_request("v3-integration-test", selected_reference_template_id=template_id),
        config={"configurable": {"thread_id": "v3-integration-test"}},
    )

    assert result["status"] == "done"

    spec = result.get("image_prompt_spec") or {}
    spec_meta = spec.get("metadata") or {}

    assert spec_meta.get("image_prompt_version") == "v3"
    assert spec_meta.get("resolved_visual_route_key") == "cafe"
    assert spec_meta.get("legacy_routing_projection", {}).get("route_key") == "cafe"
    assert "scene_plan" in spec_meta
    assert "prompt_quality_policy" in spec_meta
    assert "prompt_adapter" in spec_meta
    assert "business_visual_preset_id" in spec_meta


    assert "text-free advertising background" in spec.get("positive_prompt_en", "")
    assert "later Korean copy overlay" in spec.get("positive_prompt_en", "")
    assert spec_meta["prompt_adapter"]["metadata"].get("preset_id") == spec_meta.get("business_visual_preset_id")

    assert spec_meta.get("beauty_subtype") is None

    t2i_req = result.get("t2i_request") or {}
    t2i_meta = t2i_req.get("metadata") or {}

    assert t2i_meta.get("image_prompt_version") == "v3"
    assert t2i_meta.get("business_visual_preset_id") == spec_meta.get("business_visual_preset_id")
    assert t2i_meta.get("scene_plan") == spec_meta.get("scene_plan")
    assert t2i_meta.get("prompt_adapter") == spec_meta.get("prompt_adapter")
    assert t2i_meta.get("resolved_visual_route_key") == spec_meta.get("resolved_visual_route_key")
    assert t2i_meta.get("legacy_routing_projection") == spec_meta.get("legacy_routing_projection")


    assert "text-free advertising background" in t2i_req.get("prompt", "")
    assert "later Korean copy overlay" in t2i_req.get("prompt", "")

    assert "visual_template_id" in t2i_meta
    assert "reserved_text_areas" in t2i_meta
    assert t2i_meta.get("render_text_in_image") is False


def test_image_prompt_v3_ambiguous_beauty_integration_does_not_infer_hair():
    # A-4: ambiguous beauty plus hair terms must not infer a specialized visual route.
    result = build_marketing_graph().invoke(
        _base_request(
            "v3-beauty-integration",
            user_input="청담동 미용실 헤어 컷트 펌 할인 이벤트",
            context={
                "business_type": "beauty",
                "item_or_service": "헤어 스타일링",
                "promotion_goal": "reservation_cta",
                "extra": {"ad_format": "instagram_feed"},
            }
        ),
        config={"configurable": {"thread_id": "v3-beauty-integration"}},
    )
    
    assert result["status"] == "done"
    
    spec = result.get("image_prompt_spec") or {}
    spec_meta = spec.get("metadata") or {}
    
    assert spec_meta.get("image_prompt_version") == "v3"
    assert spec_meta.get("beauty_subtype") is None
    assert spec_meta.get("business_visual_preset_id") == "generic_clean_ad_background"
    
    t2i_req = result.get("t2i_request") or {}
    t2i_meta = t2i_req.get("metadata") or {}
    assert t2i_meta.get("beauty_subtype") is None
