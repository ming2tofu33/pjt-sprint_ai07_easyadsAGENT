import json

from scripts import run_typography_renderer_actual as runner


def test_typography_runner_creates_font_catalog_artifacts(tmp_path, monkeypatch):
    out = tmp_path / "typography"
    monkeypatch.setattr("sys.argv", ["run_typography_renderer_actual.py", "--output-dir", str(out)])
    assert runner.main() == 0
    summary = json.loads((out / "typography_actual_summary.json").read_text(encoding="utf-8"))
    assert summary["actual_generation_performed"] is True
    assert (out / "font_catalog_preview.png").exists()
    assert (out / "font_catalog_result.json").exists()
    assert summary["font_catalog"]["active_core_font_count"] == 23
    case_dir = out / "macaron_collection_001"
    assert (case_dir / "comparison_sheet_3way.png").exists()
    result = json.loads((case_dir / "result.json").read_text(encoding="utf-8"))
    assert result["status"] == "completed"
    assert result["selected_preset"] == "bilingual_editorial"
    assert result["language_policy"]["body_language_mode"] == "korean"
    assert result["font_path_null"] == 0
    assert result["fallback_font_count"] == 0


def test_typography_actual_runner_does_not_complete_unknown_cases(tmp_path, monkeypatch):
    out = tmp_path / "typography"
    monkeypatch.setattr("sys.argv", ["run_typography_renderer_actual.py", "--cases", "unknown_case", "--output-dir", str(out)])
    assert runner.main() == 0
    summary = json.loads((out / "typography_actual_summary.json").read_text(encoding="utf-8"))
    assert summary["runs"][0]["status"] == "skipped"


def test_typography_actual_runner_blocks_actual_without_background(tmp_path, monkeypatch):
    out = tmp_path / "typography"
    monkeypatch.setattr("sys.argv", ["run_typography_renderer_actual.py", "--actual", "--max-font-selection-calls", "0", "--max-vlm-calls", "0", "--reuse-background-dir", str(tmp_path / "missing"), "--output-dir", str(out)])

    assert runner.main() == 0

    result = json.loads((out / "macaron_collection_001" / "result.json").read_text(encoding="utf-8"))
    assert result["status"] == "blocked"
    assert result["failure_reasons"] == ["background_missing"]
    assert result["mock_or_fixture_count"] == 0
    assert not (out / "macaron_collection_001" / "background_flux2.png").exists()
