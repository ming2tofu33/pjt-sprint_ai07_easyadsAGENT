import json

import pytest

from orchestrator.app.llm.llm_output_validator import (
    parse_and_validate_llm_json,
    parse_llm_json,
    validate_llm_output,
)
from orchestrator.app.schemas.llm_marketing import (
    AdFormatSpec,
    CopywritingOutput,
    MarketingCopy,
    PromptOptimizationOutput,
    PromptRenderOutput,
    RefactoringOutput,
    ValidatorOutput,
)


AD_FORMAT_SPEC_PAYLOAD = {
    "ad_format": "instagram_feed",
    "platform": "instagram",
    "aspect_ratio": "1:1",
    "width": 1080,
    "height": 1080,
    "information_density": "medium",
    "visual_priority": "mood_first",
    "output_strategy": "generate_text_free_background_then_overlay",
}

LAYOUT_SPEC_PAYLOAD = {
    "layout_type": "single_hero",
    "copy_space": "bottom",
    "safe_area": {"x": 0.06, "y": 0.06, "width": 0.88, "height": 0.88},
    "text_zones": [
        {"x": 0.10, "y": 0.66, "width": 0.80, "height": 0.14, "role": "headline", "max_chars": 28},
        {"x": 0.12, "y": 0.82, "width": 0.76, "height": 0.08, "role": "cta", "max_chars": 16},
    ],
    "product_zone": {"x": 0.10, "y": 0.12, "width": 0.80, "height": 0.48},
    "cta_zone": {"x": 0.12, "y": 0.82, "width": 0.76, "height": 0.08},
    "overlay_style": "gradient",
    "text_align": "center",
    "max_text_density": "medium",
}

MARKETING_COPY_PAYLOAD = {
    "headline": "Today only BBQ set",
    "subcopy": "Warm grill, quick reservation, and a full table for dinner.",
    "cta": "Reserve now",
    "price_line": "Dinner set from 29,000 KRW",
    "period_line": "This weekend",
    "hashtags": ["#bbq", "#dinner"],
}

IMAGE_PROMPT_PAYLOAD = {
    "subject": "Korean BBQ dinner table",
    "style": "realistic commercial food photography",
    "lighting": "warm restaurant lighting",
    "composition": "text-free background with clean bottom copy space",
    "copy_space": "bottom",
    "negative_prompt": "text, letters, logo, watermark",
    "scene": "BBQ restaurant advertising background",
    "avoid_text": True,
}

USER_READABLE_GUIDE_PAYLOAD = {
    "summary": "Create a text-free BBQ advertising background.",
    "subject_ko": "Korean BBQ",
    "mood_ko": "warm and appetizing",
    "composition_ko": "bottom copy space",
    "copy_space_ko": "bottom",
    "style_keywords": ["restaurant", "food", "text_free"],
    "copy_space": "bottom",
    "warnings": ["Do not render text in the image."],
}


@pytest.mark.parametrize(
    ("schema_model", "payload", "node_name"),
    [
        (
            ValidatorOutput,
            {
                "context": {
                    "business_type": "restaurant",
                    "item_or_service": "BBQ set",
                    "promotion_goal": "reservation_cta",
                    "extra": {"ad_format": "instagram_feed"},
                },
                "missing_fields": [],
                "confidence": 0.88,
                "needs_user_selection": False,
                "inferred_entry_mode": "chat_start",
                "inferred_generation_route": "text_to_image",
                "inferred_ad_format": AD_FORMAT_SPEC_PAYLOAD,
                "progress_state": {
                    "current_step": 4,
                    "total_steps": 4,
                    "current_label": "Ready for planning",
                    "remaining_fields": [],
                    "can_skip_question_screen": True,
                },
                "reasoning_summary": "All required context fields are present.",
            },
            "validator",
        ),
        (
            CopywritingOutput,
            {
                "marketing_copy": MARKETING_COPY_PAYLOAD,
                "tone_profile": {"voice": "warm", "style": "local friendly"},
                "alternatives": [
                    {
                        "headline": "Dinner starts at our grill",
                        "subcopy": "Bring your group and reserve a warm table.",
                        "cta": "Book a table",
                    }
                ],
                "rationale": "Copy follows restaurant reservation intent.",
            },
            "copywriting",
        ),
        (
            PromptOptimizationOutput,
            {
                "image_prompt": IMAGE_PROMPT_PAYLOAD,
                "user_readable_image_guide": USER_READABLE_GUIDE_PAYLOAD,
                "negative_prompt": "text, letters, logo, watermark",
                "rationale": "Prompt keeps the generated background text-free.",
            },
            "prompt_optimization",
        ),
        (
            PromptRenderOutput,
            {
                "engine": "sd35_large",
                "positive_prompt": "Korean BBQ dinner table, realistic commercial food photography",
                "negative_prompt": "text, letters, logo, watermark",
                "render_profile": "balanced",
                "render_notes": ["Separate positive and negative prompts."],
                "width": 1080,
                "height": 1080,
                "metadata": {"render_text_in_image": False},
            },
            "prompt_renderer",
        ),
        (
            RefactoringOutput,
            {
                "marketing_copy": MARKETING_COPY_PAYLOAD,
                "ad_format_spec": AD_FORMAT_SPEC_PAYLOAD,
                "layout_spec": LAYOUT_SPEC_PAYLOAD,
                "image_prompt": IMAGE_PROMPT_PAYLOAD,
                "context": {
                    "business_type": "restaurant",
                    "item_or_service": "BBQ set",
                    "promotion_goal": "reservation_cta",
                    "extra": {"ad_format": "instagram_feed"},
                },
                "user_readable_image_guide": USER_READABLE_GUIDE_PAYLOAD,
                "rationale": "Combined structured output for legacy refactoring shape.",
            },
            "refactoring",
        ),
    ],
)
def test_parse_and_validate_valid_llm_json_outputs(schema_model, payload, node_name):
    raw_output = json.dumps(payload)

    result = parse_and_validate_llm_json(raw_output, schema_model, node_name=node_name)

    assert result.ok is True
    assert result.stage == "schema_validation"
    assert result.node_name == node_name
    assert result.schema_name == schema_model.__name__
    assert result.data
    assert result.errors == []


def test_parse_and_validate_accepts_fenced_json_block():
    raw_output = "```json\n" + json.dumps(MARKETING_COPY_PAYLOAD) + "\n```"

    result = parse_and_validate_llm_json(raw_output, MarketingCopy, node_name="copywriting")

    assert result.ok is True
    assert result.stage == "schema_validation"
    assert result.data["headline"] == MARKETING_COPY_PAYLOAD["headline"]


def test_parse_llm_json_extracts_json_from_fenced_block():
    raw_output = "```json\n" + json.dumps(MARKETING_COPY_PAYLOAD) + "\n```"

    result = parse_llm_json(raw_output, node_name="copywriting")

    assert result.ok is True
    assert result.raw_payload["headline"] == MARKETING_COPY_PAYLOAD["headline"]


def test_validate_llm_output_rejects_unknown_literal_value():
    invalid_payload = {
        **AD_FORMAT_SPEC_PAYLOAD,
        "ad_format": "insta_post",
    }

    result = validate_llm_output(invalid_payload, AdFormatSpec, node_name="format_planner")

    assert result.ok is False
    assert result.stage == "schema_validation"
    assert result.schema_name == "AdFormatSpec"
    assert "ad_format" in result.error_summary


def test_parse_and_validate_reports_invalid_json_before_schema_validation():
    result = parse_and_validate_llm_json('{"headline": "missing end"', CopywritingOutput, node_name="copywriting")

    assert result.ok is False
    assert result.stage == "json_parse"
    assert result.schema_name == "CopywritingOutput"
    assert result.errors[0]["type"] == "json_decode_error"


def test_parse_and_validate_reports_missing_required_fields():
    result = parse_and_validate_llm_json(
        {
            "engine": "sd35_large",
            "positive_prompt": "text-free BBQ background",
        },
        PromptRenderOutput,
        node_name="prompt_renderer",
    )

    assert result.ok is False
    assert result.stage == "schema_validation"
    assert "width" in result.error_summary
