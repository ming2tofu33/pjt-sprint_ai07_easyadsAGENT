from __future__ import annotations

import json

from PIL import Image

from scripts import run_final_composite_quality_actual as runner


def test_final_composite_actual_script_evaluates_existing_image(tmp_path, monkeypatch):
    out = tmp_path / "final_quality"
    monkeypatch.setattr("sys.argv", ["run_final_composite_quality_actual.py", "--dry-run", "--output-dir", str(out)])

    assert runner.main() == 0

    report = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert report["status"] == "blocked"
    assert report["actual_api_calls"] is False
    assert report["image_generation_performed"] is False


def test_final_composite_actual_requires_actual_guards(tmp_path, monkeypatch):
    out = tmp_path / "final_quality"
    monkeypatch.setattr("sys.argv", ["run_final_composite_quality_actual.py", "--actual", "--output-dir", str(out)])

    assert runner.main() == 0

    report = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert report["status"] == "blocked"
    assert "OPENAI_API_KEY" in report["missing_requirements"]


def test_final_composite_actual_rejects_synthetic_state(tmp_path, monkeypatch):
    background = tmp_path / "background.png"
    Image.new("RGB", (1000, 1000), "#f5f1ea").save(background)
    out = tmp_path / "final_quality"
    env = {
        "EASYADS_FINAL_COMPOSITE_ACTUAL": "1",
        "EASYADS_COPY_QUALITY_ACTUAL": "1",
        "EASYADS_ENABLE_LLM_CALLS": "true",
        "EASYADS_LLM_PROVIDER": "openai",
        "EASYADS_VLM_ACTUAL": "1",
        "EASYADS_FLUX2_KLEIN_ACTUAL": "1",
        "EASYADS_ENABLE_FLUX2_KLEIN_LOCAL": "true",
        "OPENAI_API_KEY": "present",
        "EASYADS_FINAL_COMPOSITE_ACTUAL_BACKGROUND_PATH": str(background),
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr("sys.argv", ["run_final_composite_quality_actual.py", "--actual", "--output-dir", str(out)])

    assert runner.main() == 0

    report = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["runs"][0]["error_code"] == "synthetic_state_rejected"
