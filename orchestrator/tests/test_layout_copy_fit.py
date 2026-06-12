from orchestrator.app.llm.copy_layout_fit import reduce_optional_copy, validate_copy_layout_fit
from orchestrator.app.schemas.text_layout import CopyItem, CopySpec, FontMetric, NormalizedBBox, TextLayoutSpec, TextSlot


def _layout(width: float = 0.35) -> TextLayoutSpec:
    metric = FontMetric(base_size_ratio=0.06, min_size_ratio=0.03, max_size_ratio=0.08, weight=800)
    return TextLayoutSpec(
        template="minimal_corner",
        canvas_width=512,
        canvas_height=512,
        slots=[TextSlot(slot_id="headline", role="headline", bbox=NormalizedBBox(x=0.06, y=0.12, w=width, h=0.12), font_metric=metric, max_lines=1)],
    )


def test_copy_layout_fit_flags_overflow_and_forbidden_placeholder_text():
    copy = CopySpec(items=[CopyItem(role="headline", text="restaurant_bbq copy_123 ... 너무 긴 문장입니다 너무 긴 문장입니다")])

    report = validate_copy_layout_fit(copy, _layout(width=0.20))

    assert report.overall_fit is False
    assert report.rewrite_required is True
    assert any("blocked_text_pattern" in warning for warning in report.warnings)
    assert any("overflow" in warning for warning in report.warnings)


def test_reduce_optional_copy_removes_one_optional_role():
    copy = CopySpec(
        items=[
            CopyItem(role="headline", text="딸기라떼 신메뉴"),
            CopyItem(role="subheadline", text="부드럽고 산뜻하게"),
            CopyItem(role="cta", text="지금 보기"),
        ]
    )

    reduced, removed = reduce_optional_copy(copy)

    assert removed == ["cta"]
    assert [item.role for item in reduced.items] == ["headline", "subheadline"]
