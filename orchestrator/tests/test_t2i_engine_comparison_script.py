from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_t2i_engine_comparison import CASES, parse_args, run_comparison

def _read_report(report: dict, kind: str = "json") -> str:
    return Path(report["report_paths"][kind]).read_text(encoding="utf-8")


def test_comparison_dry_run_does_not_call_actual_engines(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret")
    monkeypatch.setenv("HF_TOKEN", "hf-test-secret")

    report = run_comparison(
        engines=["gpt_image_2", "sd35_large", "flux"],
        dry_run=True,
        actual=False,
        confirm_cost=False,
        confirm_heavy=False,
        output_dir=tmp_path,
    )

    assert len(CASES) >= 3
    assert report["summary"]["total_results"] == len(CASES) * 3
    assert all(case["status"] == "dry_run" for case in report["cases"])
    assert "sk-test-secret" not in _read_report(report)
    assert "hf-test-secret" not in _read_report(report)
    assert "sk-test-secret" not in _read_report(report, "md")


def test_comparison_actual_without_confirm_is_blocked(tmp_path):
    report = run_comparison(
        engines=["flux"],
        dry_run=False,
        actual=True,
        confirm_cost=False,
        confirm_heavy=False,
        output_dir=tmp_path,
    )

    assert report["engine_readiness"]["flux"]["ready"] is False
    assert "--confirm-heavy" in report["engine_readiness"]["flux"]["missing_requirements"]
    assert all(case["status"] == "blocked" for case in report["cases"])
    payload = json.loads(_read_report(report))
    assert payload["summary"]["total_blocked"] == len(CASES)

def test_comparison_cli_rejects_dry_run_and_actual_together():
    with pytest.raises(SystemExit):
        parse_args(["--dry-run", "--actual"])