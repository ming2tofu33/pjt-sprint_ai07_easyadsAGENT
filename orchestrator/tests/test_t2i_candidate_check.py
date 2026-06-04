"""Tests for dry-run T2I candidate checks."""

from pathlib import Path

from scripts import check_t2i_candidates


def test_candidate_check_dry_run_writes_json_and_markdown_without_api(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    report = check_t2i_candidates.run_candidate_check(
        engines=["gpt_image_2"],
        include_api=False,
        output_dir=str(tmp_path / "candidate-images"),
    )

    json_path = Path(report["json_report_path"])
    markdown_path = Path(report["markdown_report_path"])

    assert json_path.exists()
    assert markdown_path.exists()
    assert report["include_api"] is False
    assert report["results"][0]["engine"] == "gpt_image_2"
    assert report["results"][0]["can_generate"] is False
    assert report["results"][0]["output_path"] is None


def test_sd35_check_records_missing_packages_without_crashing(monkeypatch, tmp_path):
    monkeypatch.setattr(check_t2i_candidates, "_package_available", lambda name: False)

    result = check_t2i_candidates.check_sd35_large(load_local=False, generate_local=False, output_dir=tmp_path)

    assert result["engine"] == "sd35_large"
    assert result["package_available"] is False
    assert result["torch_available"] is False
    assert result["can_import_pipeline"] is False
    assert result["can_load_model"] is False
    assert result["can_generate"] is False


def test_flux_check_records_missing_packages_without_crashing(monkeypatch, tmp_path):
    monkeypatch.setattr(check_t2i_candidates, "_package_available", lambda name: False)

    result = check_t2i_candidates.check_flux(load_local=False, generate_local=False, output_dir=tmp_path)

    assert result["engine"] == "flux"
    assert result["package_available"] is False
    assert result["torch_available"] is False
    assert result["can_import_pipeline"] is False
    assert result["can_load_model"] is False
    assert result["can_generate"] is False


def test_generate_local_requires_load_local(tmp_path):
    result = check_t2i_candidates.check_sd35_large(load_local=False, generate_local=True, output_dir=tmp_path)

    assert result["can_load_model"] is False
    assert result["can_generate"] is False
    assert result["error"] == "--generate-local requires --load-local"

