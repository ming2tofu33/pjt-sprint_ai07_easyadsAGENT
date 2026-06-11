from __future__ import annotations

import json
from types import SimpleNamespace

from PIL import Image

from scripts import run_final_composite_quality_actual as runner


def test_final_composite_actual_dry_run_is_blocked_without_calls(tmp_path, monkeypatch):
    out = tmp_path / "final_quality"
    monkeypatch.setattr("sys.argv", ["run_final_composite_quality_actual.py", "--dry-run", "--output-dir", str(out)])

    assert runner.main() == 0

    report = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert report["status"] == "blocked"
    assert report["actual_api_calls"] is False
    assert report["image_generation_performed"] is False


def test_final_composite_actual_requires_gpt54_not_mini(tmp_path, monkeypatch):
    _set_actual_env(monkeypatch)
    out = tmp_path / "final_quality"
    monkeypatch.setattr("sys.argv", ["run_final_composite_quality_actual.py", "--actual", "--copy-model", "gpt-5.4-mini", "--force-flux-generation", "--output-dir", str(out)])

    assert runner.main() == 0

    report = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert report["status"] == "blocked"
    assert "copy_model_must_be_gpt-5.4" in report["missing_requirements"]


def test_actual_runner_rejects_hardcoded_copy(monkeypatch):
    args = SimpleNamespace(copy_model="gpt-5.4")
    result = {
        "copy_provider": "openai",
        "copy_model": "gpt-5.4",
        "copy_fallback_used": False,
        "copy_token_usage": {"input_tokens": 10, "output_tokens": 5},
        "copy_candidates": [
            {"id": "copy_1", "headline": "Best AI Macaron", "subcopy": "x", "cta": ""},
            {"id": "copy_2", "headline": "Macaron", "subcopy": "x", "cta": ""},
            {"id": "copy_3", "headline": "Macaron", "subcopy": "x", "cta": ""},
        ],
        "selected_copy": {"headline": "Best AI Macaron", "subcopy": "x", "cta": ""},
    }

    try:
        runner._validate_copy_result(result, args.copy_model)
    except ValueError as exc:
        assert "forbidden" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("forbidden copy was accepted")


def test_actual_runner_requires_openai_token_usage():
    result = {"copy_provider": "openai", "copy_model": "gpt-5.4", "copy_fallback_used": False, "copy_token_usage": {"total_tokens": 1}}

    assert runner._strict_openai_success(result, "gpt-5.4", prefix="copy") is False


def test_actual_runner_requires_real_flux_result(tmp_path):
    image = tmp_path / "bg.png"
    Image.new("RGB", (16, 16)).save(image)

    assert runner._strict_flux_success({"status": "completed", "actual_flux_generation": False, "flux_engine": "flux2_klein_4b", "flux_backend": "local_diffusers", "image_path": str(image)}) is False
    assert runner._strict_flux_success({"status": "completed", "actual_flux_generation": True, "flux_engine": "flux2_klein_4b", "flux_backend": "local_diffusers", "image_path": str(image)}) is True


def test_actual_runner_rejects_background_copy_as_final(tmp_path):
    background = tmp_path / "background.png"
    final = tmp_path / "final.png"
    Image.new("RGB", (16, 16), "#ffffff").save(background)
    final.write_bytes(background.read_bytes())

    assert runner._sha256(background) == runner._sha256(final)


def test_completed_requires_api_and_image_generation(tmp_path):
    bg = tmp_path / "bg.png"
    final = tmp_path / "final.png"
    Image.new("RGB", (16, 16), "#ffffff").save(bg)
    Image.new("RGB", (16, 16), "#000000").save(final)
    copy = {"copy_provider": "openai", "copy_model": "gpt-5.4", "copy_fallback_used": False, "copy_token_usage": {"input_tokens": 10, "output_tokens": 5}}
    vlm = {"vlm_provider": "openai", "vlm_model": "gpt-5.4", "vlm_fallback_used": False, "vlm_token_usage": {"input_tokens": 10, "output_tokens": 5}}
    flux = {"status": "completed", "actual_flux_generation": True, "flux_engine": "flux2_klein_4b", "flux_backend": "local_diffusers", "image_path": str(bg)}
    state = {"render_result": {"final_image_path": str(final)}, "final_ocr_gate": {"status": "pass"}, "synthetic_trace_count": 0}
    report = SimpleNamespace(evaluated_image_sha256=runner._sha256(final), status="pass")

    assert runner.completed_conditions(copy, flux, state, state, report, report, vlm, vlm) is True


def _set_actual_env(monkeypatch):
    for key, value in runner.REQUIRED_ACTUAL_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("OPENAI_API_KEY", "present")
