"""GPT-image-2 T2I engine wrapper with cost-safe default behavior."""

from __future__ import annotations

import base64
import time
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from orchestrator.app.core.config import get_t2i_settings
from orchestrator.app.t2i.base import BaseT2IEngine
from orchestrator.app.t2i.schemas import T2IRequest, T2IResult


class GPTImage2Engine(BaseT2IEngine):
    """OpenAI image API wrapper that only calls the API when explicitly allowed."""

    name = "gpt_image_2"

    def __init__(self, allow_api_call: bool = False) -> None:
        self.allow_api_call = allow_api_call
        self._loaded = False

    def load(self) -> None:
        self._loaded = True

    def unload(self) -> None:
        self._loaded = False

    def is_loaded(self) -> bool:
        return self._loaded

    def health(self) -> dict[str, Any]:
        settings = get_t2i_settings()
        sdk_available = _is_openai_sdk_available()
        model = _resolve_model(settings.gpt_image_model)
        if not settings.openai_api_key:
            return {"available": False, "loaded": self.is_loaded(), "reason": "OPENAI_API_KEY missing", "sdk_available": sdk_available}
        if not sdk_available:
            return {"available": False, "loaded": self.is_loaded(), "reason": "openai package missing", "sdk_available": False}
        return {
            "available": True,
            "loaded": self.is_loaded(),
            "reason": None,
            "sdk_available": True,
            "model": model,
            "configured_model": settings.gpt_image_model,
            "api_call_allowed": self.allow_api_call,
        }

    def generate(self, request: T2IRequest) -> T2IResult:
        started = time.perf_counter()
        settings = get_t2i_settings()
        if not settings.openai_api_key:
            return self._error_result(request, started, "OPENAI_API_KEY missing")
        if not self.allow_api_call:
            return self._error_result(request, started, "API call disabled; pass allow_api_call=True or --include-api")
        try:
            from openai import OpenAI  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on optional SDK
            return self._error_result(request, started, f"openai package missing: {exc}")

        try:  # pragma: no cover - real API is opt-in and not used in tests
            self.load()
            output_dir = Path(request.output_dir or settings.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            client = OpenAI(api_key=settings.openai_api_key)
            size = _resolve_size(request.width, request.height)
            model = _resolve_model(settings.gpt_image_model)
            input_image_paths = [str(path) for path in request.input_image_paths if str(path).strip()]
            if input_image_paths:
                missing_paths = [path for path in input_image_paths if not Path(path).exists()]
                if missing_paths:
                    return self._error_result(request, started, f"input image not found: {missing_paths[0]}")
                with ExitStack() as stack:
                    image_files = [stack.enter_context(Path(path).open("rb")) for path in input_image_paths]
                    response = client.images.edit(
                        image=image_files,
                        model=model,
                        prompt=request.prompt,
                        size=size,
                        quality=_map_quality(request.quality),
                        n=request.num_images,
                        input_fidelity="high",
                    )
                api_operation = "edit"
            else:
                response = client.images.generate(
                    model=model,
                    prompt=request.prompt,
                    size=size,
                    quality=_map_quality(request.quality),
                    n=request.num_images,
                )
                api_operation = "generate"
            image_paths = _save_openai_images(response, output_dir)
            width, height = _size_to_dimensions(size, request.width, request.height)
            return T2IResult(
                engine=self.name,
                image_paths=image_paths,
                seed=request.seed,
                latency_ms=int((time.perf_counter() - started) * 1000),
                width=width,
                height=height,
                prompt=request.prompt,
                negative_prompt=request.negative_prompt,
                metadata={
                    **request.metadata,
                    "model": model,
                    "configured_model": settings.gpt_image_model,
                    "requested_size": f"{request.width}x{request.height}",
                    "api_size": size,
                    "api_call": True,
                    "api_operation": api_operation,
                    "input_image_paths": input_image_paths,
                    "input_fidelity": "high" if input_image_paths else None,
                },
                error=None,
            )
        except Exception as exc:  # pragma: no cover - real API is opt-in and not used in tests
            return self._error_result(request, started, str(exc))

    def _error_result(self, request: T2IRequest, started: float, error: str) -> T2IResult:
        return T2IResult(
            engine=self.name,
            image_paths=[],
            seed=request.seed,
            latency_ms=int((time.perf_counter() - started) * 1000),
            width=request.width,
            height=request.height,
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            metadata={**request.metadata, "api_call": False},
            error=error,
        )


def _is_openai_sdk_available() -> bool:
    try:
        import openai  # noqa: F401
    except Exception:
        return False
    return True


def _map_quality(quality: str) -> str:
    return {"draft": "low", "standard": "medium", "high": "high"}.get(quality, "medium")


SUPPORTED_GPT_IMAGE_MODELS = {"gpt-image-2", "gpt-image-1.5", "gpt-image-1", "gpt-image-1-mini"}
DEFAULT_GPT_IMAGE_MODEL = "gpt-image-1"


def _resolve_model(configured_model: str) -> str:
    if configured_model in SUPPORTED_GPT_IMAGE_MODELS:
        return configured_model
    return DEFAULT_GPT_IMAGE_MODEL


def _resolve_size(width: int, height: int) -> str:
    if width > height:
        return "1536x1024"
    if height > width:
        return "1024x1536"
    return "1024x1024"


def _size_to_dimensions(size: str, fallback_width: int, fallback_height: int) -> tuple[int, int]:
    try:
        width, height = size.split("x", 1)
        return int(width), int(height)
    except ValueError:
        return fallback_width, fallback_height


def _save_openai_images(response: Any, output_dir: Path) -> list[str]:
    image_paths: list[str] = []
    for index, item in enumerate(getattr(response, "data", []) or []):
        path = output_dir / f"gpt_image_2_{index}.png"
        b64_json = getattr(item, "b64_json", None)
        if b64_json:
            path.write_bytes(base64.b64decode(b64_json))
            image_paths.append(str(path))
            continue
        url = getattr(item, "url", None)
        if url:
            path.with_suffix(".url.txt").write_text(url, encoding="utf-8")
            image_paths.append(str(path.with_suffix(".url.txt")))
    return image_paths
