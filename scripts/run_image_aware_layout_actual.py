"""Guarded image-aware layout planner v2 actual runner."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator.app.llm.nodes.copy_spec_parser import copy_spec_parser_node
from orchestrator.app.llm.nodes.image_layout_analyzer import image_layout_analyzer_node
from orchestrator.app.llm.nodes.post_t2i_layout_refiner import post_t2i_layout_refiner_node
from orchestrator.app.llm.nodes.text_layout_planner import text_layout_planner_node
from orchestrator.app.llm.nodes.text_renderer import text_renderer_node
from orchestrator.app.llm.nodes.text_style_binder import text_style_binder_node
from orchestrator.app.llm.copy_visual_intent import resolve_copy_visual_intent
from orchestrator.app.schemas.llm_marketing import MarketingContext, MarketingCopy
from orchestrator.app.t2i.settings import load_t2i_settings

from scripts._actual_env import load_env_file
from scripts.run_copy_quality_actual_batch import (
    actual_run_is_complete,
    create_state,
    extract_model_name,
    extract_token_usage,
    extract_token_usage_from_metadata,
    run_actual_copy_generation,
    selected_copy_grounding,
    selected_copy_payload,
)
from scripts.run_copy_quality_visual_actual import (
    assert_actual_flux_result,
    assert_actual_vlm_result,
    build_comparison_sheet_3way,
    generate_flux2_background,
    run_actual_vlm_comparison,
)


CASE_CONTEXTS: dict[str, MarketingContext] = {
    "macaron_collection_001": MarketingContext(business_type="macaron", item_or_service="마카롱 컬렉션", promotion_goal="menu_discovery", brand_tone="premium", extra={"ad_format": "instagram_feed"}),
    "restaurant_bbq_001": MarketingContext(business_type="restaurant_bbq", item_or_service="숯불구이", promotion_goal="reservation_cta", brand_tone="premium", extra={"ad_format": "instagram_feed"}),
    "beauty_nail_001": MarketingContext(business_type="beauty_nail", item_or_service="네일 디자인", promotion_goal="consultation", brand_tone="premium", extra={"ad_format": "instagram_feed"}),
}

PREVIOUS_COPY: dict[str, dict[str, str]] = {
    "macaron_collection_001": {"headline": "달콤한 마카롱 한 상자", "subcopy": "오늘의 디저트를 우아하게 골라보세요", "cta": ""},
    "restaurant_bbq_001": {"headline": "오늘 저녁은 제대로", "subcopy": "숯불향 가득한 프리미엄 고깃집", "cta": "예약 문의하기"},
    "beauty_nail_001": {"headline": "손끝에 남는 무드", "subcopy": "감각적인 네일 디자인 상담", "cta": "상담 예약하기"},
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actual", action="store_true")
    parser.add_argument("--env-file", default="docs/api_key.env")
    parser.add_argument("--cases", default="macaron_collection_001,restaurant_bbq_001,beauty_nail_001")
    parser.add_argument("--seeds", default="62,63,64")
    parser.add_argument("--max-images", type=int, default=3)
    parser.add_argument("--max-copy-calls", type=int, default=3)
    parser.add_argument("--max-layout-vlm-calls", type=int, default=3)
    parser.add_argument("--max-final-vlm-calls", type=int, default=3)
    parser.add_argument("--output-dir", default="data/outputs/image_aware_layout_v2_actual")
    args = parser.parse_args(argv)
    report = build_report(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    filename = "summary.json" if report["status"] == "completed" else f"summary_{report['status']}_{timestamp}.json"
    path = output_dir / filename
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)
    return 0 if report["status"] in {"completed", "dry_run"} else 2


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    env_file = load_env_file(getattr(args, "env_file", None))
    cases = _select_cases(args)
    seeds = [int(value.strip()) for value in str(args.seeds).split(",") if value.strip()]
    missing = missing_actual_requirements(args)
    runs: list[dict[str, Any]] = []
    status = "dry_run"
    if args.actual and missing:
        status = "blocked"
    elif args.actual:
        status = "completed"
    for index, case_id in enumerate(cases):
        if not args.actual:
            runs.append({"case_id": case_id, "status": "dry_run", "missing_requirements": []})
            continue
        if missing:
            runs.append(_blocked_case(case_id, missing))
            continue
        try:
            run = run_actual_case(case_id, seed=seeds[index] if index < len(seeds) else None, output_dir=Path(args.output_dir), args=args)
        except Exception as exc:
            run = {"case_id": case_id, "status": "failed", "error_code": type(exc).__name__, "error_message": str(exc)}
        if run.get("status") != "completed":
            status = "failed"
        runs.append(run)
    actual_flags = _actual_flags(runs)
    if args.actual and status == "completed" and not all(actual_flags.values()):
        status = "failed"
    return {
        "schema_version": "image_aware_layout_actual_v2",
        "created_at": datetime.now(UTC).isoformat(),
        "status": status,
        "actual_requested": bool(args.actual),
        "actual_generation": bool(args.actual and status == "completed" and all(actual_flags.values())),
        "actual_openai_copy": actual_flags["actual_openai_copy"],
        "actual_flux_generation": actual_flags["actual_flux_generation"],
        "actual_vlm_evaluation": actual_flags["actual_vlm_evaluation"],
        "mock_or_fixture_count": sum(int(run.get("mock_or_fixture_count", 0)) for run in runs),
        "env_file": env_file,
        "missing_requirements": missing,
        "cases": cases,
        "runs": runs,
    }


def run_actual_case(case_id: str, *, seed: int | None, output_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    case_dir = output_dir / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    copy_payload, copy_metadata = _generate_actual_copy(case_id, args)
    flux_result = generate_flux2_background(case_id, case_dir=case_dir, seed=seed)
    assert_actual_flux_result(flux_result)
    background_path = Path(flux_result.image_paths[0])
    background_target = case_dir / "background_flux2.png"
    background_target.write_bytes(background_path.read_bytes())

    fixed_layout = _build_render_state(case_id, background_target, copy_payload, use_image_aware=False)
    previous_path = _render_variant(case_id, background_target, PREVIOUS_COPY[case_id], case_dir / "previous_copy_fixed_layout.png", fixed_state=fixed_layout)
    grounded_fixed_path = _render_variant(case_id, background_target, copy_payload, case_dir / "grounded_copy_fixed_layout.png", fixed_state=fixed_layout)
    aware_state = _build_render_state(case_id, background_target, copy_payload, use_image_aware=True)
    aware_path = _render_state_to_path(aware_state, case_dir / "grounded_copy_image_aware_layout.png")
    _assert_not_identical(background_target, grounded_fixed_path, "grounded_copy_fixed_layout")
    _assert_not_identical(background_target, aware_path, "grounded_copy_image_aware_layout")
    sheet = build_comparison_sheet_3way(previous_path, grounded_fixed_path, aware_path, case_dir / "comparison_sheet_3way.png")
    vlm = run_actual_vlm_comparison(case_id, previous_path, grounded_fixed_path, aware_path) if args.max_final_vlm_calls > 0 else None
    assert_actual_vlm_result(vlm)
    result = {
        "case_id": case_id,
        "status": "completed",
        "actual_openai_copy": True,
        "actual_flux_generation": True,
        "actual_vlm_evaluation": True,
        "mock_or_fixture_count": 0,
        "background_flux2_path": str(background_target),
        "previous_copy_fixed_layout_path": str(previous_path),
        "grounded_copy_fixed_layout_path": str(grounded_fixed_path),
        "grounded_copy_image_aware_layout_path": str(aware_path),
        "comparison_sheet_3way_path": str(sheet),
        "copy_metadata": copy_metadata,
        "selected_copy": copy_payload,
        "flux_result": flux_result.model_dump(),
        "vlm_result": vlm.model_dump() if hasattr(vlm, "model_dump") else vlm,
        "layout_refinement_result": aware_state.get("layout_refinement_result"),
    }
    (case_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _generate_actual_copy(case_id: str, args: argparse.Namespace) -> tuple[dict[str, str], dict[str, Any]]:
    if args.max_copy_calls < 1:
        raise RuntimeError("copy_actual_budget_missing")
    context = CASE_CONTEXTS[case_id]
    failures: list[dict[str, Any]] = []
    for attempt in range(1, args.max_copy_calls + 1):
        state = create_state(case_id, context)
        generated, metadata = run_actual_copy_generation(state)
        selected = selected_copy_payload(generated)
        grounding = selected_copy_grounding(generated, context)
        token_usage = extract_token_usage(state) or extract_token_usage_from_metadata(metadata)
        model_name = extract_model_name(metadata)
        selected_copy = {key: str((selected or {}).get(key) or "") for key in ("headline", "subcopy", "cta")}
        failure = _copy_contract_failure(generated, metadata, selected, selected_copy, token_usage, model_name, grounding)
        if failure is None:
            return selected_copy, {
                "provider": "openai",
                "fallback_used": False,
                "candidate_count": len(generated.candidates),
                "wrong_domain_terms": grounding.get("wrong_domain_terms", []),
                "product_drift_terms": grounding.get("product_drift_terms", []),
                "internal_terms": grounding.get("internal_terms", []),
                "cta_goal_mismatch_terms": grounding.get("cta_goal_mismatch_terms", []),
                "model_name": model_name,
                "token_usage_present": bool(token_usage),
                "attempt": attempt,
            }
        failures.append(failure)
    raise RuntimeError(f"openai_copy_actual_contract_failed:{failures[-1] if failures else 'unknown'}")


def _copy_contract_failure(generated: Any, metadata: dict[str, Any], selected: dict[str, Any] | None, selected_copy: dict[str, str], token_usage: dict[str, Any] | None, model_name: str | None, grounding: dict[str, Any]) -> dict[str, Any] | None:
    if not actual_run_is_complete(bool(metadata.get("llm_attempted")), metadata, generated, selected, token_usage, model_name, grounding):
        return {
            "reason": "base_actual_contract",
            "llm_attempted": bool(metadata.get("llm_attempted")),
            "fallback_used": bool(metadata.get("fallback_used")),
            "candidate_count": len(getattr(generated, "candidates", []) or []),
            "selected_copy": selected_copy,
            "grounding": grounding,
            "token_usage_present": bool(token_usage),
            "model_name": model_name,
        }
    if grounding.get("product_drift_terms") or grounding.get("internal_terms") or grounding.get("cta_goal_mismatch_terms"):
        return {"reason": "grounding_contract", "selected_copy": selected_copy, "grounding": grounding}
    for value in selected_copy.values():
        if "..." in value or any(term in value for term in ("beauty_nail", "restaurant_bbq", "copy_", "menu_discovery")):
            return {"reason": "internal_or_truncated_text", "selected_copy": selected_copy}
    return None


def _build_render_state(case_id: str, background_path: Path, copy: dict[str, str], *, use_image_aware: bool) -> dict[str, Any]:
    context = CASE_CONTEXTS[case_id]
    intent = resolve_copy_visual_intent(context)
    state: dict[str, Any] = {
        "job_id": f"image_aware_{case_id}_{'aware' if use_image_aware else 'fixed'}",
        "thread_id": f"{case_id}_thread",
        "t2i_result": {"image_paths": [str(background_path)]},
        "context": context.model_dump(),
        "marketing_copy": MarketingCopy(headline=copy["headline"], subcopy=copy.get("subcopy"), cta=copy.get("cta")).model_dump(),
        "copy_visual_intent": intent.model_dump(),
        "ad_format_spec": {"ad_format": "instagram_feed", "width": 1024, "height": 1024},
        "current_brief": {},
        "artifact_refs": [],
    }
    state.update(copy_spec_parser_node(state))
    state.update(text_style_binder_node(state))
    state.update(text_layout_planner_node(state))
    if use_image_aware:
        state.update(image_layout_analyzer_node(state))
        state.update(post_t2i_layout_refiner_node(state))
    return state


def _render_variant(case_id: str, background_path: Path, copy: dict[str, str], output_path: Path, *, fixed_state: dict[str, Any]) -> Path:
    state = dict(fixed_state)
    state["job_id"] = f"{case_id}_{output_path.stem}"
    state["marketing_copy"] = MarketingCopy(headline=copy["headline"], subcopy=copy.get("subcopy"), cta=copy.get("cta")).model_dump()
    state.update(copy_spec_parser_node(state))
    return _render_state_to_path(state, output_path)


def _render_state_to_path(state: dict[str, Any], output_path: Path) -> Path:
    result = text_renderer_node(state)
    if result.get("status") != "overlaying_text" or not result.get("final_image_path"):
        raise RuntimeError(f"text_render_failed:{result.get('error_message')}")
    rendered = Path(result["final_image_path"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(rendered.read_bytes())
    return output_path


def _assert_not_identical(background: Path, rendered: Path, label: str) -> None:
    with Image.open(background).convert("RGB") as bg, Image.open(rendered).convert("RGB") as out:
        if not ImageChops.difference(bg, out).getbbox():
            raise RuntimeError(f"{label}_identical_to_background")


def missing_actual_requirements(args: argparse.Namespace) -> list[str]:
    if not args.actual:
        return []
    missing: list[str] = []
    if os.getenv("EASYADS_COPY_QUALITY_ACTUAL") != "1":
        missing.append("EASYADS_COPY_QUALITY_ACTUAL=1")
    if os.getenv("EASYADS_ENABLE_LLM_CALLS", "").lower() not in {"1", "true", "yes"}:
        missing.append("EASYADS_ENABLE_LLM_CALLS=true")
    if not os.getenv("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if os.getenv("EASYADS_VLM_ACTUAL") != "1":
        missing.append("EASYADS_VLM_ACTUAL=1")
    if os.getenv("EASYADS_FLUX2_KLEIN_ACTUAL") != "1":
        missing.append("EASYADS_FLUX2_KLEIN_ACTUAL=1")
    settings = load_t2i_settings()
    if not settings.enable_flux2_klein_local:
        missing.append("EASYADS_ENABLE_FLUX2_KLEIN_LOCAL=true")
    if settings.flux2_klein_backend != "local_diffusers":
        missing.append("EASYADS_T2I_FLUX2_KLEIN_BACKEND=local_diffusers")
    if not str(settings.flux2_klein_device).startswith("cuda"):
        missing.append("EASYADS_T2I_FLUX2_KLEIN_DEVICE=cuda")
    if args.max_copy_calls < 1:
        missing.append("max_copy_calls_positive")
    if args.max_final_vlm_calls < 1:
        missing.append("max_final_vlm_calls_positive")
    return missing


def _select_cases(args: argparse.Namespace) -> list[str]:
    requested = [case.strip() for case in str(args.cases).split(",") if case.strip()]
    selected: list[str] = []
    for case_id in requested:
        if case_id not in CASE_CONTEXTS:
            raise ValueError(f"unknown_case:{case_id}")
        selected.append(case_id)
    return selected[: max(1, args.max_images)]


def _actual_flags(runs: list[dict[str, Any]]) -> dict[str, bool]:
    completed = [run for run in runs if run.get("status") == "completed"]
    return {
        "actual_openai_copy": bool(completed) and all(run.get("actual_openai_copy") is True for run in completed),
        "actual_flux_generation": bool(completed) and all(run.get("actual_flux_generation") is True for run in completed),
        "actual_vlm_evaluation": bool(completed) and all(run.get("actual_vlm_evaluation") is True for run in completed),
    }


def _blocked_case(case_id: str, missing: list[str]) -> dict[str, Any]:
    return {"case_id": case_id, "status": "blocked", "missing_requirements": missing, "actual_openai_copy": False, "actual_flux_generation": False, "actual_vlm_evaluation": False, "mock_or_fixture_count": 0}


if __name__ == "__main__":
    raise SystemExit(main())
