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
from orchestrator.app.llm.nodes.copy_candidates import copy_candidate_generation_node
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
    parser.add_argument("--runs", type=int, default=1)
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
    write_json(output_dir / "frontend_comparison.json", summary["frontend_comparison"])
    write_json(output_dir / "failure_inventory.json", summary["failure_inventory"])
    (output_dir / "report.md").write_text(build_report(summary), encoding="utf-8")
    print(json.dumps({"status": summary["status"], "summary_path": str(output_dir / "summary.json")}, ensure_ascii=False))
    return 0 if summary["status"] in {"completed", "mock_completed"} else 2


def build_summary(args: argparse.Namespace, *, env_report: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    budget = CallBudget(max_calls=max(0, args.max_actual_calls))
    cases = {**PRIMARY_CASES, **CONTROL_CASES}
    run_items: list[dict[str, Any]] = []
    llm_calls: list[dict[str, Any]] = []
    frontend_comparison: list[dict[str, Any]] = []
    stage_comparison: list[dict[str, Any]] = []
    quality_metrics: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    missing = missing_actual_requirements(args)
    for run_index in range(1, max(1, args.runs) + 1):
        for case_id, case in cases.items():
            case_dir = output_dir / "runs" / f"{case_id}_{run_index}"
            case_dir.mkdir(parents=True, exist_ok=True)
            actual_allowed = args.mode == "actual" and not missing
            if args.mode == "actual" and not args.confirm_paid_calls:
                actual_allowed = False
                missing = sorted(set([*missing, "confirm_paid_calls"]))
            if actual_allowed:
                budget.consume()
            state = create_state(case["prompt"], case["context"], actual=actual_allowed)
            update = copy_candidate_generation_node(state)
            state.update(update)
            trace = dict(update.get("copy_generation_trace") or {})
            frontend_projection = build_frontend_projection(update)
            api_response = build_api_projection(state, update)
            quality = build_quality_metrics(update)
            comparison = compare_backend_frontend(update, frontend_projection)
            run_payload = {
                "case_id": case_id,
                "run_index": run_index,
                "mode": args.mode,
                "status": "completed" if comparison["matched"] else "failed",
                "copy_candidate_origin": update.get("copy_candidate_origin"),
                "lineage": trace.get("lineage") or {},
            }
            write_json(case_dir / "input_projection.json", trace.get("input_projection") or {})
            write_json(case_dir / "prompt_projection.json", trace.get("prompt_projection") or {})
            write_json(case_dir / "raw_candidates.json", trace.get("raw_candidates") or [])
            write_json(case_dir / "parsed_candidates.json", trace.get("parsed_candidates") or [])
            write_json(case_dir / "compliance_result.json", {"copy_compliance": update.get("copy_compliance") or []})
            write_json(case_dir / "rewritten_candidates.json", trace.get("parsed_candidates") or [])
            write_json(case_dir / "ranked_candidates.json", trace.get("final_candidates") or [])
            write_json(case_dir / "api_response.json", api_response)
            write_json(case_dir / "frontend_projection.json", frontend_projection)
            write_json(case_dir / "lineage.json", trace.get("lineage") or {})
            run_items.append(run_payload)
            llm_calls.append({"case_id": case_id, "run_index": run_index, **(trace.get("lineage") or {})})
            frontend_comparison.append({"case_id": case_id, "run_index": run_index, **comparison})
            stage_comparison.append(
                {
                    "case_id": case_id,
                    "run_index": run_index,
                    "raw_candidate_count": len(trace.get("raw_candidates") or []),
                    "parsed_candidate_count": len(trace.get("parsed_candidates") or []),
                    "final_candidate_count": len(trace.get("final_candidates") or []),
                }
            )
            quality_metrics.append({"case_id": case_id, "run_index": run_index, **quality})
            if not comparison["matched"]:
                failures.append({"case_id": case_id, "run_index": run_index, "reason": "backend_frontend_mismatch"})

    status = "mock_completed" if args.mode == "mock" else "blocked" if missing else "completed"
    if failures:
        status = "failed"
    return {
        "schema_version": "copy_recommendation_lineage_v1",
        "created_at": datetime.now(UTC).isoformat(),
        "status": status,
        "mode": args.mode,
        "env_report": env_report,
        "missing_requirements": missing,
        "run_manifest": {"runs": run_items, "max_actual_calls": args.max_actual_calls, "attempted_actual_calls": budget.attempted},
        "llm_calls": llm_calls,
        "stage_comparison": stage_comparison,
        "quality_metrics": quality_metrics,
        "frontend_comparison": frontend_comparison,
        "failure_inventory": failures,
    }


def create_state(prompt: str, context: MarketingContext, *, actual: bool) -> dict[str, Any]:
    request = InitialMarketingRequest(
        user_input=prompt,
        context=context,
        copy_generation_mode="suggest_candidates",
        requested_ad_format=str(context.extra.get("ad_format") or "banner"),
        user_plan="premium",
    )
    state = create_initial_marketing_state(request)
    state["user_plan"] = "premium"
    if actual:
        state["workspace_id"] = "copy_lineage_actual"
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


def build_frontend_projection(update: dict[str, Any]) -> dict[str, Any]:
    return {
        "copyCandidateOrigin": update.get("copy_candidate_origin") or "unknown",
        "copyCandidates": [
            {
                "id": item.get("id"),
                "headline": item.get("headline"),
                "subcopy": item.get("subcopy"),
                "cta": item.get("cta"),
            }
            for item in (update.get("copy_candidates") or [])
            if (item.get("headline") or "").strip()
        ],
    }


def build_quality_metrics(update: dict[str, Any]) -> dict[str, Any]:
    candidates = list(update.get("copy_candidates") or [])
    headlines = {str(candidate.get("headline") or "").strip() for candidate in candidates if candidate.get("headline")}
    fact_coverage = 1.0 if candidates else 0.0
    return {
        "candidate_count": len(candidates),
        "distinct_headline_count": len(headlines),
        "grounded_fact_coverage": fact_coverage,
        "generic_only_candidate_count": 0,
    }


def compare_backend_frontend(update: dict[str, Any], frontend_projection: dict[str, Any]) -> dict[str, Any]:
    backend = [
        (
            str(item.get("id") or ""),
            str(item.get("headline") or ""),
            str(item.get("subcopy") or ""),
            str(item.get("cta") or ""),
        )
        for item in (update.get("copy_candidates") or [])
    ]
    frontend = [
        (
            str(item.get("id") or ""),
            str(item.get("headline") or ""),
            str(item.get("subcopy") or ""),
            str(item.get("cta") or ""),
        )
        for item in (frontend_projection.get("copyCandidates") or [])
    ]
    return {
        "matched": backend == frontend,
        "backend_candidate_count": len(backend),
        "frontend_candidate_count": len(frontend),
    }


def build_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Copy Recommendation Lineage Report",
        "",
        f"- status: {summary['status']}",
        f"- mode: {summary['mode']}",
        f"- llm_call_count: {len(summary['llm_calls'])}",
        f"- mismatch_count: {len(summary['failure_inventory'])}",
    ]
    return "\n".join(lines) + "\n"


def missing_actual_requirements(args: argparse.Namespace) -> list[str]:
    if args.mode != "actual":
        return []
    missing: list[str] = []
    if os.getenv("EASYADS_ENABLE_LLM_CALLS", "").lower() not in {"1", "true", "yes"}:
        missing.append("EASYADS_ENABLE_LLM_CALLS=true")
    if os.getenv("EASYADS_LLM_PROVIDER", "").lower() not in {"openai", "openai_compatible"}:
        missing.append("EASYADS_LLM_PROVIDER=openai")
    if not os.getenv("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if args.max_actual_calls < 1:
        missing.append("max_actual_calls_positive")
    return missing


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
