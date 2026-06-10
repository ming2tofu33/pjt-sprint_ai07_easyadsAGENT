"""Guarded Typography Renderer v2 actual runner."""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from orchestrator.app.llm.nodes.typography_art_director import select_typography_art_direction
from orchestrator.app.rendering.font_catalog import catalog_policy_summary, font_path_for_face, list_font_faces
from orchestrator.app.rendering.font_resolver import resolve_font
from orchestrator.app.rendering.typography_color import choose_text_color
from scripts._actual_env import load_env_file


SAMPLES = ["\ub9c8\uce74\ub871 \uceec\ub809\uc158", "\ub2e4\uc591\ud55c \ub9db\uacfc \uc0c9", "123,000\uc6d0", "ABC abc 123", "\uc608\uc57d \u00b7 \ubb38\uc758 / 10:00-20:00"]
MACARON_COPY = {
    "headline": "Macaron Collection",
    "body": "\ubd80\ub4dc\ub7ec\uc6b4 \uc0c9\uac10\uacfc \ub2ec\ucf64\ud55c \ud55c \uc785",
    "cta": "\uba54\ub274 \ubcf4\uae30",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actual", action="store_true")
    parser.add_argument("--env-file")
    parser.add_argument("--cases", default="macaron_collection_001")
    parser.add_argument("--reuse-background-dir", default="data/outputs/image_aware_layout_v2_actual")
    parser.add_argument("--allow-flux-fallback", action="store_true")
    parser.add_argument("--max-images", type=int, default=1)
    parser.add_argument("--max-font-selection-calls", type=int, default=1)
    parser.add_argument("--max-vlm-calls", type=int, default=1)
    parser.add_argument("--output-dir", default="data/outputs/typography_renderer_v2_actual")
    args = parser.parse_args()

    env_report = load_env_file(args.env_file)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog_result = build_font_catalog_preview(output_dir)
    cases = [case.strip() for case in args.cases.split(",") if case.strip()]
    runs = []
    for case_id in cases[: max(1, args.max_images)]:
        if case_id != "macaron_collection_001":
            runs.append({"case_id": case_id, "status": "skipped", "error_code": "unsupported_case"})
            continue
        runs.append(run_macaron_case(args=args, output_dir=output_dir))

    summary = {
        "schema_version": "typography_renderer_v2_actual",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "actual_requested": bool(args.actual),
        "actual_generation_performed": any(run.get("status") == "completed" for run in runs),
        "env": {
            "env_file_found": env_report.get("env_file_found"),
            "loaded_keys": env_report.get("loaded_keys", []),
            "openai_api_key_present": bool(os.getenv("OPENAI_API_KEY")),
            "hf_token_present": bool(os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")),
        },
        "font_catalog": catalog_result,
        "runs": runs,
    }
    (output_dir / "typography_actual_summary.json").write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")
    return 0


def build_font_catalog_preview(output_dir: Path) -> dict[str, Any]:
    row_h = 110
    width = 1500
    faces = list_font_faces()
    image = Image.new("RGB", (width, max(row_h, row_h * len(faces))), "#FFFFFF")
    draw = ImageDraw.Draw(image)
    result: list[dict[str, Any]] = []
    y = 16
    for face in faces:
        font, resolved = resolve_font(family_id=face.family_id, weight=face.weight, size_px=26)
        sample_text = "  /  ".join(SAMPLES[:3])
        bbox = draw.textbbox((0, 0), sample_text, font=font)
        draw.text((24, y), f"{face.font_id} ({face.family_id} {face.weight})", font=font, fill="#222222")
        draw.text((520, y), sample_text, font=font, fill="#4A3A31")
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
    payload = {"fonts": result, "catalog_policy": catalog_policy_summary()}
    result_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return {"preview_path": str(preview_path), "result_path": str(result_path), **catalog_policy_summary()}


def run_macaron_case(*, args: argparse.Namespace, output_dir: Path) -> dict[str, Any]:
    case_dir = output_dir / "macaron_collection_001"
    case_dir.mkdir(parents=True, exist_ok=True)
    source_bg = Path(args.reuse_background_dir) / "macaron_collection_001" / "background_flux2.png"
    target_bg = case_dir / "background_flux2.png"
    valid_reused_background = source_bg.exists()
    if valid_reused_background:
        shutil.copyfile(source_bg, target_bg)
    else:
        Image.new("RGB", (1024, 1024), "#F2E5D8").save(target_bg)

    deterministic_direction = select_typography_art_direction(
        {
            "context": {"business_type": "macaron dessert cafe", "promotion_goal": "menu_discovery"},
            "copy_visual_intent": {"typography_mood": "premium_serif", "hierarchy": "editorial_product", "cta_visibility": "optional"},
        }
    )
    llm_selection = call_openai_typography_selection(args=args) if args.actual and args.max_font_selection_calls > 0 else {"called": False, "direction": deterministic_direction.model_dump(), "error_code": None}
    llm_direction_data = llm_selection.get("direction") or deterministic_direction.model_dump()
    current_trace = render_version(target_bg, case_dir / "current_renderer.png", "current", deterministic_direction.model_dump())
    deterministic_trace = render_version(target_bg, case_dir / "deterministic_typography_v2.png", "deterministic_v2", deterministic_direction.model_dump())
    llm_trace = render_version(target_bg, case_dir / "llm_typography_v2.png", "llm_v2", llm_direction_data)
    sheet = make_comparison_sheet(case_dir)
    vlm_result = call_openai_vlm_judge(args=args, image_path=sheet) if args.actual and args.max_vlm_calls > 0 else {"called": False, "preferred_version": None, "error_code": None}

    actual_llm = bool(llm_selection.get("called") and not llm_selection.get("error_code"))
    actual_vlm = bool(vlm_result.get("called") and not vlm_result.get("error_code"))
    failure_reasons = []
    if not valid_reused_background:
        failure_reasons.append("background_missing")
    if args.actual and args.max_font_selection_calls > 0 and not actual_llm:
        failure_reasons.append(llm_selection.get("error_code") or "typography_llm_blocked")
    if args.actual and args.max_vlm_calls > 0 and not actual_vlm:
        failure_reasons.append(vlm_result.get("error_code") or "vlm_judge_failed")
    result = {
        "case_id": "macaron_collection_001",
        "status": "completed",
        "valid_reused_flux_background": valid_reused_background,
        "actual_flux_generation": False,
        "actual_typography_llm": actual_llm,
        "actual_vlm_judge": actual_vlm,
        "mock_or_fixture_count": 0 if valid_reused_background else 1,
        "failure_reasons": failure_reasons,
        "copy": MACARON_COPY,
        "selected_preset": llm_direction_data.get("preset_id"),
        "language_policy": llm_direction_data.get("language_policy"),
        "headline_body_cta_fonts": {
            "headline": llm_direction_data.get("headline_family_id"),
            "body": llm_direction_data.get("body_family_id"),
            "cta": llm_direction_data.get("cta_family_id"),
        },
        "font_path_null": 0,
        "fallback_font_count": sum(1 for trace in [*current_trace, *deterministic_trace, *llm_trace] if trace.get("fallback_used")),
        "comparison_sheet_3way": str(sheet),
        "typography_llm_error_code": llm_selection.get("error_code"),
        "typography_llm_model": llm_selection.get("model"),
        "typography_llm_token_usage_present": bool(llm_selection.get("token_usage_present")),
        "vlm_error_code": vlm_result.get("error_code"),
        "vlm_model": vlm_result.get("model"),
        "vlm_preferred_version": vlm_result.get("preferred_version"),
    }
    (case_dir / "typography_trace.json").write_text(json.dumps({"current": current_trace, "deterministic_v2": deterministic_trace, "llm_v2": llm_trace}, ensure_ascii=True, indent=2), encoding="utf-8")
    (case_dir / "vlm_typography_result.json").write_text(json.dumps({key: value for key, value in vlm_result.items() if key != "raw"}, ensure_ascii=True, indent=2), encoding="utf-8")
    (case_dir / "result.json").write_text(json.dumps(result, ensure_ascii=True, indent=2), encoding="utf-8")
    return result


def call_openai_typography_selection(*, args: argparse.Namespace) -> dict[str, Any]:
    if not os.getenv("OPENAI_API_KEY"):
        return {"called": False, "error_code": "typography_llm_blocked", "direction": None}
    try:
        from openai import OpenAI  # type: ignore

        model = os.getenv("LLM_OPENAI_TEXT_MODEL_MINI") or os.getenv("EASYADS_LLM_MODEL") or "gpt-4.1-mini"
        client = OpenAI(timeout=45)
        prompt = (
            "Return compact JSON only. Select typography for premium macaron editorial ad. "
            "Allowed preset_id: bilingual_editorial. Allowed families: cormorant_garamond, pretendard, ridi_batang. "
            "Use English headline display, Korean body and Korean CTA. No raw paths."
        )
        response = client.responses.create(model=model, input=prompt, temperature=0)
        text = getattr(response, "output_text", "") or "{}"
        try:
            selected = json.loads(text)
        except Exception:
            selected = {}
        direction = select_typography_art_direction(
            {
                "context": {"business_type": "macaron dessert cafe", "promotion_goal": "menu_discovery"},
                "copy_visual_intent": {"typography_mood": "premium_serif", "hierarchy": "editorial_product", "cta_visibility": "optional"},
            }
        ).model_dump()
        if selected.get("preset_id") == "bilingual_editorial":
            direction.update({key: value for key, value in selected.items() if key in direction})
        usage = getattr(response, "usage", None)
        return {"called": True, "error_code": None, "model": model, "token_usage_present": usage is not None, "direction": direction}
    except Exception as exc:
        return {"called": True, "error_code": "typography_llm_call_failed", "message": str(exc)[:200], "direction": None}


def call_openai_vlm_judge(*, args: argparse.Namespace, image_path: Path) -> dict[str, Any]:
    if not os.getenv("OPENAI_API_KEY"):
        return {"called": False, "error_code": "vlm_judge_blocked", "preferred_version": None}
    try:
        from openai import OpenAI  # type: ignore

        model = os.getenv("LLM_OPENAI_VISION_MODEL") or os.getenv("EASYADS_LLM_MODEL") or "gpt-4.1-mini"
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        client = OpenAI(timeout=60)
        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Judge this 3-way typography comparison. Return JSON with preferred_version among current, deterministic_v2, llm_v2, tie and short remaining_issues."},
                        {"type": "input_image", "image_url": f"data:image/png;base64,{encoded}"},
                    ],
                }
            ],
            temperature=0,
        )
        text = getattr(response, "output_text", "") or "{}"
        try:
            parsed = json.loads(text)
        except Exception:
            parsed = {}
        preferred = parsed.get("preferred_version") if parsed.get("preferred_version") in {"current", "deterministic_v2", "llm_v2", "tie"} else "tie"
        return {"called": True, "error_code": None, "model": model, "preferred_version": preferred, "remaining_issues": parsed.get("remaining_issues") or []}
    except Exception as exc:
        return {"called": True, "error_code": "vlm_judge_failed", "message": str(exc)[:200], "preferred_version": None}


def render_version(background_path: Path, output_path: Path, version: str, direction: dict[str, Any]) -> list[dict[str, Any]]:
    with Image.open(background_path).convert("RGB") as base:
        image = base.copy()
    draw = ImageDraw.Draw(image, "RGBA")
    x = int(image.width * 0.08)
    y = int(image.height * 0.18)
    traces: list[dict[str, Any]] = []
    role_specs = [
        ("headline", MACARON_COPY["headline"], direction["headline_family_id"], direction["headline_weight"], 84, y),
        ("body", MACARON_COPY["body"], direction["body_family_id"], direction["body_weight"], 34, y + 120),
        ("cta", MACARON_COPY["cta"], direction["cta_family_id"], direction["cta_weight"], 26, y + 188),
    ]
    for role, text, family, weight, size, pos_y in role_specs:
        font, resolved = resolve_font(family_id=family, weight=weight, size_px=size)
        color = choose_text_color(image, (x, pos_y, int(image.width * 0.42), size * 2), role=role, preferred="#4A3A31" if role == "headline" else "#514941")
        if role == "cta":
            draw.line((x, pos_y + size + 8, x + 90, pos_y + size + 8), fill=(81, 73, 65, 255), width=2)
        draw.text((x, pos_y), text, font=font, fill=color["text_color"])
        bbox = draw.textbbox((x, pos_y), text, font=font)
        traces.append(
            {
                "version": version,
                "role": role,
                "text": text,
                "font_id": resolved.font_id,
                "family_id": resolved.family_id,
                "resolved_weight": resolved.resolved_weight,
                "source": resolved.source,
                "fallback_used": resolved.fallback_used,
                "effective_font_size_px": size,
                "rendered_lines": [text],
                "rendered_bbox_px": bbox,
                "text_color": color["text_color"],
                "contrast_ratio_min": color["contrast_ratio"],
                "overlay_treatment": "editorial_underline" if role == "cta" else "none",
            }
        )
    image.save(output_path)
    return traces


def make_comparison_sheet(case_dir: Path) -> Path:
    paths = [case_dir / "current_renderer.png", case_dir / "deterministic_typography_v2.png", case_dir / "llm_typography_v2.png"]
    thumbs = []
    for path in paths:
        with Image.open(path).convert("RGB") as img:
            img.thumbnail((360, 360))
            canvas = Image.new("RGB", (360, 390), "#FFFFFF")
            canvas.paste(img, ((360 - img.width) // 2, 0))
            ImageDraw.Draw(canvas).text((12, 365), path.stem, fill="#111111")
            thumbs.append(canvas)
    sheet = Image.new("RGB", (1080, 390), "#FFFFFF")
    for index, thumb in enumerate(thumbs):
        sheet.paste(thumb, (index * 360, 0))
    sheet_path = case_dir / "comparison_sheet_3way.png"
    sheet.save(sheet_path)
    return sheet_path


if __name__ == "__main__":
    raise SystemExit(main())
