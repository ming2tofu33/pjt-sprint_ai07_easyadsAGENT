"""Guarded OpenAI GPT-image engine lanes."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from time import perf_counter
from typing import Any

from PIL import Image

from orchestrator.app.schemas.native_creative import NativeCreativePromptPackage
from orchestrator.app.t2i.engines.base import T2IGenerationInput, T2IGenerationOutput
from orchestrator.app.t2i.native_output_normalizer import normalize_native_output
from orchestrator.app.t2i.settings import (
    T2IEngineUnavailableError,
    get_openai_api_key,
    load_t2i_settings,
    require_t2i_enabled,
)


def _is_production_runtime() -> bool:
    from orchestrator.app.core.config import _get_env

    for key in ("EASYADS_ENV", "APP_ENV", "ENVIRONMENT", "RAILWAY_ENVIRONMENT", "RAILWAY_ENVIRONMENT_NAME", "NODE_ENV"):
        value = str(_get_env(key, "")).strip().lower()
        if value in {"production", "prod"}:
            return True
    return False


def _mock_default_engine_forbidden() -> bool:
    from orchestrator.app.core.config import _get_env

    return _is_production_runtime() and str(_get_env("T2I_DEFAULT_ENGINE", "")).strip().lower() == "mock"


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

    def generate_native_single_shot(self, *, prompt_package: NativeCreativePromptPackage, output_dir: Path) -> dict[str, Any]:
        started = perf_counter()
        settings = load_t2i_settings()
        require_t2i_enabled("gpt_image_2", settings)
        if prompt_package.image_call_limit != 1 or prompt_package.automatic_edit_allowed or prompt_package.automatic_retry_allowed:
            raise T2IEngineUnavailableError("Native single-shot prompt package violates image call policy.")
        from orchestrator.app.core.config import _get_env
        target_width = int(prompt_package.target_width or prompt_package.native_width or 1024)
        target_height = int(prompt_package.target_height or prompt_package.native_height or 1024)
        if str(_get_env("T2I_DEFAULT_ENGINE", "")).lower() == "mock":
            if _mock_default_engine_forbidden():
                raise T2IEngineUnavailableError("mock_engine_forbidden_in_production")
            output_dir.mkdir(parents=True, exist_ok=True)
            final_path = output_dir / "final_native_image.png"
            provider_path = output_dir / "provider_native_image.png"
            Image.new("RGB", (target_width, target_height), "#E5E7EB").save(provider_path)
            normalization = normalize_native_output(
                source_path=provider_path,
                target_width=target_width,
                target_height=target_height,
                output_path=final_path,
            )
            sha = _sha256(final_path)
            return {
                "provider": "mock",
                "model": "mock",
                "api_operation": "generate",
                "image_call_count": 1,
                "edit_call_count": 0,
                "retry_call_count": 0,
                "max_retries": 0,
                "request_id": "mock_req_1",
                "image_path": final_path.as_posix(),
                "provider_image_path": provider_path.as_posix(),
                "output_sha256": sha,
                "width": target_width,
                "height": target_height,
                "provider_width": target_width,
                "provider_height": target_height,
                "output_width": target_width,
                "output_height": target_height,
                "normalization_applied": normalization.normalization_applied,
                "normalization_mode": normalization.fit_mode,
                "crop_box": normalization.crop_box,
                "format": "png",
                "latency_ms": int((perf_counter() - started) * 1000),
                "prompt_sha256": prompt_package.prompt_sha256,
            }

        try:
            from openai import OpenAI  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise T2IEngineUnavailableError("OpenAI SDK is unavailable.") from exc

        output_dir.mkdir(parents=True, exist_ok=True)
        from orchestrator.app.t2i.settings import get_openai_api_key
        api_key = get_openai_api_key()
        client = OpenAI(api_key=api_key, max_retries=0)
        response = client.images.generate(
            model="gpt-image-2",
            prompt=prompt_package.final_prompt,
            size=_size(prompt_package.native_width or 1024, prompt_package.native_height or 1024),
            n=1,
        )
        image_paths = _save_response_images(response, output_dir, "native")
        source = Path(image_paths[0])
        provider_path = output_dir / "provider_native_image.png"
        if source.resolve() != provider_path.resolve():
            source.replace(provider_path)
        provider_width, provider_height = _image_size(provider_path)
        final_path = output_dir / "final_native_image.png"
        normalization = normalize_native_output(
            source_path=provider_path,
            target_width=target_width,
            target_height=target_height,
            output_path=final_path,
        )
        width, height = _image_size(final_path)
        if (width, height) != (target_width, target_height):
            raise T2IEngineUnavailableError("native_output_dimension_mismatch")
        return {
            "provider": "openai",
            "model": "gpt-image-2",
            "api_operation": "generate",
            "image_call_count": 1,
            "edit_call_count": 0,
            "retry_call_count": 0,
            "max_retries": 0,
            "request_id": getattr(response, "id", None),
            "image_path": final_path.as_posix(),
            "provider_image_path": provider_path.as_posix(),
            "output_sha256": normalization.output_sha256,
            "width": width,
            "height": height,
            "provider_width": provider_width,
            "provider_height": provider_height,
            "output_width": width,
            "output_height": height,
            "normalization_applied": normalization.normalization_applied,
            "normalization_mode": normalization.fit_mode,
            "crop_box": normalization.crop_box,
            "format": "png",
            "latency_ms": int((perf_counter() - started) * 1000),
            "prompt_sha256": prompt_package.prompt_sha256,
        }


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size
