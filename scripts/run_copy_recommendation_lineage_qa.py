"""Copy recommendation lineage QA runner."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.copy_recommendation_lineage import (
    build_candidate_quality_metrics,
    build_copy_input_projection,
)
from orchestrator.app.llm.nodes.copy_candidates import copy_candidate_generation_node
from orchestrator.app.llm.settings import get_llm_settings
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext

from scripts._actual_env import load_env_file


PRIMARY_CASES: dict[str, dict[str, Any]] = {
    "language_academy_banner": {
        "prompt": "강남 직장인을 위한 영어 회화반. 평일 저녁 수업, 소수 정원, 사전 전화 상담. 수강생 모집용 배너 문구 3개 추천해줘.",
        "context": MarketingContext(
            business_type="education",
            item_or_service="영어 회화반",
            promotion_goal="student_recruitment",
            target_persona="강남 직장인",
            time_context="평일 저녁",
            contact_or_order_method="사전 전화 상담",
            extra={"ad_format": "banner"},
        ),
    },
}

CONTROL_CASES: dict[str, dict[str, Any]] = {
    "cafe_affogato_banner": {
        "prompt": "카페의 아포가토 광고 문구를 추천해줘. 바닐라 아이스크림과 에스프레소의 조합을 강조해줘.",
        "context": MarketingContext(
            business_type="cafe",
            item_or_service="아포가토",
            promotion_goal="menu_discovery",
            extra={"ad_format": "banner"},
        ),
    },
    "tax_consulting_banner": {
        "prompt": "5월 종합소득세 신고를 준비하는 자영업자를 위한 세무 상담 광고 문구를 추천해줘. 정확한 신고 안내와 상담 가능 여부만 반영해줘.",
        "context": MarketingContext(
            business_type="professional_service",
            item_or_service="세무 상담",
            promotion_goal="consultation",
            target_persona="자영업자",
            extra={"ad_format": "banner"},
        ),
    },
}


@dataclass
class CallBudget:
    max_calls: int
    attempted: int = 0

    def consume(self) -> None:
        if self.attempted >= self.max_calls:
            raise RuntimeError("actual_call_budget_exceeded")
        self.attempted += 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("mock", "actual"), default="mock")
    parser.add_argument("--primary-runs", type=int, default=3)
    parser.add_argument("--control-runs", type=int, default=1)
    parser.add_argument("--max-actual-calls", type=int, default=5)
    parser.add_argument("--confirm-paid-calls", action="store_true")
    parser.add_argument("--env-file", default="docs/api_key.env")
    parser.add_argument("--output-dir", default="data/qa/copy_recommendation_lineage_v1")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    env_report = load_env_file(args.env_file)
    summary = build_summary(args, env_report=env_report, output_dir=output_dir)
    write_json(output_dir / "summary.json", summary)
    write_json(output_dir / "run_manifest.json", summary["run_manifest"])
    write_json(output_dir / "llm_calls.json", summary["llm_calls"])
    write_json(output_dir / "stage_comparison.json", summary["stage_comparison"])
    write_json(output_dir / "quality_metrics.json", summary["quality_metrics"])
    write_json(output_dir / "serialization_projection_comparison.json", summary["serialization_projection_comparison"])
    write_json(output_dir / "failure_inventory.json", summary["failure_inventory"])
    (output_dir / "report.md").write_text(build_report(summary), encoding="utf-8")
    print(json.dumps({"status": summary["status"], "summary_path": str(output_dir / "summary.json")}, ensure_ascii=False))
    return 0 if summary["status"] in {"completed", "mock_completed"} else 2


def build_summary(args: argparse.Namespace, *, env_report: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    budget = CallBudget(max_calls=max(0, args.max_actual_calls))
    run_items: list[dict[str, Any]] = []
    llm_calls: list[dict[str, Any]] = []
    stage_comparison: list[dict[str, Any]] = []
    quality_metrics: list[dict[str, Any]] = []
    serialization_projection_comparison: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    planned_actual_calls = count_planned_actual_calls(args)
    succeeded_actual_calls = 0
    failed_actual_calls = 0
    fallback_actual_calls = 0

    preflight = build_runner_preflight(args)
    missing = list(preflight["missing_requirements"])
    for case_id, case, run_index, is_control in iter_case_runs(args):
        case_dir = output_dir / "runs" / f"{case_id}_{run_index}"
        case_dir.mkdir(parents=True, exist_ok=True)
        actual_requested = args.mode == "actual"
        actual_allowed = actual_requested and not missing and args.confirm_paid_calls
        if actual_requested and not args.confirm_paid_calls and "confirm_paid_calls" not in missing:
            missing.append("confirm_paid_calls")
        if actual_allowed:
            budget.consume()
        state = create_state(case["prompt"], case["context"], actual=actual_allowed)
        update = copy_candidate_generation_node(state)
        state.update(update)

        trace = dict(update.get("copy_generation_trace") or {})
        lineage = dict(trace.get("lineage") or {})
        input_projection = dict(trace.get("input_projection") or build_copy_input_projection(state))
        api_response = build_api_projection(state, update)
        serialization_projection = build_serialization_projection(api_response)
        comparison = compare_api_and_serialization(api_response, serialization_projection)
        metrics = build_candidate_quality_metrics(
            list(update.get("copy_candidates") or []),
            input_projection=input_projection,
            context=case["context"],
        )
        run_status = derive_run_status(
            mode=args.mode,
            actual_allowed=actual_allowed,
            lineage=lineage,
            serialization_matched=comparison["matched"],
        )
        if args.mode == "actual" and actual_allowed:
            if actual_lineage_completed(lineage):
                succeeded_actual_calls += 1
            elif lineage.get("fallback_used"):
                fallback_actual_calls += 1
                failed_actual_calls += 1
            else:
                failed_actual_calls += 1

        write_json(case_dir / "input_projection.json", input_projection)
        write_json(case_dir / "prompt_projection.json", trace.get("prompt_projection") or {})
        write_json(case_dir / "llm_raw_candidates.json", trace.get("llm_raw_candidates") or [])
        write_json(case_dir / "fallback_candidates.json", trace.get("fallback_candidates") or [])
        write_json(case_dir / "schema_parsed_candidates.json", trace.get("schema_parsed_candidates") or [])
        write_json(case_dir / "validated_candidates.json", trace.get("validated_candidates") or [])
        write_json(case_dir / "tone_normalized_candidates.json", trace.get("tone_normalized_candidates") or [])
        write_json(case_dir / "ranked_candidates.json", trace.get("ranked_candidates") or [])
        write_json(case_dir / "compliance_annotated_candidates.json", trace.get("compliance_annotated_candidates") or [])
        write_json(case_dir / "api_response.json", api_response)
        write_json(case_dir / "frontend_projection.json", serialization_projection)
        write_json(case_dir / "lineage.json", lineage)
        write_json(case_dir / "quality_metrics.json", metrics)

        run_items.append(
            {
                "case_id": case_id,
                "run_index": run_index,
                "case_type": "control" if is_control else "primary",
                "mode": args.mode,
                "status": run_status,
                "copy_candidate_origin": update.get("copy_candidate_origin"),
                "lineage": lineage,
            }
        )
        llm_calls.append({"case_id": case_id, "run_index": run_index, **lineage})
        stage_comparison.append(
            {
                "case_id": case_id,
                "run_index": run_index,
                "llm_raw_candidate_count": len(trace.get("llm_raw_candidates") or []),
                "fallback_candidate_count": len(trace.get("fallback_candidates") or []),
                "schema_parsed_candidate_count": len(trace.get("schema_parsed_candidates") or []),
                "validated_candidate_count": len(trace.get("validated_candidates") or []),
                "tone_normalized_candidate_count": len(trace.get("tone_normalized_candidates") or []),
                "ranked_candidate_count": len(trace.get("ranked_candidates") or []),
                "api_candidate_count": len(trace.get("api_candidates") or []),
            }
        )
        quality_metrics.append({"case_id": case_id, "run_index": run_index, **metrics})
        serialization_projection_comparison.append({"case_id": case_id, "run_index": run_index, **comparison})
        if run_status not in {"completed", "mock_completed"}:
            failures.append(
                {
                    "case_id": case_id,
                    "run_index": run_index,
                    "reason": run_status,
                    "fallback_reason": lineage.get("fallback_reason"),
                }
            )

    if args.mode == "mock":
        overall_status = "mock_completed" if not failures else "failed"
    elif missing:
        overall_status = "blocked"
    else:
        overall_status = "completed" if failures == [] and all(item["status"] == "completed" for item in run_items) else "failed"

    return {
        "schema_version": "copy_recommendation_lineage_v1",
        "created_at": datetime.now(UTC).isoformat(),
        "status": overall_status,
        "mode": args.mode,
        "env_report": env_report,
        "runner_preflight": preflight,
        "missing_requirements": missing,
        "run_manifest": {
            "runs": run_items,
            "primary_runs": args.primary_runs,
            "control_runs": args.control_runs,
            "planned_actual_calls": planned_actual_calls,
            "max_actual_calls": args.max_actual_calls,
            "attempted_actual_calls": budget.attempted,
            "succeeded_actual_calls": succeeded_actual_calls,
            "failed_actual_calls": failed_actual_calls,
            "fallback_actual_calls": fallback_actual_calls,
        },
        "llm_calls": llm_calls,
        "stage_comparison": stage_comparison,
        "quality_metrics": quality_metrics,
        "serialization_projection_comparison": serialization_projection_comparison,
        "failure_inventory": failures,
    }


def iter_case_runs(args: argparse.Namespace):
    for run_index in range(1, max(1, args.primary_runs) + 1):
        for case_id, case in PRIMARY_CASES.items():
            yield case_id, case, run_index, False
    for run_index in range(1, max(1, args.control_runs) + 1):
        for case_id, case in CONTROL_CASES.items():
            yield case_id, case, run_index, True


def build_runner_preflight(args: argparse.Namespace) -> dict[str, Any]:
    settings = get_llm_settings()
    planned_actual_calls = count_planned_actual_calls(args)
    missing = missing_actual_requirements(args, settings=settings, planned_actual_calls=planned_actual_calls)
    return {
        "canonical_settings": {
            "enable_api_call": settings.enable_api_call,
            "default_provider": settings.default_provider,
            "llm_model": settings.llm_model,
            "provider_strict_mode": settings.provider_strict_mode,
        },
        "planned_actual_calls": planned_actual_calls,
        "missing_requirements": missing,
    }


def create_state(prompt: str, context: MarketingContext, *, actual: bool) -> dict[str, Any]:
    request = InitialMarketingRequest(
        user_input=prompt,
        context=context,
        copy_generation_mode="suggest_candidates",
        requested_ad_format=str(context.extra.get("ad_format") or "banner"),
        user_plan="premium",
        workspace_id="copy_lineage_actual" if actual else None,
    )
    state = create_initial_marketing_state(request)
    state["user_plan"] = "premium"
    return state


def build_api_projection(state: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "copy_candidates",
        "jobId": state.get("job_id"),
        "threadId": state.get("thread_id"),
        "status": update.get("status"),
        "copyCandidateOrigin": update.get("copy_candidate_origin"),
        "copyCandidates": [
            {
                "id": item.get("id"),
                "headline": item.get("headline"),
                "subcopy": item.get("subcopy"),
                "cta": item.get("cta"),
            }
            for item in (update.get("copy_candidates") or [])
        ],
    }


def build_serialization_projection(api_response: dict[str, Any]) -> dict[str, Any]:
    return {
        "copyCandidateOrigin": str(api_response.get("copyCandidateOrigin") or "unknown"),
        "copyCandidates": [
            {
                "id": str(item.get("id") or ""),
                "headline": str(item.get("headline") or ""),
                "subcopy": (str(item.get("subcopy")) if item.get("subcopy") is not None else None),
                "cta": (str(item.get("cta")) if item.get("cta") is not None else None),
            }
            for item in list(api_response.get("copyCandidates") or [])
            if str(item.get("headline") or "").strip()
        ],
    }


def compare_api_and_serialization(api_response: dict[str, Any], serialization_projection: dict[str, Any]) -> dict[str, Any]:
    api_candidates = [
        (
            str(item.get("id") or ""),
            str(item.get("headline") or ""),
            str(item.get("subcopy") or ""),
            str(item.get("cta") or ""),
        )
        for item in list(api_response.get("copyCandidates") or [])
    ]
    projected_candidates = [
        (
            str(item.get("id") or ""),
            str(item.get("headline") or ""),
            str(item.get("subcopy") or ""),
            str(item.get("cta") or ""),
        )
        for item in list(serialization_projection.get("copyCandidates") or [])
    ]
    return {
        "matched": api_candidates == projected_candidates
        and str(api_response.get("copyCandidateOrigin") or "unknown") == str(serialization_projection.get("copyCandidateOrigin") or "unknown"),
        "comparison_type": "serialization_projection_comparison",
        "api_candidate_count": len(api_candidates),
        "projected_candidate_count": len(projected_candidates),
    }


def derive_run_status(*, mode: str, actual_allowed: bool, lineage: dict[str, Any], serialization_matched: bool) -> str:
    if mode == "mock":
        return "mock_completed" if serialization_matched else "failed"
    if not actual_allowed:
        return "blocked"
    if not serialization_matched:
        return "failed"
    if actual_lineage_completed(lineage):
        return "completed"
    if lineage.get("fallback_used"):
        return "completed_with_fallback"
    return "failed"


def actual_lineage_completed(lineage: dict[str, Any]) -> bool:
    executed_provider = str(lineage.get("executed_provider") or "").strip().lower()
    return bool(
        lineage.get("call_attempted")
        and lineage.get("call_succeeded")
        and not lineage.get("fallback_used")
        and lineage.get("copy_source_mode") == "llm"
        and executed_provider
        and executed_provider != "mock"
        and (lineage.get("latency_ms") or 0) > 0
    )


def build_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Copy Recommendation Lineage Report",
        "",
        f"- status: {summary['status']}",
        f"- mode: {summary['mode']}",
        f"- llm_call_count: {len(summary['llm_calls'])}",
        f"- failure_count: {len(summary['failure_inventory'])}",
    ]
    return "\n".join(lines) + "\n"


def count_planned_actual_calls(args: argparse.Namespace) -> int:
    if args.mode != "actual":
        return 0
    return len(list(iter_case_runs(args)))


def missing_actual_requirements(args: argparse.Namespace, *, settings=None, planned_actual_calls: int | None = None) -> list[str]:
    if args.mode != "actual":
        return []
    settings = settings or get_llm_settings()
    planned_actual_calls = planned_actual_calls if planned_actual_calls is not None else count_planned_actual_calls(args)
    missing: list[str] = []
    if not settings.enable_api_call:
        missing.append("EASYADS_ENABLE_LLM_CALLS=true")
    if settings.default_provider not in {"openai", "openai_compatible"}:
        missing.append("EASYADS_LLM_PROVIDER=openai")
    if not os.getenv("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if args.max_actual_calls < 1:
        missing.append("max_actual_calls_positive")
    if planned_actual_calls > args.max_actual_calls:
        missing.append("actual_plan_exceeds_call_budget")
    return missing


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
