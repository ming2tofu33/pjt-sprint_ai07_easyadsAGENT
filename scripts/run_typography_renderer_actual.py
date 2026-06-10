"""Guarded typography renderer v2 actual runner.

Default mode creates only bundled-font catalog artifacts. Actual LLM/VLM/T2I calls
require explicit EASYADS_TYPOGRAPHY_ACTUAL=1 and are intentionally not performed
by tests.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from orchestrator.app.rendering.font_catalog import font_path_for_face, list_font_faces
from orchestrator.app.rendering.font_resolver import resolve_font


SAMPLES = ["마카롱 컬렉션", "다양한 맛과 색", "123,000원", "ABC abc 123", "예약 · 문의 / 10:00-20:00"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actual", action="store_true")
    parser.add_argument("--env-file")
    parser.add_argument("--cases", default="macaron_collection_001,restaurant_bbq_001,beauty_nail_001")
    parser.add_argument("--reuse-background-dir", default="data/outputs/image_aware_layout_v2_actual")
    parser.add_argument("--allow-flux-fallback", action="store_true")
    parser.add_argument("--max-images", type=int, default=3)
    parser.add_argument("--max-font-selection-calls", type=int, default=3)
    parser.add_argument("--max-vlm-calls", type=int, default=3)
    parser.add_argument("--output-dir", default="data/outputs/typography_renderer_v2_actual")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog_result = build_font_catalog_preview(output_dir)
    summary = {
        "schema_version": "typography_renderer_v2_actual",
        "actual_requested": bool(args.actual),
        "actual_generation_performed": False,
        "cases": [case.strip() for case in args.cases.split(",") if case.strip()],
        "font_catalog": catalog_result,
        "warnings": ["actual LLM/VLM/T2I execution is not performed by this guarded runner unless implemented with explicit external guards"],
    }
    (output_dir / "typography_actual_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def build_font_catalog_preview(output_dir: Path) -> dict[str, Any]:
    rows = []
    row_h = 120
    width = 1400
    faces = list_font_faces()
    image = Image.new("RGB", (width, max(row_h, row_h * len(faces))), "#FFFFFF")
    draw = ImageDraw.Draw(image)
    result: list[dict[str, Any]] = []
    y = 16
    for face in faces:
        font, resolved = resolve_font(family_id=face.family_id, weight=face.weight, size_px=28)
        sample_text = "  /  ".join(SAMPLES[:3])
        bbox = draw.textbbox((0, 0), sample_text, font=font)
        draw.text((24, y), f"{face.font_id} ({face.family_id} {face.weight})", font=font, fill="#222222")
        draw.text((420, y), sample_text, font=font, fill="#4A3A31")
        rows.append((face.font_id, y))
        result.append(
            {
                "font_id": face.font_id,
                "family_id": face.family_id,
                "weight": face.weight,
                "load_success": font_path_for_face(face).exists(),
                "source": resolved.source,
                "fallback_used": resolved.fallback_used,
                "bbox_width": bbox[2] - bbox[0],
                "glyph_sample_count": len(SAMPLES),
            }
        )
        y += row_h
    preview_path = output_dir / "font_catalog_preview.png"
    result_path = output_dir / "font_catalog_result.json"
    image.save(preview_path)
    result_path.write_text(json.dumps({"fonts": result}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"preview_path": str(preview_path), "result_path": str(result_path), "font_count": len(result)}


if __name__ == "__main__":
    raise SystemExit(main())
