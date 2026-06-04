import json
from pathlib import Path

from PIL import Image

from scripts.run_copy_visual_overlay_review import run_overlay_review


def _write_report(path: Path, final_image_path: str | None = None):
    path.write_text(
        json.dumps(
            {
                "schema_version": "gpt_image2_quality_batch_report_v1",
                "cases": [
                    {
                        "case_id": "cafe_dessert_001",
                        "job_id": "job_test",
                        "business_type": "cafe",
                        "final_image_path": final_image_path,
                        "prompt_summary": {"business_type": "cafe"},
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_dry_run_does_not_require_real_outputs(tmp_path):
    report_path = tmp_path / "batch.json"
    _write_report(report_path, "missing/final_0.png")

    result = run_overlay_review(report=report_path, output_dir=tmp_path, dry_run=True)

    assert result["status"] == "dry_run"
    assert result["cases"][0]["preview_image_path"] is None
    assert Path(result["report_json_path"]).exists()
    assert Path(result["report_md_path"]).exists()


def test_missing_report_returns_blocked_report(tmp_path):
    result = run_overlay_review(report=tmp_path / "missing.json", output_dir=tmp_path)

    assert result["status"] == "blocked"
    assert "No GPT-image-2 quality batch report was found." in result["notes"]
    assert Path(result["report_json_path"]).exists()


def test_existing_temp_image_creates_preview(tmp_path):
    output_root = tmp_path / "outputs" / "job_test"
    output_root.mkdir(parents=True)
    image_path = output_root / "final_0.png"
    Image.new("RGB", (256, 256), (230, 210, 195)).save(image_path)
    report_path = tmp_path / "batch.json"
    _write_report(report_path, str(image_path))

    result = run_overlay_review(report=report_path, output_dir=tmp_path, max_cases=1)

    preview = Path(result["cases"][0]["preview_image_path"])
    assert result["cases"][0]["status"] == "preview_created"
    assert preview.exists()
    assert preview.name == "copy_visual_preview_0.png"


def test_report_does_not_include_raw_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-value")
    report_path = tmp_path / "batch.json"
    _write_report(report_path, "missing/final_0.png")

    result = run_overlay_review(report=report_path, output_dir=tmp_path, dry_run=True)

    report_text = Path(result["report_json_path"]).read_text(encoding="utf-8")
    assert "sk-secret-value" not in report_text
