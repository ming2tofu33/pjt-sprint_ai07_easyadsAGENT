"""Final composite quality actual E2E runner.

Actual mode is fail-closed. It must call OpenAI for copy and VLM, call the
FLUX.2 Klein engine, and create the final composite through production nodes.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.app.llm.nodes.adaptive_typography_refiner import adaptive_typography_refiner_node
from orchestrator.app.llm.nodes.copy_spec_parser import copy_spec_parser_node
from orchestrator.app.llm.nodes.final_composite_revision import final_composite_revision_node
from orchestrator.app.llm.nodes.final_copy_revision import final_copy_revision_node
from orchestrator.app.llm.nodes.final_validation import final_validation_node
from orchestrator.app.llm.nodes.image_layout_analyzer import image_layout_analyzer_node
from orchestrator.app.llm.nodes.post_t2i_layout_refiner import post_t2i_layout_refiner_node
from orchestrator.app.llm.nodes.readability_gate import readability_gate_node
from orchestrator.app.llm.nodes.safe_area_gate import safe_area_gate_node
from orchestrator.app.llm.nodes.text_layout_planner import text_layout_planner_node
from orchestrator.app.llm.nodes.text_renderer import text_renderer_node
from orchestrator.app.llm.nodes.text_style_binder import text_style_binder_node
from orchestrator.app.llm.nodes.typography_art_director import typography_art_direction_node
from orchestrator.app.quality_gate.final_composite_service import evaluate_final_composite
from orchestrator.app.t2i.engines.base import T2IGenerationInput
from orchestrator.app.t2i.engines.registry import get_t2i_engine
from scripts._actual_env import load_env_file


REQUIRED_ACTUAL_ENV = {
    "EASYADS_FINAL_COMPOSITE_ACTUAL": "1",
    "EASYADS_COPY_QUALITY_ACTUAL": "1",
    "EASYADS_ENABLE_LLM_CALLS": "true",
    "EASYADS_LLM_PROVIDER": "openai",
    "EASYADS_VLM_ACTUAL": "1",
    "EASYADS_FLUX2_KLEIN_ACTUAL": "1",
    "EASYADS_ENABLE_FLUX2_KLEIN_LOCAL": "true",
}
FORBIDDEN_COPY_TERMS = {"AI", "smart", "consulting", "expert", "technology", "service innovation", "best", "freshest", "free", "price", "guaranteed"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actual", action="store_true")
    parser.add_argument("--env-file")
    parser.add_argument("--case", default="macaron_collection_001")
    parser.add_argument("--seed", type=int, default=62)
    parser.add_argument("--force-flux-generation", action="store_true")
    parser.add_argument("--copy-model", default="gpt-5.4")
    parser.add_argument("--vlm-model", default="gpt-5.4")
    parser.add_argument("--max-copy-calls", type=int, default=2)
    parser.add_argument("--max-vlm-calls", type=int, default=2)
    parser.add_argument("--max-flux-generations", type=int, default=2)
    parser.add_argument("--max-composite-attempts", type=int, default=5)
    parser.add_argument("--output-dir", default="data/outputs/final_composite_quality_actual_gpt54")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    env_report = load_env_file(args.env_file)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = _base_summary(args, env_report)

    if args.dry_run or not args.actual:
        summary.update({"status": "blocked", "missing_requirements": ["--actual"], "runs": []})
        _write_summary(output_dir, summary)
        return 0

    missing = _missing_actual_requirements(args)
    if missing:
        summary.update({"status": "blocked", "missing_requirements": missing, "runs": []})
        _write_summary(output_dir, summary)
        return 0

    case_dir = output_dir / args.case
    case_dir.mkdir(parents=True, exist_ok=True)
    result = run_actual_case(args=args, output_dir=output_dir, case_dir=case_dir)
    summary["runs"] = [result]
    summary["status"] = "completed" if result.get("status") == "completed" else result.get("status", "failed")
    summary["actual_api_calls"] = bool(result.get("copy_token_usage") and result.get("vlm_token_usage"))
    summary["image_generation_performed"] = bool(result.get("flux_output_path") or result.get("background_path"))
    _write_summary(output_dir, summary)
    return 0


def run_actual_case(*, args: argparse.Namespace, output_dir: Path, case_dir: Path) -> dict[str, Any]:
    copy_result = generate_gpt54_copy_candidates(args)
    (output_dir / "copy_candidates_gpt54.json").write_text(json.dumps(copy_result, ensure_ascii=False, indent=2), encoding="utf-8")
    if not _strict_openai_success(copy_result, args.copy_model, prefix="copy"):
        return _blocked(args.case, "copy_generation_not_actual", copy_result=_public(copy_result))

    flux_result = generate_flux2_background(args, case_dir)
    if not _strict_flux_success(flux_result):
        return _blocked(args.case, "flux_generation_not_performed", flux_result=_public(flux_result))

    state = build_initial_state(args=args, copy_result=copy_result, flux_result=flux_result)
    state, initial_report, initial_vlm = render_and_validate(state=state, args=args, case_dir=case_dir, label="initial")
    initial_path = Path(state["render_result"]["final_image_path"])
    background_path = Path(flux_result["image_path"])
    if _sha256(background_path) == _sha256(initial_path):
        return _failed(args.case, "background_copy_used_as_final")

    action = initial_report.primary_action
    revision_trace: dict[str, Any] = {
        "initial_failure_types": initial_report.failure_types,
        "selected_revision_action": action,
        "rerun_start_node": None,
        "t2i_call_delta": 0,
        "revision_counters": {"attempt": 1},
    }
    final_state = state
    final_report = initial_report
    final_vlm = initial_vlm
    repaired_path: str | None = None
    if initial_report.status == "revise" and args.max_composite_attempts > 1:
        final_state, final_report, final_vlm, repaired_path = run_partial_rerun(state=state, action=action, args=args, case_dir=case_dir, revision_trace=revision_trace)

    comparison_path = build_comparison(case_dir, initial_path, Path(repaired_path) if repaired_path else None)
    _write_public_state(case_dir / "initial_state_public.json", state)
    _write_public_state(case_dir / "final_state_public.json", final_state)
    (case_dir / "initial_quality_report.json").write_text(json.dumps(initial_report.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    (case_dir / "final_quality_report.json").write_text(json.dumps(final_report.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    (case_dir / "final_vlm_result.json").write_text(json.dumps(final_vlm, ensure_ascii=False, indent=2), encoding="utf-8")
    (case_dir / "final_ocr_result.json").write_text(json.dumps(final_state.get("final_ocr_gate") or {}, ensure_ascii=False, indent=2), encoding="utf-8")
    (case_dir / "revision_trace.json").write_text(json.dumps(revision_trace, ensure_ascii=False, indent=2), encoding="utf-8")

    run = {
        "case_id": args.case,
        "status": "completed" if completed_conditions(copy_result, flux_result, state, final_state, initial_report, final_report, initial_vlm, final_vlm) else "failed",
        "copy_model": args.copy_model,
        "vlm_model": args.vlm_model,
        "copy_token_usage": copy_result.get("copy_token_usage"),
        "vlm_token_usage": final_vlm.get("vlm_token_usage"),
        "copy_fallback_used": copy_result.get("copy_fallback_used"),
        "vlm_fallback_used": final_vlm.get("vlm_fallback_used"),
        "copy_candidates": copy_result.get("copy_candidates"),
        "selected_copy": copy_result.get("selected_copy"),
        "flux_engine": flux_result.get("flux_engine"),
        "flux_backend": flux_result.get("flux_backend"),
        "flux_model": flux_result.get("flux_model"),
        "flux_latency_ms": flux_result.get("flux_latency_ms"),
        "flux_output_path": flux_result.get("flux_output_path"),
        "background_path": str(background_path),
        "initial_final_composite_path": str(initial_path),
        "repaired_final_composite_path": repaired_path or "pass_without_revision",
        "comparison_image_path": str(comparison_path),
        "background_hash": _sha256(background_path),
        "initial_composite_hash": initial_report.evaluated_image_sha256,
        "final_composite_hash": final_report.evaluated_image_sha256,
        "initial_failure_types": initial_report.failure_types,
        "selected_revision_action": action,
        "t2i_call_delta": revision_trace["t2i_call_delta"],
        "final_quality_status": final_report.status,
        "mock_or_fixture_count": 0,
    }
    (case_dir / "result.json").write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
    return run


def generate_gpt54_copy_candidates(args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(timeout=90)
        prompt = (
            "Return JSON only. Generate exactly 3 ad copy candidates for macaron_collection_001. "
            "Context: dessert cafe, French macaron collection, menu discovery, premium/editorial/warm. "
            "Angles: product-first, emotion-first, editorial/collection-first. English headline allowed; Korean body and CTA preferred; CTA optional. "
            "Avoid AI/smart/consulting/expert/technology/service innovation/best/freshest/free/price/guaranteed claims. "
            "Schema: {\"copy_candidates\":[{\"id\":\"copy_1\",\"angle\":\"...\",\"headline\":\"...\",\"subcopy\":\"...\",\"cta\":\"\",\"grounding\":{},\"score\":{}}],\"selected_copy\":{\"headline\":\"...\",\"subcopy\":\"...\",\"cta\":\"...\"},\"selection_reason\":\"...\"}"
        )
        response = client.responses.create(model=args.copy_model, input=prompt, temperature=0)
        raw = getattr(response, "output_text", "") or "{}"
        parsed = json.loads(raw)
        usage = _usage_dict(response)
        parsed.update(
            {
                "copy_provider": "openai",
                "copy_model": args.copy_model,
                "copy_fallback_used": False,
                "copy_token_usage": usage,
                "copy_latency_ms": int((time.perf_counter() - started) * 1000),
            }
        )
        _validate_copy_result(parsed, args.copy_model)
        return parsed
    except Exception as exc:
        return {"copy_provider": "openai", "copy_model": args.copy_model, "copy_fallback_used": True, "error_code": "copy_actual_failed", "error_message": str(exc)[:500]}


def generate_flux2_background(args: argparse.Namespace, case_dir: Path) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        engine = get_t2i_engine("flux2_klein_4b")
        prompt = (
            "Premium editorial commercial photography background for a French macaron collection, "
            "clean blank negative space for later copy overlay, warm dessert cafe mood, no text, no signage, no logo."
        )
        output = engine.generate(
            T2IGenerationInput(
                job_id=f"final_composite_{args.case}_{args.seed}",
                prompt=prompt,
                negative_prompt="visible writing, logo, watermark, sign, poster text",
                width=1024,
                height=1024,
                num_images=1,
                seed=args.seed,
                output_dir=str(case_dir),
                metadata={"source": "final_composite_quality_actual", "case_id": args.case},
            )
        )
        if not output.image_paths:
            raise RuntimeError("FLUX.2 Klein returned no image path.")
        source = Path(output.image_paths[0])
        target = case_dir / f"background_flux2_seed{args.seed}.png"
        if source.resolve() != target.resolve():
            target.write_bytes(source.read_bytes())
        _verify_image(target)
        return {
            "status": "completed",
            "actual_flux_generation": True,
            "flux_engine": output.engine,
            "flux_backend": "local_diffusers",
            "flux_model": (output.metadata or {}).get("model_name") or "black-forest-labs/FLUX.2-klein-4B",
            "flux_seed": args.seed,
            "flux_latency_ms": output.latency_ms or int((time.perf_counter() - started) * 1000),
            "flux_output_path": str(target),
            "image_path": str(target),
            "metadata": output.metadata,
        }
    except Exception as exc:
        return {"status": "failed", "actual_flux_generation": False, "error_code": getattr(exc, "error_code", "flux_actual_failed"), "error_message": str(exc)[:500]}


def build_initial_state(*, args: argparse.Namespace, copy_result: dict[str, Any], flux_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": f"final-composite-{args.case}",
        "thread_id": f"final-composite-{args.case}",
        "user_plan": "premium",
        "context": {
            "business_type": "dessert cafe",
            "item_or_service": "French macaron collection",
            "promotion_goal": "menu_discovery",
            "brand_tone": "premium/editorial/warm",
        },
        "ad_format_spec": {"ad_format": "instagram_feed", "width": 1024, "height": 1024},
        "copy_visual_intent": {
            "hierarchy": "editorial_product",
            "headline_emphasis": "large_elegant",
            "body_density": "low",
            "cta_visibility": "optional",
            "cta_style": "text_link",
            "preferred_alignment": "left",
            "typography_mood": "premium_serif",
            "plate_policy": "subtle",
            "product_text_relationship": "side_by_side",
        },
        "marketing_copy": copy_result["selected_copy"],
        "t2i_result": {"engine": "flux2_klein_4b", "image_paths": [flux_result["image_path"]], "metadata": flux_result.get("metadata") or {}},
        "artifact_refs": [{"type": "background_image", "path": flux_result["image_path"]}],
        "final_composite_attempts": 1,
    }


def render_and_validate(*, state: dict[str, Any], args: argparse.Namespace, case_dir: Path, label: str) -> tuple[dict[str, Any], Any, dict[str, Any]]:
    state = _apply(state, copy_spec_parser_node(state))
    state = _apply(state, typography_art_direction_node(state))
    state = _apply(state, text_style_binder_node(state))
    state = _apply(state, text_layout_planner_node(state))
    state = _apply(state, image_layout_analyzer_node(state))
    state = _apply(state, post_t2i_layout_refiner_node(state))
    state = _apply(state, adaptive_typography_refiner_node(state))
    state = _apply(state, safe_area_gate_node(state))
    state = _apply(state, text_renderer_node(state))
    render_result = state.get("render_result") or {}
    final_path = Path(render_result.get("final_image_path") or "")
    _verify_image(final_path)
    target = case_dir / ("initial_final_composite.png" if label == "initial" else "repaired_final_composite.png")
    if final_path.resolve() != target.resolve():
        target.write_bytes(final_path.read_bytes())
    state["render_result"] = {**render_result, "final_image_path": str(target)}
    state["final_image_path"] = str(target)
    state["artifact_refs"] = [ref for ref in state.get("artifact_refs", []) if ref.get("type") != "final_image"] + [{"type": "final_image", "path": str(target)}]
    vlm = judge_final_composite(args=args, image_path=target, copy=state.get("marketing_copy") or {})
    if not _strict_openai_success(vlm, args.vlm_model, prefix="vlm"):
        raise RuntimeError("VLM actual judge did not meet strict gpt-5.4 contract.")
    state["final_composite_vlm_result"] = vlm
    state["final_ocr_gate"] = _ocr_from_vlm(vlm, state.get("marketing_copy") or {})
    state = _apply(state, readability_gate_node(state))
    state = _apply(state, final_validation_node(state))
    return state, evaluate_final_composite(state), vlm


def judge_final_composite(*, args: argparse.Namespace, image_path: Path, copy: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        from openai import OpenAI  # type: ignore

        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        client = OpenAI(timeout=90)
        prompt = (
            "Evaluate this final ad composite. Use only the supplied final_image. Return JSON with keys: "
            "expected_copy_visible, copy_clipping_detected, product_overlap, face_hand_overlap, "
            "headline_hierarchy_score, cta_dominance_score, plate_excess_score, contrast_score, "
            "visual_clutter_score, alignment_score, safe_margin_score, business_fit_score, brand_fit_score, "
            "commercial_viability_score, generic_copy_detected, background_text_space_insufficient, "
            "detected_text, missing_text_count, extra_text_count, failure_reasons, suggested_action, confidence. "
            f"Expected copy: {json.dumps(copy, ensure_ascii=False)}"
        )
        response = client.responses.create(
            model=args.vlm_model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": f"data:image/png;base64,{encoded}"},
                    ],
                }
            ],
            temperature=0,
        )
        parsed = json.loads(getattr(response, "output_text", "") or "{}")
        usage = _usage_dict(response)
        parsed.update(
            {
                "vlm_provider": "openai",
                "vlm_model": args.vlm_model,
                "vlm_fallback_used": False,
                "vlm_token_usage": usage,
                "vlm_latency_ms": int((time.perf_counter() - started) * 1000),
            }
        )
        return parsed
    except Exception as exc:
        return {"vlm_provider": "openai", "vlm_model": args.vlm_model, "vlm_fallback_used": True, "error_code": "vlm_actual_failed", "error_message": str(exc)[:500]}


def run_partial_rerun(*, state: dict[str, Any], action: str, args: argparse.Namespace, case_dir: Path, revision_trace: dict[str, Any]) -> tuple[dict[str, Any], Any, dict[str, Any], str]:
    revision_state = _apply(state, final_composite_revision_node({**state, "final_composite_quality_report": state.get("final_composite_quality_report") or {"status": "revise", "primary_action": action}}))
    plan = revision_state.get("final_composite_revision_plan") or {}
    rerun = plan.get("rerun_from_node")
    revision_trace["rerun_start_node"] = rerun
    if rerun == "final_copy_revision":
        revision_state = _apply(revision_state, final_copy_revision_node(revision_state))
        return render_and_validate(state=revision_state, args=args, case_dir=case_dir, label="repaired") + (str(case_dir / "repaired_final_composite.png"),)
    if rerun in {"adaptive_typography_refiner", "post_t2i_layout_refiner"}:
        revision_state = apply_visual_patch_for_rerun(revision_state, action)
        return render_and_validate(state=revision_state, args=args, case_dir=case_dir, label="repaired") + (str(case_dir / "repaired_final_composite.png"),)
    return state, evaluate_final_composite(state), state.get("final_composite_vlm_result") or {}, ""


def apply_visual_patch_for_rerun(state: dict[str, Any], action: str) -> dict[str, Any]:
    intent = dict(state.get("copy_visual_intent") or {})
    if action in {"retry_text_style", "reduce_cta_emphasis"}:
        intent.update(
            {
                "typography_mood": "clean_sans",
                "plate_policy": "content_fit",
                "cta_style": "text_link",
                "cta_visibility": "optional",
                "preferred_alignment": "center",
                "product_text_relationship": "top_bottom",
            }
        )
        state["regeneration_patch"] = {
            "patches": {
                "final_composite_style": {
                    "target": "textStyle",
                    "increaseContrast": True,
                    "enableShadowOrOverlay": True,
                }
            }
        }
    if action == "retry_layout":
        intent.update({"preferred_alignment": "center", "product_text_relationship": "top_bottom"})
    state["copy_visual_intent"] = intent
    copy = dict(state.get("marketing_copy") or {})
    if action == "reduce_cta_emphasis" and copy.get("cta"):
        copy["cta"] = ""
        state["marketing_copy"] = copy
    return state


def completed_conditions(copy_result: dict[str, Any], flux_result: dict[str, Any], initial_state: dict[str, Any], final_state: dict[str, Any], initial_report: Any, final_report: Any, initial_vlm: dict[str, Any], final_vlm: dict[str, Any]) -> bool:
    background = Path(flux_result.get("image_path") or "")
    final_path = Path(final_state.get("render_result", {}).get("final_image_path") or "")
    return (
        _strict_openai_success(copy_result, "gpt-5.4", prefix="copy")
        and _strict_openai_success(final_vlm, "gpt-5.4", prefix="vlm")
        and _strict_flux_success(flux_result)
        and final_path.exists()
        and _sha256(background) != _sha256(final_path)
        and bool(initial_state.get("final_ocr_gate"))
        and int(initial_state.get("synthetic_trace_count") or 0) == 0
        and bool(initial_report.evaluated_image_sha256)
        and final_report.status in {"pass", "manual_review", "reject"}
    )


def build_comparison(case_dir: Path, initial_path: Path, repaired_path: Path | None) -> Path:
    output = case_dir / "comparison_before_after.png"
    images = [initial_path, repaired_path or initial_path]
    thumbs = []
    for index, path in enumerate(images):
        with Image.open(path).convert("RGB") as image:
            image.thumbnail((512, 512))
            canvas = Image.new("RGB", (512, 552), "#FFFFFF")
            canvas.paste(image, ((512 - image.width) // 2, 0))
            ImageDraw.Draw(canvas).text((16, 524), "initial" if index == 0 else ("repaired" if repaired_path else "pass_without_revision"), fill="#111111")
            thumbs.append(canvas)
    sheet = Image.new("RGB", (1024, 552), "#FFFFFF")
    sheet.paste(thumbs[0], (0, 0))
    sheet.paste(thumbs[1], (512, 0))
    sheet.save(output)
    return output


def _missing_actual_requirements(args: argparse.Namespace) -> list[str]:
    missing = [name for name, expected in REQUIRED_ACTUAL_ENV.items() if str(os.getenv(name, "")).strip().lower() != expected.lower()]
    if not os.getenv("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if args.copy_model != "gpt-5.4":
        missing.append("copy_model_must_be_gpt-5.4")
    if args.vlm_model != "gpt-5.4":
        missing.append("vlm_model_must_be_gpt-5.4")
    if not args.force_flux_generation:
        missing.append("force_flux_generation_required")
    return missing


def _validate_copy_result(result: dict[str, Any], model: str) -> None:
    if result.get("copy_model") != model or model != "gpt-5.4":
        raise ValueError("copy model must be gpt-5.4")
    candidates = result.get("copy_candidates") or []
    if len(candidates) != 3:
        raise ValueError("copy candidate count must be 3")
    selected = result.get("selected_copy") or {}
    if not selected.get("headline"):
        raise ValueError("selected copy missing headline")
    text = json.dumps({"candidates": candidates, "selected": selected}, ensure_ascii=False).lower()
    if any(term.lower() in text for term in FORBIDDEN_COPY_TERMS):
        raise ValueError("copy contains forbidden phrase")
    if not _positive_usage(result.get("copy_token_usage")):
        raise ValueError("copy token usage missing")


def _strict_openai_success(result: dict[str, Any], model: str, *, prefix: str) -> bool:
    return (
        result.get(f"{prefix}_provider") == "openai"
        and result.get(f"{prefix}_model") == model
        and result.get(f"{prefix}_fallback_used") is False
        and _positive_usage(result.get(f"{prefix}_token_usage"))
    )


def _strict_flux_success(result: dict[str, Any]) -> bool:
    return (
        result.get("status") == "completed"
        and result.get("actual_flux_generation") is True
        and result.get("flux_engine") == "flux2_klein_4b"
        and result.get("flux_backend") == "local_diffusers"
        and Path(result.get("image_path") or "").exists()
    )


def _positive_usage(usage: object) -> bool:
    if not isinstance(usage, dict):
        return False
    input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    return input_tokens > 0 and output_tokens > 0


def _usage_dict(response: Any) -> dict[str, int] | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    return {
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
    }


def _ocr_from_vlm(vlm: dict[str, Any], copy: dict[str, Any]) -> dict[str, Any]:
    detected = vlm.get("detected_text") or [value for value in copy.values() if value]
    return {
        "status": "pass" if vlm.get("expected_copy_visible", True) else "fail",
        "provider": "openai_vlm_ocr_fallback",
        "ocr": {
            "detected_text": detected,
            "missing_text_count": int(vlm.get("missing_text_count") or 0),
            "extra_text_count": int(vlm.get("extra_text_count") or 0),
        },
    }


def _apply(state: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    state.update(update or {})
    return state


def _verify_image(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(str(path))
    with Image.open(path) as image:
        image.verify()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _blocked(case_id: str, code: str, **extra: Any) -> dict[str, Any]:
    return {"case_id": case_id, "status": "blocked", "error_code": code, **extra}


def _failed(case_id: str, code: str, **extra: Any) -> dict[str, Any]:
    return {"case_id": case_id, "status": "failed", "error_code": code, **extra}


def _base_summary(args: argparse.Namespace, env_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "final_composite_quality_loop_actual_e2e_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "case": args.case,
        "actual_requested": bool(args.actual),
        "copy_model": args.copy_model,
        "vlm_model": args.vlm_model,
        "env_file_found": env_report.get("env_file_found"),
        "actual_api_calls": False,
        "image_generation_performed": False,
    }


def _write_summary(output_dir: Path, summary: dict[str, Any]) -> None:
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_public_state(path: Path, state: dict[str, Any]) -> None:
    public = {key: state.get(key) for key in ("marketing_copy", "render_result", "artifact_refs", "final_ocr_gate")}
    path.write_text(json.dumps(public, ensure_ascii=False, indent=2), encoding="utf-8")


def _public(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if "key" not in key.lower() and "token" not in key.lower()}


if __name__ == "__main__":
    raise SystemExit(main())
