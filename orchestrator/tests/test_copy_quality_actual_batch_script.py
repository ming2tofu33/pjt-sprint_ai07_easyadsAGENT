import json
import os
from pathlib import Path

import pytest

from scripts import _actual_env
from scripts import run_copy_quality_actual_batch as batch
from scripts import run_copy_quality_visual_actual as visual
from orchestrator.app.llm.copy_quality_v2 import build_deterministic_copy_output_v2
from orchestrator.app.t2i.engines.base import T2IGenerationOutput


ACTUAL_ENV_KEYS = [
    "OPENAI_API_KEY",
    "LLM_OPENAI_VISION_MODEL",
    "EASYADS_COPY_QUALITY_ACTUAL",
    "EASYADS_ENABLE_LLM_CALLS",
    "EASYADS_LLM_PROVIDER",
    "EASYADS_VLM_ACTUAL",
    "EASYADS_FLUX2_KLEIN_ACTUAL",
    "EASYADS_ENABLE_FLUX2_KLEIN_LOCAL",
    "EASYADS_T2I_FLUX2_KLEIN_BACKEND",
    "EASYADS_T2I_FLUX2_KLEIN_DEVICE",
]


def clear_actual_env(monkeypatch):
    for key in ACTUAL_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def clear_actual_env_direct():
    for key in ACTUAL_ENV_KEYS:
        os.environ.pop(key, None)


@pytest.fixture(autouse=True)
def isolate_actual_env():
    clear_actual_env_direct()
    yield
    clear_actual_env_direct()


def test_env_file_loader_loads_docs_api_key_without_printing_secret(monkeypatch, tmp_path, capsys):
    clear_actual_env(monkeypatch)
    env_file = tmp_path / "api_key.env"
    env_file.write_text(
        "# comment\nexport OPENAI_API_KEY='sk-secret-loader-test'\nLLM_OPENAI_VISION_MODEL=\"gpt-test\"\n",
        encoding="utf-8",
    )

    report = _actual_env.load_env_file(env_file)
    captured = capsys.readouterr()

    assert report["env_file_found"] is True
    assert "OPENAI_API_KEY" in report["loaded_keys"]
    assert "sk-secret-loader-test" not in captured.out
    assert "sk-secret-loader-test" not in json.dumps(report)
    assert Path(report["env_file"]).name == "api_key.env"
    assert visual.os.getenv("OPENAI_API_KEY") == "sk-secret-loader-test"


def test_copy_quality_actual_batch_dry_run_does_not_require_openai(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    args = type("Args", (), {"actual": False, "max_cases": 2, "max_openai_calls": 2, "mode": "post", "env_file": None})()

    report = batch.build_report(args)

    assert report["status"] == "dry_run"
    assert report["total_cases"] == 2
    assert all(run["actual_openai_call"] is False for run in report["runs"])


def test_copy_quality_actual_batch_blocks_without_guard(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("EASYADS_COPY_QUALITY_ACTUAL", raising=False)
    args = type("Args", (), {"actual": True, "max_cases": 1, "max_openai_calls": 1, "mode": "post", "env_file": None})()

    report = batch.build_report(args)

    assert report["status"] == "blocked"
    assert "OPENAI_API_KEY" in report["runs"][0]["missing_requirements"]
    assert "EASYADS_COPY_QUALITY_ACTUAL=1" in report["runs"][0]["missing_requirements"]


def test_copy_quality_visual_actual_blocks_without_model_or_guard(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("EASYADS_COPY_QUALITY_ACTUAL", raising=False)
    monkeypatch.delenv("EASYADS_ENABLE_FLUX2_KLEIN_LOCAL", raising=False)
    args = type("Args", (), {"actual": True, "cases": ["macaron_collection_001"], "max_images": 1, "copy_report": None, "env_file": None})()

    report = visual.build_report(args)

    assert report["status"] == "blocked"
    assert report["runs"][0]["quality"] is None
    assert "EASYADS_COPY_QUALITY_ACTUAL=1" in report["runs"][0]["missing_requirements"]
    assert "HF_TOKEN_or_HUGGINGFACE_TOKEN" not in report["runs"][0]["missing_requirements"]


def test_copy_quality_actual_batch_calls_actual_runner_when_guarded(monkeypatch):
    calls = []

    def fake_run_actual_copy_generation(state):
        calls.append(state["context"]["business_type"])
        output = build_deterministic_copy_output_v2(state)
        return output, {"llm_attempted": True, "fallback_used": False, "model_name": "gpt-test", "llm_call_result": {"token_usage": {"input_tokens": 3, "output_tokens": 4}}}

    monkeypatch.setattr(batch, "run_actual_copy_generation", fake_run_actual_copy_generation)
    monkeypatch.setenv("EASYADS_COPY_QUALITY_ACTUAL", "1")
    monkeypatch.setenv("EASYADS_ENABLE_LLM_CALLS", "true")
    monkeypatch.setenv("EASYADS_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-redacted")
    args = type("Args", (), {"actual": True, "max_cases": 1, "max_openai_calls": 1, "mode": "post", "env_file": None})()

    report = batch.build_report(args)

    assert calls == ["macaron"]
    assert report["status"] == "completed"
    assert report["call_budget"]["attempted"] == 1
    assert report["call_budget"]["succeeded"] == 1
    assert report["runs"][0]["actual_openai_call"] is True
    assert report["runs"][0]["selected_copy"]
    assert len(report["runs"][0]["candidates"]) == 3
    assert report["runs"][0]["model_name"] == "gpt-test"


def test_copy_quality_actual_batch_enforces_call_budget(monkeypatch):
    monkeypatch.setenv("EASYADS_COPY_QUALITY_ACTUAL", "1")
    monkeypatch.setenv("EASYADS_ENABLE_LLM_CALLS", "true")
    monkeypatch.setenv("EASYADS_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-redacted")
    args = type("Args", (), {"actual": True, "max_cases": 1, "max_openai_calls": 0, "mode": "post", "env_file": None})()

    report = batch.build_report(args)

    assert report["status"] == "blocked"
    assert "max_openai_calls_positive" in report["runs"][0]["missing_requirements"]


def test_text_actual_uses_env_file_before_missing_check(monkeypatch, tmp_path):
    clear_actual_env(monkeypatch)
    env_file = tmp_path / "api_key.env"
    env_file.write_text(
        "OPENAI_API_KEY=sk-from-file\nEASYADS_COPY_QUALITY_ACTUAL=1\nEASYADS_ENABLE_LLM_CALLS=true\nEASYADS_LLM_PROVIDER=openai\n",
        encoding="utf-8",
    )
    args = type("Args", (), {"actual": True, "max_cases": 1, "max_openai_calls": 0, "mode": "post", "env_file": str(env_file)})()

    report = batch.build_report(args)

    assert "OPENAI_API_KEY" not in report["runs"][0]["missing_requirements"]
    assert "EASYADS_COPY_QUALITY_ACTUAL=1" not in report["runs"][0]["missing_requirements"]


def test_visual_actual_uses_env_file_before_missing_check(monkeypatch, tmp_path):
    clear_actual_env(monkeypatch)
    env_file = tmp_path / "api_key.env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=sk-from-file",
                "EASYADS_COPY_QUALITY_ACTUAL=1",
                "EASYADS_VLM_ACTUAL=1",
                "EASYADS_FLUX2_KLEIN_ACTUAL=1",
                "EASYADS_ENABLE_FLUX2_KLEIN_LOCAL=true",
                "EASYADS_T2I_FLUX2_KLEIN_BACKEND=local_diffusers",
                "EASYADS_T2I_FLUX2_KLEIN_DEVICE=cuda",
            ]
        ),
        encoding="utf-8",
    )
    args = type("Args", (), {"actual": True, "cases": ["macaron_collection_001"], "max_images": 1, "copy_report": None, "env_file": str(env_file)})()

    report = visual.build_report(args)

    assert report["status"] == "failed"
    assert "OPENAI_API_KEY" not in report["missing_requirements"]
    assert report["runs"][0]["error_code"] == "ValueError"


def test_visual_actual_fails_without_copy_report_in_actual_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(visual, "missing_actual_requirements", lambda args: [])
    args = type("Args", (), {"actual": True, "cases": ["macaron_collection_001"], "max_images": 1, "copy_report": None, "env_file": None})()

    report = visual.build_report(args)

    assert report["status"] == "failed"
    assert report["runs"][0]["error_code"] == "ValueError"


def test_visual_actual_success_path_uses_flux_renderer_and_vlm(monkeypatch, tmp_path):
    calls = {"flux": 0, "render": 0, "vlm": 0}
    background = tmp_path / "background.png"

    def fake_flux(case_id, *, case_dir, seed):
        calls["flux"] += 1
        from PIL import Image

        Image.new("RGB", (128, 128), (40, 40, 40)).save(background)
        return T2IGenerationOutput(
            engine="flux2_klein_4b",
            image_paths=[str(background)],
            latency_ms=12,
            metadata={"provider": "local_diffusers", "execution_backend": "local_diffusers", "model_name": "black-forest-labs/FLUX.2-klein-4B"},
        )

    def fake_render(case_id, background_path, copy, output_dir, label):
        calls["render"] += 1
        from PIL import Image

        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{label}.png"
        Image.new("RGB", (128, 128), (80 if label == "baseline" else 120, 80, 80)).save(path)
        return path

    def fake_vlm(case_id, baseline_path, v2_path):
        calls["vlm"] += 1
        return visual.CopyActualComparisonResult(
            baseline_copy_score=5,
            v2_copy_score=8,
            baseline_natural_korean=5,
            v2_natural_korean=8,
            baseline_business_fit=5,
            v2_business_fit=8,
            baseline_specificity=4,
            v2_specificity=7,
            baseline_emotional_pull=4,
            v2_emotional_pull=7,
            baseline_cta_relevance=5,
            v2_cta_relevance=8,
            baseline_generic_phrase=True,
            v2_generic_phrase=False,
            baseline_unsupported_claim=False,
            v2_unsupported_claim=False,
            baseline_text_readable=True,
            v2_text_readable=True,
            preferred_version="v2",
            improvement_reasons=["more specific"],
        )

    monkeypatch.setattr(visual, "generate_flux2_background", fake_flux)
    monkeypatch.setattr(visual, "render_baseline_and_v2_copy", fake_render)
    monkeypatch.setattr(visual, "run_actual_vlm_comparison", fake_vlm)

    run = visual.run_actual_copy_case(
        "macaron_collection_001",
        case_dir=tmp_path / "case",
        seed=42,
        copy_report={"runs": [{"case_id": "macaron_collection_001", "selected_copy": {"headline": "마카롱 컬렉션", "subcopy": "달콤한 색을 고르는 시간", "cta": "라인업 보기"}}]},
        max_vlm_calls=1,
    )

    assert run["status"] == "completed"
    assert calls == {"flux": 1, "render": 2, "vlm": 1}


def test_vlm_actual_comparison_success_path(monkeypatch, tmp_path):
    from PIL import Image

    baseline = tmp_path / "baseline.png"
    v2 = tmp_path / "v2.png"
    Image.new("RGB", (16, 16), "white").save(baseline)
    Image.new("RGB", (16, 16), "black").save(v2)

    payload = {
        "baseline_copy_score": 5,
        "v2_copy_score": 8,
        "baseline_natural_korean": 5,
        "v2_natural_korean": 8,
        "baseline_business_fit": 5,
        "v2_business_fit": 8,
        "baseline_specificity": 5,
        "v2_specificity": 8,
        "baseline_emotional_pull": 5,
        "v2_emotional_pull": 8,
        "baseline_cta_relevance": 5,
        "v2_cta_relevance": 8,
        "baseline_generic_phrase": True,
        "v2_generic_phrase": False,
        "baseline_unsupported_claim": False,
        "v2_unsupported_claim": False,
        "baseline_text_readable": True,
        "v2_text_readable": True,
        "preferred_version": "v2",
        "improvement_reasons": ["more specific"],
        "remaining_copy_issues": [],
        "layout_issues": [],
    }

    class FakeResponse:
        output_text = json.dumps(payload)

    def fake_create(**kwargs):
        assert kwargs["model"]
        assert all(str(path).endswith(".png") for path in kwargs["image_paths"])
        return FakeResponse()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-redacted")
    monkeypatch.setattr(visual, "_create_openai_vision_response", fake_create)

    result = visual.run_actual_vlm_comparison("macaron_collection_001", baseline, v2)

    assert result.preferred_version == "v2"
    assert result.v2_copy_score == 8


def test_vlm_not_implemented_never_completed(monkeypatch, tmp_path):
    from PIL import Image

    background = tmp_path / "background.png"

    def fake_flux(case_id, *, case_dir, seed):
        Image.new("RGB", (128, 128), (40, 40, 40)).save(background)
        return T2IGenerationOutput(
            engine="flux2_klein_4b",
            image_paths=[str(background)],
            latency_ms=12,
            metadata={"provider": "local_diffusers", "execution_backend": "local_diffusers", "model_name": "black-forest-labs/FLUX.2-klein-4B"},
        )

    def fake_render(case_id, background_path, copy, output_dir, label):
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{label}.png"
        Image.new("RGB", (128, 128), (80 if label == "baseline" else 120, 80, 80)).save(path)
        return path

    copy_report = tmp_path / "post_actual.json"
    copy_report.write_text(
        json.dumps({"runs": [{"case_id": "macaron_collection_001", "selected_copy": {"headline": "마카롱 컬렉션", "subcopy": "달콤한 색을 고르는 시간", "cta": "라인업 보기"}}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(visual, "missing_actual_requirements", lambda args: [])
    monkeypatch.setattr(visual, "generate_flux2_background", fake_flux)
    monkeypatch.setattr(visual, "render_baseline_and_v2_copy", fake_render)
    monkeypatch.setattr(visual, "run_actual_vlm_comparison", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("vlm_not_available")))
    args = type(
        "Args",
        (),
        {
            "actual": True,
            "cases": ["macaron_collection_001"],
            "max_images": 1,
            "copy_report": str(copy_report),
            "output_dir": str(tmp_path / "visual"),
            "seeds": [42],
            "max_vlm_calls": 1,
            "env_file": None,
        },
    )()

    report = visual.build_report(args)

    assert report["status"] == "failed"
    assert report["runs"][0]["status"] == "failed"
    assert report["runs"][0]["error_code"] == "RuntimeError"


def test_visual_false_positive_rejects_mock_flux_result(tmp_path):
    image = tmp_path / "mock.png"
    image.write_bytes(b"not an image")
    result = T2IGenerationOutput(engine="mock", image_paths=[str(image)], latency_ms=1, metadata={"provider": "mock"})

    try:
        visual.assert_actual_flux_result(result)
    except AssertionError as exc:
        assert "flux2_klein_4b" in str(exc)
    else:
        raise AssertionError("mock result should not pass actual FLUX validation")
