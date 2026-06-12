"""Characterization tests for dirty-field propagation (locked before refactor)."""

import pytest

from orchestrator.app.graph.state import calculate_dirty_fields


@pytest.mark.parametrize(
    "changed, expected",
    [
        ([], []),
        (["unknown_field"], ["unknown_field"]),
        (
            ["brand_tone"],
            sorted({
                "brand_tone", "marketing_copy", "copywriting_output",
                "image_prompt", "prompt_render_output",
                "text_style_spec", "text_layout_spec", "image_prompt_spec",
            }),
        ),
        (
            ["ad_format"],
            sorted({
                "ad_format", "image_prompt", "prompt_render_output",
                "ad_format_spec", "layout_spec",
                "text_layout_spec", "image_prompt_spec", "t2i_request",
            }),
        ),
        (
            ["business_type"],
            sorted({"business_type", "image_prompt", "prompt_render_output"}),
        ),
        (
            ["copy_generation_mode"],
            sorted({
                "copy_generation_mode", "marketing_copy", "copy_spec",
                "text_layout_spec", "image_prompt_spec", "prompt_render_output",
            }),
        ),
        (
            ["price_or_discount"],
            sorted({
                "price_or_discount", "copy_spec", "text_layout_spec",
                "image_prompt_spec", "prompt_render_output", "t2i_request",
            }),
        ),
        (
            ["region_type"],
            sorted({
                "region_type", "text_style_spec", "text_layout_spec",
                "image_prompt_spec", "prompt_render_output",
            }),
        ),
        # Propagation is single-pass: marketing_copy as a *trigger* dirties copy
        # specs, but does NOT transitively re-trigger other rules' outputs.
        (
            ["marketing_copy"],
            sorted({
                "marketing_copy", "copy_spec", "text_layout_spec",
                "image_prompt_spec", "prompt_render_output", "t2i_request",
            }),
        ),
    ],
)
def test_dirty_propagation(changed, expected):
    assert calculate_dirty_fields({}, changed) == expected


def test_multiple_changed_fields_union():
    result = calculate_dirty_fields({}, ["brand_tone", "ad_format"])
    expected = sorted(
        set(calculate_dirty_fields({}, ["brand_tone"]))
        | set(calculate_dirty_fields({}, ["ad_format"]))
    )
    assert result == expected
