"""Deterministic final composite quality evaluation."""

from __future__ import annotations

import hashlib
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

from PIL import Image

from orchestrator.app.quality_gate.final_composite_policy import actions_for_failures, primary_action_for_failures, status_for_action
from orchestrator.app.quality_gate.final_composite_schemas import (
    CompositeFailureType,
    FinalCompositeMetricReport,
    FinalCompositeQualityReport,
)


def evaluate_final_composite(state: dict[str, Any], *, attempt: int | None = None) -> FinalCompositeQualityReport:
    image_path, source_failures = resolve_evaluated_final_image_path(state)
    failures: list[CompositeFailureType] = list(source_failures)
    image_hash = _sha256_file(image_path) if image_path and Path(image_path).exists() else ""
    traces = _typography_traces(state)
    metrics = build_metric_report(state, image_path=image_path, traces=traces)
    failures.extend(_failures_from_metrics(metrics, traces))
    failures.extend(_failures_from_ocr(state))
    if _final_composite_actual_mode() and not _public_vlm(state):
        failures.append("provider_unavailable")
    failures = _dedupe(failures)
    confidence = 0.85 if image_path and Path(image_path).exists() else 0.2
    action = primary_action_for_failures(failures)
    status = status_for_action(action, confidence=confidence)
    if not image_path:
        status = "unavailable"
    return FinalCompositeQualityReport(
        status=status,  # type: ignore[arg-type]
        evaluated_image_path=image_path or "",
        evaluated_image_sha256=image_hash,
        deterministic_metrics=metrics,
        ocr_result=_public_ocr(state),
        vlm_result=_public_vlm(state),
        failure_types=failures,
        primary_action=action,
        suggested_actions=actions_for_failures(failures),
        retry_feedback=feedback_for_failures(failures),
        confidence=confidence,
        attempt=attempt or int(state.get("final_composite_attempts") or 1),
        public_summary={
            "status": status,
            "failure_types": failures,
            "primary_action": action,
            "evaluated_image_sha256": image_hash,
            "metric_summary": {
                "expected_copy_match_score": metrics.expected_copy_match_score,
                "headline_body_size_ratio": metrics.headline_body_size_ratio,
                "cta_area_ratio": metrics.cta_area_ratio,
                "safe_margin_pass": metrics.safe_margin_pass,
            },
        },
    )


def resolve_evaluated_final_image_path(state: dict[str, Any]) -> tuple[str | None, list[CompositeFailureType]]:
    render_result = state.get("render_result") if isinstance(state.get("render_result"), dict) else {}
    final_path = render_result.get("final_image_path")
    failures: list[CompositeFailureType] = []
    if not final_path:
        return None, ["provider_unavailable"]
    top_level = state.get("final_image_path")
    if top_level and str(top_level) != str(final_path):
        failures.append("final_image_contract_mismatch")
    artifacts = state.get("artifact_refs") or []
    if not any(isinstance(item, dict) and item.get("type") == "final_image" and str(item.get("path")) == str(final_path) for item in artifacts):
        failures.append("provider_unavailable")
    path = Path(str(final_path))
    if not path.exists():
        return str(final_path), ["provider_unavailable"]
    try:
        with Image.open(path) as image:
            image.verify()
    except Exception:
        failures.append("provider_unavailable")
    if str(path.name).endswith("failed_composite_preview.png"):
        failures.append("copy_clipping")
    if bool(render_result.get("metadata", {}).get("overflow_detected")):
        failures.append("copy_clipping")
    if int(render_result.get("rendered_slot_count") or 0) <= 0 and _expected_copy(state):
        failures.append("expected_copy_mismatch")
    background = state.get("background_image_path") or render_result.get("background_image_path")
    if background and Path(str(background)).exists() and _sha256_file(path) == _sha256_file(background):
        failures.append("provider_unavailable")
    return str(final_path), failures


def build_metric_report(state: dict[str, Any], *, image_path: str | None, traces: list[dict[str, Any]]) -> FinalCompositeMetricReport:
    headline = _trace_for_role(traces, "headline")
    body = _trace_for_role(traces, "body") or _trace_for_role(traces, "subheadline")
    cta = _trace_for_role(traces, "cta")
    h_size = _num(headline.get("effective_font_size_px") if headline else None)
    b_size = _num(body.get("effective_font_size_px") if body else None)
    cta_size = _num(cta.get("effective_font_size_px") if cta else None)
    canvas_area = _image_area(image_path)
    cta_area = _bbox_area(cta.get("rendered_bbox_px") if cta else None) / canvas_area
    plate_area = sum(_bbox_area(trace.get("overlay_bbox_px")) for trace in traces if trace.get("overlay_bbox_px")) / canvas_area
    return FinalCompositeMetricReport(
        expected_copy_match_score=_expected_copy_match_score(state),
        clipping_detected=bool((state.get("render_result") or {}).get("metadata", {}).get("overflow_detected")) or any(_trace_clipped(trace, state) for trace in traces),
        product_overlap_ratio=_max_overlap(traces, state, {"product"}),
        face_hand_overlap_ratio=_max_overlap(traces, state, {"face", "hand", "person"}),
        headline_body_size_ratio=h_size / b_size if b_size else 0.0,
        cta_headline_size_ratio=cta_size / h_size if h_size else 0.0,
        cta_area_ratio=cta_area,
        plate_area_ratio=plate_area,
        headline_contrast_ratio=_contrast(headline),
        body_contrast_ratio=_contrast(body),
        cta_contrast_ratio=_contrast(cta),
        safe_margin_pass=all(_safe_margin(trace, image_path) for trace in traces),
        alignment_score=_vlm_score(state, "alignment_score"),
        visual_clutter_score=_vlm_score(state, "visual_clutter_score"),
        business_fit_score=_vlm_score(state, "business_fit_score"),
        brand_fit_score=_vlm_score(state, "brand_fit_score"),
        commercial_viability_score=_vlm_score(state, "commercial_viability_score"),
    )


def feedback_for_failures(failures: list[str]) -> list[str]:
    return [f"final_composite:{failure}" for failure in failures]


def _failures_from_metrics(metrics: FinalCompositeMetricReport, traces: list[dict[str, Any]]) -> list[CompositeFailureType]:
    failures: list[CompositeFailureType] = []
    if metrics.expected_copy_match_score < 0.80:
        failures.append("expected_copy_mismatch")
    if metrics.clipping_detected:
        failures.append("copy_clipping")
    if metrics.product_overlap_ratio >= 0.08:
        failures.append("product_overlap")
    if metrics.face_hand_overlap_ratio >= 0.01:
        failures.append("face_hand_overlap")
    if 0 < metrics.headline_body_size_ratio < 1.5:
        failures.append("weak_headline_hierarchy")
    if metrics.cta_headline_size_ratio > 0.8 or metrics.cta_area_ratio > 0.10:
        failures.append("cta_dominance")
    if metrics.plate_area_ratio > 0.20:
        failures.append("plate_too_large")
    if any(value is not None and value < threshold for value, threshold in ((metrics.headline_contrast_ratio, 3.0), (metrics.body_contrast_ratio, 4.5), (metrics.cta_contrast_ratio, 4.5))):
        failures.append("low_contrast")
    if not metrics.safe_margin_pass:
        failures.append("safe_margin_violation")
    if any(trace.get("fallback_used") for trace in traces):
        failures.append("font_fallback")
    if metrics.visual_clutter_score is not None and metrics.visual_clutter_score > 0.60:
        failures.append("visual_clutter")
    if metrics.alignment_score is not None and metrics.alignment_score < 0.55:
        failures.append("alignment_error")
    if metrics.business_fit_score is not None and metrics.business_fit_score < 0.55:
        failures.append("business_fit_mismatch")
    if metrics.brand_fit_score is not None and metrics.brand_fit_score < 0.55:
        failures.append("brand_fit_mismatch")
    if metrics.commercial_viability_score is not None and metrics.commercial_viability_score < 0.55:
        failures.append("commercial_viability_low")
    return failures


def _failures_from_ocr(state: dict[str, Any]) -> list[CompositeFailureType]:
    final_ocr = state.get("final_ocr_gate") if isinstance(state.get("final_ocr_gate"), dict) else {}
    if not final_ocr:
        return ["provider_unavailable"]
    ocr = final_ocr.get("ocr") if isinstance(final_ocr.get("ocr"), dict) else {}
    if int(ocr.get("missing_text_count") or 0) > 0:
        return ["expected_copy_mismatch"]
    if int(ocr.get("extra_text_count") or 0) > 2:
        return ["unexpected_text"]
    return []


def _expected_copy_match_score(state: dict[str, Any]) -> float:
    expected = [_normalize_text(item) for item in _expected_copy(state)]
    if not expected:
        return 1.0
    detected = " ".join(_normalize_text(item) for item in _detected_copy(state))
    if not detected:
        return 0.0
    matches = sum(1 for item in expected if item and item in detected)
    return matches / max(1, len(expected))


def _expected_copy(state: dict[str, Any]) -> list[str]:
    copy_spec = state.get("copy_spec") if isinstance(state.get("copy_spec"), dict) else {}
    items = copy_spec.get("items") if isinstance(copy_spec, dict) else []
    values = [str(item.get("text")) for item in items or [] if isinstance(item, dict) and item.get("is_renderable", True) and item.get("text")]
    marketing = state.get("marketing_copy") if isinstance(state.get("marketing_copy"), dict) else {}
    for key in ("headline", "subcopy", "cta", "price_line"):
        if marketing.get(key):
            values.append(str(marketing[key]))
    return _dedupe(values)


def _detected_copy(state: dict[str, Any]) -> list[str]:
    final_ocr = state.get("final_ocr_gate") if isinstance(state.get("final_ocr_gate"), dict) else {}
    ocr = final_ocr.get("ocr") if isinstance(final_ocr.get("ocr"), dict) else {}
    detected = ocr.get("detected_text") or final_ocr.get("detected_text") or []
    if isinstance(detected, dict):
        return [str(item) for item in detected.values() if item]
    return [str(item) for item in detected or []]


def _typography_traces(state: dict[str, Any]) -> list[dict[str, Any]]:
    render_result = state.get("render_result") if isinstance(state.get("render_result"), dict) else {}
    metadata = render_result.get("metadata") if isinstance(render_result.get("metadata"), dict) else {}
    return [trace for trace in metadata.get("typography_render_traces") or [] if isinstance(trace, dict)]


def _trace_for_role(traces: list[dict[str, Any]], role: str) -> dict[str, Any] | None:
    return next((trace for trace in traces if trace.get("role") == role), None)


def _trace_clipped(trace: dict[str, Any], state: dict[str, Any]) -> bool:
    bbox = trace.get("rendered_bbox_px")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return True
    return any("..." in str(line) or "…" in str(line) for line in trace.get("rendered_lines") or [])


def _max_overlap(traces: list[dict[str, Any]], state: dict[str, Any], zone_types: set[str]) -> float:
    analysis = state.get("image_layout_analysis") if isinstance(state.get("image_layout_analysis"), dict) else {}
    zones = analysis.get("exclusion_zones") if isinstance(analysis, dict) else []
    max_ratio = 0.0
    width = int(analysis.get("canvas_width") or 1)
    height = int(analysis.get("canvas_height") or 1)
    for trace in traces:
        tb = trace.get("rendered_bbox_px")
        if not isinstance(tb, (list, tuple)) or len(tb) != 4:
            continue
        for zone in zones or []:
            if not isinstance(zone, dict) or zone.get("zone_type") not in zone_types:
                continue
            zb = zone.get("bbox") or {}
            px = (int(zb.get("x", 0) * width), int(zb.get("y", 0) * height), int((zb.get("x", 0) + zb.get("w", 0)) * width), int((zb.get("y", 0) + zb.get("h", 0)) * height))
            max_ratio = max(max_ratio, _iou(tuple(tb), px))
    return max_ratio


def _safe_margin(trace: dict[str, Any], image_path: str | None) -> bool:
    if not image_path:
        return False
    try:
        with Image.open(image_path) as image:
            w, h = image.size
    except Exception:
        return False
    bbox = trace.get("rendered_bbox_px")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return False
    margin = int(min(w, h) * 0.04)
    return bbox[0] >= margin and bbox[1] >= margin and bbox[2] <= w - margin and bbox[3] <= h - margin


def _public_ocr(state: dict[str, Any]) -> dict[str, Any]:
    final_ocr = state.get("final_ocr_gate") if isinstance(state.get("final_ocr_gate"), dict) else {}
    return {key: final_ocr.get(key) for key in ("status", "decision", "retry_feedback", "ocr") if key in final_ocr}


def _public_vlm(state: dict[str, Any]) -> dict[str, Any] | None:
    value = state.get("final_composite_vlm_result")
    return value if isinstance(value, dict) else None


def _vlm_score(state: dict[str, Any], key: str) -> float | None:
    vlm = _public_vlm(state) or {}
    if key not in vlm:
        return None
    try:
        score = float(vlm[key])
        return score / 10.0 if score > 1.0 else score
    except Exception:
        return None


def _final_composite_actual_mode() -> bool:
    return str(os.getenv("EASYADS_FINAL_COMPOSITE_ACTUAL", "")).strip().lower() in {"1", "true", "yes", "on"}


def _contrast(trace: dict[str, Any] | None) -> float | None:
    if not trace:
        return None
    value = trace.get("contrast_ratio_min") or trace.get("contrast_ratio_average")
    return float(value) if value is not None else None


def _bbox_area(bbox: object) -> float:
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return 0.0
    return max(0.0, float(bbox[2]) - float(bbox[0])) * max(0.0, float(bbox[3]) - float(bbox[1]))


def _image_area(image_path: str | None) -> float:
    if not image_path:
        return 1.0
    try:
        with Image.open(image_path) as image:
            return float(max(1, image.width * image.height))
    except Exception:
        return 1.0


def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    denom = max(1, min(_bbox_area(a), _bbox_area(b)))
    return inter / denom


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w가-힣一-龥 ]+", "", text)
    return text.strip()


def _num(value: object) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _dedupe(values: list[Any]) -> list[Any]:
    output = []
    for value in values:
        if value not in output:
            output.append(value)
    return output
