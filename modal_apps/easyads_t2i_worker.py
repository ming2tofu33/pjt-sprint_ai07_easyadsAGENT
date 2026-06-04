"""EasyAds Modal T2I workers.

``generate_image`` stays as the cheap deterministic smoke worker. The real
FLUX worker is exposed as ``generate_flux_schnell_image`` so production can
switch to GPU inference without making every connectivity smoke test allocate
a GPU.
"""

from __future__ import annotations

import base64
import io
import os
import time
from typing import Any

import modal


APP_NAME = "easyads-t2i"
FLUX_MODEL_ID = "black-forest-labs/FLUX.1-schnell"
SD35_MODEL_ID = "stabilityai/stable-diffusion-3.5-large"
FLUX_REAL_RUN_MODES = {"flux_schnell_real", "flux_real", "flux_modal_real"}
SD35_REAL_RUN_MODES = {"sd35_large_real", "sd35_real", "sd35_modal_real"}
FLUX_GPU = os.getenv("EASYADS_MODAL_FLUX_GPU", "L40S")
SD35_GPU = os.getenv("EASYADS_MODAL_SD35_GPU", FLUX_GPU)
try:
    FLUX_TIMEOUT_SECONDS = int(os.getenv("EASYADS_MODAL_FLUX_TIMEOUT_SECONDS", "900"))
except ValueError:
    FLUX_TIMEOUT_SECONDS = 900
try:
    SD35_TIMEOUT_SECONDS = int(os.getenv("EASYADS_MODAL_SD35_TIMEOUT_SECONDS", "1800"))
except ValueError:
    SD35_TIMEOUT_SECONDS = 1800
FLUX_VOLUME_NAME = os.getenv("EASYADS_MODAL_FLUX_VOLUME_NAME", "easyads-hf-cache")

mock_image = modal.Image.debian_slim(python_version="3.12").pip_install("Pillow==12.2.0")
diffusers_image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "Pillow==12.2.0",
    "torch>=2.5.1,<3",
    "diffusers>=0.36.0,<0.37",
    "transformers>=4.46.0,<5",
    "accelerate>=1.1.0,<2",
    "safetensors>=0.6.0,<1",
    "huggingface_hub>=0.26.0,<1",
    "sentencepiece>=0.2.0,<1",
    "protobuf>=5,<7",
)
hf_cache_volume = modal.Volume.from_name(FLUX_VOLUME_NAME, create_if_missing=True)
hf_secret = modal.Secret.from_name("easyads-hf-token")
app = modal.App(APP_NAME, image=mock_image)
_flux_pipeline_cache: dict[str, Any] = {}
_sd35_pipeline_cache: dict[str, Any] = {}


@app.function(image=mock_image, timeout=300)
def generate_image(payload: dict[str, Any]) -> dict[str, Any]:
    if _is_real_flux_request(payload) or _is_real_sd35_request(payload):
        return _failed_result(
            payload,
            error_code="modal_function_mismatch",
            message=(
                "Real image requests must use a model-specific Modal function, "
                "not generate_image."
            ),
        )

    started = time.perf_counter()
    image_b64 = _render_mock_png_base64(payload)
    duration_ms = int((time.perf_counter() - started) * 1000)
    return {
        "status": "succeeded",
        "modal_call_id": _current_modal_call_id(payload),
        "image_b64": image_b64,
        "mime_type": "image/png",
        "filename": "final_0.png",
        "result_payload": {
            "schema_version": "result_artifact_v1",
            "engine": str(payload.get("engine") or "modal_mock"),
            "render_mode": "modal_mock_worker",
            "prompt_summary": {
                "prompt_preview": _preview_text(payload.get("prompt")),
                "run_mode": payload.get("run_mode"),
            },
            "validation_summary": {
                "overall_pass": True,
                "checks": ["modal_worker_invoked", "mock_image_rendered"],
            },
        },
        "usage": {
            "gpu_type": "none",
            "gpu_seconds": 0,
            "duration_ms": duration_ms,
            "model_name": payload.get("model_name") or payload.get("engine") or "modal_mock",
            "cost_usd": 0,
        },
        "metadata": {
            "worker": "easyads_t2i_worker",
            "worker_mode": "mock",
        },
    }


@app.function(
    image=diffusers_image,
    gpu=FLUX_GPU,
    timeout=FLUX_TIMEOUT_SECONDS,
    startup_timeout=FLUX_TIMEOUT_SECONDS,
    secrets=[hf_secret],
    volumes={"/cache": hf_cache_volume},
    env={
        "HF_HOME": "/cache/huggingface",
        "HF_HUB_CACHE": "/cache/huggingface/hub",
        "HF_HUB_ENABLE_HF_TRANSFER": "0",
    },
)
def generate_flux_schnell_image(payload: dict[str, Any]) -> dict[str, Any]:
    if not _is_real_flux_request(payload):
        return _failed_result(
            payload,
            error_code="modal_real_flux_run_mode_required",
            message="Real FLUX worker requires run_mode=flux_schnell_real or params.render_mode=flux_schnell.",
        )

    started = time.perf_counter()
    try:
        image_b64 = _render_flux_schnell_png_base64(payload)
    except Exception as exc:
        return _failed_result(
            payload,
            error_code="modal_flux_generation_failed",
            message="FLUX.1-schnell generation failed.",
            detail=_safe_exception_detail(exc),
        )

    duration_ms = int((time.perf_counter() - started) * 1000)
    options = _flux_generation_options(payload)
    model_id = _flux_model_id(payload)
    return {
        "status": "succeeded",
        "modal_call_id": _current_modal_call_id(payload),
        "image_b64": image_b64,
        "mime_type": "image/png",
        "filename": "final_0.png",
        "result_payload": {
            "schema_version": "result_artifact_v1",
            "engine": "flux",
            "render_mode": "modal_flux_schnell",
            "model_name": model_id,
            "prompt_summary": {
                "prompt_preview": _preview_text(payload.get("prompt")),
                "run_mode": payload.get("run_mode"),
            },
            "generation_params": {
                "width": options["width"],
                "height": options["height"],
                "num_inference_steps": options["num_inference_steps"],
                "guidance_scale": options["guidance_scale"],
                "max_sequence_length": options["max_sequence_length"],
                "seed": options["seed"],
            },
            "validation_summary": {
                "overall_pass": True,
                "checks": ["modal_worker_invoked", "flux_schnell_rendered"],
            },
        },
        "usage": {
            "gpu_type": FLUX_GPU,
            "gpu_seconds": duration_ms / 1000,
            "duration_ms": duration_ms,
            "model_name": model_id,
            "cost_usd": None,
        },
        "metadata": {
            "worker": "easyads_t2i_worker",
            "worker_mode": "flux_schnell",
        },
    }


@app.function(
    image=diffusers_image,
    gpu=SD35_GPU,
    timeout=SD35_TIMEOUT_SECONDS,
    startup_timeout=SD35_TIMEOUT_SECONDS,
    secrets=[hf_secret],
    volumes={"/cache": hf_cache_volume},
    env={
        "HF_HOME": "/cache/huggingface",
        "HF_HUB_CACHE": "/cache/huggingface/hub",
        "HF_HUB_ENABLE_HF_TRANSFER": "0",
    },
)
def generate_sd35_large_image(payload: dict[str, Any]) -> dict[str, Any]:
    if not _is_real_sd35_request(payload):
        return _failed_result(
            payload,
            error_code="modal_real_sd35_run_mode_required",
            message="Real SD3.5 worker requires run_mode=sd35_large_real or params.render_mode=sd35_large.",
        )

    started = time.perf_counter()
    try:
        image_b64 = _render_sd35_large_png_base64(payload)
    except Exception as exc:
        return _failed_result(
            payload,
            error_code="modal_sd35_generation_failed",
            message="SD3.5 Large generation failed.",
            detail=_safe_exception_detail(exc),
        )

    duration_ms = int((time.perf_counter() - started) * 1000)
    options = _sd35_generation_options(payload)
    model_id = _sd35_model_id(payload)
    return {
        "status": "succeeded",
        "modal_call_id": _current_modal_call_id(payload),
        "image_b64": image_b64,
        "mime_type": "image/png",
        "filename": "final_0.png",
        "result_payload": {
            "schema_version": "result_artifact_v1",
            "engine": "sd35_large",
            "render_mode": "modal_sd35_large",
            "model_name": model_id,
            "prompt_summary": {
                "prompt_preview": _preview_text(payload.get("prompt")),
                "negative_prompt_preview": _preview_text(payload.get("negative_prompt")),
                "run_mode": payload.get("run_mode"),
            },
            "generation_params": {
                "width": options["width"],
                "height": options["height"],
                "num_inference_steps": options["num_inference_steps"],
                "guidance_scale": options["guidance_scale"],
                "seed": options["seed"],
            },
            "validation_summary": {
                "overall_pass": True,
                "checks": ["modal_worker_invoked", "sd35_large_rendered"],
            },
        },
        "usage": {
            "gpu_type": SD35_GPU,
            "gpu_seconds": duration_ms / 1000,
            "duration_ms": duration_ms,
            "model_name": model_id,
            "cost_usd": None,
        },
        "metadata": {
            "worker": "easyads_t2i_worker",
            "worker_mode": "sd35_large",
        },
    }


def _render_flux_schnell_png_base64(payload: dict[str, Any]) -> str:
    import torch

    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN is not set in Modal secret easyads-hf-token.")

    options = _flux_generation_options(payload)
    model_id = _flux_model_id(payload)
    pipe = _get_flux_pipeline(model_id, token)

    generator = None
    if options["seed"] is not None:
        generator = torch.Generator("cuda").manual_seed(options["seed"])

    image = pipe(
        prompt=str(payload.get("prompt") or ""),
        width=options["width"],
        height=options["height"],
        num_inference_steps=options["num_inference_steps"],
        guidance_scale=options["guidance_scale"],
        max_sequence_length=options["max_sequence_length"],
        generator=generator,
    ).images[0]

    output = io.BytesIO()
    image.save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


def _render_sd35_large_png_base64(payload: dict[str, Any]) -> str:
    import torch

    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN is not set in Modal secret easyads-hf-token.")

    options = _sd35_generation_options(payload)
    model_id = _sd35_model_id(payload)
    pipe = _get_sd35_pipeline(model_id, token)

    generator = None
    if options["seed"] is not None:
        generator = torch.Generator("cuda").manual_seed(options["seed"])

    image = pipe(
        prompt=str(payload.get("prompt") or ""),
        negative_prompt=str(payload.get("negative_prompt") or ""),
        width=options["width"],
        height=options["height"],
        num_inference_steps=options["num_inference_steps"],
        guidance_scale=options["guidance_scale"],
        generator=generator,
    ).images[0]

    output = io.BytesIO()
    image.save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


def _get_flux_pipeline(model_id: str, token: str):
    if model_id in _flux_pipeline_cache:
        return _flux_pipeline_cache[model_id]

    import torch
    from diffusers import FluxPipeline

    pipe = FluxPipeline.from_pretrained(model_id, torch_dtype=torch.bfloat16, token=token)
    if hasattr(pipe, "enable_model_cpu_offload"):
        pipe.enable_model_cpu_offload()
    else:
        pipe.to("cuda")
    _flux_pipeline_cache[model_id] = pipe
    try:
        hf_cache_volume.commit()
    except Exception:
        pass
    return pipe


def _get_sd35_pipeline(model_id: str, token: str):
    if model_id in _sd35_pipeline_cache:
        return _sd35_pipeline_cache[model_id]

    import torch
    from diffusers import StableDiffusion3Pipeline

    pipe = StableDiffusion3Pipeline.from_pretrained(model_id, torch_dtype=torch.float16, token=token)
    if hasattr(pipe, "enable_model_cpu_offload"):
        pipe.enable_model_cpu_offload()
    else:
        pipe.to("cuda")
    _sd35_pipeline_cache[model_id] = pipe
    try:
        hf_cache_volume.commit()
    except Exception:
        pass
    return pipe


def _render_mock_png_base64(payload: dict[str, Any]) -> str:
    from PIL import Image, ImageDraw

    width = _safe_int(payload.get("width"), 1024)
    height = _safe_int(payload.get("height"), 1024)
    width = min(max(width, 256), 1536)
    height = min(max(height, 256), 1536)

    canvas = Image.new("RGB", (width, height), "#eef2ff")
    draw = ImageDraw.Draw(canvas)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        red = int(238 - ratio * 58)
        green = int(242 - ratio * 30)
        blue = int(255 - ratio * 70)
        draw.line([(0, y), (width, y)], fill=(red, green, blue))

    margin = max(28, width // 14)
    panel_top = int(height * 0.67)
    draw.rectangle((margin, panel_top, width - margin, height - margin), fill="#111827")
    draw.text((margin + 32, panel_top + 34), "EasyAds Modal Worker", fill="#ffffff")
    draw.text((margin + 32, panel_top + 78), _preview_text(payload.get("prompt"), 80), fill="#fde68a")
    draw.text((margin + 32, panel_top + 120), str(payload.get("engine") or "modal_mock"), fill="#bfdbfe")

    output = io.BytesIO()
    canvas.save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


def _is_real_flux_request(payload: dict[str, Any]) -> bool:
    run_mode = str(payload.get("run_mode") or "").strip().lower()
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    render_mode = str(params.get("render_mode") or "").strip().lower()
    return run_mode in FLUX_REAL_RUN_MODES or render_mode in {"real_flux", "flux_schnell"}


def _is_real_sd35_request(payload: dict[str, Any]) -> bool:
    run_mode = str(payload.get("run_mode") or "").strip().lower()
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    render_mode = str(params.get("render_mode") or "").strip().lower()
    return run_mode in SD35_REAL_RUN_MODES or render_mode in {"real_sd35", "sd35_large"}


def _flux_model_id(payload: dict[str, Any]) -> str:
    value = str(payload.get("model_name") or "").strip()
    if value and value not in {"flux", "flux_local", "flux_schnell"}:
        return value
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    param_value = str(params.get("model_id") or "").strip()
    if param_value:
        return param_value
    return FLUX_MODEL_ID


def _sd35_model_id(payload: dict[str, Any]) -> str:
    value = str(payload.get("model_name") or "").strip()
    if value and value not in {"sd35_large", "sd35", "sd3.5"}:
        return value
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    param_value = str(params.get("model_id") or "").strip()
    if param_value:
        return param_value
    return SD35_MODEL_ID


def _flux_generation_options(payload: dict[str, Any]) -> dict[str, Any]:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    width = _snap_to_multiple(_safe_int(params.get("width") or payload.get("width"), 1024), 16)
    height = _snap_to_multiple(_safe_int(params.get("height") or payload.get("height"), 1024), 16)
    return {
        "width": min(max(width, 256), 1024),
        "height": min(max(height, 256), 1024),
        "num_inference_steps": min(max(_safe_int(params.get("num_inference_steps"), 4), 1), 8),
        "guidance_scale": min(max(_safe_float(params.get("guidance_scale"), 0.0), 0.0), 5.0),
        "max_sequence_length": min(max(_safe_int(params.get("max_sequence_length"), 256), 64), 512),
        "seed": _optional_int(params.get("seed") if params.get("seed") is not None else payload.get("seed")),
    }


def _sd35_generation_options(payload: dict[str, Any]) -> dict[str, Any]:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    width = _snap_to_multiple(_safe_int(params.get("width") or payload.get("width"), 1024), 16)
    height = _snap_to_multiple(_safe_int(params.get("height") or payload.get("height"), 1024), 16)
    return {
        "width": min(max(width, 512), 1024),
        "height": min(max(height, 512), 1024),
        "num_inference_steps": min(max(_safe_int(params.get("num_inference_steps"), 8), 1), 28),
        "guidance_scale": min(max(_safe_float(params.get("guidance_scale"), 4.0), 0.0), 10.0),
        "seed": _optional_int(params.get("seed") if params.get("seed") is not None else payload.get("seed")),
    }


def _failed_result(
    payload: dict[str, Any],
    *,
    error_code: str,
    message: str,
    detail: str | None = None,
) -> dict[str, Any]:
    return {
        "status": "failed",
        "modal_call_id": _current_modal_call_id(payload),
        "error": {
            "error_code": error_code,
            "message": message,
            "detail": detail,
        },
        "metadata": {
            "worker": "easyads_t2i_worker",
            "worker_mode": "error",
        },
    }


def _current_modal_call_id(payload: dict[str, Any]) -> str:
    try:
        value = modal.current_function_call_id()
    except Exception:
        value = None
    return str(value or payload.get("modal_call_id") or payload.get("job_id") or "modal_local")


def _preview_text(value: Any, max_length: int = 120) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3]}..."


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _snap_to_multiple(value: int, multiple: int) -> int:
    return max(multiple, (value // multiple) * multiple)


def _safe_exception_detail(exc: Exception) -> str:
    text = f"{type(exc).__name__}: {exc}".strip()
    for env_name in ("HF_TOKEN", "HUGGINGFACE_TOKEN", "MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET"):
        secret = os.getenv(env_name)
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return text[:500]
