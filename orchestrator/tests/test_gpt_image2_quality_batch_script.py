from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import run_gpt_image2_quality_batch as batch


def test_quality_batch_cases_define_minimum_three() -> None:
    cases = batch.get_quality_batch_cases()

    assert len(cases) >= 3
    assert [case.case_id for case in cases[:3]] == [
        "cafe_dessert_001",
        "restaurant_bbq_001",
        "beauty_salon_001",
    ]


def test_dry_run_writes_report_without_api_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_testclient(*args, **kwargs):  # pragma: no cover - should not be called
        raise AssertionError("dry-run must not create TestClient or call actual API")

    monkeypatch.setattr(batch, "TestClient", fail_testclient)
    report = batch.run_quality_batch(
        actual=False,
        dry_run=True,
        max_cases=3,
        confirm_cost=False,
        output_dir=tmp_path,
    )

    assert report["status"] == "dry_run"
    assert report["actual_generation"] is False
    assert len(report["cases"]) == 3
    assert all(item["selected_reference_template_id"] is not None for item in report["cases"])
    assert all(item["visual_template_id"] for item in report["cases"])
    assert Path(report["report_paths"]["json"]).exists()
    assert Path(report["report_paths"]["md"]).exists()


def test_actual_without_confirm_cost_is_blocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EASYADS_ENABLE_EXTERNAL_T2I", "true")
    monkeypatch.setenv("EASYADS_ENABLE_GPT_IMAGE_2", "true")
    monkeypatch.setenv("EASYADS_QUALITY_BATCH_CONFIRM", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret")

    report = batch.run_quality_batch(
        actual=True,
        dry_run=False,
        max_cases=1,
        confirm_cost=False,
        output_dir=tmp_path,
    )

    assert report["status"] == "blocked"
    assert report["reason"] == "missing_actual_generation_requirements"
    assert "--confirm-cost" in report["missing_requirements"]


def test_actual_without_env_is_blocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "EASYADS_ENABLE_EXTERNAL_T2I",
        "EASYADS_ENABLE_GPT_IMAGE_2",
        "EASYADS_QUALITY_BATCH_CONFIRM",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    report = batch.run_quality_batch(
        actual=True,
        dry_run=False,
        max_cases=1,
        confirm_cost=True,
        output_dir=tmp_path,
    )

    assert report["status"] == "blocked"
    assert "EASYADS_ENABLE_EXTERNAL_T2I" in report["missing_requirements"]
    assert "OPENAI_API_KEY" in report["missing_requirements"]


def test_max_cases_hard_cap() -> None:
    with pytest.raises(ValueError, match="between 1 and 6"):
        batch.run_quality_batch(actual=False, dry_run=True, max_cases=7, confirm_cost=False, output_dir=Path("data/logs"))


def test_report_redacts_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-raw-secret")
    report = batch.run_quality_batch(
        actual=True,
        dry_run=False,
        max_cases=1,
        confirm_cost=False,
        output_dir=tmp_path,
    )

    raw = json.dumps(report, ensure_ascii=False)
    assert "sk-raw-secret" not in raw
    assert "openai_api_key_present" in raw


def test_generation_payload_includes_selected_reference_or_none() -> None:
    case = batch.get_quality_batch_cases()[0]
    template = batch.select_reference_template_for_case(case)
    payload = batch.build_generation_payload(case, template)

    assert "selected_reference_template_id" in payload
    assert payload["metadata"]["quality_batch_id"] == batch.BATCH_ID
    assert payload["metadata"]["case_id"] == case.case_id
