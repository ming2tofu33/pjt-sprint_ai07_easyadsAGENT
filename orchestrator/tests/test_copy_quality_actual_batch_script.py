from scripts import run_copy_quality_actual_batch as batch
from scripts import run_copy_quality_visual_actual as visual


def test_copy_quality_actual_batch_dry_run_does_not_require_openai(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    args = type("Args", (), {"actual": False, "max_cases": 2, "max_openai_calls": 2, "mode": "post"})()

    report = batch.build_report(args)

    assert report["status"] == "dry_run"
    assert report["total_cases"] == 2
    assert all(run["actual_openai_call"] is False for run in report["runs"])


def test_copy_quality_actual_batch_blocks_without_guard(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("EASYADS_COPY_QUALITY_ACTUAL", raising=False)
    args = type("Args", (), {"actual": True, "max_cases": 1, "max_openai_calls": 1, "mode": "post"})()

    report = batch.build_report(args)

    assert report["status"] == "blocked"
    assert "OPENAI_API_KEY" in report["runs"][0]["missing_requirements"]
    assert "EASYADS_COPY_QUALITY_ACTUAL=1" in report["runs"][0]["missing_requirements"]


def test_copy_quality_visual_actual_blocks_without_model_or_guard(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("EASYADS_COPY_QUALITY_ACTUAL", raising=False)
    monkeypatch.delenv("EASYADS_ENABLE_FLUX2_KLEIN_LOCAL", raising=False)
    args = type("Args", (), {"actual": True, "max_cases": 1})()

    report = visual.build_report(args)

    assert report["status"] == "blocked"
    assert report["runs"][0]["quality"] is None
    assert "EASYADS_COPY_QUALITY_ACTUAL=1" in report["runs"][0]["missing_requirements"]
