"""Guarded FLUX.2 Klein 4B local lane."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any

from orchestrator.app.t2i.engines.base import T2IGenerationInput, T2IGenerationOutput
from orchestrator.app.t2i.settings import T2IEngineUnavailableError, get_hf_token, load_t2i_settings, require_t2i_enabled


FLUX2_KLEIN_ENGINE = "flux2_klein_4b"
FLUX2_KLEIN_ALIASES = {"flux2_klein", "flux2-klein-4b", "flux_2_klein_4b", FLUX2_KLEIN_ENGINE}
_PIPELINE = None
_TORCH = None


class Flux2KleinDependencyMissing(T2IEngineUnavailableError):
    error_code = "flux2_klein_dependency_missing"


class Flux2KleinModelLoadFailed(T2IEngineUnavailableError):
    error_code = "flux2_klein_model_load_failed"


class Flux2KleinGenerationFailed(T2IEngineUnavailableError):
    error_code = "flux2_klein_generation_failed"


class Flux2KleinCudaOOM(T2IEngineUnavailableError):
    error_code = "flux2_klein_oom"


def normalize_flux2_klein_engine_key(engine_name: str | None) -> str | None:
    value = str(engine_name or "").strip()
    return FLUX2_KLEIN_ENGINE if value in FLUX2_KLEIN_ALIASES else engine_name


def clear_flux2_klein_pipeline_cache() -> None:
    global _PIPELINE
    _PIPELINE = None


class Flux2KleinEngine:
    engine_name = FLUX2_KLEIN_ENGINE

    def generate(self, request: T2IGenerationInput) -> T2IGenerationOutput:
        started = perf_counter()
        settings = load_t2i_settings()
        require_t2i_enabled(self.engine_name, settings)
        if settings.flux2_klein_backend == "modal":
            raise T2IEngineUnavailableError("FLUX.2 Klein Modal execution is handled by graph/modal adapter.")
        if request.num_images > 1:
            raise Flux2KleinGenerationFailed("FLUX.2 Klein smoke supports one image per request.")

        output_dir = Path(request.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        timings: dict[str, int] = {}
        try:
            pipe = _load_pipeline(settings, timings)
            kwargs = _build_call_kwargs(request, settings)
            inference_started = perf_counter()
            print("[flux2-klein] inference started")
            result = pipe(**kwargs)  # pragma: no cover - actual local GPU opt-in
            timings["inference_ms"] = int((perf_counter() - inference_started) * 1000)
            print("[flux2-klein] inference completed")
        except Flux2KleinDependencyMissing:
            raise
        except RuntimeError as exc:
            if "out of memory" in str(exc).lower() or "cuda oom" in str(exc).lower():
                raise Flux2KleinCudaOOM("FLUX.2 Klein CUDA out of memory.") from exc
            raise Flux2KleinGenerationFailed("FLUX.2 Klein generation failed.") from exc
        except Exception as exc:
            raise Flux2KleinGenerationFailed("FLUX.2 Klein generation failed.") from exc

        image_paths: list[str] = []
        save_started = perf_counter()
        for index, image in enumerate(getattr(result, "images", []) or []):
            path = output_dir / f"flux2_klein_{index}.png"
            image.save(path)
            image_paths.append(path.as_posix())
        timings["image_save_ms"] = int((perf_counter() - save_started) * 1000)
        if not image_paths:
            raise Flux2KleinGenerationFailed("FLUX.2 Klein response did not include images.")

        return T2IGenerationOutput(
            engine=self.engine_name,
            image_paths=image_paths,
            latency_ms=int((perf_counter() - started) * 1000),
            metadata={
                **_safe_metadata(request.metadata),
                "engine": self.engine_name,
                "model_name": settings.flux2_klein_model_id,
                "execution_backend": "local_diffusers",
                "dtype": settings.flux2_klein_dtype,
                "device_summary": _device_summary(settings.flux2_klein_device),
                "model_loaded": True,
                "api_call": False,
                "hf_token_present": bool(get_hf_token()),
                "num_inference_steps": settings.flux2_klein_num_inference_steps,
                "guidance_scale": settings.flux2_klein_guidance_scale,
                "timings": timings,
            },
        )


def _load_pipeline(settings, timings: dict[str, int] | None = None):
    global _PIPELINE, _TORCH
    if _PIPELINE is not None:
        return _PIPELINE
    timings = timings if timings is not None else {}
    dependency_started = perf_counter()
    print("[flux2-klein] dependency check started")
    try:
        import torch  # type: ignore
        from diffusers import Flux2KleinPipeline  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on optional local deps
        raise Flux2KleinDependencyMissing(
            "Flux2KleinPipeline is unavailable. Install a Diffusers version with FLUX.2 Klein support."
        ) from exc
    timings["dependency_check_ms"] = int((perf_counter() - dependency_started) * 1000)
    _TORCH = torch

    dtype = getattr(torch, settings.flux2_klein_dtype, torch.bfloat16)
    try:
        load_started = perf_counter()
        print("[flux2-klein] pipeline load started")
        pipe = Flux2KleinPipeline.from_pretrained(
            settings.flux2_klein_model_id,
            torch_dtype=dtype,
            cache_dir=settings.flux2_klein_cache_dir,
            token=get_hf_token() or None,
        )
        if settings.flux2_klein_enable_cpu_offload and hasattr(pipe, "enable_model_cpu_offload"):
            pipe.enable_model_cpu_offload()
        elif hasattr(pipe, "to"):
            pipe.to(settings.flux2_klein_device)
        timings["model_download_and_load_ms"] = int((perf_counter() - load_started) * 1000)
        print("[flux2-klein] pipeline load completed")
    except RuntimeError as exc:
        if "out of memory" in str(exc).lower():
            raise Flux2KleinCudaOOM("FLUX.2 Klein CUDA out of memory.") from exc
        raise Flux2KleinModelLoadFailed("FLUX.2 Klein model load failed.") from exc
    except Exception as exc:
        raise Flux2KleinModelLoadFailed("FLUX.2 Klein model load failed.") from exc
    _PIPELINE = pipe
    return pipe


def _build_call_kwargs(request: T2IGenerationInput, settings) -> dict[str, Any]:
    kwargs = {
        "prompt": request.prompt,
        "width": request.width,
        "height": request.height,
        "num_images_per_prompt": 1,
        "num_inference_steps": settings.flux2_klein_num_inference_steps,
        "guidance_scale": settings.flux2_klein_guidance_scale,
    }
    seed = getattr(request, "seed", None)
    if seed is not None and _TORCH is not None:
        kwargs["generator"] = _TORCH.Generator(device=settings.flux2_klein_device).manual_seed(seed)
    return kwargs


def _safe_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    blocked = {"hf_token", "huggingface_token", "token", "authorization", "api_key", "secret", "object_key", "bucket"}
    safe: dict[str, Any] = {}
    for key, value in (metadata or {}).items():
        lower = str(key).lower()
        if lower in blocked or "path" in lower and isinstance(value, str) and (":" in value or value.startswith("/")):
            continue
        safe[str(key)] = value
    return safe


def _device_summary(device: str) -> str:
    value = str(device or "auto").lower()
    if "cuda" in value:
        return "cuda"
    if "cpu" in value:
        return "cpu"
    return "auto"
