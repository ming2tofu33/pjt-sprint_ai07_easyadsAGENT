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
