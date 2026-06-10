from PIL import Image, ImageDraw

from orchestrator.app.rendering.font_catalog import nearest_available_weight
from orchestrator.app.rendering.font_resolver import resolve_font


def test_resolve_ridi_batang_to_bundled_font():
    font, resolved = resolve_font(family_id="RIDIBatang", weight=700, size_px=42)
    assert resolved.family_id == "ridi_batang"
    assert resolved.source == "bundled"
    assert resolved.relative_path
    assert not resolved.fallback_used
    assert getattr(font, "path", None)


def test_unsupported_weight_maps_to_nearest_available():
    assert nearest_available_weight("ridi_batang", 900) == 400
    _, resolved = resolve_font(family_id="ridi_batang", weight=900, size_px=32)
    assert resolved.resolved_weight == 400


def test_hangul_glyph_coverage_has_positive_bbox():
    font, resolved = resolve_font(family_id="pretendard", weight=400, size_px=32)
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    bbox = draw.textbbox((0, 0), "마카롱 컬렉션 ABC 123", font=font)
    assert resolved.source == "bundled"
    assert bbox[2] - bbox[0] > 0
