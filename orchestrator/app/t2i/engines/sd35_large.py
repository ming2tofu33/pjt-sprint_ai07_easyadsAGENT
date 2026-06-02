"""Guarded SD3.5 local engine lane."""

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


class SD35LargeLocalEngine:
    engine_name = "sd35_large"

    def generate(self, request: T2IGenerationInput) -> T2IGenerationOutput:
        started = perf_counter()
        settings = load_t2i_settings()
        require_t2i_enabled(self.engine_name, settings)

        model_ref = settings.sd35_local_path or settings.sd35_model_id
        pipe = _load_pipeline(model_ref)

        output_dir = Path(request.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        result = pipe(  # pragma: no cover - heavy local opt-in only
            prompt=request.prompt,
            negative_prompt=request.negative_prompt or "",
            width=request.width,
            height=request.height,
            num_images_per_prompt=min(request.num_images, settings.max_images_per_job),
            num_inference_steps=8,
            guidance_scale=4.0,
        )

        image_paths: list[str] = []
        for index, image in enumerate(getattr(result, "images", []) or []):
            path = output_dir / f"sd35_large_{index}.png"
            image.save(path)
            image_paths.append(path.as_posix())

        model_source = "local_path" if settings.sd35_local_path else "model_id"

        return T2IGenerationOutput(
            engine=self.engine_name,
            image_paths=image_paths,
            latency_ms=int((perf_counter() - started) * 1000),
            metadata={
                "model": settings.sd35_model_id if not settings.sd35_local_path else None,
                "model_source": model_source,
                "local_path_present": bool(settings.sd35_local_path),
                "hf_token_present": settings.hf_token_present,
                **request.metadata,
            },
        )


def _load_pipeline(model_ref: str | None):
    global _PIPELINE
    if _PIPELINE is not None:
        return _PIPELINE

    try:
        import torch  # type: ignore
        from diffusers import StableDiffusion3Pipeline  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise T2IEngineUnavailableError("SD3.5 dependencies are unavailable.") from exc

    if not model_ref:
        raise T2IEngineUnavailableError("SD3.5 model reference is missing.")

    kwargs = {"torch_dtype": torch.float16}

    token = get_hf_token()
    if token:
        kwargs["token"] = token

    _PIPELINE = StableDiffusion3Pipeline.from_pretrained(model_ref, **kwargs)  # pragma: no cover

    if torch.cuda.is_available():  # pragma: no cover
        _PIPELINE = _PIPELINE.to("cuda")

    return _PIPELINE