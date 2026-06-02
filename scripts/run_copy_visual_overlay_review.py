#!/usr/bin/env python
"""Create deterministic copy/visual overlay previews from existing batch outputs."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.app.llm.copy_tone_policy import normalize_copy_for_business, score_copy_visual_fit
from orchestrator.app.rendering.copy_visual_validation import build_copy_visual_validation_report
from orchestrator.app.rendering.font_resolver import load_font

SAMPLE_COPY_BY_CASE: dict[str, dict[str, str]] = {
    "cafe_dessert_001": {
        "business_type": "cafe",
        "headline": "\ub538\uae30\ub77c\ub5bc \uc2e0\uba54\ub274",
        "subcopy": "\ubd80\ub4dc\ub7fd\uace0 \uc0b0\ub73b\ud55c \uc624\ub298\uc758 \ud55c \uc794",
        "cta": "\uc9c0\uae08 \ub9cc\ub098\ubcf4\uae30",
    },
    "restaurant_bbq_001": {
        "business_type": "restaurant_bbq",
        "headline": "\uc624\ub298 \uc800\ub141\uc740 \uc81c\ub300\ub85c",
        "subcopy": "\uc22f\ubd88\ud5a5 \uac00\ub4dd\ud55c \ud504\ub9ac\ubbf8\uc5c4 \uace0\uae43\uc9d1",
        "cta": "\uc608\uc57d \ubb38\uc758\ud558\uae30",
    },
    "beauty_salon_001": {
        "business_type": "beauty_skincare",
        "headline": "\ub9d1\uc740 \ud53c\ubd80 \ub8e8\ud2f4",
        "subcopy": "\ub098\uc5d0\uac8c \ub9de\ucd98 \ud504\ub9ac\ubbf8\uc5c4 \ucf00\uc5b4",
        "cta": "\uc0c1\ub2f4 \uc608\uc57d\ud558\uae30",
    },
}

TEXT_AREAS = {
    "cafe_dessert_001": {"x": 0.08, "y": 0.18, "w": 0.42, "h": 0.45},
    "restaurant_bbq_001": {"x": 0.08, "y": 0.18, "w": 0.42, "h": 0.45},
    "beauty_salon_001": {"x": 0.08, "y": 0.16, "w": 0.46, "h": 0.48},
}

TEXT_COLORS = {
    "cafe_dessert_001": "#4a2418",
    "restaurant_bbq_001": "#fff3dc",
    "beauty_salon_001": "#2f2f36",
}


def find_latest_batch_report(log_dir: Path = Path("data/logs")) -> Path | None:
    reports = sorted(log_dir.glob("gpt_image2_quality_batch_v1_*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    return reports[0] if reports else None


def load_batch_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_overlay_review(
    report: Path | None = None,
    output_dir: Path = Path("data/logs"),
    max_cases: int = 3,
    dry_run: bool = False,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    source_report = report or find_latest_batch_report()
    review = {
        "schema_version": "copy_visual_quality_loop_v1",
        "created_at": datetime.now(UTC).isoformat(),
        "source_batch_report": str(source_report) if source_report else None,
        "status": "dry_run" if dry_run else "completed",
        "total_cases": 0,
        "cases": [],
        "notes": [],
    }
    if not source_report or not source_report.exists():
        review["status"] = "blocked"
        review["notes"].append("No GPT-image-2 quality batch report was found.")
        return _write_reports(review, output_dir, timestamp)

    batch = load_batch_report(source_report)
    cases = list(batch.get("cases") or [])[: max(0, max_cases)]
    review["total_cases"] = len(cases)
    for case in cases:
        review["cases"].append(_review_case(case, dry_run=dry_run))

    return _write_reports(review, output_dir, timestamp)


def _review_case(case: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    case_id = str(case.get("case_id") or "unknown_case")
    job_id = str(case.get("job_id") or "")
    result_payload = case.get("result_payload") or {}
    final_image_path = case.get("final_image_path") or result_payload.get("final_image_path") or case.get("output_path")
    sample = SAMPLE_COPY_BY_CASE.get(case_id, {"business_type": str(case.get("business_type") or "generic"), "headline": "\uad11\uace0 \uc2dc\uc548", "subcopy": "\uae54\ub054\ud55c \ube0c\ub79c\ub4dc \uba54\uc2dc\uc9c0", "cta": "\uc790\uc138\ud788 \ubcf4\uae30"})
    business_type = sample["business_type"]
    normalized = normalize_copy_for_business(sample, business_type)
    text_area = TEXT_AREAS.get(case_id, {"x": 0.08, "y": 0.18, "w": 0.44, "h": 0.44})
    text_color = TEXT_COLORS.get(case_id, "#222222")
    case_review: dict[str, Any] = {
        "case_id": case_id,
        "job_id": job_id,
        "business_type": business_type,
        "background_image_path": final_image_path,
        "preview_image_path": None,
        "copy": normalized["normalized_copy"],
        "copy_quality": normalized,
        "visual_validation": None,
        "copy_visual_fit": score_copy_visual_fit(normalized["normalized_copy"], business_type, case.get("visual_metadata") or case.get("prompt_summary")),
        "recommendation": {},
        "status": "dry_run" if dry_run else "pending",
    }
    if dry_run:
        case_review["recommendation"] = {"next_step": "Run without --dry-run when local final image artifacts are available."}
        return case_review
    if not final_image_path or not Path(final_image_path).exists():
        case_review["status"] = "skipped"
        case_review["recommendation"] = {"next_step": "Preview skipped because final image artifact is missing."}
        return case_review

    preview_path, render_result = render_overlay_preview(
        Path(final_image_path),
        normalized["normalized_copy"],
        business_type,
        text_area,
        text_color,
    )
    validation = build_copy_visual_validation_report(
        str(final_image_path),
        text_area,
        text_color,
        render_result,
        min_font_size=render_result.get("min_font_size"),
    )
    case_review["preview_image_path"] = str(preview_path)
    case_review["visual_validation"] = validation
    case_review["status"] = "preview_created"
    case_review["recommendation"] = _build_recommendation(case_id, validation, normalized)
    return case_review

def render_overlay_preview(
    image_path: Path,
    copy: dict[str, str],
    business_type: str,
    text_area: dict[str, float],
    text_color: str,
) -> tuple[Path, dict[str, Any]]:
    image = Image.open(image_path).convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    width, height = image.size
    x = int(text_area["x"] * width)
    y = int(text_area["y"] * height)
    area_w = int(text_area["w"] * width)
    area_h = int(text_area["h"] * height)
    headline_size = max(28, int(width * 0.058))
    subcopy_size = max(22, int(width * 0.032))
    cta_size = max(22, int(width * 0.03))
    headline_font = load_font(headline_size, weight="bold")
    subcopy_font = load_font(subcopy_size)
    cta_font = load_font(cta_size, weight="bold")
    uses_light_plate = business_type == "cafe" or business_type.startswith("beauty")

    if uses_light_plate:
        draw.rounded_rectangle(
            (x - 26, y - 24, x + area_w, y + area_h),
            radius=28,
            fill=(255, 255, 255, 178),
        )
    else:
        draw.rounded_rectangle(
            (x - 18, y - 16, x + area_w, y + area_h),
            radius=22,
            fill=(0, 0, 0, 70),
        )
    rgba = _hex_to_rgba(text_color)
    shadow = (0, 0, 0, 120) if rgba[:3] != (255, 255, 255) else (0, 0, 0, 160)
    boxes = []
    cursor_y = y
    for text, font, spacing in [
        (copy.get("headline") or "", headline_font, int(headline_size * 1.25)),
        (copy.get("subcopy") or "", subcopy_font, int(subcopy_size * 1.5)),
    ]:
        if not text:
            continue
        bbox = draw.textbbox((x, cursor_y), text, font=font)
        draw.text((x + 2, cursor_y + 2), text, font=font, fill=shadow)
        draw.text((x, cursor_y), text, font=font, fill=rgba)
        boxes.append({"text": text, "bbox": bbox})
        cursor_y += spacing
    cta = copy.get("cta") or ""
    if cta:
        bbox = draw.textbbox((x, cursor_y), cta, font=cta_font)
        pad_x = 18
        pad_y = 10
        button = (x, cursor_y - pad_y, bbox[2] + pad_x * 2, bbox[3] + pad_y)
        draw.rounded_rectangle(
            button,
            radius=18,
            fill=(40, 40, 48, 220) if uses_light_plate else (255, 255, 255, 220),
        )
        cta_fill = (255, 255, 255, 255) if uses_light_plate else (40, 40, 48, 255)
        draw.text((x + pad_x, cursor_y), cta, font=cta_font, fill=cta_fill)
        boxes.append({"text": cta, "bbox": button})
    preview_path = image_path.with_name("copy_visual_preview_0.png")
    image.convert("RGB").save(preview_path)
    return preview_path, {"canvas": {"width": width, "height": height}, "text_boxes": boxes, "min_font_size": min(headline_size, subcopy_size, cta_size)}


def _build_recommendation(case_id: str, validation: dict[str, Any], copy_quality: dict[str, Any]) -> dict[str, Any]:
    recommendations: list[str] = []
    if validation.get("plate_required"):
        recommendations.append("Use a semi-transparent text plate for this background.")
    if validation.get("shadow_required"):
        recommendations.append("Keep subtle shadow or outline for Korean copy readability.")
    if validation.get("safe_area_background_complexity", 0) > 0.45:
        recommendations.append("Ask ImagePrompt v3 for cleaner low-detail negative space.")
    if copy_quality.get("warnings"):
        recommendations.append("Review business tone policy warnings before final copy.")
    if case_id == "beauty_salon_001":
        recommendations.append("Beauty backgrounds should reserve a cleaner bright plate area by default.")
    return {"items": recommendations or ["Overlay preview passes v1 rule-based checks."]}


def _write_reports(review: dict[str, Any], output_dir: Path, timestamp: str) -> dict[str, Any]:
    json_path = output_dir / f"copy_visual_quality_loop_v1_{timestamp}.json"
    md_path = output_dir / f"copy_visual_quality_loop_v1_{timestamp}.md"
    json_path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(review), encoding="utf-8")
    review["report_json_path"] = str(json_path)
    review["report_md_path"] = str(md_path)
    return review


def _render_markdown(review: dict[str, Any]) -> str:
    lines = [
        "# Copy Visual Quality Loop v1",
        "",
        "## Summary",
        f"- Status: {review.get('status')}",
        f"- Source batch report: {review.get('source_batch_report')}",
        f"- Total cases: {review.get('total_cases')}",
        "",
        "## Cases",
    ]
    for case in review.get("cases", []):
        if not isinstance(case, dict):
            lines.extend([
                "",
                "### invalid_case",
                "- Status: invalid",
                "- Warning: case review entry was not a dictionary.",
            ])
            continue

        validation = case.get("visual_validation") or {}
        lines.extend([
            "",
            f"### {case.get('case_id')}",
            f"- Job ID: {case.get('job_id')}",
            f"- Business type: {case.get('business_type')}",
            f"- Background: {case.get('background_image_path')}",
            f"- Preview: {case.get('preview_image_path')}",
            f"- Status: {case.get('status')}",
            f"- Copy score: {case.get('copy_quality', {}).get('quality_score')}",
            f"- Contrast: {validation.get('contrast_ratio_estimate')}",
            f"- Safe area complexity: {validation.get('safe_area_background_complexity')}",
            f"- Warnings: {', '.join(validation.get('warnings') or []) or 'none'}",
        ])
    lines.extend([
        "",
        "## Notes",
        "- This runner does not call GPT-image-2, SD3.5, FLUX, LLM, VLM, OCR, rembg, or SAM.",
        "- Preview images and runtime reports are local artifacts under ignored data directories.",
    ])
    return "\n".join(lines) + "\n"


def _hex_to_rgba(value: str) -> tuple[int, int, int, int]:
    color = value.strip().lstrip("#")
    if len(color) == 3:
        color = "".join(ch * 2 for ch in color)
    if len(color) != 6:
        return (255, 255, 255, 255)
    return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16), 255)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=Path("data/logs"))
    parser.add_argument("--max-cases", type=int, default=3)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    review = run_overlay_review(report=args.report, output_dir=args.output_dir, max_cases=args.max_cases, dry_run=args.dry_run)
    print(json.dumps({"status": review.get("status"), "report_json_path": review.get("report_json_path"), "report_md_path": review.get("report_md_path")}, ensure_ascii=False))
    return 0 if review.get("status") != "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
