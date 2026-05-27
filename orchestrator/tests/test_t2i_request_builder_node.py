from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.nodes.t2i_request_builder import t2i_request_builder_node
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def test_t2i_request_builder_maps_prompt_render_output_to_t2i_request():
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            job_id="builder-job",
            thread_id="builder-thread",
            context=MarketingContext(
                business_type="restaurant",
                item_or_service="삼겹살",
                promotion_goal="reservation_cta",
                extra={"ad_format": "instagram_feed"},
            ),
        )
    )
    state["ad_format_spec"] = {"ad_format": "instagram_feed", "platform": "instagram", "aspect_ratio": "1:1", "width": 1080, "height": 1080}
    state["layout_spec"] = {"layout_type": "single_hero", "copy_space": "bottom"}
    state["image_prompt_spec"] = {"reserved_text_areas": [{"x": 0.05, "y": 0.06, "w": 0.90, "h": 0.18}]}
    state["prompt_render_output"] = {
        "engine": "mock",
        "positive_prompt": "text-free bbq background",
        "negative_prompt": "text, watermark, logo",
        "width": 1080,
        "height": 1080,
    }

    update = t2i_request_builder_node(state)
    request = update["t2i_request"]

    assert request["prompt"] == "text-free bbq background"
    assert request["negative_prompt"] == "text, watermark, logo"
    assert request["metadata"]["job_id"] == "builder-job"
    assert request["metadata"]["thread_id"] == "builder-thread"
    assert request["metadata"]["render_text_in_image"] is False
    assert request["metadata"]["text_overlay_pending"] is True
    assert request["metadata"]["reserved_text_areas"] == [{"x": 0.05, "y": 0.06, "w": 0.90, "h": 0.18}]
    assert request["metadata"]["source_node"] == "t2i_request_builder"
