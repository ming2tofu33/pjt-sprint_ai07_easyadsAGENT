"""Guarded Copy Quality Core v2 actual text verification runner."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.copy_fallbacks import build_message_strategy
from orchestrator.app.llm.copy_grounding import evaluate_copy_grounding
from orchestrator.app.llm.copy_quality_v2 import build_deterministic_copy_output_v2, generate_copy_candidates_v2_actual
from orchestrator.app.llm.copy_quality_v2 import select_recommended_copy
from orchestrator.app.llm.node_runner import run_structured_node
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext

from scripts._actual_env import load_env_file


CASES: dict[str, MarketingContext] = {
    "macaron_collection_001": MarketingContext(business_type="macaron", item_or_service="마카롱 컬렉션", promotion_goal="menu_discovery", extra={"ad_format": "instagram_feed"}),
    "cafe_strawberry_latte_001": MarketingContext(business_type="cafe", item_or_service="딸기라떼", promotion_goal="new_launch", extra={"ad_format": "instagram_feed"}),
    "restaurant_bbq_001": MarketingContext(business_type="restaurant_bbq", item_or_service="숯불구이", promotion_goal="reservation_cta", extra={"ad_format": "instagram_feed"}),
    "restaurant_table_001": MarketingContext(business_type="restaurant_bbq", item_or_service="회식 한상", promotion_goal="visit", extra={"ad_format": "instagram_feed"}),
    "beauty_nail_001": MarketingContext(business_type="beauty_nail", item_or_service="네일 디자인", promotion_goal="consultation", extra={"ad_format": "instagram_feed"}),
    "beauty_hair_color_001": MarketingContext(business_type="beauty_hair", item_or_service="헤어 컬러", promotion_goal="consultation", extra={"ad_format": "instagram_feed"}),
    "fitness_coach_001": MarketingContext(business_type="fitness", item_or_service="개인 운동 코칭", promotion_goal="consultation", extra={"ad_format": "instagram_feed"}),
    "flower_profile_photo_001": MarketingContext(business_type="photo_studio", item_or_service="꽃다발 프로필 촬영", promotion_goal="reservation_cta", extra={"ad_format": "instagram_feed"}),
    "car_detailing_001": MarketingContext(business_type="car_detailing", item_or_service="차량 디테일링", promotion_goal="inquiry", extra={"ad_format": "instagram_feed"}),
    "education_class_001": MarketingContext(business_type="education", item_or_service="학습 상담", promotion_goal="consultation", extra={"ad_format": "instagram_feed"}),
}


@dataclass
class ActualCallBudget:
    max_calls: int
    attempted: int = 0
    succeeded: int = 0
    failed: int = 0

    def consume(self, reason: str) -> None:
        if self.remaining <= 0:
            raise RuntimeError(f"actual_call_budget_exceeded:{reason}")
        self.attempted += 1

    @property
    def remaining(self) -> int:
        return max(0, self.max_calls - self.attempted)

    def mark_success(self) -> None:
        self.succeeded += 1

    def mark_failed(self) -> None:
        self.failed += 1

    def model_dump(self) -> dict[str, int]:
        return {"max_calls": self.max_calls, "attempted": self.attempted, "succeeded": self.succeeded, "failed": self.failed, "remaining": self.remaining}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actual", action="store_true")
    parser.add_argument("--max-cases", type=int, default=10)
    parser.add_argument("--cases", nargs="*", default=None)
    parser.add_argument("--max-openai-calls", type=int, default=10)
    parser.add_argument("--output-dir", default="data/outputs/copy_quality_actual_v2")
    parser.add_argument("--mode", choices=["baseline", "post"], default="post")
    parser.add_argument("--env-file", default="docs/api_key.env")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(args)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"copy_quality_actual_batch_v2_{timestamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.mode == "post":
        canonical_path = output_dir / "post_actual.json"
        canonical_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)
    return 2 if report["status"] == "blocked" else 0


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    env_file = load_env_file(getattr(args, "env_file", None))
    missing = missing_actual_requirements(args)
    budget = ActualCallBudget(max_calls=max(0, args.max_openai_calls))
    runs = []
    for case_id, context in select_cases(args):
        state = create_state(case_id, context)
        if args.mode == "baseline":
            generated = build_deterministic_copy_output_v2(state)
            llm_metadata: dict[str, Any] = {"baseline_mode": True, "llm_attempted": False}
            actual_call = False
            status = "dry_run" if not args.actual else "baseline_no_actual"
        elif args.actual and not missing:
            try:
                budget.consume("copy_generation")
                generated, llm_metadata = run_actual_copy_generation(state)
                actual_call = bool(llm_metadata.get("llm_attempted"))
                selected_copy = selected_copy_payload(generated)
                selected_grounding = selected_copy_grounding(generated, context)
                token_usage = extract_token_usage(state) or extract_token_usage_from_metadata(llm_metadata)
                model_name = extract_model_name(llm_metadata)
                if actual_run_is_complete(actual_call, llm_metadata, generated, selected_copy, token_usage, model_name, selected_grounding):
                    budget.mark_success()
                    status = "completed"
                else:
                    budget.mark_failed()
                    status = "failed"
            except Exception as exc:
                generated = build_deterministic_copy_output_v2(state)
                llm_metadata = {"error": type(exc).__name__, "message": str(exc)}
                actual_call = False
                budget.mark_failed()
                status = "failed"
        else:
            generated = build_deterministic_copy_output_v2(state)
            llm_metadata = {"llm_attempted": False, "fallback_used": True, "fallback_reason": "dry_run_or_missing_requirements"}
            actual_call = False
            status = "blocked" if args.actual and missing else "dry_run"
        selected_copy = selected_copy_payload(generated)
        selected_grounding = selected_copy_grounding(generated, context)
        token_usage = extract_token_usage(state) or extract_token_usage_from_metadata(llm_metadata)
        model_name = extract_model_name(llm_metadata)
        model_selection = extract_model_selection(llm_metadata)
        runs.append(
            {
                "case_id": case_id,
                "status": status,
                "actual_openai_call": actual_call,
                "business_type": context.business_type,
                "recommended_candidate_id": generated.recommended_candidate_id,
                "candidate_count": len(generated.candidates),
                "candidate_ids": [candidate.id for candidate in generated.candidates],
                "candidates": [
                    {
                        "id": candidate.id,
                        "angle": candidate.angle,
                        "headline": candidate.headline,
                        "subcopy": candidate.subcopy,
                        "cta": candidate.cta,
                        "score": next((card.model_dump() for card in generated.ranking.scorecards if card.candidate_id == candidate.id), {}),
                    }
                    for candidate in generated.candidates
                ],
                "selected_copy": selected_copy,
                "selected_grounding": selected_grounding,
                "grounded": bool(selected_grounding.get("grounded")),
                "wrong_domain_terms": selected_grounding.get("wrong_domain_terms", []),
                "provider": model_selection.get("provider"),
                "selected_model_class": model_selection.get("selected_model_class"),
                "fallback_used": bool(llm_metadata.get("fallback_used")),
                "recommended_distribution_key": generated.recommended_candidate_id,
                "ranking": generated.ranking.model_dump(),
                "message_strategy": generated.message_strategy.model_dump(),
                "llm_metadata": sanitize_llm_metadata(llm_metadata),
                "token_usage": token_usage,
                "model_name": model_name,
                "missing_requirements": missing if args.actual else [],
            }
        )
    status = "blocked" if args.actual and missing else "completed" if args.actual and all(run["status"] == "completed" for run in runs) else "failed" if args.actual else "dry_run"
    return {
        "schema_version": "copy_quality_actual_batch_v2",
        "created_at": datetime.now(UTC).isoformat(),
        "mode": args.mode,
        "status": status,
        "actual_requested": args.actual,
        "env_file": env_file,
        "openai_api_key_present": bool(os.getenv("OPENAI_API_KEY")),
        "max_openai_calls": args.max_openai_calls,
        "call_budget": budget.model_dump(),
        "total_cases": len(runs),
        "recommended_id_distribution": distribution(run["recommended_candidate_id"] for run in runs),
        "runs": runs,
    }


def select_cases(args: argparse.Namespace) -> list[tuple[str, MarketingContext]]:
    requested = getattr(args, "cases", None) or list(CASES)
    selected: list[tuple[str, MarketingContext]] = []
    for case_id in requested:
        if case_id not in CASES:
            raise ValueError(f"unknown_case:{case_id}")
        selected.append((case_id, CASES[case_id]))
    return selected[: max(1, args.max_cases)]


def run_actual_copy_generation(state: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    prompt = (
        "Create Copy Quality Core v2 Korean ad copy. Return JSON matching this shape exactly: "
        "{\"candidates\":[{\"id\":\"copy_1\",\"headline\":\"...\",\"subcopy\":\"...\",\"cta\":\"...\","
        "\"angle\":\"product_first\",\"strategy_summary\":\"...\",\"metadata\":{}}],"
        "\"recommended_candidate_id\":\"copy_1\",\"metadata\":{}}. Return exactly three candidates with angles "
        "product_first, emotion_first, benefit_action_first. Avoid generic placeholder language and unsupported claims."
    )
    return generate_copy_candidates_v2_actual(state, run_structured_node_fn=run_structured_node, prompt=prompt, max_candidates=3)


def selected_copy_payload(generated: Any) -> dict[str, str | None] | None:
    selected = select_recommended_copy(generated.candidates, generated.ranking)
    if selected is None:
        return None
    return {"headline": selected.headline, "subcopy": selected.subcopy, "cta": selected.cta}


def selected_copy_grounding(generated: Any, context: MarketingContext) -> dict[str, Any]:
    selected = select_recommended_copy(generated.candidates, generated.ranking)
    if selected is None:
        return {"grounded": False, "wrong_domain_terms": ["no_selected_copy"], "grounding_level": "missing"}
    return evaluate_copy_grounding(selected, context=context, strategy=build_message_strategy(context)).model_dump()


def create_state(case_id: str, context: MarketingContext) -> dict[str, Any]:
    state = create_initial_marketing_state(
        InitialMarketingRequest(user_input=f"{case_id} copy quality actual", user_plan="premium", copy_generation_mode="suggest_candidates", context=context)
    )
    state["user_plan"] = "premium"
    policy = dict(state.get("plan_policy") or {})
    policy["max_api_calls_per_job"] = 1
    state["plan_policy"] = policy
    return state


def missing_actual_requirements(args: argparse.Namespace) -> list[str]:
    missing: list[str] = []
    if not args.actual:
        return missing
    if os.getenv("EASYADS_COPY_QUALITY_ACTUAL") != "1":
        missing.append("EASYADS_COPY_QUALITY_ACTUAL=1")
    if os.getenv("EASYADS_ENABLE_LLM_CALLS", "").lower() not in {"1", "true", "yes"}:
        missing.append("EASYADS_ENABLE_LLM_CALLS=true")
    if os.getenv("EASYADS_LLM_PROVIDER", "").lower() not in {"openai", "openai_compatible"}:
        missing.append("EASYADS_LLM_PROVIDER=openai")
    if not os.getenv("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if args.max_openai_calls < 1:
        missing.append("max_openai_calls_positive")
    return missing


def extract_token_usage(state: dict[str, Any]) -> dict[str, Any] | None:
    for result in reversed(state.get("llm_call_results") or []):
        usage = result.get("token_usage") or result.get("usage")
        if usage:
            return usage
    return None


def extract_token_usage_from_metadata(metadata: dict[str, Any]) -> dict[str, Any] | None:
    candidates = [
        metadata.get("token_usage"),
        metadata.get("usage"),
        (metadata.get("llm_call_result") or {}).get("token_usage"),
        (metadata.get("llm_call_result") or {}).get("usage"),
    ]
    for usage in candidates:
        if usage:
            return usage
    return None


def extract_model_name(metadata: dict[str, Any]) -> str | None:
    selection = metadata.get("model_selection") or {}
    call = metadata.get("llm_call_result") or {}
    return (
        metadata.get("model_name")
        or metadata.get("model")
        or call.get("model_name")
        or call.get("model")
        or selection.get("model_name")
        or selection.get("provider_profile")
        or selection.get("selected_model_class")
    )


def extract_model_selection(metadata: dict[str, Any]) -> dict[str, Any]:
    selection = dict(metadata.get("model_selection") or {})
    call = dict(metadata.get("llm_call_result") or {})
    return {
        "provider": metadata.get("provider") or call.get("provider") or selection.get("provider"),
        "selected_model_class": metadata.get("selected_model_class") or call.get("selected_model_class") or selection.get("selected_model_class"),
    }


def actual_run_is_complete(
    actual_call: bool,
    metadata: dict[str, Any],
    generated: Any,
    selected_copy: dict[str, str | None] | None,
    token_usage: dict[str, Any] | None,
    model_name: str | None,
    selected_grounding: dict[str, Any],
) -> bool:
    return bool(
        actual_call
        and not metadata.get("fallback_used")
        and len(getattr(generated, "candidates", []) or []) == 3
        and selected_copy
        and token_usage
        and model_name
        and selected_grounding.get("grounded")
        and not selected_grounding.get("wrong_domain_terms")
    )


def sanitize_llm_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(metadata, ensure_ascii=False)
    for value in (os.getenv("OPENAI_API_KEY"), os.getenv("HF_TOKEN"), os.getenv("HUGGINGFACE_TOKEN")):
        if value:
            text = text.replace(value, "[redacted]")
    return json.loads(text)


def distribution(values) -> dict[str, int]:
    output: dict[str, int] = {}
    for value in values:
        key = str(value or "none")
        output[key] = output.get(key, 0) + 1
    return output


if __name__ == "__main__":
    raise SystemExit(main())
