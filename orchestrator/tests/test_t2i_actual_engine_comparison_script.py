import json
from pathlib import Path

import pytest

from scripts import run_t2i_actual_engine_comparison as runner


def test_dry_run_does_not_call_actual_engines(monkeypatch, tmp_path):
    def fail_create_app():
        raise AssertionError("actual app path should not run during dry-run")

    monkeypatch.setattr(runner, "create_app", fail_create_app)

    report = runner.run_comparison(
        plan="premium",
        requested_engines=["gpt_image_2", "sd35_large", "flux"],
        case_ids=["cafe_dessert_001"],
        max_cases=1,
        dry_run=True,
        confirm_actual=False,
        execution_backend="auto",
        require_db_r2=False,
        include_comparison=False,
        output_json=tmp_path / "report.json",
    )

    assert report["status"] == "dry_run"
    assert {run["status"] for run in report["runs"]} == {"dry_run"}


def test_dry_run_writes_report_json(tmp_path):
    path = tmp_path / "comparison.json"

    report = runner.run_comparison(
        plan="premium",
        requested_engines=["flux"],
        case_ids=["cafe_dessert_001"],
        max_cases=1,
        dry_run=True,
        confirm_actual=False,
        execution_backend="auto",
        require_db_r2=False,
        include_comparison=False,
        output_json=path,
    )

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert path.exists()
    assert saved["schema_version"] == "t2i_actual_engine_comparison_v1"
    assert saved["report_path"] == path.as_posix()
    assert report["report_path"] == path.as_posix()


def test_free_plan_resolves_only_sd35_large_and_flux(tmp_path):
    report = runner.run_comparison(
        plan="free",
        requested_engines=["gpt_image_2", "sd35_large", "flux"],
        case_ids=["cafe_dessert_001"],
        max_cases=1,
        dry_run=True,
        confirm_actual=False,
        execution_backend="auto",
        require_db_r2=False,
        include_comparison=False,
        output_json=tmp_path / "report.json",
    )

    assert report["resolved_engines"] == ["sd35_large", "flux2_klein_4b"]


def test_economic_plan_allows_gpt_image_1(tmp_path):
    report = runner.run_comparison(
        plan="economic",
        requested_engines=["gpt_image_1"],
        case_ids=["cafe_dessert_001"],
        max_cases=1,
        dry_run=True,
        confirm_actual=False,
        execution_backend="auto",
        require_db_r2=False,
        include_comparison=False,
        output_json=tmp_path / "report.json",
    )

    assert report["resolved_engines"] == ["gpt_image_1"]


def test_premium_include_comparison_resolves_all_engines(tmp_path):
    report = runner.run_comparison(
        plan="premium",
        requested_engines=None,
        case_ids=["cafe_dessert_001"],
        max_cases=1,
        dry_run=True,
        confirm_actual=False,
        execution_backend="auto",
        require_db_r2=False,
        include_comparison=True,
        output_json=tmp_path / "report.json",
    )

    assert report["resolved_engines"] == ["gpt_image_1", "gpt_image_2", "sd35_large", "flux2_klein_4b"]


def test_report_redacts_secret_env_values(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    monkeypatch.setenv("HF_TOKEN", "hf-secret")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "modal-secret")
    monkeypatch.setenv("EASYADS_R2_SECRET_ACCESS_KEY", "r2-secret")
    path = tmp_path / "report.json"

    runner.run_comparison(
        plan="premium",
        requested_engines=["gpt_image_2", "sd35_large", "flux"],
        case_ids=["cafe_dessert_001"],
        max_cases=1,
        dry_run=True,
        confirm_actual=False,
        execution_backend="auto",
        require_db_r2=False,
        include_comparison=False,
        output_json=path,
    )

    text = path.read_text(encoding="utf-8")
    assert "sk-secret" not in text
    assert "hf-secret" not in text
    assert "modal-secret" not in text
    assert "r2-secret" not in text


def test_blocked_run_has_no_arbitrary_manual_quality_score(tmp_path):
    report = runner.run_comparison(
        plan="premium",
        requested_engines=["gpt_image_2"],
        case_ids=["cafe_dessert_001"],
        max_cases=1,
        dry_run=False,
        confirm_actual=False,
        execution_backend="auto",
        require_db_r2=False,
        include_comparison=False,
        output_json=tmp_path / "report.json",
    )

    assert report["runs"][0]["status"] == "blocked"
    assert report["runs"][0]["manual_review"]["quality"] is None


def test_unknown_engine_is_ignored_without_crash(tmp_path):
    report = runner.run_comparison(
        plan="premium",
        requested_engines=["unknown", "flux"],
        case_ids=["cafe_dessert_001"],
        max_cases=1,
        dry_run=True,
        confirm_actual=False,
        execution_backend="auto",
        require_db_r2=False,
        include_comparison=False,
        output_json=tmp_path / "report.json",
    )

    assert report["resolved_engines"] == ["flux2_klein_4b"]


@pytest.mark.parametrize(
    ("engine", "expected_run_mode"),
    [("sd35_large", "sd35_local"), ("flux", "flux2_klein_4b")],
)
def test_engine_maps_to_actual_run_mode(engine, expected_run_mode, tmp_path):
    report = runner.run_comparison(
        plan="premium",
        requested_engines=[engine],
        case_ids=["cafe_dessert_001"],
        max_cases=1,
        dry_run=False,
        confirm_actual=True,
        execution_backend="auto",
        require_db_r2=False,
        include_comparison=False,
        output_json=tmp_path / "report.json",
    )

    assert report["runs"][0]["run_mode"] == expected_run_mode


def test_auto_execution_backend_uses_modal_readiness_for_flux(monkeypatch):
    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "modal")
    monkeypatch.setenv("EASYADS_ENABLE_MODAL_EXECUTION", "true")
    monkeypatch.setenv("EASYADS_MODAL_APP_NAME", "easyads-t2i")
    monkeypatch.setenv("EASYADS_MODAL_FUNCTION_NAME", "generate_image")
    monkeypatch.setenv("MODAL_TOKEN_ID", "token-id")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "token-secret")
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")

    readiness = runner._engine_readiness(
        "flux2_klein_4b",
        execution_backend="auto",
        require_db_r2=False,
    )

    assert readiness["ready"] is True
    assert readiness["missing_requirements"] == []


def test_auto_execution_backend_uses_modal_readiness_for_sd35(monkeypatch):
    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "modal")
    monkeypatch.setenv("EASYADS_ENABLE_MODAL_EXECUTION", "true")
    monkeypatch.setenv("EASYADS_MODAL_APP_NAME", "easyads-t2i")
    monkeypatch.setenv("EASYADS_MODAL_FUNCTION_NAME", "generate_image")
    monkeypatch.setenv("MODAL_TOKEN_ID", "token-id")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "token-secret")
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")

    readiness = runner._engine_readiness(
        "sd35_large",
        execution_backend="auto",
        require_db_r2=False,
    )

    assert readiness["ready"] is True
    assert readiness["missing_requirements"] == []

def test_report_status_treats_running_as_partial():
    runs = [{"status": "running"}, {"status": "blocked"}]

    assert runner._report_status(runs, dry_run=False) == "partial"

def test_summary_counts_pending_statuses():
    runs = [{"status": "running"}, {"status": "queued"}, {"status": "success"}]

    summary = runner._summary(runs, [{"case_id": "case_1"}])

    assert summary["pending"] == 2
    assert summary["success"] == 1


def test_main_prints_safe_run_summary(monkeypatch, tmp_path, capsys):
    path = tmp_path / "report.json"

    exit_code = runner.main(
        [
            "--dry-run",
            "--plan",
            "premium",
            "--engines",
            "flux",
            "--cases",
            "cafe_dessert_001",
            "--output-json",
            path.as_posix(),
        ]
    )

    printed = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert printed["status"] == "dry_run"
    assert printed["report_path"] == path.as_posix()
    assert printed["runs"][0]["engine"] == "flux2_klein_4b"
    assert "prompt_preview" not in printed["runs"][0]


def test_main_returns_nonzero_for_failed_report(monkeypatch, tmp_path, capsys):
    def fake_run_comparison(**kwargs):
        return {
            "status": "failed",
            "report_path": (tmp_path / "report.json").as_posix(),
            "runs": [
                {
                    "engine": "flux",
                    "case_id": "cafe_dessert_001",
                    "status": "failed",
                    "error_code": "flux_prompt_token_budget_unresolvable",
                    "error_type": "FluxPromptTokenBudgetError",
                    "error_message": "budget failed",
                    "clip_token_count": 77,
                    "clip_max_tokens": 77,
                    "clip_truncated": True,
                    "prompt_2_used": True,
                    "critical_constraints_preserved": False,
                }
            ],
        }

    monkeypatch.setattr(runner, "run_comparison", fake_run_comparison)

    exit_code = runner.main(["--confirm-actual", "--engines", "flux"])

    printed = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert printed["runs"][0]["error_type"] == "FluxPromptTokenBudgetError"
