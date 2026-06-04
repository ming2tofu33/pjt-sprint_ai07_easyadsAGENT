"""EasyAds Modal T2I worker.

The first deployed worker is intentionally a lightweight deterministic image
generator. It validates the Railway -> Modal -> R2 path before heavier SD/FLUX
model code is enabled.
"""

from __future__ import annotations

import base64
import io
import time
from typing import Any

import modal


APP_NAME = "easyads-t2i"

image = modal.Image.debian_slim(python_version="3.12").pip_install("Pillow==12.2.0")
app = modal.App(APP_NAME, image=image)


@app.function(timeout=300)
def generate_image(payload: dict[str, Any]) -> dict[str, Any]:
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
