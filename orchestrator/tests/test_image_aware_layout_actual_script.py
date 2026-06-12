import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from scripts import run_image_aware_layout_actual as runner
from scripts.run_image_aware_layout_actual import main


def test_image_aware_layout_actual_script_dry_run_writes_noncanonical_summary(tmp_path):
    output_dir = tmp_path / "image_aware"

    exit_code = main(["--output-dir", str(output_dir), "--cases", "macaron_collection_001,restaurant_bbq_001", "--max-images", "1"])

    assert exit_code == 0
    reports = list(output_dir.glob("summary_dry_run_*.json"))
    assert len(reports) == 1
    assert not (output_dir / "summary.json").exists()
    data = json.loads(reports[0].read_text(encoding="utf-8"))
    assert data["status"] == "dry_run"
    assert data["actual_generation"] is False
    assert data["cases"] == ["macaron_collection_001"]


def test_image_aware_layout_actual_blocks_without_real_requirements(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    args = SimpleNamespace(
        actual=True,
        env_file=None,
        cases="macaron_collection_001",
        seeds="62",
        max_images=1,
        max_copy_calls=1,
        max_layout_vlm_calls=1,
        max_final_vlm_calls=1,
        output_dir=str(tmp_path),
    )

    report = runner.build_report(args)

    assert report["status"] == "blocked"
    assert report["actual_generation"] is False
    assert report["actual_openai_copy"] is False
    assert report["actual_flux_generation"] is False
    assert report["actual_vlm_evaluation"] is False


def test_image_aware_layout_actual_with_mocked_real_contract_completes(monkeypatch, tmp_path):
    monkeypatch.setenv("EASYADS_COPY_QUALITY_ACTUAL", "1")
    monkeypatch.setenv("EASYADS_ENABLE_LLM_CALLS", "true")
    monkeypatch.setenv("EASYADS_VLM_ACTUAL", "1")
    monkeypatch.setenv("EASYADS_FLUX2_KLEIN_ACTUAL", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("EASYADS_ENABLE_FLUX2_KLEIN_LOCAL", "true")
    monkeypatch.setenv("EASYADS_T2I_FLUX2_KLEIN_BACKEND", "local_diffusers")
    monkeypatch.setenv("EASYADS_T2I_FLUX2_KLEIN_DEVICE", "cuda")

    class Candidate:
        id = "copy_1"
        headline = "마카롱 컬렉션"
        subcopy = "선물처럼 고르는 오늘의 디저트"
        cta = ""

    generated = SimpleNamespace(candidates=[Candidate(), Candidate(), Candidate()], ranking=SimpleNamespace(), recommended_candidate_id="copy_1")

    def fake_copy(case_id, args):
        return {"headline": "마카롱 컬렉션", "subcopy": "선물처럼 고르는 오늘의 디저트", "cta": ""}, {"provider": "openai", "fallback_used": False, "candidate_count": 3, "wrong_domain_terms": []}

    def fake_flux(case_id, *, case_dir, seed):
        path = Path(case_dir) / "flux2_klein_0.png"
        Image.new("RGB", (1024, 1024), "#f3eee7").save(path)
        return SimpleNamespace(engine="flux2_klein_4b", image_paths=[str(path)], latency_ms=123, metadata={"execution_backend": "local_diffusers", "provider": "local_diffusers", "model_name": "black-forest-labs/FLUX.2-klein-4B", "device_summary": "cuda"}, model_dump=lambda: {"engine": "flux2_klein_4b", "image_paths": [str(path)], "latency_ms": 123, "metadata": {"execution_backend": "local_diffusers", "provider": "local_diffusers", "model_name": "black-forest-labs/FLUX.2-klein-4B", "device_summary": "cuda"}})

    monkeypatch.setattr(runner, "_generate_actual_copy", fake_copy)
    monkeypatch.setattr(runner, "generate_flux2_background", fake_flux)
    monkeypatch.setattr(runner, "assert_actual_flux_result", lambda result: None)
    monkeypatch.setattr(runner, "run_actual_vlm_comparison", lambda *args: SimpleNamespace(preferred_version="v2", model_dump=lambda: {"preferred_version": "v2"}))
    monkeypatch.setattr(runner, "assert_actual_vlm_result", lambda result: None)

    args = SimpleNamespace(actual=True, env_file=None, cases="macaron_collection_001", seeds="62", max_images=1, max_copy_calls=1, max_layout_vlm_calls=1, max_final_vlm_calls=1, output_dir=str(tmp_path))

    report = runner.build_report(args)

    assert report["status"] == "completed"
    assert report["actual_generation"] is True
    run = report["runs"][0]
    assert run["actual_openai_copy"] is True
    assert run["actual_flux_generation"] is True
    assert run["actual_vlm_evaluation"] is True
    assert Path(run["grounded_copy_fixed_layout_path"]).read_bytes() != Path(run["background_flux2_path"]).read_bytes()


def test_image_aware_layout_actual_rejects_identical_grounded_fixed(monkeypatch, tmp_path):
    background = tmp_path / "background.png"
    rendered = tmp_path / "rendered.png"
    Image.new("RGB", (20, 20), "#ffffff").save(background)
    rendered.write_bytes(background.read_bytes())

    try:
        runner._assert_not_identical(background, rendered, "grounded_copy_fixed_layout")
    except RuntimeError as exc:
        assert "identical_to_background" in str(exc)
    else:
        raise AssertionError("identical image should fail")
