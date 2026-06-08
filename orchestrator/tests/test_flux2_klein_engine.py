import sys
import types

from PIL import Image

from orchestrator.app.t2i.engines.flux2_klein import Flux2KleinEngine, clear_flux2_klein_pipeline_cache, normalize_flux2_klein_engine_key
from orchestrator.app.t2i.engines.registry import get_t2i_engine
from orchestrator.app.t2i.engines.base import T2IGenerationInput


def test_flux2_klein_alias_normalization():
    assert normalize_flux2_klein_engine_key("flux2_klein") == "flux2_klein_4b"
    assert normalize_flux2_klein_engine_key("flux2-klein-4b") == "flux2_klein_4b"
    assert normalize_flux2_klein_engine_key("flux_2_klein_4b") == "flux2_klein_4b"


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

    diffusers_module.FluxPipeline = FakePipeline
    monkeypatch.setitem(sys.modules, "torch", torch_module)
    monkeypatch.setitem(sys.modules, "diffusers", diffusers_module)
    monkeypatch.setenv("EASYADS_T2I_FLUX2_KLEIN_BACKEND", "local_diffusers")

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

