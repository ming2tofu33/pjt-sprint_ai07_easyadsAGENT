from orchestrator.app.llm.prompt_renderer import render_prompt_for_engine
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
