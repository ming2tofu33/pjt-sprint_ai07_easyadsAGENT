"""Generate a Korean demo poster using the existing Final RC rendering pipeline.

This script is intentionally separate from test_* scripts. It creates a stable
demo output without calling external image APIs by default, while keeping the
source-image input replaceable for later live gpt-image-2 outputs.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter

from orchestrator.app.llm.nodes.design_recommendation_node import design_recommendation_node
from orchestrator.app.llm.nodes.image_analysis import image_analysis_node
from orchestrator.app.llm.nodes.image_aware_quality_gate import image_aware_quality_gate_node
from orchestrator.app.llm.nodes.poster_layout_planner import poster_layout_planner_node
from orchestrator.app.llm.nodes.poster_renderer import poster_renderer_node
from orchestrator.app.rendering.font_resolver import resolve_font_path


DEFAULT_PAYLOAD_PATH = Path("data/demo/korean_poster_payload.json")
DEFAULT_OUTPUT_DIR = Path("data/outputs/demo-korean-poster-final-rc")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the Korean Final RC demo poster.")
    parser.add_argument("--payload", default=str(DEFAULT_PAYLOAD_PATH), help="Path to the Korean demo payload JSON.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for demo output artifacts.")
    parser.add_argument("--source-image", default=None, help="Optional source image path. If omitted, a local mock image is generated.")
    return parser.parse_args()


def load_payload(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def create_demo_source_image(path: Path, width: int = 1024, height: int = 1024) -> None:
    """Create a text-free mock image with a right-side subject and left safe zone."""
    image = Image.new("RGB", (width, height), "#111827")
    draw = ImageDraw.Draw(image)

    for y in range(height):
        t = y / max(1, height - 1)
        r = int(17 + 18 * t)
        g = int(24 + 28 * t)
        b = int(39 + 36 * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((560, 120, 1160, 820), fill=(59, 130, 246, 58))
    glow_draw.ellipse((650, 380, 1100, 1080), fill=(20, 184, 166, 44))
    glow = glow.filter(ImageFilter.GaussianBlur(42))
    image = Image.alpha_composite(image.convert("RGBA"), glow)
    draw = ImageDraw.Draw(image)

    panel = (640, 160, 930, 780)
    draw.rounded_rectangle(panel, radius=44, fill=(248, 250, 252, 235), outline=(147, 197, 253, 180), width=3)
    draw.rounded_rectangle((690, 230, 880, 385), radius=28, fill=(30, 64, 175, 235))
    draw.rounded_rectangle((695, 430, 875, 470), radius=18, fill=(191, 219, 254, 230))
    draw.rounded_rectangle((695, 500, 850, 532), radius=16, fill=(125, 211, 252, 210))
    draw.rounded_rectangle((695, 585, 895, 650), radius=26, fill=(17, 24, 39, 230))
    draw.line((720, 675, 860, 675), fill=(148, 163, 184, 210), width=5)

    image.convert("RGB").save(path)


def prepare_source_image(payload: dict[str, Any], output_dir: Path, source_image_arg: str | None) -> tuple[Path, str]:
    source_out = output_dir / "source_or_mock_image.png"
    source_from_payload = payload.get("image_path") or payload.get("source_image_path")
    source_candidate = source_image_arg or source_from_payload

    if source_candidate:
        source_path = Path(source_candidate)
        if not source_path.exists():
            raise FileNotFoundError(f"source image not found: {source_path}")
        shutil.copyfile(source_path, source_out)
        return source_out, "provided_source_image"

    create_demo_source_image(source_out)
    return source_out, "generated_local_mock"


def build_initial_state(payload: dict[str, Any], source_image_path: Path, output_dir: Path) -> dict[str, Any]:
    job_id = payload.get("job_id") or "demo-korean-poster-final-rc"
    copy_items = (payload.get("copy_spec") or {}).get("items", [])
    footer_text = next((item.get("text") for item in copy_items if item.get("role") == "footer" and item.get("text")), None)
    return {
        "job_id": job_id,
        "renderer_mode": payload.get("renderer_mode", "poster_components"),
        "rendering_engine": "python",
        "requested_template_id": payload.get("requested_template_id"),
        "requested_asset_id": payload.get("requested_asset_id"),
        "copy_spec": payload.get("copy_spec") or {},
        "marketing_copy": {"footer": footer_text} if footer_text else {},
        "image_analysis": payload.get("image_analysis") or {},
        "image_input": {"image_path": str(source_image_path)},
        "t2i_result": {"image_paths": [str(source_image_path)]},
        "text_style_spec": {
            "profile": "clean",
            "typography": {
                "headline_font": "NotoSansKR",
                "body_font": "NotoSansKR",
                "headline_weight": 700,
                "body_weight": 400,
                "primary_color": "#FFFFFF",
                "secondary_color": "#D1D5DB",
            },
        },
        "demo_output_dir": str(output_dir),
    }


def run_pipeline(state: dict[str, Any]) -> dict[str, Any]:
    for node in (
        image_analysis_node,
        poster_layout_planner_node,
        poster_renderer_node,
        image_aware_quality_gate_node,
        design_recommendation_node,
    ):
        state.update(node(state))
    return state


def collect_report(
    payload: dict[str, Any],
    state: dict[str, Any],
    output_dir: Path,
    source_image_path: Path,
    source_image_mode: str,
) -> dict[str, Any]:
    render_result = state.get("render_result") or {}
    metadata = render_result.get("metadata", {}) if isinstance(render_result, dict) else {}
    final_image_path = state.get("final_image_path") or render_result.get("final_image_path")

    font_checks = {
        "Pretendard-Regular": bool(resolve_font_path("assets/fonts/Pretendard-Regular.otf")),
        "Pretendard-Bold": bool(resolve_font_path("assets/fonts/Pretendard-Bold.otf")),
        "NotoSansKR-Regular": bool(resolve_font_path("assets/fonts/NotoSansKR-Regular.ttf")),
        "NotoSansKR-Bold": bool(resolve_font_path("assets/fonts/NotoSansKR-Bold.ttf")),
    }

    return {
        "job_id": payload.get("job_id"),
        "topic": payload.get("topic"),
        "purpose": payload.get("purpose"),
        "tone": payload.get("tone"),
        "final_image_path": final_image_path,
        "source_image_path": str(source_image_path),
        "source_image_mode": source_image_mode,
        "payload_path": str(output_dir / "payload.json"),
        "copy_spec": payload.get("copy_spec", {}),
        "image_analysis": state.get("image_analysis") or payload.get("image_analysis", {}),
        "image_analysis_diagnostics": metadata.get("image_analysis_diagnostics", {}),
        "template_diagnostics": metadata.get("template_diagnostics", {}),
        "asset_diagnostics": metadata.get("asset_diagnostics", {}),
        "planner_diagnostics": metadata.get("planner_diagnostics", {}),
        "component_diagnostics": metadata.get("component_diagnostics", []),
        "image_aware_quality_diagnostics": metadata.get("image_aware_quality_diagnostics", {}),
        "design_recommendation": metadata.get("design_recommendation", {}),
        "render_success": metadata.get("render_success", False),
        "quality_pass": metadata.get("quality_pass", False),
        "layout_quality_pass": metadata.get("layout_quality_pass", False),
        "font_checks": font_checks,
    }


def main() -> None:
    args = parse_args()
    payload_path = Path(args.payload)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = load_payload(payload_path)
    payload_copy_path = output_dir / "payload.json"
    payload_copy_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    source_image_path, source_image_mode = prepare_source_image(payload, output_dir, args.source_image)
    state = build_initial_state(payload, source_image_path, output_dir)
    state = run_pipeline(state)

    report = collect_report(payload, state, output_dir, source_image_path, source_image_mode)
    report_path = output_dir / "demo_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Korean demo poster generated.")
    print(f"- final_image_path: {report['final_image_path']}")
    print(f"- source_image_path: {report['source_image_path']}")
    print(f"- demo_report: {report_path}")
    print(f"- recommendation_level: {report['design_recommendation'].get('recommendation_level')}")
    print(f"- quality_pass: {report['quality_pass']}")
    print(f"- layout_quality_pass: {report['layout_quality_pass']}")


if __name__ == "__main__":
    main()
