"""Consolidated typography tests.

Merged from:
- orchestrator/tests/test_typography_adaptive_color.py
- orchestrator/tests/test_typography_art_direction.py
- orchestrator/tests/test_typography_auto_fit.py
- orchestrator/tests/test_typography_language_policy.py
- orchestrator/tests/test_typography_overlay_policy.py
- orchestrator/tests/test_typography_pixel_wrap.py
- orchestrator/tests/test_typography_renderer_actual_script.py
- orchestrator/tests/test_typography_role_styles.py
"""



# ===== from test_typography_adaptive_color.py =====
from PIL import Image

from orchestrator.app.rendering.typography_color import choose_text_color


def test_white_on_light_is_corrected_to_dark_color():
    image = Image.new("RGB", (200, 200), "#F6E8D8")
    result = choose_text_color(image, (0, 0, 200, 200), role="body", preferred="#FFFFFF")
    assert result["text_color"].lower() != "#ffffff"
    assert result["contrast_ratio"] >= 4.5


def test_dark_background_can_choose_light_text():
    image = Image.new("RGB", (200, 200), "#201712")
    result = choose_text_color(image, (0, 0, 200, 200), role="headline")
    assert result["contrast_ratio"] >= 3.0


# ===== from test_typography_art_direction.py =====
import pytest

from orchestrator.app.llm.nodes.typography_art_director import TypographyArtDirection, select_typography_art_direction


def test_macaron_uses_bilingual_editorial_and_no_button():
    direction = select_typography_art_direction(
        {
            "context": {"business_type": "macaron", "promotion_goal": "menu_discovery"},
            "copy_visual_intent": {"typography_mood": "premium_serif", "hierarchy": "editorial_product", "cta_visibility": "optional"},
        }
    )
    assert direction.preset_id == "bilingual_editorial"
    assert direction.headline_family_id == "cormorant_garamond"
    assert direction.body_family_id == "pretendard"
    assert direction.cta_treatment == "editorial_underline"
    assert direction.language_policy.primary_locale == "mixed"
    assert direction.language_policy.body_language_mode == "korean"
    assert direction.headline_script == "latin"
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


def test_hangul_headline_cormorant_falls_back_to_korean_family():
    direction = TypographyArtDirection(
        preset_id="bilingual_editorial",
        headline_family_id="cormorant_garamond",
        body_family_id="pretendard",
        cta_family_id="pretendard",
        headline_weight=500,
        body_weight=400,
        cta_weight=500,
        headline_scale="display_large",
        body_scale="body_small",
        headline_tracking="tight",
        body_tracking="normal",
        headline_leading="compact",
        body_leading="relaxed",
        headline_script="hangul",
        korean_fallback_family_id="ridi_batang",
    )
    assert direction.headline_family_id == "ridi_batang"


# ===== from test_typography_auto_fit.py =====
from orchestrator.app.rendering.font_resolver import resolve_font
from orchestrator.app.rendering.text_metrics import fit_text_block_to_bbox


def test_auto_fit_binary_search_finds_effective_size():
    fit = fit_text_block_to_bbox(
        "마카롱 컬렉션",
        font_factory=lambda size: resolve_font(family_id="ridi_batang", weight=400, size_px=size)[0],
        bbox_width=360,
        bbox_height=120,
        max_lines=2,
        max_size=72,
        min_size=20,
        line_height_ratio=1.08,
    )
    assert fit["fits"] is True
    assert 20 <= fit["font_size"] <= 72
    assert fit["lines"]


def test_auto_fit_reports_manual_review_when_too_small():
    fit = fit_text_block_to_bbox(
        "매우 긴 문장을 작은 박스에 넣어야 하는 상황",
        font_factory=lambda size: resolve_font(family_id="pretendard", weight=400, size_px=size)[0],
        bbox_width=40,
        bbox_height=20,
        max_lines=1,
        max_size=24,
        min_size=18,
    )
    assert fit["fits"] is False
    assert fit["fit_action"] == "manual_review"


# ===== from test_typography_language_policy.py =====
from orchestrator.app.schemas.text_layout import TypographyLanguagePolicy


def test_typography_language_policy_defaults_keep_body_korean():
    policy = TypographyLanguagePolicy()
    assert policy.primary_locale == "ko-KR"
    assert policy.body_language_mode == "korean"
    assert "body" in policy.korean_required_roles
    assert "headline" in policy.english_allowed_roles


def test_typography_language_policy_allows_english_display_headline():
    policy = TypographyLanguagePolicy(primary_locale="mixed", headline_language_mode="english")
    assert policy.allow_english_display_headline is True
    assert policy.body_language_mode == "korean"


# ===== from test_typography_overlay_policy.py =====
from orchestrator.app.llm.nodes.typography_art_director import select_typography_art_direction


def test_menu_discovery_blocks_large_button_cta():
    direction = select_typography_art_direction(
        {
            "context": {"business_type": "cafe", "promotion_goal": "menu_discovery"},
            "copy_visual_intent": {"typography_mood": "premium_serif", "cta_visibility": "required"},
        }
    )
    assert direction.cta_treatment in {"text_link", "editorial_underline"}


def test_reservation_allows_small_chip():
    direction = select_typography_art_direction(
        {
            "context": {"business_type": "restaurant_bbq", "promotion_goal": "reservation"},
            "copy_visual_intent": {"typography_mood": "clean_sans", "cta_visibility": "required"},
        }
    )
    assert direction.cta_treatment == "small_chip"


# ===== from test_typography_pixel_wrap.py =====
from PIL import Image, ImageDraw

from orchestrator.app.rendering.font_resolver import resolve_font
from orchestrator.app.rendering.text_metrics import measure_text_with_tracking, wrap_text_no_ellipsis


def test_pixel_wrap_uses_text_width_without_ellipsis():
    font, _ = resolve_font(family_id="pretendard", weight=400, size_px=28)
    lines = wrap_text_no_ellipsis("부드럽고 산뜻한 오늘의 마카롱 컬렉션", font=font, max_width=210, max_lines=3)
    assert 1 < len(lines) <= 3
    assert "..." not in "".join(lines)
    assert "…" not in "".join(lines)


def test_tracking_changes_measurement():
    font, _ = resolve_font(family_id="pretendard", weight=400, size_px=28)
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    normal = measure_text_with_tracking(draw, "ABC 123", font=font, tracking_px=0)
    tracked = measure_text_with_tracking(draw, "ABC 123", font=font, tracking_px=2)
    assert tracked > normal


# ===== from test_typography_renderer_actual_script.py =====
import json

from scripts import run_typography_renderer_actual as runner


def test_typography_runner_creates_font_catalog_artifacts(tmp_path, monkeypatch):
    out = tmp_path / "typography"
    monkeypatch.setattr("sys.argv", ["run_typography_renderer_actual.py", "--output-dir", str(out)])
    assert runner.main() == 0
    summary = json.loads((out / "typography_actual_summary.json").read_text(encoding="utf-8"))
    assert summary["actual_generation_performed"] is True
    assert (out / "font_catalog_preview.png").exists()
    assert (out / "font_catalog_result.json").exists()
    assert summary["font_catalog"]["active_core_font_count"] == 23
    case_dir = out / "macaron_collection_001"
    assert (case_dir / "comparison_sheet_3way.png").exists()
    result = json.loads((case_dir / "result.json").read_text(encoding="utf-8"))
    assert result["status"] == "completed"
    assert result["selected_preset"] == "bilingual_editorial"
    assert result["language_policy"]["body_language_mode"] == "korean"
    assert result["font_path_null"] == 0
    assert result["fallback_font_count"] == 0


def test_typography_actual_runner_does_not_complete_unknown_cases(tmp_path, monkeypatch):
    out = tmp_path / "typography"
    monkeypatch.setattr("sys.argv", ["run_typography_renderer_actual.py", "--cases", "unknown_case", "--output-dir", str(out)])
    assert runner.main() == 0
    summary = json.loads((out / "typography_actual_summary.json").read_text(encoding="utf-8"))
    assert summary["runs"][0]["status"] == "skipped"


# ===== from test_typography_role_styles.py =====
from orchestrator.app.llm.nodes.text_style_binder import build_role_styles


def test_role_styles_separate_headline_body_and_cta_hierarchy():
    styles = build_role_styles(
        {
            "preset_id": "editorial_serif_sans",
            "headline_family_id": "ridi_batang",
            "body_family_id": "pretendard",
            "cta_family_id": "pretendard",
            "headline_weight": 400,
            "body_weight": 400,
            "cta_weight": 500,
            "headline_scale": "display_large",
            "body_scale": "body_small",
            "headline_tracking": "tight",
            "body_tracking": "normal",
            "headline_leading": "compact",
            "body_leading": "relaxed",
            "cta_treatment": "editorial_underline",
        }
    )
    assert styles["headline"].family_id != styles["body"].family_id
    assert styles["headline"].size_ratio / styles["body"].size_ratio >= 1.7
    assert styles["headline"].size_ratio / styles["cta"].size_ratio >= 1.5
    assert styles["cta"].overlay_treatment == "editorial_underline"
