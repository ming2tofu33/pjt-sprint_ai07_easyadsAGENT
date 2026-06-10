import json

from scripts import run_typography_renderer_actual as runner


def test_typography_runner_creates_font_catalog_artifacts(tmp_path, monkeypatch):
    out = tmp_path / "typography"
    monkeypatch.setattr("sys.argv", ["run_typography_renderer_actual.py", "--output-dir", str(out)])
    assert runner.main() == 0
    summary = json.loads((out / "typography_actual_summary.json").read_text(encoding="utf-8"))
    assert summary["actual_generation_performed"] is False
    assert (out / "font_catalog_preview.png").exists()
    assert (out / "font_catalog_result.json").exists()
    assert summary["font_catalog"]["font_count"] >= 18
