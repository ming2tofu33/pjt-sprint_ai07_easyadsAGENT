import pytest

from orchestrator.app.llm.nodes.typography_art_director import TypographyArtDirection, select_typography_art_direction


def test_macaron_uses_editorial_serif_sans_and_no_button():
    direction = select_typography_art_direction(
        {
            "context": {"business_type": "macaron", "promotion_goal": "menu_discovery"},
            "copy_visual_intent": {"typography_mood": "premium_serif", "hierarchy": "editorial_product", "cta_visibility": "optional"},
        }
    )
    assert direction.preset_id == "editorial_serif_sans"
    assert direction.headline_family_id == "ridi_batang"
    assert direction.body_family_id == "pretendard"
    assert direction.cta_treatment == "editorial_underline"
    assert len({direction.headline_family_id, direction.body_family_id, direction.cta_family_id}) <= 2


def test_unknown_family_rejected():
    with pytest.raises(ValueError):
        TypographyArtDirection(
            preset_id="clean_modern",
            headline_family_id="assets/fonts/not_allowed.ttf",
            body_family_id="pretendard",
            cta_family_id="pretendard",
            headline_weight=700,
            body_weight=400,
            cta_weight=500,
            headline_scale="headline_large",
            body_scale="body_medium",
            headline_tracking="normal",
            body_tracking="normal",
            headline_leading="normal",
            body_leading="normal",
        )


def test_editorial_button_corrected():
    direction = TypographyArtDirection(
        preset_id="editorial_serif_sans",
        headline_family_id="ridi_batang",
        body_family_id="pretendard",
        cta_family_id="pretendard",
        headline_weight=700,
        body_weight=400,
        cta_weight=500,
        headline_scale="display_large",
        body_scale="body_small",
        headline_tracking="tight",
        body_tracking="normal",
        headline_leading="compact",
        body_leading="relaxed",
        cta_treatment="button",
    )
    assert direction.cta_treatment == "editorial_underline"
