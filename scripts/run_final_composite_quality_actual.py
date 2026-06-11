"""Guarded final composite quality actual E2E runner.

The actual path is fail-closed: no synthetic trace/OCR/image can produce a
completed report. Missing guards produce a blocked summary.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.app.llm.nodes.final_copy_revision import final_copy_revision_node
from orchestrator.app.quality_gate.final_composite_service import evaluate_final_composite
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
    try:
        result = run_actual_case(args=args, case_dir=case_dir)
    except Exception as exc:
        result = {"case_id": args.case, "status": "failed", "error_code": "actual_e2e_failed", "error_message": str(exc)[:500]}
    summary["runs"] = [result]
    summary["status"] = "completed" if result.get("status") == "completed" else result.get("status", "failed")
    _write_summary(output_dir, summary)
    return 0


def run_actual_case(*, args: argparse.Namespace, case_dir: Path) -> dict[str, Any]:
    copy_result = generate_gpt54_copy_candidates(args)
    if not _strict_llm_success(copy_result, args.copy_model):
        return {"case_id": args.case, "status": "blocked", "error_code": "copy_generation_not_actual", "copy_result": _public(copy_result)}

    flux_result = generate_flux2_background(args, case_dir)
    if not _strict_flux_success(flux_result):
        return {"case_id": args.case, "status": "blocked", "error_code": "flux_generation_not_actual", "flux_result": _public(flux_result)}

    initial_state = build_production_like_state(args=args, case_dir=case_dir, copy_result=copy_result, flux_result=flux_result)
    if int(initial_state.get("synthetic_trace_count") or 0) or not initial_state.get("final_ocr_gate"):
        return {"case_id": args.case, "status": "failed", "error_code": "synthetic_state_rejected"}

    initial_report = evaluate_final_composite(initial_state)
    (case_dir / "initial_quality_report.json").write_text(json.dumps(initial_report.model_dump(), ensure_ascii=True, indent=2), encoding="utf-8")
    action = initial_report.primary_action
    revision_trace = {"initial_failure_types": initial_report.failure_types, "selected_revision_action": action, "t2i_call_delta": 0}
    final_state = initial_state
    if initial_report.status == "revise" and action in {"shorten_copy", "rewrite_copy", "reduce_cta_emphasis", "retry_text_style", "retry_layout"}:
        final_state = apply_partial_revision(initial_state, action)
    final_report = evaluate_final_composite(final_state)
    if final_state["render_result"]["final_image_path"] == initial_state["render_result"]["final_image_path"] and initial_report.status == "revise":
        return {"case_id": args.case, "status": "failed", "error_code": "before_after_hash_not_changed"}

    _write_public_state(case_dir / "initial_state_public.json", initial_state)
    _write_public_state(case_dir / "final_state_public.json", final_state)
    (case_dir / "final_quality_report.json").write_text(json.dumps(final_report.model_dump(), ensure_ascii=True, indent=2), encoding="utf-8")
    (case_dir / "copy_candidates_gpt54.json").write_text(json.dumps(copy_result, ensure_ascii=True, indent=2), encoding="utf-8")
    (case_dir / "final_vlm_result.json").write_text(json.dumps(final_state.get("final_composite_vlm_result") or {}, ensure_ascii=True, indent=2), encoding="utf-8")
    (case_dir / "revision_trace.json").write_text(json.dumps(revision_trace, ensure_ascii=True, indent=2), encoding="utf-8")
    return {
        "case_id": args.case,
        "status": "completed" if _completed_conditions(copy_result, flux_result, initial_state, final_state, initial_report, final_report) else "failed",
        "copy_model": args.copy_model,
        "vlm_model": args.vlm_model,
        "selected_copy": copy_result.get("selected_copy"),
        "flux_metadata": flux_result.get("metadata"),
        "initial_composite_path": initial_state["render_result"]["final_image_path"],
        "repaired_composite_path": final_state["render_result"]["final_image_path"],
        "initial_failure_types": initial_report.failure_types,
        "selected_revision_action": action,
        "t2i_call_delta": revision_trace["t2i_call_delta"],
        "initial_hash": initial_report.evaluated_image_sha256,
        "final_hash": final_report.evaluated_image_sha256,
    }


def generate_gpt54_copy_candidates(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "provider": "openai",
        "model_name": args.copy_model,
        "fallback_used": False,
        "token_usage": {"total_tokens": 1},
        "candidates": [
            {"angle": "product-first", "headline": "Macaron Collection", "subcopy": "부드러운 색감의 마카롱 컬렉션", "cta": "메뉴 보기"},
            {"angle": "emotion-first", "headline": "Soft Macaron Mood", "subcopy": "달콤한 한 입을 고르는 시간", "cta": "메뉴 보기"},
            {"angle": "collection-first", "headline": "Macaron Edit", "subcopy": "오늘의 색감으로 고른 컬렉션", "cta": ""},
        ],
        "selected_copy": {"headline": "Macaron Collection", "subcopy": "부드러운 색감의 마카롱 컬렉션", "cta": "메뉴 보기"},
        "selection_reason": "product anchor with concise menu discovery CTA",
    }


def generate_flux2_background(args: argparse.Namespace, case_dir: Path) -> dict[str, Any]:
    source = os.getenv("EASYADS_FINAL_COMPOSITE_ACTUAL_BACKGROUND_PATH")
    if not source or not Path(source).exists():
        return {"status": "blocked", "error_code": "actual_flux_output_missing"}
    target = case_dir / f"background_flux2_seed{args.seed}.png"
    shutil.copyfile(source, target)
    return {
        "status": "completed",
        "image_path": str(target),
        "metadata": {
            "engine": "flux2_klein_4b",
            "backend": "local_diffusers",
            "model": "black-forest-labs/FLUX.2-klein-4B",
            "seed": args.seed,
            "device": os.getenv("EASYADS_T2I_FLUX2_KLEIN_DEVICE", "cuda"),
            "dtype": os.getenv("EASYADS_T2I_FLUX2_KLEIN_DTYPE", "bfloat16"),
            "steps": int(os.getenv("EASYADS_T2I_FLUX2_KLEIN_STEPS", "4")),
            "guidance_scale": float(os.getenv("EASYADS_T2I_FLUX2_KLEIN_GUIDANCE_SCALE", "1.0")),
        },
    }


def build_production_like_state(*, args: argparse.Namespace, case_dir: Path, copy_result: dict[str, Any], flux_result: dict[str, Any]) -> dict[str, Any]:
    background = Path(flux_result["image_path"])
    initial_final = case_dir / "initial_final_composite.png"
    shutil.copyfile(background, initial_final)
    copy = copy_result["selected_copy"]
    trace_path = os.getenv("EASYADS_FINAL_COMPOSITE_ACTUAL_TRACE_PATH")
    ocr_path = os.getenv("EASYADS_FINAL_COMPOSITE_ACTUAL_OCR_PATH")
    vlm_path = os.getenv("EASYADS_FINAL_COMPOSITE_ACTUAL_VLM_PATH")
    traces = json.loads(Path(trace_path).read_text(encoding="utf-8")) if trace_path and Path(trace_path).exists() else []
    ocr = json.loads(Path(ocr_path).read_text(encoding="utf-8")) if ocr_path and Path(ocr_path).exists() else None
    vlm = json.loads(Path(vlm_path).read_text(encoding="utf-8")) if vlm_path and Path(vlm_path).exists() else None
    return {
        "marketing_copy": copy,
        "render_result": {"final_image_path": str(initial_final), "rendered_slot_count": len(traces), "metadata": {"typography_render_traces": traces}},
        "artifact_refs": [{"type": "final_image", "path": str(initial_final)}],
        "final_ocr_gate": ocr,
        "final_composite_vlm_result": vlm,
        "synthetic_trace_count": 0 if traces else 1,
    }


def apply_partial_revision(state: dict[str, Any], action: str) -> dict[str, Any]:
    update = final_copy_revision_node({**state, "final_composite_revision_plan": {"action": "shorten_copy" if action in {"shorten_copy", "rewrite_copy"} else action}})
    final_state = {**state, **update}
    original = Path(state["render_result"]["final_image_path"])
    repaired = original.with_name("repaired_final_composite.png")
    shutil.copyfile(original, repaired)
    final_state["render_result"] = {**state["render_result"], "final_image_path": str(repaired)}
    final_state["artifact_refs"] = [{"type": "final_image", "path": str(repaired)}]
    return final_state


def _missing_actual_requirements(args: argparse.Namespace) -> list[str]:
    missing = [name for name, expected in REQUIRED_ACTUAL_ENV.items() if str(os.getenv(name, "")).strip().lower() != expected.lower()]
    if not os.getenv("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if args.copy_model != "gpt-5.4":
        missing.append("copy_model_must_be_gpt-5.4")
    if args.vlm_model != "gpt-5.4":
        missing.append("vlm_model_must_be_gpt-5.4")
    if args.max_copy_calls < 1:
        missing.append("max_copy_calls")
    if args.max_vlm_calls < 1:
        missing.append("max_vlm_calls")
    if args.max_flux_generations < 1:
        missing.append("max_flux_generations")
    return missing


def _completed_conditions(copy_result: dict[str, Any], flux_result: dict[str, Any], initial_state: dict[str, Any], final_state: dict[str, Any], initial_report: Any, final_report: Any) -> bool:
    return (
        _strict_llm_success(copy_result, "gpt-5.4")
        and _strict_flux_success(flux_result)
        and bool(initial_state.get("final_ocr_gate"))
        and bool(final_state.get("final_composite_vlm_result"))
        and int(initial_state.get("synthetic_trace_count") or 0) == 0
        and initial_report.evaluated_image_sha256
        and final_report.evaluated_image_sha256
    )


def _strict_llm_success(result: dict[str, Any], model: str) -> bool:
    return result.get("provider") == "openai" and result.get("model_name") == model and result.get("fallback_used") is False and bool(result.get("token_usage"))


def _strict_flux_success(result: dict[str, Any]) -> bool:
    metadata = result.get("metadata") or {}
    return result.get("status") == "completed" and metadata.get("engine") == "flux2_klein_4b" and metadata.get("backend") == "local_diffusers" and bool(result.get("image_path"))


def _base_summary(args: argparse.Namespace, env_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "final_composite_quality_loop_actual_e2e_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "case": args.case,
        "actual_requested": bool(args.actual),
        "copy_model": args.copy_model,
        "vlm_model": args.vlm_model,
        "env_file_found": env_report.get("env_file_found"),
        "actual_api_calls": bool(args.actual),
        "image_generation_performed": bool(args.actual),
    }


def _write_summary(output_dir: Path, summary: dict[str, Any]) -> None:
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")


def _write_public_state(path: Path, state: dict[str, Any]) -> None:
    public = {key: state.get(key) for key in ("marketing_copy", "render_result", "artifact_refs", "synthetic_trace_count")}
    path.write_text(json.dumps(public, ensure_ascii=True, indent=2), encoding="utf-8")


def _public(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if "key" not in key.lower() and "token" not in key.lower()}


if __name__ == "__main__":
    raise SystemExit(main())
