"""FLUX.2 Klein local smoke runner.

This script performs readiness checks by default. Actual image generation requires
both --actual and EASYADS_FLUX2_KLEIN_ACTUAL=1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from statistics import pstdev
from time import perf_counter
from typing import Any

from PIL import Image, ImageStat

from orchestrator.app.t2i.engines.base import T2IGenerationInput
from orchestrator.app.t2i.engines.flux2_klein import FLUX2_KLEIN_ENGINE, Flux2KleinEngine
from orchestrator.app.t2i.settings import load_t2i_settings


DEFAULT_PROMPT = (
    "A premium commercial advertising background for a Korean summer iced latte campaign. "
    "A clear glass of iced latte with condensation on a clean stone table, fresh citrus accents, "
    "soft natural sunlight, elegant modern cafe atmosphere, high-end product photography, realistic materials, "
    "balanced composition. Keep the upper-left area visually simple and empty for Korean advertising copy. "
    "Place the main product toward the lower-right. No text, no letters, no numbers, no logo, no watermark, "
    "no signature, no label, no UI elements. Square social media advertisement background."
)


def main() -> int:
    args = _parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "flux2_klein_smoke_result.json"
    report: dict[str, Any] = {
        "runId": f"flux2_klein_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "executedAt": datetime.now(timezone.utc).isoformat(),
        "engine": FLUX2_KLEIN_ENGINE,
        "backend": "local_diffusers",
        "actual": bool(args.actual),
        "errors": [],
        "timingsMs": {},
    }

    missing = _missing_requirements(args)
    report["missingRequirements"] = missing
    if missing:
        report["status"] = "blocked"
        _write_report(report_path, report)
        print(json.dumps({"status": "blocked", "missingRequirements": missing, "report": report_path.as_posix()}, ensure_ascii=False))
        return 2
    if not args.actual:
        report["status"] = "ready"
        _write_report(report_path, report)
        print(json.dumps({"status": "ready", "report": report_path.as_posix()}, ensure_ascii=False))
        return 0

    settings = load_t2i_settings()
    if args.cpu_offload:
        os.environ["EASYADS_T2I_FLUX2_KLEIN_CPU_OFFLOAD"] = "true"
        settings = load_t2i_settings()

    started = perf_counter()
    try:
        _reset_peak_memory()
        output = Flux2KleinEngine().generate(
            T2IGenerationInput(
                job_id="flux2_klein_local_smoke",
                prompt=args.prompt,
                width=int(args.width),
                height=int(args.height),
                num_images=1,
                seed=args.seed,
                output_dir=output_dir.as_posix(),
                metadata={"source": "flux2_klein_local_smoke"},
            )
        )
        image_path = Path(output.image_paths[0])
        validation = validate_generated_image(image_path, expected_width=args.width, expected_height=args.height)
        report.update(
            {
                "status": "success" if validation["valid"] else "failed",
                "modelId": settings.flux2_klein_model_id,
                "pipelineClass": "Flux2KleinPipeline",
                "device": settings.flux2_klein_device,
                "dtype": settings.flux2_klein_dtype,
                "cpuOffload": settings.flux2_klein_enable_cpu_offload,
                "width": args.width,
                "height": args.height,
                "steps": settings.flux2_klein_num_inference_steps,
                "guidanceScale": settings.flux2_klein_guidance_scale,
                "seed": args.seed,
                "imageValidation": validation,
                "imagePath": image_path.as_posix(),
                "engineMetadata": _redact(output.metadata),
                "vram": _vram_report(),
            }
        )
    except Exception as exc:
        report["status"] = "failed"
        report["errors"].append({"errorCode": getattr(exc, "error_code", "flux2_klein_smoke_failed"), "message": str(exc)[:500]})
    finally:
        report["timingsMs"]["total"] = int((perf_counter() - started) * 1000)
        _write_report(report_path, report)
    print(json.dumps({"status": report["status"], "report": report_path.as_posix(), "imagePath": report.get("imagePath")}, ensure_ascii=False))
    return 0 if report["status"] == "success" else 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actual", action="store_true")
    parser.add_argument("--prepare-model", action="store_true")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--output-dir", default="data/outputs/flux2_klein_local_smoke")
    parser.add_argument("--cpu-offload", action="store_true")
    return parser.parse_args()


def _missing_requirements(args: argparse.Namespace) -> list[str]:
    missing = []
    if args.actual and os.getenv("EASYADS_FLUX2_KLEIN_ACTUAL") != "1":
        missing.append("EASYADS_FLUX2_KLEIN_ACTUAL=1")
    if args.actual and os.getenv("EASYADS_ENABLE_FLUX2_KLEIN_LOCAL", "").lower() not in {"1", "true", "yes", "on"}:
        missing.append("EASYADS_ENABLE_FLUX2_KLEIN_LOCAL=true")
    settings = load_t2i_settings()
    if settings.flux2_klein_backend != "local_diffusers":
        missing.append("EASYADS_T2I_FLUX2_KLEIN_BACKEND=local_diffusers")
    try:
        import torch

        if not torch.cuda.is_available():
            missing.append("torch.cuda_available")
    except Exception:
        missing.append("torch")
    try:
        from diffusers import Flux2KleinPipeline  # noqa: F401
    except Exception:
        missing.append("diffusers.Flux2KleinPipeline")
    return missing


def validate_generated_image(image_path: Path, *, expected_width: int, expected_height: int) -> dict[str, Any]:
    result: dict[str, Any] = {"path": image_path.as_posix(), "valid": False}
    result["exists"] = image_path.exists()
    result["sizeBytes"] = image_path.stat().st_size if image_path.exists() else 0
    if not image_path.exists() or result["sizeBytes"] <= 0:
        return result
    data = image_path.read_bytes()
    result["sha256"] = hashlib.sha256(data).hexdigest()
    with Image.open(image_path) as image:
        image.verify()
    with Image.open(image_path) as image:
        image.load()
        rgb = image.convert("RGB")
        stat = ImageStat.Stat(rgb)
        result.update(
            {
                "width": rgb.width,
                "height": rgb.height,
                "format": image.format,
                "mode": rgb.mode,
                "channelMean": [round(value, 2) for value in stat.mean],
                "channelStddev": [round(value, 2) for value in stat.stddev],
                "flatImage": max(stat.stddev) < 1.0,
            }
        )
        result["valid"] = rgb.width == expected_width and rgb.height == expected_height and not result["flatImage"]
    return result


def _reset_peak_memory() -> None:
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
    except Exception:
        return


def _vram_report() -> dict[str, Any]:
    try:
        import torch

        if not torch.cuda.is_available():
            return {"gpu": "not measured", "peakAllocatedBytes": "not measured", "peakReservedBytes": "not measured"}
        return {
            "gpu": torch.cuda.get_device_name(0),
            "peakAllocatedBytes": int(torch.cuda.max_memory_allocated()),
            "peakReservedBytes": int(torch.cuda.max_memory_reserved()),
        }
    except Exception:
        return {"gpu": "not measured", "peakAllocatedBytes": "not measured", "peakReservedBytes": "not measured"}


def _redact(metadata: dict[str, Any]) -> dict[str, Any]:
    blocked = {"hf_token", "token", "authorization", "secret", "api_key"}
    return {key: ("present" if key.lower() in blocked else value) for key, value in metadata.items() if key.lower() not in blocked}


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
