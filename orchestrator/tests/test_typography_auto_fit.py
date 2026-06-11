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
