"""Guarded Copy Quality Core v2 actual text verification runner."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.copy_quality_v2 import generate_copy_candidates_v2
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


CASES: dict[str, MarketingContext] = {
    "cafe_dessert_001": MarketingContext(business_type="cafe", item_or_service="딸기라떼", promotion_goal="new_launch", extra={"ad_format": "instagram_feed"}),
    "restaurant_bbq_001": MarketingContext(business_type="restaurant_bbq", item_or_service="숯불 한상", promotion_goal="reservation_cta", extra={"ad_format": "instagram_feed"}),
    "beauty_salon_001": MarketingContext(business_type="beauty_skincare", item_or_service="프리미엄 스킨케어", promotion_goal="reservation_cta", extra={"ad_format": "instagram_feed"}),
    "beauty_hair_001": MarketingContext(business_type="beauty_hair", item_or_service="헤어 상담", promotion_goal="reservation_cta", extra={"ad_format": "instagram_feed"}),
    "beauty_nail_001": MarketingContext(business_type="beauty_nail", item_or_service="네일 디자인", promotion_goal="reservation_cta", extra={"ad_format": "instagram_feed"}),
    "beauty_spa_001": MarketingContext(business_type="beauty_spa", item_or_service="웰니스 케어", promotion_goal="reservation_cta", extra={"ad_format": "instagram_feed"}),
    "fitness_001": MarketingContext(business_type="fitness", item_or_service="맞춤 운동 루틴", promotion_goal="consultation", extra={"ad_format": "instagram_feed"}),
    "clinic_001": MarketingContext(business_type="clinic", item_or_service="진료 상담", promotion_goal="reservation_cta", extra={"ad_format": "instagram_feed"}),
    "education_001": MarketingContext(business_type="education", item_or_service="맞춤 수업", promotion_goal="consultation", extra={"ad_format": "instagram_feed"}),
    "retail_001": MarketingContext(business_type="retail", item_or_service="시즌 컬렉션", promotion_goal="new_launch", extra={"ad_format": "instagram_feed"}),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actual", action="store_true")
    parser.add_argument("--max-cases", type=int, default=10)
    parser.add_argument("--max-openai-calls", type=int, default=10)
    parser.add_argument("--output-dir", default="data/outputs/copy_quality_actual_v2")
    parser.add_argument("--mode", choices=["baseline", "post"], default="post")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(args)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"copy_quality_actual_batch_v2_{timestamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)
    if report["status"] == "blocked":
        return 2
    return 0


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    missing = missing_actual_requirements(args)
    cases = list(CASES.items())[: max(1, args.max_cases)]
    runs = []
    for case_id, context in cases:
        state = create_initial_marketing_state(
            InitialMarketingRequest(user_input=f"{case_id} copy quality actual", copy_generation_mode="suggest_candidates", context=context)
        )
        generated = generate_copy_candidates_v2(state)
        runs.append(
            {
                "case_id": case_id,
                "status": "blocked" if missing and args.actual else "dry_run",
                "actual_openai_call": False,
                "business_type": context.business_type,
                "recommended_candidate_id": generated.recommended_candidate_id,
                "candidate_count": len(generated.candidates),
                "ranking": generated.ranking.model_dump(),
                "message_strategy": generated.message_strategy.model_dump(),
                "missing_requirements": missing if args.actual else [],
            }
        )
    status = "blocked" if args.actual and missing else "dry_run"
    return {
        "schema_version": "copy_quality_actual_batch_v2",
        "created_at": datetime.now(UTC).isoformat(),
        "mode": args.mode,
        "status": status,
        "actual_requested": args.actual,
        "openai_api_key_present": bool(os.getenv("OPENAI_API_KEY")),
        "max_openai_calls": args.max_openai_calls,
        "total_cases": len(runs),
        "runs": runs,
    }


def missing_actual_requirements(args: argparse.Namespace) -> list[str]:
    missing: list[str] = []
    if not args.actual:
        return missing
    if os.getenv("EASYADS_COPY_QUALITY_ACTUAL") != "1":
        missing.append("EASYADS_COPY_QUALITY_ACTUAL=1")
    if not os.getenv("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if args.max_openai_calls < 1:
        missing.append("max_openai_calls_positive")
    return missing


if __name__ == "__main__":
    raise SystemExit(main())
