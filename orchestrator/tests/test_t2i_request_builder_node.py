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
    assert request["metadata"]["must_not_include_text"] is True
    assert request["metadata"]["negative_prompt_required_terms"] == ["text", "letters", "numbers", "Hangul", "logo", "watermark"]
    assert request["metadata"]["source_node"] == "t2i_request_builder"


def test_t2i_request_builder_passes_source_image_as_input_image():
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            job_id="photo-builder-job",
            thread_id="photo-builder-thread",
            source_image_path="data/uploads/menu.png",
            context=MarketingContext(
                business_type="cafe",
                item_or_service="딸기라떼",
                promotion_goal="discount_event",
                extra={"ad_format": "instagram_feed"},
            ),
        )
    )
    state["prompt_render_output"] = {
        "engine": "gpt_image_2",
        "positive_prompt": "text-free cafe drink background",
        "negative_prompt": "text, watermark, logo",
        "width": 1080,
        "height": 1080,
    }

    update = t2i_request_builder_node(state)
    request = update["t2i_request"]

    assert request["input_image_paths"] == ["data/uploads/menu.png"]
    assert request["metadata"]["input_image_paths"] == ["data/uploads/menu.png"]
    assert request["metadata"]["source_image_path"] == "data/uploads/menu.png"


def test_t2i_request_metadata_aligns_tlfp_reference_and_product_fields():
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            job_id="builder-contract-job",
            thread_id="builder-contract-thread",
            selected_reference_template_id="ref-1",
            context=MarketingContext(
                business_type="cafe",
                item_or_service="딸기라떼",
                promotion_goal="discount_event",
                extra={"ad_format": "instagram_feed"},
            ),
        )
    )
    state["copy_generation_mode"] = "auto_pilot"
    state["ad_format_spec"] = {"ad_format": "instagram_feed", "platform": "instagram", "aspect_ratio": "1:1", "width": 1080, "height": 1080}
    state["layout_spec"] = {"layout_type": "single_hero", "copy_space": "bottom"}
    state["copy_spec"] = {"copy_mode": "standard", "items": [{"role": "headline", "text": "딸기라떼 출시"}]}
    state["text_style_spec"] = {"profile": "premium"}
    state["text_layout_spec"] = {"reserved_text_areas": [{"x": 0.10, "y": 0.70, "w": 0.80, "h": 0.20}]}
    state["image_prompt_spec"] = {
        "reserved_text_areas": [{"x": 0.10, "y": 0.70, "w": 0.80, "h": 0.20}],
        "must_not_include_text": True,
    }
    state["reference_style_profile"] = {"ad_style_prompt": "reference-inspired"}
    state["product_preserve_spec"] = {"product_bbox": {"x": 0.25, "y": 0.20, "w": 0.50, "h": 0.50}}
    state["selected_reference_template"] = {"template_id": "ref-1", "title": "Cafe Feed"}
    state["reference_template_selection"] = {
        "style_profile_hint": {
            "style_keywords": ["fresh", "clean"],
            "color_palette": ["#F9A8D4"],
            "layout_hint": "bottom text",
            "typography_hint": "rounded",
        }
    }
    state["prompt_render_output"] = {
        "engine": "mock",
        "positive_prompt": "text-free cafe background",
        "negative_prompt": "text, watermark, logo",
        "width": 1080,
        "height": 1080,
        "metadata": {"reserved_text_areas": [{"x": 0.90, "y": 0.90, "w": 0.05, "h": 0.05}]},
    }

    request = t2i_request_builder_node(state)["t2i_request"]
    metadata = request["metadata"]

    assert metadata["copy_generation_mode"] == "auto_pilot"
    assert metadata["copy_spec"]["items"][0]["text"] == "딸기라떼 출시"
    assert metadata["text_layout_spec"]["reserved_text_areas"]
    assert metadata["reserved_text_areas"] == [{"x": 0.10, "y": 0.70, "w": 0.80, "h": 0.20}]
    assert metadata["text_style_spec"]["profile"] == "premium"
    assert metadata["image_prompt_spec"]["must_not_include_text"] is True
    assert metadata["reference_style_profile"]["ad_style_prompt"] == "reference-inspired"
    assert metadata["product_preserve_spec"]["product_bbox"]["w"] == 0.50
    assert metadata["selected_reference_template"]["template_id"] == "ref-1"
    assert metadata["reference_template_style_keywords"] == ["fresh", "clean"]
