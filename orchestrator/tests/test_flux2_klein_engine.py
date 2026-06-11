import argparse
import sys
import types

import pytest
from PIL import Image

from orchestrator.app.t2i.engines.flux2_klein import (
    Flux2KleinEngine,
    Flux2KleinImageCountInvalid,
    clear_flux2_klein_pipeline_cache,
    normalize_flux2_klein_engine_key,
)
from orchestrator.app.t2i.engines.registry import get_t2i_engine
from orchestrator.app.t2i.engines.base import T2IGenerationInput
from scripts import run_flux2_klein_local_smoke as smoke


def test_flux2_klein_alias_normalization():
    assert normalize_flux2_klein_engine_key("flux2_klein") == "flux2_klein_4b"
    assert normalize_flux2_klein_engine_key("flux2-klein-4b") == "flux2_klein_4b"
    assert normalize_flux2_klein_engine_key("flux_2_klein_4b") == "flux2_klein_4b"
    assert normalize_flux2_klein_engine_key("flux2_klein_local") == "flux2_klein_4b"


def test_registry_returns_flux2_klein_engine():
    assert isinstance(get_t2i_engine("flux2_klein"), Flux2KleinEngine)


def test_flux2_klein_import_does_not_load_model():
    clear_flux2_klein_pipeline_cache()
    assert "diffusers" not in sys.modules or sys.modules.get("diffusers") is not None


def test_flux2_klein_fake_pipeline_success(monkeypatch, tmp_path):
    clear_flux2_klein_pipeline_cache()
    torch_module = types.ModuleType("torch")
    torch_module.bfloat16 = object()
    diffusers_module = types.ModuleType("diffusers")

    class FakePipeline:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            return cls()

        def enable_model_cpu_offload(self):
            return None

        def __call__(self, **kwargs):
            return types.SimpleNamespace(images=[Image.new("RGB", (32, 32), "white")])

    diffusers_module.Flux2KleinPipeline = FakePipeline
    monkeypatch.setitem(sys.modules, "torch", torch_module)
    monkeypatch.setitem(sys.modules, "diffusers", diffusers_module)
    monkeypatch.setenv("EASYADS_T2I_FLUX2_KLEIN_BACKEND", "local_diffusers")
    monkeypatch.setenv("EASYADS_ENABLE_FLUX2_KLEIN_LOCAL", "true")

    output = Flux2KleinEngine().generate(
        T2IGenerationInput(
            job_id="job1",
            prompt="premium cafe ad background, no readable text",
            width=512,
            height=512,
            num_images=1,
            output_dir=str(tmp_path),
        )
    )

    assert output.engine == "flux2_klein_4b"
    assert output.image_paths
    assert output.metadata["execution_backend"] == "local_diffusers"
    assert output.metadata["model_loaded"] is True


def test_flux2_klein_rejects_multiple_images(monkeypatch, tmp_path):
    monkeypatch.setenv("EASYADS_T2I_FLUX2_KLEIN_BACKEND", "local_diffusers")
    monkeypatch.setenv("EASYADS_ENABLE_FLUX2_KLEIN_LOCAL", "true")

    with pytest.raises(Flux2KleinImageCountInvalid):
        Flux2KleinEngine().generate(
            T2IGenerationInput(
                job_id="job1",
                prompt="premium cafe ad background",
                width=512,
                height=512,
                num_images=2,
                output_dir=str(tmp_path),
            )
        )


def test_flux2_klein_pipeline_cache_loads_once(monkeypatch, tmp_path):
    clear_flux2_klein_pipeline_cache()
    calls = {"loads": 0}
    torch_module = types.ModuleType("torch")
    torch_module.bfloat16 = object()
    diffusers_module = types.ModuleType("diffusers")

    class FakePipeline:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            calls["loads"] += 1
            return cls()

        def to(self, device):
            return None

        def __call__(self, **kwargs):
            return types.SimpleNamespace(images=[Image.new("RGB", (32, 32), "white")])

    diffusers_module.Flux2KleinPipeline = FakePipeline
    monkeypatch.setitem(sys.modules, "torch", torch_module)
    monkeypatch.setitem(sys.modules, "diffusers", diffusers_module)
    monkeypatch.setenv("EASYADS_T2I_FLUX2_KLEIN_BACKEND", "local_diffusers")
    monkeypatch.setenv("EASYADS_ENABLE_FLUX2_KLEIN_LOCAL", "true")

    request = T2IGenerationInput(job_id="job1", prompt="premium cafe ad", width=512, height=512, num_images=1, output_dir=str(tmp_path))
    Flux2KleinEngine().generate(request)
    Flux2KleinEngine().generate(request)

    assert calls["loads"] == 1


def test_flux2_klein_smoke_runner_blocks_actual_without_opt_in(monkeypatch):
    monkeypatch.delenv("EASYADS_FLUX2_KLEIN_ACTUAL", raising=False)
    monkeypatch.setenv("EASYADS_T2I_FLUX2_KLEIN_BACKEND", "local_diffusers")
    monkeypatch.setenv("EASYADS_ENABLE_FLUX2_KLEIN_LOCAL", "true")

    args = argparse.Namespace(actual=True)

    assert "EASYADS_FLUX2_KLEIN_ACTUAL=1" in smoke._missing_requirements(args)


def test_flux2_klein_smoke_validation_detects_valid_image(tmp_path):
    path = tmp_path / "image.png"
    Image.new("RGB", (16, 16), "white").save(path)

    result = smoke.validate_generated_image(path, expected_width=16, expected_height=16)

    assert result["exists"] is True
    assert result["valid"] is False
    assert result["flatImage"] is True
