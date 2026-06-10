"""Layout-aware copy fit checks."""

from __future__ import annotations

import re
from typing import Any

from PIL import ImageFont

from orchestrator.app.rendering.text_metrics import fit_text_block_to_bbox
from orchestrator.app.schemas.text_layout import CopySpec, LayoutCopyFitReport, TextLayoutSpec


BLOCKED_TEXT_PATTERNS = (
    re.compile(r"\.\.\."),
    re.compile(r"\b(beauty_nail|restaurant_bbq|copy_[0-9]+)\b"),
)


def validate_copy_layout_fit(copy_spec: CopySpec, layout: TextLayoutSpec, *, canvas_width: int | None = None, canvas_height: int | None = None) -> LayoutCopyFitReport:
    canvas_width = canvas_width or layout.canvas_width
    canvas_height = canvas_height or layout.canvas_height
    role_results: list[dict[str, Any]] = []
    warnings: list[str] = []
    overflow_total = 0.0
    rewrite_required = False
    for slot in layout.slots:
        item = copy_spec.get_renderable()
        copy_item = next((candidate for candidate in item if candidate.role == slot.role), None)
        if not copy_item:
            continue
        blocked = [pattern.pattern for pattern in BLOCKED_TEXT_PATTERNS if pattern.search(copy_item.text)]
        x, y, w, h = slot.bbox.to_pixels(canvas_width, canvas_height)
        max_size = max(18, int(min(canvas_width, canvas_height) * slot.font_metric.max_size_ratio))
        min_size = max(12, int(min(canvas_width, canvas_height) * slot.font_metric.min_size_ratio))
        fit = fit_text_block_to_bbox(
            copy_item.text,
            font_factory=lambda size: ImageFont.load_default(size=max(1, size)),
            bbox_width=max(1, w),
            bbox_height=max(1, h),
            max_lines=slot.max_lines,
            max_size=max_size,
            min_size=min_size,
            line_height_ratio=slot.font_metric.line_height_em,
        )
        overflow_total += float(fit["overflow_ratio"])
        role_ok = bool(fit["fits"]) and not blocked
        if blocked:
            warnings.append(f"{slot.role}:blocked_text_pattern")
            rewrite_required = True
        if not fit["fits"]:
            warnings.append(f"{slot.role}:overflow")
            rewrite_required = True
        role_results.append({"role": slot.role, "fits": role_ok, "overflow_ratio": fit["overflow_ratio"], "font_size": fit["font_size"], "blocked_patterns": blocked, "bbox": {"x": x, "y": y, "w": w, "h": h}})
    overflow_ratio = overflow_total / max(1, len(role_results))
    return LayoutCopyFitReport(overall_fit=not rewrite_required, role_results=role_results, rewrite_required=rewrite_required, overflow_ratio=round(overflow_ratio, 3), warnings=warnings)


def reduce_optional_copy(copy_spec: CopySpec) -> tuple[CopySpec, list[str]]:
    removed: list[str] = []
    items = list(copy_spec.items)
    for role in ("cta", "subheadline", "body"):
        next_items = [item for item in items if item.role != role]
        if len(next_items) != len(items):
            removed.append(role)
            items = next_items
            break
    return copy_spec.model_copy(update={"items": items}), removed
