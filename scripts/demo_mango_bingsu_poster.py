"""Generate a mango bingsu demo poster through the Final RC rendering pipeline.

The image-generation step requests a text-free source image. All Korean copy,
feature list, footer/CTA, and decorative components are composited later by the
PIL poster renderer.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFilter

from orchestrator.app.llm.nodes.design_recommendation_node import design_recommendation_node
from orchestrator.app.llm.nodes.image_analysis import image_analysis_node
from orchestrator.app.llm.nodes.image_aware_quality_gate import image_aware_quality_gate_node
from orchestrator.app.llm.nodes.poster_layout_planner import poster_layout_planner_node
from orchestrator.app.llm.nodes.poster_renderer import poster_renderer_node
from orchestrator.app.llm.nodes.t2i_generation import t2i_generation_node
from orchestrator.app.rendering.font_resolver import resolve_font_path


DEFAULT_PAYLOAD_PATH = Path("data/demo/mango_bingsu_payload.json")
DEFAULT_OUTPUT_DIR = Path("data/outputs/demo-mango-bingsu-final-rc")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a mango bingsu Korean demo poster.")
    parser.add_argument("--payload", default=str(DEFAULT_PAYLOAD_PATH), help="Path to the mango bingsu demo payload JSON.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for demo output artifacts.")
    parser.add_argument("--source-image", default=None, help="Optional pre-generated text-free source image.")
    parser.add_argument(
        "--no-local-fallback",
        action="store_true",
        help="Fail instead of creating a local text-free fallback image if gpt-image-2 is unavailable.",
    )
    return parser.parse_args()


def load_payload(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def ensure_gpt_image_flags() -> None:
    os.environ.setdefault("EASYADS_ENABLE_EXTERNAL_T2I", "1")
    os.environ.setdefault("EASYADS_ENABLE_GPT_IMAGE_2", "1")
    os.environ.setdefault("EASYADS_GPT_IMAGE_MODEL", "gpt-image-2")
    os.environ.setdefault("T2I_ALLOW_API_CALLS", "1")


def create_local_text_free_mango_source(path: Path, width: int = 1024, height: int = 1024) -> None:
    """Create a text-free fallback visual with mango bingsu on the lower right."""
    image = Image.new("RGB", (width, height), "#E0F2FE")
    draw = ImageDraw.Draw(image)

    for y in range(height):
        t = y / max(1, height - 1)
        r = int(224 + 16 * t)
        g = int(242 + 5 * t)
        b = int(254 - 28 * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((520, 250, 1120, 1040), fill=(251, 191, 36, 80))
    glow_draw.ellipse((620, 150, 1040, 760), fill=(125, 211, 252, 52))
    glow = glow.filter(ImageFilter.GaussianBlur(34))
    image = Image.alpha_composite(image.convert("RGBA"), glow)
    draw = ImageDraw.Draw(image)

    shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.ellipse((575, 770, 980, 890), fill=(15, 23, 42, 50))
    shadow = shadow.filter(ImageFilter.GaussianBlur(20))
    image = Image.alpha_composite(image, shadow)
    draw = ImageDraw.Draw(image)

    bowl_box = (590, 510, 970, 850)
    draw.ellipse((575, 620, 985, 880), fill=(248, 250, 252, 245), outline=(186, 230, 253, 255), width=5)
    draw.ellipse(bowl_box, fill=(255, 251, 235, 255), outline=(14, 165, 233, 120), width=4)

    ice_color = (255, 255, 255, 255)
    draw.ellipse((625, 455, 940, 680), fill=ice_color, outline=(224, 242, 254, 255), width=3)
    draw.ellipse((670, 405, 890, 610), fill=(254, 249, 195, 255), outline=(253, 224, 71, 200), width=3)

    mango_colors = [(251, 191, 36, 255), (245, 158, 11, 255), (253, 224, 71, 255)]
    mango_rects = [
        (690, 410, 760, 470),
        (780, 420, 850, 480),
        (650, 500, 725, 560),
        (740, 510, 820, 575),
        (835, 505, 910, 565),
        (705, 590, 790, 650),
        (810, 585, 900, 650),
    ]
    for idx, rect in enumerate(mango_rects):
        draw.rounded_rectangle(rect, radius=14, fill=mango_colors[idx % len(mango_colors)])

    draw.ellipse((890, 385, 940, 435), fill=(34, 197, 94, 255))
    draw.ellipse((915, 360, 975, 415), fill=(74, 222, 128, 240))

    image.convert("RGB").save(path)


def generate_or_prepare_source(
    payload: dict[str, Any],
    output_dir: Path,
    source_image_arg: str | None,
    allow_local_fallback: bool,
) -> tuple[Path, dict[str, Any]]:
    source_path = output_dir / "source_image.png"
    generation = {
        "requested_engine": "gpt_image_2",
        "source_image_mode": "",
        "gpt_image_2_attempted": False,
        "gpt_image_2_success": False,
        "error": None,
        "prompt": payload.get("t2i_request", {}).get("prompt"),
        "negative_prompt": payload.get("t2i_request", {}).get("negative_prompt"),
    }

    if source_image_arg:
        shutil.copyfile(source_image_arg, source_path)
        source_arg_path = Path(source_image_arg)
        source_mode = "provided_gpt_image_2_source" if "gpt_image_2" in source_arg_path.name or "gpt-image-2" in source_arg_path.as_posix() else "provided_source_image"
        generation.update({"source_image_mode": source_mode})
        if source_mode == "provided_gpt_image_2_source":
            generation.update({"gpt_image_2_success": True, "raw_gpt_image_path": source_arg_path.as_posix()})
        return source_path, generation

    request = payload.get("t2i_request", {})
    state = {
        "job_id": payload.get("job_id"),
        "engine": "gpt_image_2",
        "t2i_request": {
            "prompt": request.get("prompt"),
            "negative_prompt": request.get("negative_prompt"),
            "output_dir": str(output_dir / "gpt-image-2-source"),
            "width": int(request.get("width") or 1024),
            "height": int(request.get("height") or 1024),
            "metadata": {
                "engine": "gpt_image_2",
                "requested_engine": "gpt_image_2",
                "api_call": True,
                "business_type": "cafe",
                "text_overlay_pending": True,
            },
        },
    }

    generation["gpt_image_2_attempted"] = True
    try:
        result = t2i_generation_node(state)
        image_paths = (result.get("t2i_result") or {}).get("image_paths") or []
        if not image_paths:
            raise RuntimeError(result.get("error_message") or "gpt-image-2 returned no image path")
        shutil.copyfile(image_paths[0], source_path)
        generation.update({
            "source_image_mode": "gpt_image_2",
            "gpt_image_2_success": True,
            "raw_gpt_image_path": image_paths[0],
            "t2i_metadata": (result.get("t2i_result") or {}).get("metadata", {}),
        })
        return source_path, generation
    except Exception as exc:
        generation["error"] = str(exc)
        if not allow_local_fallback:
            raise
        create_local_text_free_mango_source(source_path)
        generation.update({"source_image_mode": "local_text_free_fallback"})
        return source_path, generation


def footer_text_from_payload(payload: dict[str, Any]) -> str:
    items = (payload.get("copy_spec") or {}).get("items", [])
    cta = next((item.get("text") for item in items if item.get("role") == "cta" and item.get("text")), "")
    footer = next((item.get("text") for item in items if item.get("role") == "footer" and item.get("text")), "")
    return " · ".join(part for part in [cta, footer] if part)


def build_initial_state(payload: dict[str, Any], source_image_path: Path) -> dict[str, Any]:
    return {
        "job_id": payload.get("job_id"),
        "renderer_mode": payload.get("renderer_mode", "poster_components"),
        "rendering_engine": "python",
        "requested_template_id": payload.get("requested_template_id"),
        "requested_asset_id": payload.get("requested_asset_id"),
        "copy_spec": payload.get("copy_spec") or {},
        "marketing_copy": {"footer": footer_text_from_payload(payload)},
        "image_analysis": payload.get("image_analysis") or {},
        "image_input": {"image_path": str(source_image_path)},
        "t2i_result": {"image_paths": [str(source_image_path)]},
        "text_style_spec": {
            "profile": "event",
            "typography": {
                "headline_font": "BMDOHYEON",
                "body_font": "NotoSansKR",
                "headline_weight": 900,
                "body_weight": 500,
                "primary_color": "#FFFFFF",
                "secondary_color": "#E0F2FE",
            },
        },
    }


def add_demo_components(state: dict[str, Any], payload: dict[str, Any]) -> None:
    layout = state.get("poster_layout_spec") or {}
    components = layout.setdefault("components", [])
    features = payload.get("features") or []
    sticker = payload.get("decorative_sticker") or {}

    for component in components:
        if component.get("type") == "footer_panel":
            component["bbox"] = {"x": 0.08, "y": 0.76, "w": 0.44, "h": 0.07}
            component.setdefault("style", {})["background_color"] = "#0F172ABF"

    if features:
        components.append({
            "type": "icon_feature_list",
            "bbox": {"x": 0.08, "y": 0.54, "w": 0.44, "h": 0.18},
            "content": features,
            "style": {
                "font_size": 30,
                "text_color": "#F8FAFC",
                "icon_color": "#FACC15",
                "background_color": "#0F172A99",
                "asset_id": None,
            },
            "z_index": 22,
        })

    components.append({
        "type": "decorative_sticker",
        "bbox": {"x": 0.08, "y": 0.86, "w": 0.34, "h": 0.035},
        "content": "",
        "style": {
            "sticker_type": sticker.get("sticker_type", "underline_accent"),
            "color": sticker.get("color", "#FACC15"),
            "opacity": sticker.get("opacity", 0.28),
            "asset_id": sticker.get("asset_id"),
        },
        "z_index": 18,
    })

    state["poster_layout_spec"] = layout


def run_pipeline(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    state.update(image_analysis_node(state))
    state.update(poster_layout_planner_node(state))
    add_demo_components(state, payload)
    state.update(poster_renderer_node(state))
    state.update(image_aware_quality_gate_node(state))
    state.update(design_recommendation_node(state))
    return state


def collect_report(payload: dict[str, Any], state: dict[str, Any], output_dir: Path, source_path: Path, generation: dict[str, Any]) -> dict[str, Any]:
    render_result = state.get("render_result") or {}
    metadata = render_result.get("metadata", {}) if isinstance(render_result, dict) else {}
    return {
        "job_id": payload.get("job_id"),
        "topic": payload.get("topic"),
        "purpose": payload.get("purpose"),
        "final_image_path": state.get("final_image_path") or render_result.get("final_image_path"),
        "source_image_path": str(source_path),
        "payload_path": str(output_dir / "payload.json"),
        "source_generation": generation,
        "copy_spec": payload.get("copy_spec", {}),
        "features": payload.get("features", []),
        "decorative_sticker": payload.get("decorative_sticker", {}),
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
        "font_checks": {
            "BMDOHYEON": bool(resolve_font_path("assets/fonts/BMDOHYEON_ttf.ttf")),
            "NotoSansKR-Regular": bool(resolve_font_path("assets/fonts/NotoSansKR-Regular.ttf")),
            "NotoSansKR-Bold": bool(resolve_font_path("assets/fonts/NotoSansKR-Bold.ttf")),
            "Pretendard-Regular": bool(resolve_font_path("assets/fonts/Pretendard-Regular.otf")),
        },
    }


def main() -> None:
    load_dotenv()
    ensure_gpt_image_flags()
    args = parse_args()
    payload_path = Path(args.payload)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = load_payload(payload_path)
    (output_dir / "payload.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    source_path, generation = generate_or_prepare_source(
        payload,
        output_dir,
        args.source_image,
        allow_local_fallback=not args.no_local_fallback,
    )
    state = build_initial_state(payload, source_path)
    state = run_pipeline(state, payload)
    report = collect_report(payload, state, output_dir, source_path, generation)
    (output_dir / "demo_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Mango bingsu demo poster generated.")
    print(f"- source_image_path: {report['source_image_path']}")
    print(f"- source_image_mode: {report['source_generation'].get('source_image_mode')}")
    print(f"- final_image_path: {report['final_image_path']}")
    print(f"- demo_report: {output_dir / 'demo_report.json'}")
    print(f"- recommendation_level: {report['design_recommendation'].get('recommendation_level')}")
    print(f"- quality_pass: {report['quality_pass']}")
    print(f"- layout_quality_pass: {report['layout_quality_pass']}")
    if report["source_generation"].get("error"):
        print(f"- gpt_image_2_error: {report['source_generation']['error']}")


if __name__ == "__main__":
    main()
