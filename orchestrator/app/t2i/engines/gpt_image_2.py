"""Guarded OpenAI GPT-image engine lanes."""

from __future__ import annotations

import base64
from pathlib import Path
from time import perf_counter
from typing import Any

from orchestrator.app.t2i.engines.base import T2IGenerationInput, T2IGenerationOutput
from orchestrator.app.t2i.settings import (
    T2IEngineUnavailableError,
    get_openai_api_key,
    load_t2i_settings,
    require_t2i_enabled,
)

class GPTImageActualEngine:
    engine_name = "gpt_image_1"
    model_settings_field = "gpt_image_1_model"

    def generate(self, request: T2IGenerationInput) -> T2IGenerationOutput:
        started = perf_counter()
        settings = load_t2i_settings()
        require_t2i_enabled(self.engine_name, settings)
        model = _resolve_model(str(getattr(settings, self.model_settings_field)))
        try:
            from openai import OpenAI  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise T2IEngineUnavailableError("OpenAI SDK is unavailable.") from exc

        output_dir = Path(request.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        api_key = get_openai_api_key()
        client = OpenAI(api_key=api_key)
        response = client.images.generate(
            model=model,
            prompt=request.prompt,
            size=_size(request.width, request.height),
            n=min(request.num_images, settings.max_images_per_job),
        )
        image_paths = _save_response_images(response, output_dir, self.engine_name)
        return T2IGenerationOutput(
            engine=self.engine_name,
            image_paths=image_paths,
            latency_ms=int((perf_counter() - started) * 1000),
            metadata={"api_call": True, "model": model, **request.metadata},
        )


class GPTImage1ActualEngine(GPTImageActualEngine):
    engine_name = "gpt_image_1"
    model_settings_field = "gpt_image_1_model"


class GPTImage2ActualEngine(GPTImageActualEngine):
    engine_name = "gpt_image_2"
    model_settings_field = "gpt_image_2_model"


def _size(width: int, height: int) -> str:
    if width > height:
        return "1536x1024"
    if height > width:
        return "1024x1536"
    return "1024x1024"


SUPPORTED_GPT_IMAGE_MODELS = {"gpt-image-2", "gpt-image-1.5", "gpt-image-1", "gpt-image-1-mini"}


def _resolve_model(configured_model: str) -> str:
    if configured_model in SUPPORTED_GPT_IMAGE_MODELS:
        return configured_model
    return "gpt-image-1"


def _save_response_images(response: Any, output_dir: Path, engine_name: str) -> list[str]:
    paths: list[str] = []
    data = getattr(response, "data", []) or []

    for index, item in enumerate(data):
        path = output_dir / f"{engine_name}_{index}.png"
        b64_json = getattr(item, "b64_json", None)
        if not b64_json:
            continue
        path.write_bytes(base64.b64decode(b64_json))
        paths.append(path.as_posix())

    if not paths:
        raise T2IEngineUnavailableError("OpenAI image response did not include b64_json image data.")

    return paths
