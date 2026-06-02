"""Guarded FLUX local engine lane."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter

from orchestrator.app.t2i.engines.base import T2IGenerationInput, T2IGenerationOutput
from orchestrator.app.t2i.settings import (
    T2IEngineUnavailableError,
    get_hf_token,
    load_t2i_settings,
    require_t2i_enabled,
)

_PIPELINE = None


class FluxLocalEngine:
    engine_name = "flux"

    def generate(self, request: T2IGenerationInput) -> T2IGenerationOutput:
        started = perf_counter()
        settings = load_t2i_settings()
        require_t2i_enabled(self.engine_name, settings)
        _require_flux_model_readiness(settings)

        model_ref = settings.flux_local_path or settings.flux_model_id
        pipe = _load_pipeline(model_ref, settings.flux_device)

        output_dir = Path(request.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        result = pipe(  # pragma: no cover - heavy local opt-in only
            prompt=request.prompt,
            width=request.width,
            height=request.height,
            num_images_per_prompt=min(request.num_images, settings.max_images_per_job),
            num_inference_steps=settings.flux_num_inference_steps,
            guidance_scale=settings.flux_guidance_scale,
        )

        image_paths: list[str] = []
        for index, image in enumerate(getattr(result, "images", []) or []):
            path = output_dir / f"flux_{index}.png"
            image.save(path)
            image_paths.append(path.as_posix())

        if not image_paths:
            raise T2IEngineUnavailableError("FLUX response did not include generated images.")

        return T2IGenerationOutput(
            engine=self.engine_name,
            image_paths=image_paths,
            latency_ms=int((perf_counter() - started) * 1000),
            metadata={
                "api_call": False,
                "model": settings.flux_model_id if not settings.flux_local_path else None,
                "model_source": "local_path" if settings.flux_local_path else "model_id",
                "local_path_present": bool(settings.flux_local_path),
                "hf_token_present": settings.hf_token_present,
                "num_inference_steps": settings.flux_num_inference_steps,
                "guidance_scale": settings.flux_guidance_scale,
                **request.metadata,
            },
        )


def _load_pipeline(model_ref: str | None, device: str):
    global _PIPELINE
    if _PIPELINE is not None:
        return _PIPELINE

    try:
        import torch  # type: ignore
        from diffusers import FluxPipeline  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise T2IEngineUnavailableError("FLUX dependencies are unavailable.") from exc

    if not model_ref:
        raise T2IEngineUnavailableError("FLUX model reference is missing.")

    kwargs = {}
    token = get_hf_token()
    if token:
        kwargs["token"] = token

    _PIPELINE = FluxPipeline.from_pretrained(model_ref, **kwargs)  # pragma: no cover

    target_device = device
    if target_device == "auto":
        target_device = "cuda" if torch.cuda.is_available() else "cpu"
    if hasattr(_PIPELINE, "to"):  # pragma: no cover
        _PIPELINE = _PIPELINE.to(target_device)

    return _PIPELINE

def _require_flux_model_readiness(settings) -> None:
    if settings.flux_local_path or settings.hf_token_present:
        return
    raise T2IEngineUnavailableError(
        "FLUX local lane requires HF_TOKEN/HUGGINGFACE_TOKEN or EASYADS_FLUX_LOCAL_PATH."
    )