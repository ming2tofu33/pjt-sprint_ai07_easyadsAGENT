import os
import pytest
from orchestrator.app.llm.schemas.image_prompt_v3 import ScenePlan, PromptQualityPolicy
from orchestrator.app.llm.prompt_adapters import (
    render_gpt_image_2_prompt,
    render_sd35_large_prompt,
    render_flux_prompt,
    render_engine_prompt,
)


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


@pytest.fixture
def sample_scene_plan():
    return ScenePlan(
        business_type="cafe",
        ad_format="instagram_feed",
        product_or_service="strawberry latte",
        desired_mood=["pastel pink", "cream"],
        primary_subject="strawberry latte product hero on the right",
        secondary_props=["fresh strawberries", "saucer"],
        reserved_copy_area="left",
    )


@pytest.fixture
def sample_policy():
    return PromptQualityPolicy(
        no_text_policy="No text allowed",
        safe_area_policy="Keep left area clear",
        brand_safety_policy="Brand safe",
        stock_like_risk_policy="Avoid stock-like setups",
        tacky_visual_risk_policy="Ensure high-end look",
        business_fit_policy="Fit cafe business constraints",
        fake_text_negative_terms=["text", "letters", "logo", "watermark", "signage"],
        positive_safe_area_terms=["clean empty table space", "blank negative space"],
    )


def test_gpt_image_2_prompt_adapter(sample_scene_plan, sample_policy):
    output = render_gpt_image_2_prompt(
        sample_scene_plan,
        sample_policy,
        preset_id="cafe_dessert_soft_premium",
    )

    assert output.metadata.get("adapter_version") == "v3"
    assert output.metadata.get("subject_placement") == "right"
    assert output.metadata.get("reserved_copy_area") == "left"
    
    assert output.engine == "gpt_image_2"
    assert output.negative_prompt is None
    
    prompt = output.prompt
    assert "text-free advertising background" in prompt
    assert "later Korean copy overlay" in prompt
    assert "Do not include any text" in prompt
    assert "letters" in prompt
    assert "logo" in prompt
    assert "watermark" in prompt
    assert "signage" in prompt
    assert "right" in prompt  # subject placement (opposite of left)
    
    assert output.metadata.get("adapter_version") == "v3"
    assert output.metadata.get("subject_placement") == "right"
    assert output.metadata.get("reserved_copy_area") == "left"


def test_sd35_large_prompt_adapter(sample_scene_plan, sample_policy):
    output = render_sd35_large_prompt(sample_scene_plan, sample_policy)
    
    assert output.engine == "sd35_large"
    assert output.prompt is not None
    assert output.negative_prompt is not None
    
    # positive should contain tag terms
    assert "premium commercial photography" in output.prompt
    assert "cafe ad background" in output.prompt
    
    # negative should contain text/logo terms
    neg = output.negative_prompt
    assert "text" in neg
    assert "logo" in neg
    assert "watermark" in neg
    assert "typography" in neg


def test_flux_prompt_adapter(sample_scene_plan, sample_policy):
    output = render_flux_prompt(sample_scene_plan, sample_policy)
    
    assert output.engine == "flux"
    assert output.negative_prompt is None
    assert output.metadata.get("flux_negative_policy") == "positive_substitution"
    
    # flux should use positive safe language
    prompt = output.prompt
    assert "clean unmarked surfaces" in prompt
    assert "blank negative space" in prompt
    assert "no visible writing" in prompt or "no visible writing or signage" in prompt


def test_render_engine_prompt_routing(sample_scene_plan, sample_policy):
    out_gpt_1 = render_engine_prompt(
        "gpt_image_1",
        sample_scene_plan,
        sample_policy,
        preset_id="cafe_dessert_soft_premium",
    )
    assert out_gpt_1.engine == "gpt_image_1"

    out_gpt = render_engine_prompt(
        "gpt_image_2",
        sample_scene_plan,
        sample_policy,
        preset_id="cafe_dessert_soft_premium",
    )
    assert out_gpt.engine == "gpt_image_2"
    assert out_gpt.metadata.get("preset_id") == "cafe_dessert_soft_premium"
    
    out_sd35 = render_engine_prompt(
        "sd35_large",
        sample_scene_plan,
        sample_policy,
        preset_id="cafe_dessert_soft_premium",
    )
    assert out_sd35.engine == "sd35_large"
    assert out_sd35.metadata.get("preset_id") == "cafe_dessert_soft_premium"

    out_flux = render_engine_prompt(
        "flux",
        sample_scene_plan,
        sample_policy,
        preset_id="cafe_dessert_soft_premium",
    )
    assert out_flux.engine == "flux"
    assert out_flux.metadata.get("preset_id") == "cafe_dessert_soft_premium"
    
    # Unknown engine fallback
    out_fallback = render_engine_prompt(
        "unknown_engine",
        sample_scene_plan,
        sample_policy,
        preset_id="cafe_dessert_soft_premium",
    )
    assert out_fallback.engine == "gpt_image_1"
    assert out_fallback.metadata.get("preset_id") == "cafe_dessert_soft_premium"
    assert len(out_fallback.warnings) > 0
    assert "gpt_image_1" in out_fallback.warnings[0] or "unknown_engine" in out_fallback.warnings[0]
