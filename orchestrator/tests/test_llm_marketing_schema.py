from typing import get_args

import pytest
from pydantic import ValidationError

from orchestrator.app.schemas import llm_marketing as schema


def _is_snake_case(value: str) -> bool:
    return value == value.lower() and "-" not in value and " " not in value


def test_literal_values_are_snake_case():
    literal_types = [
        schema.EntryMode,
        schema.GenerationRoute,
        schema.GenerationEngine,
        schema.RenderProfile,
        schema.JobStatus,
        schema.CopySpace,
        schema.MissingField,
    ]

    for literal_type in literal_types:
        for value in get_args(literal_type):
            assert _is_snake_case(value), value


def test_required_llm_schema_classes_exist():
    expected = [
        "ConversationMessage",
        "MarketingContext",
        "ProgressState",
        "ValidatorOutput",
        "OptionItem",
        "OptionQuestion",
        "UserSelectionRequest",
        "AdFormatSpec",
        "Zone",
        "TextZone",
        "LayoutSpec",
        "MarketingCopy",
        "CopywritingOutput",
        "ImagePrompt",
        "UserReadableImageGuide",
        "PromptOptimizationOutput",
        "PromptRenderOutput",
        "RefactoringOutput",
        "ImageInput",
        "ImageFeatures",
        "ReferenceInput",
        "ReferenceStyleSpec",
        "GeneratedImageCandidate",
        "TextOverlayConfig",
        "BackgroundValidationReport",
        "FinalValidationReport",
        "ValidationReport",
        "JobStatusResponse",
        "ArtifactRef",
        "ErrorInfo",
    ]

    for name in expected:
        assert hasattr(schema, name), name


def test_marketing_context_fields_are_snake_case():
    for field_name in schema.MarketingContext.model_fields:
        assert _is_snake_case(field_name), field_name


def test_llm_schema_uses_existing_t2i_contracts():
    from orchestrator.app.t2i.schemas import T2IRequest, T2IResult

    assert schema.T2IRequest is T2IRequest
    assert schema.T2IResult is T2IResult


def test_progress_state_supports_dynamic_question_steps():
    progress = schema.ProgressState(
        current_step=1,
        total_steps=4,
        current_label="업종 선택",
        remaining_fields=["business_type", "ad_format"],
        can_skip_question_screen=False,
    )

    assert progress.current_step == 1
    assert progress.remaining_fields == ["business_type", "ad_format"]


def test_image_prompt_requires_six_core_fields():
    with pytest.raises(ValidationError):
        schema.ImagePrompt(subject="삼겹살")

    prompt = schema.ImagePrompt(
        subject="삼겹살",
        style="commercial food photography",
        lighting="warm amber lighting",
        composition="copy space at bottom",
        copy_space="bottom",
        negative_prompt="text, watermark, logo",
    )
    assert prompt.negative_prompt == "text, watermark, logo"


def test_prompt_render_output_uses_positive_prompt_and_render_profile():
    output = schema.PromptRenderOutput(
        engine="sd35_large",
        positive_prompt="text-free bbq background",
        negative_prompt="text, logo",
        render_profile="balanced",
        render_notes=["separate positive and negative prompts"],
        width=1024,
        height=1024,
    )

    assert output.positive_prompt.startswith("text-free")
    assert output.render_profile == "balanced"


def test_ad_format_spec_rejects_unknown_branch_values():
    with pytest.raises(ValidationError):
        schema.AdFormatSpec(
            ad_format="random_format",
            platform="instagram",
            aspect_ratio="1:1",
            width=1080,
            height=1080,
            output_strategy="generate_text_free_background_then_overlay",
        )

    with pytest.raises(ValidationError):
        schema.AdFormatSpec(
            ad_format="instagram_feed",
            platform="unknown_platform",
            aspect_ratio="1:1",
            width=1080,
            height=1080,
            output_strategy="generate_text_free_background_then_overlay",
        )

    with pytest.raises(ValidationError):
        schema.AdFormatSpec(
            ad_format="instagram_feed",
            platform="instagram",
            aspect_ratio="3:2",
            width=1080,
            height=1080,
            output_strategy="generate_text_free_background_then_overlay",
        )
