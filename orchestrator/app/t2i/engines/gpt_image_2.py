"""Guarded GPT-image-2 engine lane."""

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

class GPTImage2ActualEngine:
    engine_name = "gpt_image_2"

    def generate(self, request: T2IGenerationInput) -> T2IGenerationOutput:
        started = perf_counter()
        settings = load_t2i_settings()
        require_t2i_enabled(self.engine_name, settings)
        try:
            from openai import OpenAI  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise T2IEngineUnavailableError("OpenAI SDK is unavailable.") from exc

        output_dir = Path(request.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        api_key = get_openai_api_key()
        client = OpenAI(api_key=api_key)
        response = client.images.generate(
            model=settings.gpt_image_model,
            prompt=request.prompt,
            size=_size(request.width, request.height),
            n=min(request.num_images, settings.max_images_per_job),
        )
        image_paths = _save_response_images(response, output_dir)
        return T2IGenerationOutput(
            engine=self.engine_name,
            image_paths=image_paths,
            latency_ms=int((perf_counter() - started) * 1000),
            metadata={"api_call": True, "model": settings.gpt_image_model, **request.metadata},
        )


def _size(width: int, height: int) -> str:
    if width > height:
        return "1536x1024"
    if height > width:
        return "1024x1536"
    return "1024x1024"


def _save_response_images(response: Any, output_dir: Path) -> list[str]:
    paths: list[str] = []
    data = getattr(response, "data", []) or []

    for index, item in enumerate(data):
        path = output_dir / f"gpt_image_2_{index}.png"
        b64_json = getattr(item, "b64_json", None)
        if not b64_json:
            continue
        path.write_bytes(base64.b64decode(b64_json))
        paths.append(path.as_posix())

    if not paths:
        raise T2IEngineUnavailableError("GPT-image-2 response did not include b64_json image data.")

    return paths

