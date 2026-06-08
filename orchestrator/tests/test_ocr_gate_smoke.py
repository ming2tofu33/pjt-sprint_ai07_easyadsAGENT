import json

from scripts import run_ocr_gate_smoke


def test_ocr_gate_smoke_writes_report(monkeypatch, tmp_path):
    monkeypatch.setattr(run_ocr_gate_smoke, "OUTPUT_DIR", tmp_path)

    assert run_ocr_gate_smoke.main([]) == 0
    report = json.loads((tmp_path / "ocr_gate_result.json").read_text(encoding="utf-8"))

    assert report["background"]["decision"] in {"retry_image", "reject"}
    assert report["final_ad"]["decision"] == "pass"
    assert report["actual_ocr"]["executed"] is False
