"""Generate and score image-aware text layout candidates."""

from __future__ import annotations

from dataclasses import dataclass

from orchestrator.app.llm.copy_layout_fit import validate_copy_layout_fit
from orchestrator.app.schemas.text_layout import CopySpec, CopyVisualIntent, ImageLayoutAnalysis, LayoutCandidateScore, NormalizedBBox, TextLayoutSpec, TextSlot, TextStyleSpec
from orchestrator.app.vision.layout_analysis import bbox_overlap_ratio


@dataclass(frozen=True)
class CandidateTemplate:
    candidate_id: str
    template: str
    text_box: NormalizedBBox
    product_zone: NormalizedBBox
    alignment: str


def generate_layout_candidates(intent: CopyVisualIntent | None, analysis: ImageLayoutAnalysis, copy_spec: CopySpec, style_spec: TextStyleSpec) -> list[TextLayoutSpec]:
    candidates = [
        CandidateTemplate("left_editorial", "left_text_right_product", NormalizedBBox(x=0.06, y=0.12, w=0.40, h=0.62), NormalizedBBox(x=0.52, y=0.10, w=0.42, h=0.80), "left"),
        CandidateTemplate("right_editorial", "right_text_left_product", NormalizedBBox(x=0.54, y=0.12, w=0.40, h=0.62), NormalizedBBox(x=0.06, y=0.10, w=0.42, h=0.80), "right"),
        CandidateTemplate("top_left_compact", "minimal_corner", NormalizedBBox(x=0.06, y=0.08, w=0.38, h=0.42), NormalizedBBox(x=0.48, y=0.20, w=0.46, h=0.62), "left"),
        CandidateTemplate("top_right_compact", "minimal_corner", NormalizedBBox(x=0.56, y=0.08, w=0.38, h=0.42), NormalizedBBox(x=0.06, y=0.20, w=0.46, h=0.62), "right"),
        CandidateTemplate("bottom_left_compact", "bottom_overlay_panel", NormalizedBBox(x=0.08, y=0.62, w=0.48, h=0.30), NormalizedBBox(x=0.48, y=0.08, w=0.44, h=0.50), "left"),
        CandidateTemplate("bottom_panel", "bottom_overlay_panel", NormalizedBBox(x=0.10, y=0.66, w=0.80, h=0.26), NormalizedBBox(x=0.15, y=0.08, w=0.70, h=0.50), "center"),
    ]
    if analysis.suggested_negative_space_regions:
        region = analysis.suggested_negative_space_regions[0]
        candidates.insert(0, CandidateTemplate("negative_space_primary", "dynamic_side_split", region, NormalizedBBox(x=0.52 if region.x < 0.5 else 0.06, y=0.10, w=0.42, h=0.80), "left" if region.x < 0.5 else "right"))
    return [_layout_from_candidate(candidate, copy_spec, style_spec, intent) for candidate in candidates[: max(4, min(8, len(candidates)))]]


def score_layout_candidate(layout: TextLayoutSpec, copy_spec: CopySpec, analysis: ImageLayoutAnalysis, *, reference_hint: str | None = None) -> LayoutCandidateScore:
    product_overlap = 0.0
    face_hand_overlap = 0.0
    saliency_penalty = 0.0
    hard_rejected = False
    reasons: list[str] = []
    for slot in layout.slots:
        for zone in analysis.exclusion_zones:
            overlap = bbox_overlap_ratio(slot.bbox, zone.bbox)
            if zone.zone_type == "product":
                product_overlap = max(product_overlap, overlap)
                if zone.hard_exclusion and ((slot.role == "headline" and overlap >= 0.08) or (slot.role == "cta" and overlap >= 0.03)):
                    hard_rejected = True
                    reasons.append(f"{slot.role}_product_overlap")
            elif zone.zone_type in {"face", "hand", "person"}:
                face_hand_overlap = max(face_hand_overlap, overlap)
                if overlap > 0:
                    hard_rejected = True
                    reasons.append(f"{slot.role}_face_hand_overlap")
            elif zone.zone_type == "high_saliency":
                saliency_penalty = max(saliency_penalty, overlap * 0.5)
    safe_margin_penalty = 0.0
    for slot in layout.slots:
        if slot.bbox.x < 0.02 or slot.bbox.y < 0.02 or slot.bbox.x + slot.bbox.w > 0.98 or slot.bbox.y + slot.bbox.h > 0.98:
            safe_margin_penalty = 1.0
            hard_rejected = True
            reasons.append(f"{slot.role}_safe_margin")
    fit = validate_copy_layout_fit(copy_spec, layout)
    edge_penalty = _slot_region_average(layout, analysis.edge_density_summary)
    contrast_penalty = _contrast_penalty(layout, analysis.luminance_summary)
    text_area_continuity = max(0.0, 1.0 - edge_penalty - saliency_penalty)
    reference_alignment = 1.0 if reference_hint and reference_hint.replace(" ", "_") in layout.template else 0.5
    balance = 0.8 if layout.product_zone else 0.5
    final = 1.0 - product_overlap - face_hand_overlap - saliency_penalty - edge_penalty - contrast_penalty - safe_margin_penalty
    final += fit.overall_fit * 0.25 + text_area_continuity * 0.2 + reference_alignment * 0.1 + balance * 0.1
    if hard_rejected:
        final -= 1.0
    return LayoutCandidateScore(
        candidate_id=layout.spec_id,
        template=layout.template,
        final_score=round(final, 3),
        product_overlap_ratio=round(product_overlap, 3),
        face_hand_overlap_ratio=round(face_hand_overlap, 3),
        saliency_penalty=round(saliency_penalty, 3),
        edge_density_penalty=round(edge_penalty, 3),
        contrast_penalty=round(contrast_penalty, 3),
        safe_margin_penalty=round(safe_margin_penalty, 3),
        text_area_continuity_score=round(text_area_continuity, 3),
        composition_balance_score=balance,
        reference_alignment_score=reference_alignment,
        copy_fit_score=1.0 if fit.overall_fit else max(0.0, 1.0 - fit.overflow_ratio),
        hard_rejected=hard_rejected or not fit.overall_fit,
        rejection_reasons=reasons + fit.warnings,
    )


def _layout_from_candidate(candidate: CandidateTemplate, copy_spec: CopySpec, style_spec: TextStyleSpec, intent: CopyVisualIntent | None) -> TextLayoutSpec:
    slots: list[TextSlot] = []
    roles = [item.role for item in copy_spec.get_renderable()]
    y = candidate.text_box.y
    heights = {"headline": 0.18, "subheadline": 0.14, "body": 0.14, "cta": 0.08}
    for role in roles:
        h = heights.get(role, 0.10)
        if y + h > candidate.text_box.y + candidate.text_box.h:
            break
        slots.append(TextSlot(slot_id=f"{candidate.candidate_id}_{role}", role=role, bbox=NormalizedBBox(x=candidate.text_box.x, y=y, w=candidate.text_box.w, h=h), rendered_text=next(item.text for item in copy_spec.items if item.role == role), font_metric=_font_metric(style_spec, role), alignment=candidate.alignment, anchor="top_left", overlay_treatment="plain" if role == "cta" and intent and intent.cta_style == "text_link" else style_spec.typography.default_overlay, overlay_color=style_spec.typography.accent_color if role == "cta" else style_spec.typography.primary_color, overlay_opacity=0.82 if role == "cta" and intent and intent.cta_style not in {"none", "text_link"} else 0.0, max_lines=2 if role == "headline" else 3))
        y += h + 0.035
    return TextLayoutSpec(template=candidate.template, canvas_width=1024, canvas_height=1024, slots=slots, product_zone=candidate.product_zone, auto_find_empty_space=True)


def _font_metric(style_spec: TextStyleSpec, role: str):
    from orchestrator.app.schemas.text_layout import FontMetric

    ratio = style_spec.typography.headline_size_ratio if role == "headline" else style_spec.typography.body_size_ratio
    return FontMetric(font_family=style_spec.typography.headline_font, base_size_ratio=ratio, min_size_ratio=max(0.016, ratio * 0.55), max_size_ratio=min(0.12, ratio * 1.15), weight=style_spec.typography.headline_weight if role == "headline" else style_spec.typography.body_weight)


def _slot_region_average(layout: TextLayoutSpec, summary: dict[str, float]) -> float:
    if not layout.slots:
        return 0.0
    values = []
    for slot in layout.slots:
        side = "left" if slot.bbox.x < 0.33 else "right" if slot.bbox.x > 0.50 else "center"
        values.append(summary.get(side, 0.0))
    return sum(values) / max(1, len(values))


def _contrast_penalty(layout: TextLayoutSpec, luminance: dict[str, float]) -> float:
    if not layout.slots:
        return 0.0
    penalties = []
    for slot in layout.slots:
        side = "left" if slot.bbox.x < 0.33 else "right" if slot.bbox.x > 0.50 else "center"
        value = luminance.get(side, 128.0) / 255
        penalties.append(0.2 if 0.35 < value < 0.65 else 0.0)
    return sum(penalties) / len(penalties)
