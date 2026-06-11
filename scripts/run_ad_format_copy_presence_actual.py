"""Run Ad Format & Copy Presence actual comparison cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from orchestrator.app.t2i.engines.registry import get_t2i_engine

from orchestrator.app.llm.ad_format_policy import (
    build_ad_format_contract,
    build_copy_presence_plan,
    build_information_panel_plan,
    decide_creative_lane,
)
from scripts._actual_creative_pipeline import ActualCreativeCase, ActualRuntimeContext, run_actual_creative_case


CASES = {
    "macaron_feed_visual_first": {
        "user_input": "editorial macaron product visual, no promotion, no price, no period",
        "ad_format": "instagram_feed",
        "business_type": "cafe",
        "item_or_service": "macaron",
        "promotion_goal": "brand_awareness",
    },
    "serum_story_information_design": {
        "user_input": "serum story, 3 verified benefits glow moisture calming, discount 20%, period 5.20-5.27",
        "ad_format": "instagram_story",
        "business_type": "beauty_skincare",
        "item_or_service": "serum",
        "promotion_goal": "conversion",
        "benefits": ["glow", "moisture", "calming"],
    },
    "seasonal_sale_poster": {
        "user_input": "seasonal sale poster, discount tiers 20%, period 5.20-5.27, price 29000원",
        "ad_format": "poster",
        "business_type": "retail",
        "item_or_service": "seasonal collection",
        "promotion_goal": "discount_event",
    },
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actual", action="store_true")
    parser.add_argument("--env-file")
    parser.add_argument("--cases", default=",".join(CASES))
    parser.add_argument("--seeds", default="71,72,73")
    parser.add_argument("--max-images", type=int, default=3)
    parser.add_argument("--max-text-calls", type=int, default=3)
    parser.add_argument("--max-vlm-calls", type=int, default=3)
    parser.add_argument("--output-dir", default="data/outputs/ad_format_copy_presence_actual")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--case", dest="single_case")
    args = parser.parse_args(argv)

    if args.env_file:
        _load_env_file(Path(args.env_file))

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    case_arg = args.single_case or args.cases
    case_ids = [item.strip() for item in case_arg.split(",") if item.strip()]
    seeds = [int(item.strip()) for item in args.seeds.split(",") if item.strip()]
    readiness = _readiness(args.actual)
    runtime = _build_runtime(readiness) if args.actual and not readiness["missing_requirements"] else None
    runs = []
    for index, case_id in enumerate(case_ids[: args.max_images]):
        case = CASES[case_id]
        seed = seeds[index] if index < len(seeds) else 100 + index
        case_dir = output_dir / case_id
        if args.resume and _completed_result_exists(case_dir):
            runs.append(json.loads((case_dir / "result.json").read_text(encoding="utf-8")))
            continue
        runs.append(_run_case(case_id, case, seed, case_dir, readiness, args.actual, runtime))
    summary = {
        "schema_version": "ad_format_copy_presence_actual_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": _summary_status(runs, readiness),
        "actual_requested": args.actual,
        "readiness": readiness,
        "mock_fixture_count": sum(1 for run in runs if run.get("mock_or_fixture_used")),
        "runs": runs,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "contract_comparison.json").write_text(json.dumps([run.get("contract_summary", {"case_id": run.get("case_id"), "status": run.get("status")}) for run in runs], ensure_ascii=False, indent=2), encoding="utf-8")
    if any(run.get("final_composite_path") for run in runs):
        _write_comparison_sheet(output_dir / "comparison_sheet_all_cases.png", runs)
    print(json.dumps({"status": summary["status"], "summary_path": str(output_dir / "summary.json"), "readiness": readiness}, ensure_ascii=False))
    return 0 if summary["status"] == "completed" else 2


def _run_case(case_id: str, case: dict[str, Any], seed: int, output_dir: Path, readiness: dict[str, Any], actual: bool, runtime: ActualRuntimeContext | None) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    state = _case_state(case)
    contract = build_ad_format_contract(state)
    lane = decide_creative_lane(state, contract)
    copy_plan = build_copy_presence_plan(contract, lane, state)
    panel = build_information_panel_plan(contract, lane)
    _write_json(output_dir / "contract.json", contract.model_dump())
    _write_json(output_dir / "copy_presence_plan.json", copy_plan.model_dump())
    if panel.enabled:
        _write_json(output_dir / "information_panel_plan.json", panel.model_dump())
    if not actual or readiness["missing_requirements"]:
        result = {
            "case_id": case_id,
            "status": "blocked",
            "seed": seed,
            "missing_requirements": readiness["missing_requirements"],
            "actual_flux_generation": False,
            "actual_openai_call": False,
            "actual_vlm_call": False,
            "mock_or_fixture_used": False,
            "contract_summary": _contract_summary(case_id, contract, lane, copy_plan, panel),
        }
        _write_json(output_dir / "result.json", result)
        return result

    if runtime is None:
        raise RuntimeError("actual runtime unavailable despite readiness pass")
    actual_case = ActualCreativeCase(
        case_id=case_id,
        seed=seed,
        width=1080 if contract.aspect_ratio != "9:16" else 1080,
        height=1920 if contract.aspect_ratio == "9:16" else 1080,
        context=_case_state(case)["context"],
        user_input=case["user_input"],
        ad_format_contract=contract.model_dump(),
        creative_lane_decision=lane.model_dump(),
        copy_presence_plan=copy_plan.model_dump(),
        information_panel_plan=panel.model_dump(),
        platform_safe_zone_spec=contract.platform_safe_zones.model_dump(),
        required_information=_required_information_payload(case),
        copy_prompt_constraints={"forbid_embedded_cta": contract.embedded_cta_policy in {"forbidden", "platform_only"}},
        output_dir=output_dir,
    )
    try:
        result = run_actual_creative_case(actual_case, runtime)
    except Exception as exc:
        result = {
            "case_id": case_id,
            "status": "failed",
            "seed": seed,
            "error_code": "actual_creative_case_failed",
            "error_message": str(exc)[:500],
            "actual_flux_generation": False,
            "actual_openai_call": False,
            "actual_vlm_call": False,
            "mock_or_fixture_used": False,
            "contract_summary": _contract_summary(case_id, contract, lane, copy_plan, panel),
        }
    result["contract_summary"] = _contract_summary(case_id, contract, lane, copy_plan, panel)
    _write_json(output_dir / "result.json", result)
    return result


def _readiness(actual: bool) -> dict[str, Any]:
    required = {
        "EASYADS_AD_FORMAT_ACTUAL": "1",
        "EASYADS_COPY_QUALITY_ACTUAL": "1",
        "EASYADS_ENABLE_LLM_CALLS": "true",
        "EASYADS_LLM_PROVIDER": "openai",
        "EASYADS_LLM_MODEL": "gpt-5.4",
        "LLM_OPENAI_TEXT_MODEL_FULL": "gpt-5.4",
        "LLM_OPENAI_VISION_MODEL": "gpt-5.4",
        "EASYADS_VLM_ACTUAL": "1",
        "EASYADS_FLUX2_KLEIN_ACTUAL": "1",
        "EASYADS_ENABLE_FLUX2_KLEIN_LOCAL": "true",
    }
    missing = []
    if not actual:
        missing.append("--actual")
    for name, expected in required.items():
        if str(os.getenv(name, "")).strip().lower() != expected:
            missing.append(name)
    if not os.getenv("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    return {
        "missing_requirements": missing,
        "openai_api_key_present": bool(os.getenv("OPENAI_API_KEY")),
        "required_text_model": "gpt-5.4",
        "required_vlm_model": "gpt-5.4",
        "required_flux_model": "black-forest-labs/FLUX.2-klein-4B",
    }


def _build_runtime(readiness: dict[str, Any]) -> ActualRuntimeContext:
    if readiness["missing_requirements"]:
        raise RuntimeError("actual runtime requested with missing requirements")
    from openai import OpenAI  # type: ignore

    return ActualRuntimeContext(
        openai_client=OpenAI(timeout=90),
        flux_engine=get_t2i_engine("flux2_klein_4b"),
        copy_model="gpt-5.4",
        vlm_model="gpt-5.4",
    )


def _summary_status(runs: list[dict[str, Any]], readiness: dict[str, Any]) -> str:
    if readiness["missing_requirements"]:
        return "blocked"
    completed = sum(1 for run in runs if run.get("status") == "completed")
    if completed == len(runs) and runs:
        return "completed"
    if completed:
        return "partial"
    if any(run.get("status") == "manual_review" for run in runs):
        return "manual_review"
    return "failed"


def _completed_result_exists(case_dir: Path) -> bool:
    path = case_dir / "result.json"
    if not path.exists():
        return False
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("status") == "completed"
    except Exception:
        return False


def _case_state(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_input": case["user_input"],
        "current_brief": {"requested_ad_format": case["ad_format"]},
        "context": {
            "business_type": case["business_type"],
            "item_or_service": case["item_or_service"],
            "promotion_goal": case["promotion_goal"],
            "extra": {"ad_format": case["ad_format"], "benefits": case.get("benefits", [])},
        },
    }


def _contract_summary(case_id: str, contract, lane, copy_plan, panel) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "placement": contract.placement,
        "interaction_mode": contract.interaction_mode,
        "embedded_cta_policy": contract.embedded_cta_policy,
        "creative_lane": lane.lane,
        "archetype": lane.archetype,
        "copy_presence_mode": copy_plan.mode,
        "max_text_area_ratio": copy_plan.max_text_area_ratio,
        "information_panel_enabled": panel.enabled,
        "panel_type": panel.panel_type,
    }


def _required_information_payload(case: dict[str, Any]) -> dict[str, Any]:
    text = case["user_input"]
    return {
        "benefits": case.get("benefits") or [],
        "discount": "20%" if "20%" in text else None,
        "period": "5.20-5.27" if "5.20" in text else None,
        "price": "29000원" if "29000" in text else None,
    }


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _write_comparison_sheet(path: Path, runs: list[dict[str, Any]]) -> None:
    sheet = Image.new("RGB", (512 * max(1, len(runs)), 560), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    for index, run in enumerate(runs):
        final = run.get("final_composite_path")
        if final and Path(final).exists():
            with Image.open(final).resize((512, 512)) as tile:
                sheet.paste(tile, (index * 512, 0))
        draw.text((index * 512 + 12, 520), f"{run['case_id']} {run['status']}", fill=(0, 0, 0))
    sheet.save(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


if __name__ == "__main__":
    raise SystemExit(main())


def main_with_args_for_test(argv: list[str]) -> int:
    return main(argv)
