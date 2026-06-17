from __future__ import annotations

import argparse
import json
import os
import re
import sys
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import uuid4

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.app.graph.builder import build_marketing_graph
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.ad_format_presets import build_ad_format_spec
from orchestrator.app.ocr_gate.schemas import OCRSpan, OCRTextMatch, OCRValidationResult
from orchestrator.app.quality_gate.ocr_validation import normalize_ocr_text
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest
from scripts._actual_env import load_env_file


DEFAULT_OUTPUT_DIR = Path("data/qa/ad_format_render_e2e_v1")
CASE_MANIFEST_PATH = Path(__file__).with_name("ad_format_render_e2e_cases_v1.json")
EXPECTED_FORMATS = ("banner", "flyer", "product_detail")
AD_FORMAT_TO_CHANNEL_ID = {
    "banner": "banner",
    "flyer": "flyer",
    "product_detail": "product_detail",
}
SUPPORTED_ACTUAL_ENGINES = {
    "gpt_image_2": {
        "lane_flags": {
            "EASYADS_ENABLE_LLM_CALLS": "1",
            "EASYADS_ENABLE_EXTERNAL_T2I": "1",
            "EASYADS_VLM_ACTUAL": "1",
            "EASYADS_FINAL_COMPOSITE_ACTUAL": "1",
            "EASYADS_ENABLE_GPT_IMAGE_2": "1",
            "T2I_ALLOW_API_CALLS": "1",
        }
    },
    "flux2_klein_4b": {
        "lane_flags": {
            "EASYADS_ENABLE_LLM_CALLS": "1",
            "EASYADS_ENABLE_EXTERNAL_T2I": "1",
            "EASYADS_VLM_ACTUAL": "1",
            "EASYADS_FINAL_COMPOSITE_ACTUAL": "1",
            "EASYADS_ENABLE_FLUX2_KLEIN_LOCAL": "1",
            "EASYADS_FLUX2_KLEIN_ACTUAL": "1",
            "T2I_ALLOW_API_CALLS": "1",
        }
    },
}
BASE_ACTUAL_ENV_REQUIREMENTS = ("OPENAI_API_KEY",)
TRANSPORT_ERROR_PATTERNS = (
    "timeout",
    "timed out",
    "connection",
    "connecterror",
    "connectionerror",
    "rate limit",
    "429",
    "500",
    "502",
    "503",
    "504",
    "service unavailable",
)
CTA_TERMS = ("지금 구매", "자세히 보기", "예약하기", "바로가기", "주문하기", "문의하기")
REDACTED_KEY_PATTERNS = ("api_key", "authorization", "signed_url", "token", "secret", "bucket", "object_key", "base64", "raw_body", "credential")
REQUIRED_VISUAL_REVIEW_FIELDS = (
    "product_visibility",
    "text_readability",
    "text_overlap",
    "safe_area",
    "unexpected_button_shape",
    "unexpected_text",
    "format_suitability",
    "crop_damage",
)
PASS_VALUES = {"pass"}
FAIL_VALUES = {"fail"}
MANUAL_VALUES = {"manual_review", "awaiting_manual_review", "review"}


class LaneOptInError(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("mock", "actual"))
    parser.add_argument("--formats", default="banner,flyer,product_detail")
    parser.add_argument("--engine", default=None)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--max-successful-calls", type=int, default=3)
    parser.add_argument("--max-actual-attempts", type=int, default=6)
    parser.add_argument("--allow-transport-retry", action="store_true")
    parser.add_argument("--confirm-paid-calls", action="store_true")
    parser.add_argument("--enable-required-lane-flags", action="store_true")
    parser.add_argument("--env-file", default="docs/api_key.env")
    parser.add_argument("--review-file", default=None)
    parser.add_argument("--self-check", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.self_check:
        result = run_self_check(args)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["status"] == "ok" else 2
    if not args.mode:
        raise SystemExit("--mode is required unless --self-check is used")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    env_report = load_env_file(args.env_file if args.mode == "actual" else None)
    review_map = load_review_map(args.review_file)
    formats = parse_formats(args.formats)
    cases = select_cases(formats)

    if args.mode == "mock":
        summary = run_mock_suite(cases=cases, output_dir=output_dir, env_report=env_report)
    else:
        summary = run_actual_suite(
            cases=cases,
            output_dir=output_dir,
            engine=args.engine,
            max_successful_calls=args.max_successful_calls,
            max_actual_attempts=args.max_actual_attempts,
            allow_transport_retry=args.allow_transport_retry,
            confirm_paid_calls=args.confirm_paid_calls,
            enable_required_lane_flags=args.enable_required_lane_flags,
            review_map=review_map,
            env_report=env_report,
        )

    summary = merge_existing_summary(output_dir, summary)
    write_summary_artifacts(output_dir, summary)
    print(json.dumps({"status": summary["status"], "summary_path": str(output_dir / "summary.json")}, ensure_ascii=False))
    return 0 if summary["status"] in {"completed", "completed_with_findings"} else 2


def run_self_check(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[str] = []
    cases = load_cases()
    seen_case_ids: set[str] = set()
    formats_seen: set[str] = set()
    for case in cases:
        case_id = str(case["case_id"])
        if case_id in seen_case_ids:
            errors.append(f"duplicate_case_id:{case_id}")
        seen_case_ids.add(case_id)
        ad_format = str(case["ad_format"])
        formats_seen.add(ad_format)
        if ad_format not in EXPECTED_FORMATS:
            errors.append(f"unsupported_format:{ad_format}")
            continue
        preset = build_ad_format_spec(ad_format)
        if int(case["expected_width"]) != preset.width or int(case["expected_height"]) != preset.height:
            errors.append(f"preset_dimension_mismatch:{ad_format}")
        if str(case["expected_aspect_ratio"]) != str(preset.aspect_ratio):
            errors.append(f"preset_aspect_ratio_mismatch:{ad_format}")
        if str(case["selected_channel_id"]) != AD_FORMAT_TO_CHANNEL_ID[ad_format]:
            errors.append(f"channel_mismatch:{ad_format}")
        visible_range = case.get("expected_visible_text_range") or case.get("expected_text_block_range") or []
        if len(visible_range) != 2 or int(visible_range[0]) < 0 or int(visible_range[1]) < int(visible_range[0]):
            errors.append(f"invalid_visible_text_range:{ad_format}")
        if ad_format == "flyer" and not case.get("flyer_plan_type"):
            errors.append("missing_flyer_plan_type")
    if formats_seen != set(EXPECTED_FORMATS):
        errors.append(f"unexpected_formats:{sorted(formats_seen)}")
    return {
        "status": "ok" if not errors else "failed",
        "case_manifest_path": str(CASE_MANIFEST_PATH),
        "case_count": len(cases),
        "formats": sorted(formats_seen),
        "default_output_dir": str(Path(args.output_dir)),
        "errors": errors,
    }


def run_mock_suite(*, cases: list[dict[str, Any]], output_dir: Path, env_report: dict[str, Any]) -> dict[str, Any]:
    results: dict[str, dict[str, Any]] = {}
    call_log: list[dict[str, Any]] = []
    with mocked_ocr_gate():
        for case in cases:
            case_result, case_calls = run_case_with_retry(
                case=case,
                mode="mock",
                engine=None,
                output_dir=output_dir / "mock" / case["ad_format"],
                allow_transport_retry=False,
                remaining_attempt_budget=1,
                review_payload=None,
            )
            results[case["ad_format"]] = case_result
            call_log.extend(case_calls)
    return build_summary(
        status=summary_status(mode="mock", case_results=results),
        mode="mock",
        engine="mock",
        env_report=env_report,
        mock_results=results,
        actual_results={},
        call_log=call_log,
        production_code_changed=False,
        missing_requirements=[],
    )


def run_actual_suite(
    *,
    cases: list[dict[str, Any]],
    output_dir: Path,
    engine: str | None,
    max_successful_calls: int,
    max_actual_attempts: int,
    allow_transport_retry: bool,
    confirm_paid_calls: bool,
    enable_required_lane_flags: bool,
    review_map: dict[str, dict[str, Any]],
    env_report: dict[str, Any],
) -> dict[str, Any]:
    opt_in_errors = actual_opt_in_errors(
        engine=engine,
        confirm_paid_calls=confirm_paid_calls,
        enable_required_lane_flags=enable_required_lane_flags,
    )
    env_updates = {}
    if not opt_in_errors and enable_required_lane_flags:
        env_updates = enable_actual_lane_flags(engine=engine, confirmed_paid_calls=confirm_paid_calls)

    with temporary_env_updates(env_updates):
        missing = opt_in_errors + actual_missing_requirements(engine)
        if missing:
            actual_results = build_blocked_actual_results(cases=cases, output_dir=output_dir, blocker=", ".join(missing))
            return build_summary(
                status="blocked",
                mode="actual",
                engine=engine,
                env_report=env_report,
                mock_results={},
                actual_results=actual_results,
                call_log=[{"mode": "actual", "status": "blocked", "missing_requirements": missing}],
                production_code_changed=False,
                missing_requirements=missing,
            )

        actual_results: dict[str, dict[str, Any]] = {}
        call_log: list[dict[str, Any]] = []
        successful_calls = 0
        actual_attempts = 0

        for case in cases:
            if successful_calls >= max_successful_calls:
                actual_results[case["ad_format"]] = blocked_case_result(case, blocker="max_successful_calls_reached")
                continue
            if actual_attempts >= max_actual_attempts:
                actual_results[case["ad_format"]] = blocked_case_result(case, blocker="max_actual_attempts_reached")
                continue

            remaining_budget = max_actual_attempts - actual_attempts
            case_result, case_calls = run_case_with_retry(
                case=case,
                mode="actual",
                engine=engine,
                output_dir=output_dir / "actual" / case["ad_format"],
                allow_transport_retry=allow_transport_retry,
                remaining_attempt_budget=remaining_budget,
                review_payload=resolve_review_payload(review_map, case),
            )
            actual_results[case["ad_format"]] = case_result
            call_log.extend(case_calls)
            actual_attempts += len(case_calls)
            if case_result["overall_status"] in {"passed", "completed_with_findings", "awaiting_manual_review"} and int(case_result.get("actual_calls") or 0) > 0:
                successful_calls += int(case_result.get("actual_calls") or 0)

        return build_summary(
            status=summary_status(mode="actual", case_results=actual_results),
            mode="actual",
            engine=engine,
            env_report=env_report,
            mock_results={},
            actual_results=actual_results,
            call_log=call_log,
            production_code_changed=False,
            missing_requirements=[],
        )


def build_blocked_actual_results(*, cases: list[dict[str, Any]], output_dir: Path, blocker: str) -> dict[str, dict[str, Any]]:
    actual_results: dict[str, dict[str, Any]] = {}
    for case in cases:
        result = blocked_case_result(case, blocker=blocker)
        actual_results[case["ad_format"]] = result
        case_dir = output_dir / "actual" / case["ad_format"]
        case_dir.mkdir(parents=True, exist_ok=True)
        write_json(case_dir / "qa_result.json", result)
    return actual_results


def blocked_case_result(case: dict[str, Any], *, blocker: str) -> dict[str, Any]:
    return {
        "case_id": case["case_id"],
        "ad_format": case["ad_format"],
        "mode": "actual",
        "pipeline_status": "blocked",
        "dimension_status": "not_run",
        "cta_status": "not_run",
        "layout_status": "not_run",
        "ocr_status": "not_run",
        "visual_review_status": "not_run",
        "overall_status": "blocked",
        "failure_code": "blocked",
        "blocker": blocker,
        "actual_calls": 0,
        "billable_call_count": 0,
        "attempt_count": 0,
    }


def summarize_case_maps(
    *, mock_results: dict[str, dict[str, Any]], actual_results: dict[str, dict[str, Any]]
) -> dict[str, int]:
    all_case_results = [*mock_results.values(), *actual_results.values()]
    return {
        "dimension_failures": sum(1 for value in all_case_results if value.get("dimension_status") == "failed"),
        "cta_failures": sum(1 for value in all_case_results if value.get("cta_status") == "failed"),
        "layout_failures": sum(1 for value in all_case_results if value.get("layout_status") == "failed"),
        "ocr_failures": sum(1 for value in all_case_results if value.get("ocr_status") == "failed"),
        "manual_review_count": sum(
            1
            for value in all_case_results
            if value.get("ocr_status") == "manual_review" or value.get("visual_review_status") in {"manual_review", "awaiting_manual_review"}
        ),
    }


def run_case_with_retry(
    *,
    case: dict[str, Any],
    mode: str,
    engine: str | None,
    output_dir: Path,
    allow_transport_retry: bool,
    remaining_attempt_budget: int,
    review_payload: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    call_log: list[dict[str, Any]] = []
    max_case_attempts = min(2 if allow_transport_retry and mode == "actual" else 1, max(1, remaining_attempt_budget))
    final_result = blocked_case_result(case, blocker="no_attempt_executed") if mode == "actual" else {}

    for attempt in range(1, max_case_attempts + 1):
        started_at = datetime.now(UTC).isoformat()
        try:
            request, result = invoke_graph_case(case=case, mode=mode, engine=engine)
            qa = evaluate_case(case=case, request=request, result=result, mode=mode, review_payload=review_payload)
            ended_at = datetime.now(UTC).isoformat()
            entry = {
                "mode": mode,
                "format": case["ad_format"],
                "attempt": attempt,
                "attempt_executed": True,
                "engine": engine or "mock",
                "started_at": started_at,
                "ended_at": ended_at,
                "status": qa["overall_status"],
                "error_type": qa.get("error_type"),
                "billable_call": bool(qa.get("billable_call_count")),
                "retry_reason": None,
            }
            call_log.append(entry)
            write_case_artifacts(output_dir=output_dir, request=request, result=result, qa=qa)
            final_result = qa
            if qa["overall_status"] == "blocked" and qa.get("failure_code") == "actual_engine_did_not_execute":
                return qa, call_log
            return qa, call_log
        except Exception as exc:  # noqa: BLE001
            failure = failure_from_exception(case=case, mode=mode, engine=engine, exc=exc)
            ended_at = datetime.now(UTC).isoformat()
            entry = {
                "mode": mode,
                "format": case["ad_format"],
                "attempt": attempt,
                "attempt_executed": True,
                "engine": engine or "mock",
                "started_at": started_at,
                "ended_at": ended_at,
                "status": failure["overall_status"],
                "error_type": failure.get("error_type"),
                "billable_call": False,
                "retry_reason": failure.get("retry_reason"),
            }
            call_log.append(entry)
            write_case_artifacts(output_dir=output_dir, request=None, result=None, qa=failure)
            final_result = failure
            if not should_retry_transport_failure(failure=failure, allow_transport_retry=allow_transport_retry, mode=mode, attempt=attempt, max_case_attempts=max_case_attempts):
                return failure, call_log
    return final_result, call_log


def invoke_graph_case(*, case: dict[str, Any], mode: str, engine: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
    request = build_graph_request(case, engine=engine, run_token=uuid4().hex[:8])
    graph_input = build_graph_input(request, engine=engine)
    graph = build_marketing_graph()
    if mode == "mock":
        with mocked_ocr_gate():
            result = graph.invoke(graph_input, config={"configurable": {"thread_id": request["thread_id"]}})
    else:
        result = graph.invoke(graph_input, config={"configurable": {"thread_id": request["thread_id"]}})
    return request, result


def build_graph_request(case: dict[str, Any], *, engine: str | None, run_token: str) -> dict[str, Any]:
    job_id = f"qa-{case['case_id']}-{run_token}"
    request = {
        "user_input": case["user_input"],
        "job_id": job_id,
        "thread_id": job_id,
        "copy_generation_mode": case["copy_generation_mode"],
        "selected_channel_id": case["selected_channel_id"],
        "selected_ad_format": case["ad_format"],
        "context": {
            "business_type": "cafe",
            "item_or_service": "latte",
            "promotion_goal": "new_launch",
            "brand_tone": "clean",
            "extra": {
                "ad_format": case["ad_format"],
                "selected_channel_id": case["selected_channel_id"],
            },
        },
    }
    if case.get("user_custom_headline"):
        request["user_custom_headline"] = case["user_custom_headline"]
    if case.get("user_custom_subcopy"):
        request["user_custom_subcopy"] = case["user_custom_subcopy"]
    if engine:
        request["engine"] = engine
        request["current_brief"] = {"requested_engine": engine, "engine": engine}
    return request


def build_graph_input(request: dict[str, Any], *, engine: str | None) -> dict[str, Any]:
    render_profile = "premium_api" if engine in {"gpt_image_1", "gpt_image_2"} else "balanced"
    initial_request = InitialMarketingRequest(
        user_input=str(request["user_input"]),
        job_id=str(request["job_id"]),
        thread_id=str(request["thread_id"]),
        context=request.get("context") or {},
        copy_generation_mode=str(request.get("copy_generation_mode") or "auto_pilot"),
        requested_ad_format=str(request.get("selected_ad_format") or ""),
        render_profile=render_profile,
        user_custom_headline=clean_optional_text(request.get("user_custom_headline")),
        user_custom_subcopy=clean_optional_text(request.get("user_custom_subcopy")),
    )
    state = create_initial_marketing_state(initial_request)
    state["selected_channel_id"] = request.get("selected_channel_id")
    state["selected_ad_format"] = request.get("selected_ad_format")
    state["current_brief"]["selected_channel_id"] = request.get("selected_channel_id")
    state["current_brief"]["requested_ad_format"] = request.get("selected_ad_format")
    if engine:
        state["engine"] = engine
        state["current_brief"]["requested_engine"] = engine
        state["current_brief"]["engine"] = engine
    return state


def evaluate_case(
    *,
    case: dict[str, Any],
    request: dict[str, Any],
    result: dict[str, Any],
    mode: str,
    review_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    if result.get("status") != "done":
        failure = failure_from_result(case=case, mode=mode, engine=str(request.get("engine") or "mock"), result=result)
        failure["request_projection"] = project_request(request)
        failure["result_projection"] = project_state_summary(result)
        return failure

    expected_width = int(case["expected_width"])
    expected_height = int(case["expected_height"])
    expected_aspect_ratio = str(case["expected_aspect_ratio"])
    final_image_path = Path(str(result.get("final_image_path") or ""))
    final_width, final_height = read_image_size(final_image_path)
    ad_format_spec = result.get("ad_format_spec") or {}
    t2i_request = result.get("t2i_request") or {}
    t2i_result = result.get("t2i_result") or {}
    text_layout_spec = result.get("text_layout_spec") or {}
    render_result = result.get("render_result") or {}
    render_image_path = Path(str((render_result.get("final_image_path") or result.get("final_image_path") or "")))
    render_width, render_height = read_image_size(render_image_path)
    copy_spec = result.get("copy_spec") or {}
    ocr_result = result.get("final_ocr_gate") or {}
    current_brief = result.get("current_brief") or {}
    traces = ((render_result.get("metadata") or {}).get("typography_render_traces") or [])
    provider = actual_provider_name(t2i_result)
    selected_channel_id = (
        clean_optional_text(result.get("selected_channel_id"))
        or clean_optional_text(current_brief.get("selected_channel_id"))
        or clean_optional_text((result.get("context") or {}).get("extra", {}).get("selected_channel_id"))
        or AD_FORMAT_TO_CHANNEL_ID.get(str(current_brief.get("requested_ad_format") or ad_format_spec.get("ad_format") or ""))
    )
    graph_requested_ad_format = clean_optional_text(current_brief.get("requested_ad_format")) or clean_optional_text(ad_format_spec.get("ad_format"))
    actual_engine = clean_optional_text(request.get("engine")) or clean_optional_text((t2i_result.get("metadata") or {}).get("effective_engine")) or clean_optional_text(t2i_result.get("engine"))
    native_layout = is_native_typography_result(result)
    visible_range = case.get("expected_visible_text_range") or [0, 0]

    dimension_checks = {
        "ad_format_spec": (
            int(ad_format_spec.get("width") or 0) == expected_width
            and int(ad_format_spec.get("height") or 0) == expected_height
            and str(ad_format_spec.get("aspect_ratio") or "") == expected_aspect_ratio
        ),
        "t2i_request": (
            True
            if native_layout and not t2i_request
            else int(t2i_request.get("width") or 0) == expected_width and int(t2i_request.get("height") or 0) == expected_height
        ),
        "t2i_result": int(t2i_result.get("width") or 0) == expected_width and int(t2i_result.get("height") or 0) == expected_height,
        "renderer_canvas": render_width == expected_width and render_height == expected_height,
        "final_image": final_width == expected_width and final_height == expected_height,
    }
    dimension_status = "passed" if all(dimension_checks.values()) else "failed"

    cta_visibility = (
        (((copy_spec.get("metadata") or {}).get("copy_visual_intent") or {}).get("cta_visibility"))
        or (((result.get("copy_visual_intent") or {})).get("cta_visibility"))
        or ("hidden" if native_layout else None)
        or "unknown"
    )
    copy_items = copy_spec.get("items") or []
    cta_items = [item for item in copy_items if item.get("role") == "cta"]
    cta_status = "passed" if cta_visibility == case["expected_cta_visibility"] and not cta_items else "failed"

    layout_status, layout_failure_reason, block_count, native_contract = evaluate_visible_text_contract(
        case=case,
        result=result,
        traces=traces,
        width=final_width,
        height=final_height,
        native_layout=native_layout,
        visible_range=visible_range,
    )

    expected_texts = [item.get("text") for item in copy_items if item.get("role") == "headline" and item.get("text")]
    expected_matches = ocr_result.get("expected_matches") or []
    detected_spans = ocr_result.get("detected_spans") or []
    unexpected_text = [span.get("text") for span in (ocr_result.get("unexpected_text") or []) if span.get("text")]
    matched_headlines = {match.get("expected") for match in expected_matches if match.get("status") == "matched"}
    missing_expected_text = [text for text in expected_texts if text not in matched_headlines]
    detected_text = [span.get("text") for span in detected_spans if span.get("text")]
    detected_region_count = len(detected_spans)
    ocr_provider_status = str(ocr_result.get("status") or "unavailable")
    if unexpected_text or any(term in " ".join(detected_text) for term in CTA_TERMS):
        ocr_status = "failed"
    elif native_layout and ocr_provider_status in {"manual_review", "unavailable"} and not missing_expected_text:
        ocr_status = "passed"
    elif ocr_provider_status == "pass" and not missing_expected_text:
        ocr_status = "passed"
    elif ocr_provider_status == "fail" and missing_expected_text:
        ocr_status = "failed"
    elif ocr_provider_status in {"manual_review", "unavailable"}:
        ocr_status = "manual_review"
    elif missing_expected_text:
        ocr_status = "failed"
    else:
        ocr_status = "manual_review"

    visual_review_status, visual_review_result = resolve_visual_review(
        mode=mode,
        review_payload=review_payload,
    )

    if mode == "actual" and provider.lower() == "mock":
        overall_status = "blocked"
        pipeline_status = "blocked"
        failure_code = "actual_engine_did_not_execute"
    elif dimension_status == "failed":
        overall_status = "failed"
        pipeline_status = "failed"
        failure_code = "dimension_contract_failure"
    elif cta_status == "failed":
        overall_status = "failed"
        pipeline_status = "failed"
        failure_code = "cta_contract_failure"
    elif layout_status == "failed":
        overall_status = "failed"
        pipeline_status = "failed"
        failure_code = "layout_block_failure"
    elif ocr_status == "failed":
        overall_status = "failed"
        pipeline_status = "completed"
        failure_code = "ocr_expected_text_missing" if missing_expected_text else "ocr_unexpected_text"
    elif mode == "actual" and visual_review_status == "awaiting_manual_review":
        overall_status = "awaiting_manual_review"
        pipeline_status = "completed"
        failure_code = None
    elif ocr_status == "manual_review" or visual_review_status == "manual_review":
        overall_status = "completed_with_findings"
        pipeline_status = "completed"
        failure_code = None
    else:
        overall_status = "passed"
        pipeline_status = "completed"
        failure_code = None

    billable_call_count = 1 if mode == "actual" and provider.lower() != "mock" else 0
    qa = {
        "case_id": case["case_id"],
        "ad_format": case["ad_format"],
        "mode": mode,
        "request_ad_format": case["ad_format"],
        "response_selected_channel_id": selected_channel_id,
        "graph_requested_ad_format": graph_requested_ad_format,
        "actual_provider": provider,
        "actual_engine": actual_engine,
        "native_typography": native_layout,
        "pipeline_status": pipeline_status,
        "dimension_status": dimension_status,
        "cta_status": cta_status,
        "layout_status": layout_status,
        "ocr_status": ocr_status,
        "visual_review_status": visual_review_status,
        "overall_status": overall_status,
        "failure_code": failure_code,
        "blocker": "actual_engine_did_not_execute" if failure_code == "actual_engine_did_not_execute" else None,
        "attempt_count": 1,
        "actual_calls": billable_call_count,
        "billable_call_count": billable_call_count,
        "expected_width": expected_width,
        "expected_height": expected_height,
        "expected_aspect_ratio": expected_aspect_ratio,
        "final_image_path": str(final_image_path),
        "provider_source_path": clean_optional_text((t2i_result.get("metadata") or {}).get("provider_image_path")),
        "final_size": [final_width, final_height],
        "renderer_size": [render_width, render_height],
        "detected_text": detected_text,
        "missing_expected_text": missing_expected_text,
        "unexpected_text": unexpected_text,
        "ocr_confidence": float(ocr_result.get("confidence") or 0.0),
        "detected_region_count": detected_region_count,
        "text_block_count": block_count,
        "expected_visible_text_range": [int(visible_range[0]), int(visible_range[1])],
        "dimension_checks": dimension_checks,
        "layout_failure_reason": layout_failure_reason,
        "native_contract": native_contract,
        "visual_review": visual_review_result,
        "request_projection": project_request(request),
        "ad_format_spec": project_ad_format_spec(ad_format_spec),
        "image_prompt_spec": project_image_prompt_spec(result.get("image_prompt_spec") or {}),
        "copy_spec": project_copy_spec(copy_spec),
        "text_layout_spec": project_text_layout_spec(text_layout_spec),
        "t2i_request": project_t2i_request(t2i_request),
        "t2i_result": project_t2i_result(t2i_result),
        "render_result": project_render_result(render_result),
        "ocr_result": project_ocr_result(ocr_result),
    }
    return qa


def resolve_visual_review(*, mode: str, review_payload: dict[str, Any] | None) -> tuple[str, dict[str, Any] | None]:
    if mode == "mock":
        return "not_run", None
    if review_payload is None:
        return "awaiting_manual_review", None
    values = {field: str(review_payload.get(field) or "") for field in REQUIRED_VISUAL_REVIEW_FIELDS}
    manual_notes = clean_optional_text(review_payload.get("manual_notes"))
    if any(value in FAIL_VALUES for value in values.values()):
        status = "failed"
    elif any(value in MANUAL_VALUES for value in values.values()):
        status = "manual_review"
    elif all(value in PASS_VALUES for value in values.values()):
        status = "pass"
    else:
        status = "manual_review"
    payload = dict(values)
    if manual_notes:
        payload["manual_notes"] = manual_notes
    return status, payload


def failure_from_result(*, case: dict[str, Any], mode: str, engine: str, result: dict[str, Any]) -> dict[str, Any]:
    error_code = clean_optional_text((result.get("error_info") or {}).get("error_code")) or "graph_execution_failed"
    error_message = clean_optional_text(result.get("error_message")) or clean_optional_text((result.get("error_info") or {}).get("message")) or "Graph execution failed."
    failure_code = "provider_transport_failure" if is_transport_error_text(f"{error_code} {error_message}") else "provider_generation_failure"
    rejection = build_rejection_diagnostics(result)
    return {
        "case_id": case["case_id"],
        "ad_format": case["ad_format"],
        "mode": mode,
        "pipeline_status": "failed",
        "dimension_status": "not_run",
        "cta_status": "not_run",
        "layout_status": "not_run",
        "ocr_status": "not_run",
        "visual_review_status": "not_run",
        "overall_status": "failed",
        "failure_code": failure_code,
        "error_type": clean_optional_text((result.get("error_info") or {}).get("error_type")),
        "error_message": error_message,
        "retry_reason": failure_code if failure_code == "provider_transport_failure" else None,
        "attempt_count": 1,
        "actual_calls": 0,
        "billable_call_count": 0,
        "request_projection": None,
        "result_projection": project_state_summary(result),
        "reject_stage": rejection["reject_stage"],
        "rejection_diagnostics": rejection,
    }


def failure_from_exception(*, case: dict[str, Any], mode: str, engine: str | None, exc: Exception) -> dict[str, Any]:
    error_message = str(exc)
    failure_code = "provider_transport_failure" if is_transport_error_text(error_message) else "provider_generation_failure"
    return {
        "case_id": case["case_id"],
        "ad_format": case["ad_format"],
        "mode": mode,
        "pipeline_status": "failed",
        "dimension_status": "not_run",
        "cta_status": "not_run",
        "layout_status": "not_run",
        "ocr_status": "not_run",
        "visual_review_status": "not_run",
        "overall_status": "failed",
        "failure_code": failure_code,
        "error_type": type(exc).__name__,
        "error_message": error_message,
        "retry_reason": failure_code if failure_code == "provider_transport_failure" else None,
        "attempt_count": 1,
        "actual_calls": 0,
        "billable_call_count": 0,
    }


def should_retry_transport_failure(*, failure: dict[str, Any], allow_transport_retry: bool, mode: str, attempt: int, max_case_attempts: int) -> bool:
    if mode != "actual" or not allow_transport_retry:
        return False
    if failure.get("failure_code") != "provider_transport_failure":
        return False
    return attempt < max_case_attempts


def summary_status(*, mode: str, case_results: dict[str, dict[str, Any]]) -> str:
    statuses = [result["overall_status"] for result in case_results.values()]
    if not statuses:
        return "blocked"
    if any(status == "blocked" for status in statuses) and all(status == "blocked" for status in statuses):
        return "blocked"
    if any(status == "failed" for status in statuses):
        return "completed_with_findings"
    if any(status in {"completed_with_findings", "awaiting_manual_review"} for status in statuses):
        return "completed_with_findings"
    return "completed"


def build_summary(
    *,
    status: str,
    mode: str,
    engine: str | None,
    env_report: dict[str, Any],
    mock_results: dict[str, dict[str, Any]],
    actual_results: dict[str, dict[str, Any]],
    call_log: list[dict[str, Any]],
    production_code_changed: bool,
    missing_requirements: list[str],
) -> dict[str, Any]:
    case_stats = summarize_case_maps(mock_results=mock_results, actual_results=actual_results)
    return {
        "schema_version": "ad_format_render_e2e_qa_v2",
        "created_at": datetime.now(UTC).isoformat(),
        "status": status,
        "mode": mode,
        "engine": engine,
        "mock": {key: value["overall_status"] for key, value in mock_results.items()},
        "actual": {key: value["overall_status"] for key, value in actual_results.items()},
        "mock_results": mock_results,
        "actual_results": actual_results,
        "successful_actual_calls": sum(int(value.get("actual_calls") or 0) for value in actual_results.values()),
        "actual_attempts": sum(1 for entry in call_log if entry.get("mode", mode) == "actual" and entry.get("attempt_executed")),
        "billable_call_count": sum(1 for entry in call_log if entry.get("billable_call")),
        **case_stats,
        "production_code_changed": production_code_changed,
        "missing_requirements": missing_requirements,
        "env_report": project_env_report(env_report),
        "call_log": call_log,
    }


def merge_existing_summary(output_dir: Path, summary: dict[str, Any]) -> dict[str, Any]:
    summary_path = output_dir / "summary.json"
    if not summary_path.exists():
        return summary
    existing = json.loads(summary_path.read_text(encoding="utf-8"))
    merged = dict(summary)
    merged["mock"] = dict(existing.get("mock") or {}) | dict(summary.get("mock") or {})
    merged["actual"] = dict(existing.get("actual") or {}) | dict(summary.get("actual") or {})
    merged["mock_results"] = dict(existing.get("mock_results") or {}) | dict(summary.get("mock_results") or {})
    merged["actual_results"] = dict(existing.get("actual_results") or {}) | dict(summary.get("actual_results") or {})
    merged["call_log"] = [*(existing.get("call_log") or []), *(summary.get("call_log") or [])]
    merged["successful_actual_calls"] = sum(int(value.get("actual_calls") or 0) for value in (merged["actual_results"] or {}).values())
    merged["actual_attempts"] = sum(1 for entry in merged["call_log"] if entry.get("mode") == "actual" and entry.get("attempt_executed"))
    merged["billable_call_count"] = sum(1 for entry in merged["call_log"] if entry.get("billable_call"))
    merged.update(summarize_case_maps(mock_results=merged["mock_results"], actual_results=merged["actual_results"]))
    return merged


def write_summary_artifacts(output_dir: Path, summary: dict[str, Any]) -> None:
    write_json(output_dir / "summary.json", summary)
    write_json(output_dir / "scenario_manifest.json", load_cases())
    write_json(output_dir / "call_log.json", summary["call_log"])
    write_json(output_dir / "comparison.json", {"mock": summary["mock"], "actual": summary["actual"]})
    (output_dir / "report.md").write_text(build_report_markdown(summary), encoding="utf-8")


def write_case_artifacts(*, output_dir: Path, request: dict[str, Any] | None, result: dict[str, Any] | None, qa: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    if request is not None:
        write_json(output_dir / "request.json", project_request(request))
    if result is not None:
        write_json(output_dir / "state_summary.json", project_state_summary(result))
        write_json(output_dir / "copy_spec.json", project_copy_spec(result.get("copy_spec") or {}))
        write_json(output_dir / "layout_spec.json", project_text_layout_spec(result.get("text_layout_spec") or {}))
        write_json(output_dir / "render_result.json", project_render_result(result.get("render_result") or {}))
        write_json(output_dir / "ocr_result.json", project_ocr_result(result.get("final_ocr_gate") or {}))
    write_json(output_dir / "qa_result.json", redact_recursive(qa))
    rejection_diagnostics = qa.get("rejection_diagnostics")
    if isinstance(rejection_diagnostics, dict) and rejection_diagnostics:
        write_json(output_dir / "rejection_diagnostics.json", rejection_diagnostics)
    provider_source_path = Path(str(qa.get("provider_source_path") or ""))
    if str(provider_source_path) not in {"", "."} and provider_source_path.exists():
        target = output_dir / "provider_source.png"
        if provider_source_path.resolve() != target.resolve():
            target.write_bytes(provider_source_path.read_bytes())
    final_image_path = Path(str(qa.get("final_image_path") or ""))
    if str(final_image_path) not in {"", "."} and final_image_path.exists():
        target = output_dir / "final.png"
        if final_image_path.resolve() != target.resolve():
            target.write_bytes(final_image_path.read_bytes())


def build_report_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Ad Format Render E2E QA",
        "",
        f"- Status: `{summary['status']}`",
        f"- Mode: `{summary['mode']}`",
        f"- Engine: `{summary['engine']}`",
        f"- Successful actual calls: `{summary['successful_actual_calls']}`",
        f"- Actual attempts: `{summary['actual_attempts']}`",
        f"- Billable actual calls: `{summary['billable_call_count']}`",
        "",
        "| Format | Mock | Actual |",
        "| --- | --- | --- |",
    ]
    for ad_format in EXPECTED_FORMATS:
        lines.append(f"| {ad_format} | {summary['mock'].get(ad_format, 'not_run')} | {summary['actual'].get(ad_format, 'not_run')} |")
    if summary.get("missing_requirements"):
        lines.extend(["", "## Missing requirements", *[f"- `{item}`" for item in summary["missing_requirements"]]])
    return "\n".join(lines) + "\n"


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(redact_recursive(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def load_cases() -> list[dict[str, Any]]:
    return json.loads(CASE_MANIFEST_PATH.read_text(encoding="utf-8"))


def parse_formats(value: str) -> list[str]:
    requested = [item.strip() for item in str(value).split(",") if item.strip()]
    invalid = [item for item in requested if item not in EXPECTED_FORMATS]
    if invalid:
        raise ValueError(f"unsupported_formats:{invalid}")
    return requested


def select_cases(formats: list[str]) -> list[dict[str, Any]]:
    by_format = {case["ad_format"]: case for case in load_cases()}
    return [deepcopy(by_format[ad_format]) for ad_format in formats]


def actual_opt_in_errors(*, engine: str | None, confirm_paid_calls: bool, enable_required_lane_flags: bool) -> list[str]:
    if not enable_required_lane_flags:
        return []
    if not confirm_paid_calls:
        return ["--confirm-paid-calls is required with --enable-required-lane-flags"]
    if not engine or engine not in SUPPORTED_ACTUAL_ENGINES:
        return [f"unsupported_engine_for_lane_flags:{engine}"]
    return []


def enable_actual_lane_flags(*, engine: str | None, confirmed_paid_calls: bool) -> dict[str, str]:
    if not confirmed_paid_calls:
        raise LaneOptInError("confirm_paid_calls_required")
    if not engine or engine not in SUPPORTED_ACTUAL_ENGINES:
        raise LaneOptInError(f"unsupported_engine:{engine}")
    return dict(SUPPORTED_ACTUAL_ENGINES[engine]["lane_flags"])


@contextmanager
def temporary_env_updates(updates: dict[str, str]):
    previous: dict[str, str | None] = {key: os.getenv(key) for key in updates}
    try:
        for key, value in updates.items():
            os.environ[key] = value
        yield
    finally:
        for key, old_value in previous.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value


def actual_missing_requirements(engine: str | None) -> list[str]:
    missing = [name for name in BASE_ACTUAL_ENV_REQUIREMENTS if not bool(os.getenv(name))]
    if not engine:
        missing.append("--engine")
        return missing
    engine_config = SUPPORTED_ACTUAL_ENGINES.get(engine)
    if not engine_config:
        missing.append(f"unsupported_engine:{engine}")
        return missing
    for env_name in engine_config["lane_flags"]:
        if os.getenv(env_name, "").strip().lower() not in {"1", "true", "yes", "on"}:
            missing.append(env_name)
    return missing


def load_review_map(review_file: str | None) -> dict[str, dict[str, Any]]:
    if not review_file:
        return {}
    path = Path(review_file)
    if not path.exists():
        raise FileNotFoundError(f"review_file_not_found:{review_file}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("review_file_must_be_object")
    return {str(key): value for key, value in payload.items() if isinstance(value, dict)}


def resolve_review_payload(review_map: dict[str, dict[str, Any]], case: dict[str, Any]) -> dict[str, Any] | None:
    return review_map.get(str(case["case_id"])) or review_map.get(str(case["ad_format"]))


def read_image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def validate_trace_boxes(*, traces: list[dict[str, Any]], width: int, height: int) -> None:
    boxes: list[tuple[int, int, int, int]] = []
    for trace in traces:
        x1, y1, x2, y2 = [int(value) for value in trace.get("rendered_bbox_px") or (0, 0, 0, 0)]
        assert 0 <= x1 < x2 <= width, "layout_block_failure"
        assert 0 <= y1 < y2 <= height, "layout_block_failure"
        boxes.append((x1, y1, x2, y2))
    for index, box in enumerate(boxes):
        for other in boxes[index + 1 :]:
            if intersects(box, other):
                raise AssertionError("layout_block_failure")


def intersects(left: tuple[int, int, int, int], right: tuple[int, int, int, int]) -> bool:
    return left[0] < right[2] and right[0] < left[2] and left[1] < right[3] and right[1] < left[3]


def actual_provider_name(t2i_result: dict[str, Any]) -> str:
    metadata = t2i_result.get("metadata") or {}
    return str(metadata.get("provider") or metadata.get("modal_provider") or t2i_result.get("engine") or "unknown")


def is_native_typography_result(result: dict[str, Any]) -> bool:
    t2i_metadata = (result.get("t2i_result") or {}).get("metadata") or {}
    render_metadata = (result.get("render_result") or {}).get("metadata") or {}
    return bool(t2i_metadata.get("native_typography")) or str(render_metadata.get("source")) == "native_typography"


def evaluate_visible_text_contract(
    *,
    case: dict[str, Any],
    result: dict[str, Any],
    traces: list[dict[str, Any]],
    width: int,
    height: int,
    native_layout: bool,
    visible_range: list[int],
) -> tuple[str, str | None, int, dict[str, Any]]:
    if native_layout:
        minimum = int(visible_range[0])
        maximum = int(visible_range[1])
        package = result.get("native_creative_prompt_package") or {}
        exact_allowed_texts = [text for text in (package.get("exact_allowed_texts") or []) if clean_optional_text(text)]
        block_count = len(exact_allowed_texts)
        contract = {
            "lane": "native_typography",
            "exact_allowed_text_count": block_count,
            "max_text_blocks": package.get("approved_copy", {}).get("max_text_blocks"),
            "format_plan_allowed_text_count": None,
        }
        matching_allowed = matching_extended_allowed_texts(result)
        if matching_allowed is not None:
            contract["format_plan_allowed_text_count"] = len(matching_allowed)
            if exact_allowed_texts != matching_allowed:
                return "failed", "native_allowed_texts_mismatch", block_count, contract
        if not (minimum <= block_count <= maximum):
            return "failed", f"visible_text_count_out_of_range:{block_count}", block_count, contract
        return "passed", None, block_count, contract

    overlay_range = case.get("expected_text_block_range") or visible_range
    minimum = int(overlay_range[0])
    maximum = int(overlay_range[1])
    block_count = len(traces)
    if not (minimum <= block_count <= maximum):
        return "failed", f"text_block_count_out_of_range:{block_count}", block_count, {"lane": "overlay", "trace_count": block_count}
    try:
        validate_trace_boxes(traces=traces, width=width, height=height)
    except AssertionError as exc:
        return "failed", str(exc), block_count, {"lane": "overlay", "trace_count": block_count}
    return "passed", None, block_count, {"lane": "overlay", "trace_count": block_count}


def matching_extended_allowed_texts(result: dict[str, Any]) -> list[str] | None:
    for field in ("flyer_approved_copy_plan", "flyer_promotional_approved_copy_plan", "product_detail_approved_feature_plan"):
        payload = result.get(field) or {}
        allowed = payload.get("allowed_texts")
        if isinstance(allowed, list) and allowed:
            return [str(text) for text in allowed]
    return None


def is_transport_error_text(text: str) -> bool:
    normalized = str(text or "").lower()
    return any(pattern in normalized for pattern in TRANSPORT_ERROR_PATTERNS)


def clean_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def project_request(request: dict[str, Any]) -> dict[str, Any]:
    projected = {
        "job_id": request.get("job_id"),
        "thread_id": request.get("thread_id"),
        "copy_generation_mode": request.get("copy_generation_mode"),
        "user_custom_headline": request.get("user_custom_headline"),
        "user_custom_subcopy": request.get("user_custom_subcopy"),
        "selected_channel_id": request.get("selected_channel_id"),
        "selected_ad_format": request.get("selected_ad_format"),
        "engine": request.get("engine"),
        "context": request.get("context"),
    }
    return redact_recursive(projected)


def project_state_summary(result: dict[str, Any]) -> dict[str, Any]:
    return redact_recursive(
        {
            "status": result.get("status"),
            "final_image_path": result.get("final_image_path"),
            "native_generation_status": result.get("native_generation_status"),
            "approved_native_copy_brief": project_approved_native_copy_brief(result.get("approved_native_copy_brief") or {}),
            "format_approved_plan_bundle": project_format_approved_plan_bundle(result.get("format_approved_plan_bundle") or {}),
            "native_creative_preflight_review": project_preflight_review(result.get("native_creative_preflight_review") or {}),
            "native_generation_review": project_generation_review(result.get("native_generation_review") or {}),
            "error_info": result.get("error_info"),
            "error_message": result.get("error_message"),
        }
    )


def build_rejection_diagnostics(result: dict[str, Any]) -> dict[str, Any]:
    bundle = result.get("format_approved_plan_bundle") or {}
    brief = result.get("approved_native_copy_brief") or {}
    preflight = result.get("native_creative_preflight_review") or {}
    generation_review = result.get("native_generation_review") or {}
    reject_stage = classify_reject_stage(result)
    return redact_recursive(
        {
            "status": result.get("status"),
            "selected_ad_format": result.get("selected_ad_format"),
            "native_generation_status": result.get("native_generation_status"),
            "reject_stage": reject_stage,
            "approved_native_copy_brief": {
                "compliance_status": brief.get("compliance_status"),
                "rejection_reasons": brief.get("rejection_reasons"),
                "copy_source_mode": brief.get("copy_source_mode"),
                "allowed_text_count": len(brief.get("allowed_texts") or []),
            },
            "format_approved_plan_bundle": {
                "decision": bundle.get("decision"),
                "reason_codes": bundle.get("reason_codes") or [],
                "provider_metadata": {
                    "provider": (bundle.get("provider_metadata") or {}).get("provider"),
                    "model": (bundle.get("provider_metadata") or {}).get("model"),
                    "provider_profile": (bundle.get("provider_metadata") or {}).get("provider_profile"),
                    "fallback_used": (bundle.get("provider_metadata") or {}).get("fallback_used"),
                    "error": clean_optional_text((bundle.get("provider_metadata") or {}).get("error")),
                },
            },
            "extended_plan_presence": {
                "flyer_approved_copy_plan": bool(result.get("flyer_approved_copy_plan")),
                "flyer_promotional_approved_copy_plan": bool(result.get("flyer_promotional_approved_copy_plan")),
                "product_detail_approved_feature_plan": bool(result.get("product_detail_approved_feature_plan")),
            },
            "native_creative_preflight_review": {
                "decision": preflight.get("decision"),
                "failure_reasons": preflight.get("failure_reasons") or [],
            },
            "native_generation_review": {
                "decision": generation_review.get("decision"),
                "failure_reasons": generation_review.get("failure_reasons") or [],
            },
            "error_info": {
                "error_code": clean_optional_text((result.get("error_info") or {}).get("error_code")),
                "error_type": clean_optional_text((result.get("error_info") or {}).get("error_type")),
                "message": clean_optional_text((result.get("error_info") or {}).get("message")) or clean_optional_text(result.get("error_message")),
            },
        }
    )


def classify_reject_stage(result: dict[str, Any]) -> str:
    brief = result.get("approved_native_copy_brief") or {}
    if brief.get("compliance_status") in {"rejected", "manual_review"}:
        return "approved_copy_rejected"
    bundle = result.get("format_approved_plan_bundle")
    ad_format = clean_optional_text(result.get("selected_ad_format")) or ""
    if ad_format in {"flyer", "product_detail"}:
        if not bundle:
            return "format_plan_missing"
        decision = clean_optional_text(bundle.get("decision")) or ""
        reason_codes = {str(code) for code in (bundle.get("reason_codes") or [])}
        if decision == "manual_review":
            return "format_plan_manual_review"
        if "provider_payload_schema_invalid" in reason_codes:
            return "format_plan_schema_invalid"
        if decision == "rejected":
            return "format_plan_rejected"
    preflight = result.get("native_creative_preflight_review") or {}
    if preflight.get("decision") in {"rejected", "manual_review", "revision_required"}:
        return "preflight_rejected"
    generation_review = result.get("native_generation_review") or {}
    if generation_review.get("decision") in {"rejected", "manual_review"}:
        return "post_generation_rejected"
    return "provider_generation_failure"


def project_ad_format_spec(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "ad_format": spec.get("ad_format"),
        "aspect_ratio": spec.get("aspect_ratio"),
        "platform": spec.get("platform"),
        "width": spec.get("width"),
        "height": spec.get("height"),
        "information_density": spec.get("information_density"),
        "visual_priority": spec.get("visual_priority"),
    }


def project_image_prompt_spec(spec: dict[str, Any]) -> dict[str, Any]:
    metadata = spec.get("metadata") or {}
    return redact_recursive(
        {
            "selected_channel_id": metadata.get("selected_channel_id"),
            "render_text_in_image": metadata.get("render_text_in_image"),
            "visual_template_id": metadata.get("visual_template_id"),
            "scene_plan": {
                "ad_format": ((metadata.get("scene_plan") or {}).get("ad_format")),
                "expected_overlay_position": ((metadata.get("scene_plan") or {}).get("expected_overlay_position")),
            },
        }
    )


def project_copy_spec(copy_spec: dict[str, Any]) -> dict[str, Any]:
    metadata = copy_spec.get("metadata") or {}
    return {
        "copy_mode": copy_spec.get("copy_mode"),
        "items": [{"role": item.get("role"), "text": item.get("text")} for item in (copy_spec.get("items") or [])],
        "cta_visibility": (((metadata.get("copy_visual_intent") or {}).get("cta_visibility"))),
        "cta_style": (((metadata.get("copy_visual_intent") or {}).get("cta_style"))),
    }


def project_approved_native_copy_brief(brief: dict[str, Any]) -> dict[str, Any]:
    return {
        "compliance_status": brief.get("compliance_status"),
        "rejection_reasons": brief.get("rejection_reasons") or [],
        "copy_source_mode": brief.get("copy_source_mode"),
        "allowed_text_count": len(brief.get("allowed_texts") or []),
    }


def project_format_approved_plan_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    metadata = bundle.get("provider_metadata") or {}
    return {
        "decision": bundle.get("decision"),
        "reason_codes": bundle.get("reason_codes") or [],
        "provider_metadata": {
            "provider": metadata.get("provider"),
            "model": metadata.get("model"),
            "provider_profile": metadata.get("provider_profile"),
            "fallback_used": metadata.get("fallback_used"),
            "error": clean_optional_text(metadata.get("error")),
        },
    }


def project_preflight_review(review: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision": review.get("decision"),
        "failure_reasons": review.get("failure_reasons") or [],
    }


def project_generation_review(review: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision": review.get("decision"),
        "failure_reasons": review.get("failure_reasons") or [],
    }


def project_text_layout_spec(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "template": spec.get("template"),
        "canvas_width": spec.get("canvas_width"),
        "canvas_height": spec.get("canvas_height"),
        "slot_count": len(spec.get("slots") or []),
        "slots": [
            {
                "slot_id": slot.get("slot_id"),
                "role": slot.get("role"),
                "bbox": slot.get("bbox"),
                "rendered_text": slot.get("rendered_text"),
                "max_lines": slot.get("max_lines"),
            }
            for slot in (spec.get("slots") or [])
        ],
    }


def project_t2i_request(request: dict[str, Any]) -> dict[str, Any]:
    metadata = request.get("metadata") or {}
    return redact_recursive(
        {
            "width": request.get("width"),
            "height": request.get("height"),
            "num_images": request.get("num_images"),
            "metadata": {
                "job_id": metadata.get("job_id"),
                "engine": metadata.get("engine"),
                "effective_engine": metadata.get("effective_engine"),
                "ad_format_spec": project_ad_format_spec(metadata.get("ad_format_spec") or {}),
                "must_not_include_text": metadata.get("must_not_include_text"),
                "render_text_in_image": metadata.get("render_text_in_image"),
            },
        }
    )


def project_t2i_result(result: dict[str, Any]) -> dict[str, Any]:
    metadata = result.get("metadata") or {}
    return redact_recursive(
        {
            "engine": result.get("engine"),
            "width": result.get("width"),
            "height": result.get("height"),
            "image_paths": [str(path) for path in (result.get("image_paths") or [])[:1]],
            "metadata": {
                "provider": metadata.get("provider"),
                "effective_engine": metadata.get("effective_engine"),
                "execution_backend": metadata.get("execution_backend"),
                "modal_provider": metadata.get("modal_provider"),
                "api_call": metadata.get("api_call"),
                "provider_image_path": metadata.get("provider_image_path"),
                "provider_width": metadata.get("provider_width"),
                "provider_height": metadata.get("provider_height"),
                "output_width": metadata.get("output_width"),
                "output_height": metadata.get("output_height"),
                "normalization_applied": metadata.get("normalization_applied"),
                "normalization_mode": metadata.get("normalization_mode"),
                "crop_box": metadata.get("crop_box"),
                "image_call_count": metadata.get("image_call_count"),
                "edit_call_count": metadata.get("edit_call_count"),
                "retry_call_count": metadata.get("retry_call_count"),
            },
        }
    )


def project_render_result(result: dict[str, Any]) -> dict[str, Any]:
    metadata = result.get("metadata") or {}
    return {
        "final_image_path": result.get("final_image_path"),
        "rendered_slot_count": result.get("rendered_slot_count"),
        "skipped_slot_count": result.get("skipped_slot_count"),
        "warnings": result.get("warnings"),
        "metadata": {
            "has_text_overlay": metadata.get("has_text_overlay"),
            "overflow_detected": metadata.get("overflow_detected"),
            "source_node": metadata.get("source_node"),
            "typography_render_traces": [
                {
                    "role": trace.get("role"),
                    "font_id": trace.get("font_id"),
                    "effective_font_size_px": trace.get("effective_font_size_px"),
                    "rendered_lines": trace.get("rendered_lines"),
                    "rendered_bbox_px": trace.get("rendered_bbox_px"),
                    "overlay_treatment": trace.get("overlay_treatment"),
                }
                for trace in (metadata.get("typography_render_traces") or [])
            ],
        },
    }


def project_ocr_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": result.get("provider"),
        "status": result.get("status"),
        "decision": result.get("decision"),
        "confidence": result.get("confidence"),
        "detected_spans": [{"text": span.get("text"), "confidence": span.get("confidence")} for span in (result.get("detected_spans") or [])],
        "expected_matches": [
            {"expected": match.get("expected"), "status": match.get("status"), "similarity": match.get("similarity")}
            for match in (result.get("expected_matches") or [])
        ],
        "unexpected_text": [{"text": span.get("text"), "confidence": span.get("confidence")} for span in (result.get("unexpected_text") or [])],
    }


def project_env_report(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "env_file": report.get("env_file"),
        "env_file_found": report.get("env_file_found"),
        "loaded_keys": report.get("loaded_keys") or [],
        "skipped_existing_keys": report.get("skipped_existing_keys") or [],
    }


def redact_recursive(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(pattern in lowered for pattern in REDACTED_KEY_PATTERNS):
                continue
            if lowered == "image_paths" and isinstance(item, list):
                redacted[key] = [redact_signed_url(str(path)) for path in item]
                continue
            redacted[key] = redact_recursive(item)
        return redacted
    if isinstance(value, list):
        return [redact_recursive(item) for item in value]
    if isinstance(value, str):
        return redact_signed_url(value)
    return value


def redact_signed_url(value: str) -> str:
    if "?" in value and ("http://" in value or "https://" in value):
        return value.split("?", 1)[0]
    return value


@contextmanager
def mocked_ocr_gate():
    def fake_run_ocr_gate(*, request, **_kwargs):
        spans = [
            OCRSpan(
                text=text,
                normalized_text=normalize_ocr_text(text),
                confidence=0.99,
                source="stub",
            )
            for text in request.expected_text
        ]
        matches = [
            OCRTextMatch(expected=text, matched_span=span, similarity=1.0, status="matched")
            for text, span in zip(request.expected_text, spans)
        ]
        return OCRValidationResult(
            stage=request.stage,
            provider="qa_stub",
            status="pass",
            decision="pass",
            detected_spans=spans,
            expected_matches=matches,
            unexpected_text=[],
            confidence=0.99,
            retry_feedback=[],
            revision_action="none",
            latency_ms=1,
        )

    with patch("orchestrator.app.llm.nodes.ocr_gate.run_ocr_gate", fake_run_ocr_gate):
        yield


if __name__ == "__main__":
    raise SystemExit(main())
