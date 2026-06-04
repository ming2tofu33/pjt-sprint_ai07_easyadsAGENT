from orchestrator.app.llm.prompt_renderer import render_prompt_for_engine
from orchestrator.app.llm.nodes.prompt_renderer import prompt_renderer_node
from orchestrator.app.schemas.llm_marketing import ImagePrompt


def _prompt():
    return ImagePrompt(
        subject="삼겹살",
        style="professional commercial food photography",
        lighting="warm commercial lighting",
        composition="text-free background with bottom copy space",
        copy_space="bottom",
        negative_prompt="text, watermark, logo, letters, numbers",
    )


def test_prompt_renderer_outputs_engine_specific_prompts():
    mock = render_prompt_for_engine(_prompt(), "mock")
    sd35 = render_prompt_for_engine(_prompt(), "sd35_large")
    flux = render_prompt_for_engine(_prompt(), "flux")
    gpt = render_prompt_for_engine(_prompt(), "gpt_image_2")

    assert mock.positive_prompt != sd35.positive_prompt
    assert "no text" in flux.positive_prompt
    assert "no watermark" in flux.positive_prompt
    assert "no logo" in flux.positive_prompt
    assert "Create a text-free advertising background" in gpt.positive_prompt


def test_prompt_renderer_separates_sd35_positive_and_negative_prompts():
    output = render_prompt_for_engine(_prompt(), "sd35_large")

    assert "text, watermark" not in output.positive_prompt
    assert output.negative_prompt == "text, watermark, logo, letters, numbers"


def test_prompt_renderer_metadata_keeps_no_text_policy():
    output = render_prompt_for_engine(_prompt(), "mock", metadata={"ad_format": "instagram_feed"})

    assert output.metadata["render_text_in_image"] is False
    assert output.metadata["ad_format"] == "instagram_feed"


def test_prompt_renderer_node_preserves_tlfp_metadata():
    state = {
        "job_id": "prompt-render-job",
        "thread_id": "prompt-render-thread",
        "engine": "mock",
        "render_profile": "balanced",
        "ad_format_spec": {"ad_format": "instagram_feed", "platform": "instagram", "aspect_ratio": "1:1", "width": 1080, "height": 1080},
        "layout_spec": {"copy_space": "bottom"},
        "copy_spec": {"copy_mode": "standard"},
        "text_style_spec": {"profile": "premium"},
        "text_layout_spec": {"reserved_text_areas": [{"x": 0.05, "y": 0.06, "w": 0.90, "h": 0.18}]},
        "image_prompt_spec": {
            "scene_description": "clean background",
            "product_subject": "삼겹살",
            "composition": "Reserve bottom area",
            "lighting": "warm",
            "reserved_text_areas": [{"x": 0.05, "y": 0.06, "w": 0.90, "h": 0.18}],
            "must_not_include_text": True,
            "negative_prompt_en": "text, letters, numbers, hangul, watermark, logo",
            "target_width": 1080,
            "target_height": 1080,
            "aspect_ratio": "1:1",
        },
        "reference_style_profile": {"ad_style_prompt": "reference-inspired"},
        "product_preserve_spec": {"product_bbox": {"x": 0.3, "y": 0.3, "w": 0.4, "h": 0.4}},
        "selected_reference_template_id": "ref-1",
        "selected_reference_template": {"template_id": "ref-1"},
        "reference_template_selection": {"style_profile_hint": {"style_keywords": ["clean"]}},
        "text_overlay_pending": True,
    }

    output = prompt_renderer_node(state)["prompt_render_output"]
    metadata = output["metadata"]

    assert metadata["reserved_text_areas"] == [{"x": 0.05, "y": 0.06, "w": 0.90, "h": 0.18}]
    assert metadata["render_text_in_image"] is False
    assert metadata["must_not_include_text"] is True
    assert metadata["selected_reference_template_id"] == "ref-1"
    assert "copy_spec" not in metadata
    assert "product_preserve_spec" not in metadata
    assert "selected_reference_template" not in metadata
