from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from PIL import Image

from scripts import run_ad_format_render_e2e_qa as runner


def _write_image(path: Path, width: int, height: int) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (width, height), "#ffffff").save(path)
    return str(path)


def _fake_done_result(
    tmp_path: Path,
    case: dict[str, object],
    *,
    provider: str = "openai",
    engine: str = "gpt_image_2",
    selected_channel_id: str | None = None,
    cta_visibility: str | None = None,
    expected_matches_status: str = "matched",
    unexpected_text: list[dict[str, object]] | None = None,
    native_typography: bool = False,
) -> dict[str, object]:
    width = int(case["expected_width"])
    height = int(case["expected_height"])
    final_path = _write_image(tmp_path / f"{case['ad_format']}_final.png", width, height)
    t2i_path = _write_image(tmp_path / f"{case['ad_format']}_t2i.png", width, height)
    headline = f"{case['ad_format']} headline"
    subheadline = f"{case['ad_format']} subheadline"
    requested_ad_format = str(case["ad_format"])
    actual_channel = selected_channel_id or str(case["selected_channel_id"])
    expected_matches = [
        {"expected": headline, "status": expected_matches_status, "similarity": 1.0},
        {"expected": subheadline, "status": "matched", "similarity": 1.0},
    ]
    detected_spans = [
        {"text": headline, "confidence": 0.99},
        {"text": subheadline, "confidence": 0.98},
    ]
    if expected_matches_status != "matched":
        detected_spans = [{"text": subheadline, "confidence": 0.98}]
    render_metadata = {
        "has_text_overlay": True,
        "overflow_detected": False,
        "source_node": "text_renderer",
        "typography_render_traces": [
            {
                "role": "headline",
                "font_id": "pretendard_bold",
                "effective_font_size_px": 48,
                "rendered_lines": [headline],
                "rendered_bbox_px": [100, 100, 500, 220],
                "overlay_treatment": "plain",
            },
            {
                "role": "subheadline",
                "font_id": "pretendard_regular",
                "effective_font_size_px": 28,
                "rendered_lines": [subheadline],
                "rendered_bbox_px": [100, 260, 580, 340],
                "overlay_treatment": "plain",
            },
        ],
    }
    if native_typography:
        render_metadata = {
            "has_text_overlay": False,
            "overflow_detected": False,
            "source": "native_typography",
            "typography_render_traces": [],
        }
    return {
        "status": "done",
        "selected_channel_id": actual_channel,
        "current_brief": {
            "selected_channel_id": actual_channel,
            "requested_ad_format": requested_ad_format,
        },
        "context": {"extra": {"selected_channel_id": actual_channel}},
        "ad_format_spec": {
            "ad_format": requested_ad_format,
            "aspect_ratio": case["expected_aspect_ratio"],
            "width": width,
            "height": height,
            "platform": "web",
            "information_density": "medium",
            "visual_priority": "conversion",
        },
        "image_prompt_spec": {
            "metadata": {
                "selected_channel_id": actual_channel,
                "render_text_in_image": False,
                "visual_template_id": "qa-template",
                "scene_plan": {
                    "ad_format": requested_ad_format,
                    "expected_overlay_position": "left",
                },
            }
        },
        "copy_spec": {
            "copy_mode": "standard",
            "items": [
                {"role": "headline", "text": headline},
                {"role": "subheadline", "text": subheadline},
            ],
            "metadata": {
                "copy_visual_intent": {
                    "cta_visibility": cta_visibility or case["expected_cta_visibility"],
                    "cta_style": "none",
                }
            },
        },
        "text_layout_spec": {
            "template": "dynamic_side_split",
            "canvas_width": 1024,
            "canvas_height": 1024,
            "slots": [
                {
                    "slot_id": "headline",
                    "role": "headline",
                    "bbox": {"x": 0.1, "y": 0.1, "w": 0.3, "h": 0.15},
                    "rendered_text": headline,
                    "max_lines": 2,
                },
                {
                    "slot_id": "subheadline",
                    "role": "subheadline",
                    "bbox": {"x": 0.1, "y": 0.3, "w": 0.35, "h": 0.12},
                    "rendered_text": subheadline,
                    "max_lines": 2,
                },
            ],
        },
        "t2i_request": {
            "width": width,
            "height": height,
            "num_images": 1,
            "metadata": {
                "job_id": f"qa-{case['case_id']}",
                "engine": engine,
                "effective_engine": engine,
                "ad_format_spec": {
                    "ad_format": requested_ad_format,
                    "aspect_ratio": case["expected_aspect_ratio"],
                    "width": width,
                    "height": height,
                },
                "must_not_include_text": True,
                "render_text_in_image": False,
            },
        },
        "t2i_result": {
            "engine": engine,
            "width": width,
            "height": height,
            "image_paths": [t2i_path],
            "metadata": {
                "provider": provider,
                "effective_engine": engine,
                "execution_backend": "openai",
                "modal_provider": provider,
                "native_typography": native_typography,
                "provider_image_path": t2i_path,
                "provider_width": width,
                "provider_height": height,
                "output_width": width,
                "output_height": height,
                "image_call_count": 1,
                "edit_call_count": 0,
                "retry_call_count": 0,
                "api_call": {
                    "signed_url": "https://example.com/output.png?sig=secret",
                    "raw_body": "omit",
                    "bucket": "secret-bucket",
                    "object_key": "secret-key",
                },
            },
        },
        "render_result": {
            "final_image_path": final_path,
            "rendered_slot_count": 2,
            "skipped_slot_count": 0,
            "warnings": [],
            "metadata": render_metadata,
        },
        "final_ocr_gate": {
            "provider": "qa_stub",
            "status": "pass" if expected_matches_status == "matched" else "fail",
            "decision": "pass" if expected_matches_status == "matched" else "fail",
            "confidence": 0.99,
            "detected_spans": detected_spans,
            "expected_matches": expected_matches,
            "unexpected_text": unexpected_text or [],
        },
        "native_creative_prompt_package": {
            "exact_allowed_texts": [headline, subheadline],
            "approved_copy": {"max_text_blocks": 2},
        },
        "final_image_path": final_path,
    }


def _fake_request(case: dict[str, object], *, engine: str | None = None) -> dict[str, object]:
    request = {
        "job_id": f"qa-{case['case_id']}",
        "thread_id": f"qa-{case['case_id']}",
        "copy_generation_mode": case["copy_generation_mode"],
        "selected_channel_id": case["selected_channel_id"],
        "selected_ad_format": case["ad_format"],
        "context": {"extra": {"selected_channel_id": case["selected_channel_id"]}},
    }
    if engine:
        request["engine"] = engine
    return request


def test_self_check_reports_expected_formats():
    result = runner.run_self_check(runner.parse_args(["--self-check"]))

    assert result["status"] == "ok"
    assert result["formats"] == ["banner", "flyer", "product_detail"]


def test_request_builder_passes_custom_copy_fields():
    case = runner.select_cases(["flyer"])[0]

    request = runner.build_graph_request(case, engine="gpt_image_2", run_token="abcd1234")
    graph_input = runner.build_graph_input(request, engine="gpt_image_2")

    assert request["user_custom_headline"] == case["user_custom_headline"]
    assert request["user_custom_subcopy"] == case["user_custom_subcopy"]
    assert graph_input["user_custom_headline"] == case["user_custom_headline"]
    assert graph_input["user_custom_subcopy"] == case["user_custom_subcopy"]


def test_mock_suite_writes_summary_and_separated_artifacts(tmp_path):
    cases = runner.select_cases(["banner", "flyer", "product_detail"])

    summary = runner.run_mock_suite(cases=cases, output_dir=tmp_path, env_report={})
    runner.write_summary_artifacts(tmp_path, summary)

    assert summary["status"] == "completed"
    assert summary["mock"] == {"banner": "passed", "flyer": "passed", "product_detail": "passed"}
    assert (tmp_path / "summary.json").exists()
    assert (tmp_path / "mock" / "banner" / "final.png").exists()
    assert (tmp_path / "mock" / "flyer" / "qa_result.json").exists()
    assert (tmp_path / "mock" / "product_detail" / "render_result.json").exists()
    payload = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert payload["successful_actual_calls"] == 0


def test_lane_flag_enable_requires_confirm():
    errors = runner.actual_opt_in_errors(
        engine="gpt_image_2",
        confirm_paid_calls=False,
        enable_required_lane_flags=True,
    )

    assert errors == ["--confirm-paid-calls is required with --enable-required-lane-flags"]


def test_enable_required_lane_flags_rejects_unsupported_engine():
    with pytest.raises(runner.LaneOptInError):
        runner.enable_actual_lane_flags(engine="unknown_engine", confirmed_paid_calls=True)


def test_actual_suite_blocks_without_required_env(tmp_path, monkeypatch):
    for name in [
        "OPENAI_API_KEY",
        "EASYADS_ENABLE_LLM_CALLS",
        "EASYADS_ENABLE_EXTERNAL_T2I",
        "EASYADS_VLM_ACTUAL",
        "EASYADS_FINAL_COMPOSITE_ACTUAL",
        "EASYADS_ENABLE_GPT_IMAGE_2",
    ]:
        monkeypatch.delenv(name, raising=False)

    cases = runner.select_cases(["banner", "flyer", "product_detail"])
    summary = runner.run_actual_suite(
        cases=cases,
        output_dir=tmp_path,
        engine="gpt_image_2",
        max_successful_calls=3,
        max_actual_attempts=6,
        allow_transport_retry=False,
        confirm_paid_calls=False,
        enable_required_lane_flags=False,
        review_map={},
        env_report={},
    )

    assert summary["status"] == "blocked"
    assert summary["actual"] == {"banner": "blocked", "flyer": "blocked", "product_detail": "blocked"}
    assert summary["actual_calls"] == 0 if "actual_calls" in summary else True
    assert summary["actual_attempts"] == 0
    assert "OPENAI_API_KEY" in summary["missing_requirements"]


def test_actual_provider_mock_is_blocked(tmp_path):
    case = runner.select_cases(["banner"])[0]
    qa = runner.evaluate_case(
        case=case,
        request=_fake_request(case, engine="gpt_image_2"),
        result=_fake_done_result(tmp_path, case, provider="mock"),
        mode="actual",
        review_payload=None,
    )

    assert qa["overall_status"] == "blocked"
    assert qa["failure_code"] == "actual_engine_did_not_execute"
    assert qa["billable_call_count"] == 0


def test_actual_provider_real_counts_billable_call(tmp_path):
    case = runner.select_cases(["banner"])[0]
    review_payload = {field: "pass" for field in runner.REQUIRED_VISUAL_REVIEW_FIELDS}
    qa = runner.evaluate_case(
        case=case,
        request=_fake_request(case, engine="gpt_image_2"),
        result=_fake_done_result(tmp_path, case, provider="openai"),
        mode="actual",
        review_payload=review_payload,
    )

    assert qa["overall_status"] == "passed"
    assert qa["actual_calls"] == 1
    assert qa["actual_provider"] == "openai"
    assert qa["actual_engine"] == "gpt_image_2"


def test_three_format_actual_success_summary(tmp_path, monkeypatch):
    for name in runner.SUPPORTED_ACTUAL_ENGINES["gpt_image_2"]["lane_flags"]:
        monkeypatch.setenv(name, "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_invoke_graph_case(*, case, mode, engine):
        return _fake_request(case, engine=engine), _fake_done_result(tmp_path, case, provider="openai", engine=engine)

    monkeypatch.setattr(runner, "invoke_graph_case", fake_invoke_graph_case)
    cases = runner.select_cases(["banner", "flyer", "product_detail"])
    review_map = {case["case_id"]: {field: "pass" for field in runner.REQUIRED_VISUAL_REVIEW_FIELDS} for case in cases}

    summary = runner.run_actual_suite(
        cases=cases,
        output_dir=tmp_path,
        engine="gpt_image_2",
        max_successful_calls=3,
        max_actual_attempts=6,
        allow_transport_retry=False,
        confirm_paid_calls=True,
        enable_required_lane_flags=False,
        review_map=review_map,
        env_report={},
    )

    assert summary["status"] == "completed"
    assert summary["actual"] == {"banner": "passed", "flyer": "passed", "product_detail": "passed"}
    assert summary["successful_actual_calls"] == 3
    assert summary["actual_attempts"] == 3
    assert summary["billable_call_count"] == 3


def test_transport_retry_retries_once_for_transport_failure(tmp_path, monkeypatch):
    for name in runner.SUPPORTED_ACTUAL_ENGINES["gpt_image_2"]["lane_flags"]:
        monkeypatch.setenv(name, "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    case = runner.select_cases(["banner"])[0]
    attempts = {"count": 0}

    def fake_invoke_graph_case(*, case, mode, engine):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise TimeoutError("connection timeout")
        return _fake_request(case, engine=engine), _fake_done_result(tmp_path, case, provider="openai", engine=engine)

    monkeypatch.setattr(runner, "invoke_graph_case", fake_invoke_graph_case)
    review_map = {case["case_id"]: {field: "pass" for field in runner.REQUIRED_VISUAL_REVIEW_FIELDS}}

    summary = runner.run_actual_suite(
        cases=[case],
        output_dir=tmp_path,
        engine="gpt_image_2",
        max_successful_calls=1,
        max_actual_attempts=2,
        allow_transport_retry=True,
        confirm_paid_calls=True,
        enable_required_lane_flags=False,
        review_map=review_map,
        env_report={},
    )

    assert attempts["count"] == 2
    assert summary["actual_attempts"] == 2
    assert summary["successful_actual_calls"] == 1


def test_transport_retry_does_not_retry_non_transport_failure(tmp_path, monkeypatch):
    for name in runner.SUPPORTED_ACTUAL_ENGINES["gpt_image_2"]["lane_flags"]:
        monkeypatch.setenv(name, "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    case = runner.select_cases(["banner"])[0]
    attempts = {"count": 0}

    def fake_invoke_graph_case(*, case, mode, engine):
        attempts["count"] += 1
        raise ValueError("layout contract broken")

    monkeypatch.setattr(runner, "invoke_graph_case", fake_invoke_graph_case)

    summary = runner.run_actual_suite(
        cases=[case],
        output_dir=tmp_path,
        engine="gpt_image_2",
        max_successful_calls=1,
        max_actual_attempts=2,
        allow_transport_retry=True,
        confirm_paid_calls=True,
        enable_required_lane_flags=False,
        review_map={},
        env_report={},
    )

    assert attempts["count"] == 1
    assert summary["actual_attempts"] == 1
    assert summary["actual"]["banner"] == "failed"


def test_max_actual_attempts_caps_execution(tmp_path, monkeypatch):
    for name in runner.SUPPORTED_ACTUAL_ENGINES["gpt_image_2"]["lane_flags"]:
        monkeypatch.setenv(name, "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    call_order: list[str] = []

    def fake_run_case_with_retry(**kwargs):
        case = kwargs["case"]
        call_order.append(case["ad_format"])
        return runner.blocked_case_result(case, blocker="synthetic"), [
            {
                "mode": "actual",
                "format": case["ad_format"],
                "attempt": 1,
                "attempt_executed": True,
                "engine": "gpt_image_2",
                "started_at": "t1",
                "ended_at": "t2",
                "status": "failed",
                "error_type": "TimeoutError",
                "billable_call": False,
                "retry_reason": None,
            }
        ]

    monkeypatch.setattr(runner, "run_case_with_retry", fake_run_case_with_retry)
    cases = runner.select_cases(["banner", "flyer", "product_detail"])

    summary = runner.run_actual_suite(
        cases=cases,
        output_dir=tmp_path,
        engine="gpt_image_2",
        max_successful_calls=3,
        max_actual_attempts=1,
        allow_transport_retry=False,
        confirm_paid_calls=True,
        enable_required_lane_flags=False,
        review_map={},
        env_report={},
    )

    assert call_order == ["banner"]
    assert summary["actual_attempts"] == 1
    assert summary["actual"]["flyer"] == "blocked"
    assert summary["actual"]["product_detail"] == "blocked"


def test_manifest_preset_mismatch_fails_self_check(monkeypatch):
    cases = deepcopy(runner.load_cases())
    cases[0]["expected_aspect_ratio"] = "1:1"
    monkeypatch.setattr(runner, "load_cases", lambda: cases)

    result = runner.run_self_check(runner.parse_args(["--self-check"]))

    assert result["status"] == "failed"
    assert "preset_aspect_ratio_mismatch:banner" in result["errors"]


def test_ocr_expected_text_missing_fails(tmp_path):
    case = runner.select_cases(["banner"])[0]
    qa = runner.evaluate_case(
        case=case,
        request=_fake_request(case, engine="gpt_image_2"),
        result=_fake_done_result(tmp_path, case, expected_matches_status="missing"),
        mode="actual",
        review_payload={field: "pass" for field in runner.REQUIRED_VISUAL_REVIEW_FIELDS},
    )

    assert qa["ocr_status"] == "failed"
    assert qa["failure_code"] == "ocr_expected_text_missing"
    assert qa["missing_expected_text"]


def test_actual_cta_visibility_uses_actual_copy_spec(tmp_path):
    case = runner.select_cases(["banner"])[0]
    qa = runner.evaluate_case(
        case=case,
        request=_fake_request(case, engine="gpt_image_2"),
        result=_fake_done_result(tmp_path, case, cta_visibility="required"),
        mode="actual",
        review_payload={field: "pass" for field in runner.REQUIRED_VISUAL_REVIEW_FIELDS},
    )

    assert qa["cta_status"] == "failed"
    assert qa["failure_code"] == "cta_contract_failure"


def test_native_typography_uses_prompt_package_visible_text_contract(tmp_path):
    case = runner.select_cases(["banner"])[0]
    qa = runner.evaluate_case(
        case=case,
        request=_fake_request(case, engine="gpt_image_2"),
        result=_fake_done_result(tmp_path, case, native_typography=True),
        mode="actual",
        review_payload={field: "pass" for field in runner.REQUIRED_VISUAL_REVIEW_FIELDS},
    )

    assert qa["layout_status"] == "passed"
    assert qa["native_typography"] is True
    assert qa["text_block_count"] == 2
    assert qa["native_contract"]["lane"] == "native_typography"


def test_native_typography_without_ocr_result_still_passes_ocr_contract(tmp_path):
    case = runner.select_cases(["banner"])[0]
    qa = runner.evaluate_case(
        case=case,
        request=_fake_request(case, engine="gpt_image_2"),
        result=_fake_done_result(tmp_path, case, native_typography=True),
        mode="actual",
        review_payload={field: "pass" for field in runner.REQUIRED_VISUAL_REVIEW_FIELDS},
    )

    assert qa["ocr_status"] == "passed"


def test_failed_result_writes_rejection_diagnostics(tmp_path):
    case = runner.select_cases(["flyer"])[0]
    qa = runner.failure_from_result(
        case=case,
        mode="actual",
        engine="gpt_image_2",
        result={
            "status": "failed",
            "selected_ad_format": "flyer",
            "native_generation_status": "rejected",
            "approved_native_copy_brief": {
                "compliance_status": "approved",
                "copy_source_mode": "user_exact",
                "allowed_texts": ["라떼 카페 라떼", "부드럽고 은은한 단맛의 카페 라떼"],
            },
            "format_approved_plan_bundle": {
                "decision": "rejected",
                "reason_codes": ["provider_error"],
                "provider_metadata": {"provider": "openai", "model": "gpt-5.4", "error": "missing credentials"},
            },
            "error_info": {"error_code": "graph_execution_failed", "message": "rejected"},
            "error_message": "rejected",
        },
    )

    runner.write_case_artifacts(output_dir=tmp_path / "actual" / "flyer", request=None, result=None, qa=qa)
    payload = json.loads((tmp_path / "actual" / "flyer" / "rejection_diagnostics.json").read_text(encoding="utf-8"))

    assert qa["reject_stage"] == "format_plan_rejected"
    assert payload["format_approved_plan_bundle"]["decision"] == "rejected"
    assert payload["format_approved_plan_bundle"]["provider_metadata"]["error"] == "missing credentials"


def test_summary_merge_preserves_mock_and_actual_counts(tmp_path):
    mock_summary = runner.build_summary(
        status="completed",
        mode="mock",
        engine="mock",
        env_report={},
        mock_results={"banner": {"overall_status": "passed", "dimension_status": "passed", "cta_status": "passed", "layout_status": "passed", "ocr_status": "passed", "visual_review_status": "not_run"}},
        actual_results={},
        call_log=[],
        production_code_changed=False,
        missing_requirements=[],
    )
    runner.write_summary_artifacts(tmp_path, mock_summary)

    actual_summary = runner.build_summary(
        status="completed",
        mode="actual",
        engine="gpt_image_2",
        env_report={},
        mock_results={},
        actual_results={"banner": {"overall_status": "passed", "dimension_status": "passed", "cta_status": "passed", "layout_status": "passed", "ocr_status": "passed", "visual_review_status": "pass", "actual_calls": 1}},
        call_log=[{"mode": "actual", "attempt_executed": True, "billable_call": True}],
        production_code_changed=False,
        missing_requirements=[],
    )

    merged = runner.merge_existing_summary(tmp_path, actual_summary)

    assert merged["mock"]["banner"] == "passed"
    assert merged["actual"]["banner"] == "passed"
    assert merged["successful_actual_calls"] == 1
    assert merged["actual_attempts"] == 1
    assert merged["billable_call_count"] == 1


def test_artifact_redaction_removes_sensitive_fields():
    payload = {
        "signed_url": "https://example.com/file.png?sig=secret",
        "raw_body": "secret-body",
        "bucket": "hidden",
        "object_key": "hidden",
        "nested": {"authorization": "Bearer secret"},
        "image_paths": ["https://example.com/asset.png?token=abc"],
    }

    redacted = runner.redact_recursive(payload)

    assert "signed_url" not in redacted
    assert "raw_body" not in redacted
    assert "bucket" not in redacted
    assert "object_key" not in redacted
    assert "authorization" not in redacted["nested"]
    assert redacted["image_paths"] == ["https://example.com/asset.png"]


def test_main_mock_mode_generates_summary(tmp_path):
    exit_code = runner.main(["--mode", "mock", "--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert Path(tmp_path / "summary.json").exists()
