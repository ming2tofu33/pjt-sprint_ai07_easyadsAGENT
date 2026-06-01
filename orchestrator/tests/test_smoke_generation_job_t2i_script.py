from __future__ import annotations

import json
from pathlib import Path

from scripts.smoke_generation_job_t2i import run_smoke


def _read_report(report: dict, kind: str = "json") -> str:
    return Path(report["report_paths"][kind]).read_text(encoding="utf-8")


def test_gpt_image_2_dry_run_report_has_no_secret(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret")

    report = run_smoke(
        engine="gpt_image_2",
        prompt="Cafe strawberry latte ad background",
        dry_run=True,
        output_dir=tmp_path,
    )

    assert report["status"] == "dry_run"
    assert report["would_call_actual_engine"] is False
    assert report["env"]["api_key_present"] is True
    assert "sk-test-secret" not in _read_report(report)
    assert "sk-test-secret" not in _read_report(report, "md")


def test_sd35_dry_run_report_has_no_secret(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_TOKEN", "hf-test-secret")

    report = run_smoke(
        engine="sd35_large",
        prompt="Premium BBQ restaurant ad background",
        dry_run=True,
        output_dir=tmp_path,
    )

    assert report["status"] == "dry_run"
    assert report["would_call_actual_engine"] is False
    assert report["env"]["hf_token_present"] is True
    assert "hf-test-secret" not in _read_report(report)


def test_missing_env_blocks_actual_smoke_without_api_call(monkeypatch, tmp_path):
    monkeypatch.delenv("EASYADS_ENABLE_EXTERNAL_T2I", raising=False)
    monkeypatch.delenv("EASYADS_ENABLE_GPT_IMAGE_2", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    report = run_smoke(
        engine="gpt_image_2",
        prompt="Cafe ad background",
        dry_run=False,
        output_dir=tmp_path,
    )

    assert report["status"] == "blocked"
    assert report["would_call_actual_engine"] is False
    assert report["job_id"] is None
    assert "EASYADS_ENABLE_EXTERNAL_T2I" in report["missing_requirements"]
    payload = json.loads(_read_report(report))
    assert payload["status"] == "blocked"
