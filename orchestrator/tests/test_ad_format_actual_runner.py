import json

from scripts import run_ad_format_copy_presence_actual as runner


def _enable_actual_env(monkeypatch):
    for key, value in {
        "OPENAI_API_KEY": "sk-test",
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
    }.items():
        monkeypatch.setenv(key, value)


def test_actual_runner_dry_run_blocks_without_provider_calls(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    output_dir = tmp_path / "actual"

    code = runner.main_with_args_for_test(["--output-dir", str(output_dir)])

    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert code == 2
    assert summary["status"] == "blocked"
    assert summary["mock_fixture_count"] == 0
    assert summary["runs"][0]["actual_flux_generation"] is False


def test_actual_runner_requires_gpt54_and_flux_actual_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    readiness = runner._readiness(actual=True)

    assert "EASYADS_LLM_MODEL" in readiness["missing_requirements"]
    assert readiness["required_text_model"] == "gpt-5.4"
    assert readiness["required_vlm_model"] == "gpt-5.4"


def test_readiness_success_calls_canonical_actual_bridge_for_three_cases(tmp_path, monkeypatch):
    _enable_actual_env(monkeypatch)
    calls = []

    def fake_runtime(readiness):
        assert readiness["missing_requirements"] == []
        return object()

    def fake_case(case, runtime):
        calls.append(case)
        return {
            "case_id": case.case_id,
            "status": "completed",
            "actual_flux_generation": True,
            "actual_openai_call": case.copy_presence_plan["mode"] != "image_only",
            "actual_vlm_call": True,
            "mock_or_fixture_used": False,
            "final_composite_path": str(case.output_dir / "final_composite.png"),
        }

    monkeypatch.setattr(runner, "_build_runtime", fake_runtime)
    monkeypatch.setattr(runner, "run_actual_creative_case", fake_case)

    code = runner.main_with_args_for_test(["--actual", "--output-dir", str(tmp_path / "actual")])

    assert code == 0
    assert len(calls) == 3
    assert [case.seed for case in calls] == [71, 72, 73]
    summary = json.loads((tmp_path / "actual" / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "completed"


def test_image_only_case_can_skip_copy_call(tmp_path, monkeypatch):
    _enable_actual_env(monkeypatch)
    monkeypatch.setattr(runner, "_build_runtime", lambda readiness: object())

    def fake_case(case, runtime):
        case.copy_presence_plan["mode"] = "image_only"
        return {
            "case_id": case.case_id,
            "status": "completed",
            "copy_call_required": False,
            "copy_call_skipped_reason": "image_only",
            "actual_flux_generation": True,
            "actual_openai_call": False,
            "actual_vlm_call": True,
            "mock_or_fixture_used": False,
        }

    monkeypatch.setattr(runner, "run_actual_creative_case", fake_case)

    runner.main_with_args_for_test(["--actual", "--case", "macaron_feed_visual_first", "--output-dir", str(tmp_path / "actual")])
    result = json.loads((tmp_path / "actual" / "macaron_feed_visual_first" / "result.json").read_text(encoding="utf-8"))

    assert result["copy_call_skipped_reason"] == "image_only"


def test_manual_review_does_not_become_blocked(tmp_path, monkeypatch):
    _enable_actual_env(monkeypatch)
    monkeypatch.setattr(runner, "_build_runtime", lambda readiness: object())
    monkeypatch.setattr(
        runner,
        "run_actual_creative_case",
        lambda case, runtime: {"case_id": case.case_id, "status": "manual_review", "mock_or_fixture_used": False, "actual_flux_generation": True, "actual_vlm_call": True},
    )

    runner.main_with_args_for_test(["--actual", "--case", "macaron_feed_visual_first", "--output-dir", str(tmp_path / "actual")])
    summary = json.loads((tmp_path / "actual" / "summary.json").read_text(encoding="utf-8"))

    assert summary["status"] == "manual_review"


def test_resume_skips_completed_case(tmp_path, monkeypatch):
    _enable_actual_env(monkeypatch)
    case_dir = tmp_path / "actual" / "macaron_feed_visual_first"
    case_dir.mkdir(parents=True)
    (case_dir / "result.json").write_text(json.dumps({"case_id": "macaron_feed_visual_first", "status": "completed", "mock_or_fixture_used": False}), encoding="utf-8")
    monkeypatch.setattr(runner, "_build_runtime", lambda readiness: object())
    monkeypatch.setattr(runner, "run_actual_creative_case", lambda case, runtime: (_ for _ in ()).throw(AssertionError("should skip")))

    runner.main_with_args_for_test(["--actual", "--resume", "--case", "macaron_feed_visual_first", "--output-dir", str(tmp_path / "actual")])
    summary = json.loads((tmp_path / "actual" / "summary.json").read_text(encoding="utf-8"))

    assert summary["status"] == "completed"
