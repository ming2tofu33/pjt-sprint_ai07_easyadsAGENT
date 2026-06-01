"""Deterministic GenerationJob execution bridge."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest, GenerationJobResponse
from orchestrator.app.generation_jobs.service import (
    get_generation_job,
    mark_generation_job_done,
    mark_generation_job_failed,
    mark_generation_job_running,
)

OUTPUTS_ROOT = Path("data") / "outputs"


def get_generation_job_output_dir(job_id: str) -> Path:
    if not job_id.startswith("job_") or ".." in job_id or "/" in job_id or "\\" in job_id:
        raise ValueError("invalid generation job id")
    path = OUTPUTS_ROOT / job_id
    resolved_outputs = OUTPUTS_ROOT.resolve()
    resolved_path = path.resolve()
    if resolved_path != resolved_outputs and resolved_outputs not in resolved_path.parents:
        raise ValueError("generation job output path escaped outputs root")
    return path


def execute_generation_job_immediate(job_id: str, request: GenerationJobCreateRequest) -> GenerationJobResponse:
    job = get_generation_job(job_id)
    if not job:
        raise ValueError("generation job was not found")

    try:
        mark_generation_job_running(job_id, stage="rendering")
        output_dir = get_generation_job_output_dir(job_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        background_path = output_dir / "background_0.png"
        final_path = output_dir / "final_0.png"
        metadata_path = output_dir / "metadata.json"
        prompt_path = output_dir / "prompt.json"
        validation_path = output_dir / "validation.json"

        _write_mock_images(background_path, final_path, request)
        _write_json(
            metadata_path,
            {
                "schema_version": "generation_result_mock_v1",
                "job_id": job_id,
                "engine": "mock",
                "render_mode": "deterministic_mock",
                "requested_run_mode": request.run_mode,
                "effective_run_mode": "mock_immediate",
                "execution_mode": "deterministic_mock",
            },
        )
        _write_json(prompt_path, {"user_input_preview": " ".join(request.user_input.split())[:120]})
        _write_json(validation_path, {"overall_pass": True, "checks": ["mock_artifacts_written"]})

        result_payload = {
            "schema_version": "generation_result_mock_v1",
            "job_id": job_id,
            "output_dir": _as_posix(output_dir),
            "background_image_path": _as_posix(background_path),
            "final_image_path": _as_posix(final_path),
            "metadata_path": _as_posix(metadata_path),
            "prompt_path": _as_posix(prompt_path),
            "validation_path": _as_posix(validation_path),
            "has_text_overlay": True,
            "engine": "mock",
            "render_mode": "deterministic_mock",
            "download_url": None,
        }
        done = mark_generation_job_done(
            job_id,
            result_payload=result_payload,
            output_path=_as_posix(final_path),
            metadata={
                "requested_run_mode": request.run_mode,
                "effective_run_mode": "mock_immediate",
                "execution_mode": "deterministic_mock",
            },
        )
        if not done:
            raise ValueError("generation job was not found")
        return done
    except Exception as exc:
        failed = mark_generation_job_failed(
            job_id,
            {
                "error_code": "generation_job_execution_failed",
                "message": "Generation job mock execution failed.",
                "detail": str(exc),
            },
            metadata={"execution_mode": "deterministic_mock_failed"},
        )
        if failed:
            return failed
        raise


def _write_mock_images(background_path: Path, final_path: Path, request: GenerationJobCreateRequest) -> None:
    width, height = 1024, 1024
    image = Image.new("RGB", (width, height), "#F6F2EA")
    draw = ImageDraw.Draw(image)
    for y in range(height):
        color = (246, max(210, 242 - y // 20), max(190, 234 - y // 18))
        draw.line([(0, y), (width, y)], fill=color)
    image.save(background_path)

    final = image.copy()
    draw = ImageDraw.Draw(final)
    draw.rectangle((96, 760, 928, 920), fill="#111827")
    label = request.ad_format or "mock_ad"
    draw.text((128, 800), f"EasyAds Mock Result - {label}", fill="#FFFFFF")
    draw.text((128, 850), "deterministic mock output", fill="#FDE68A")
    final.save(final_path)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _as_posix(path: Path) -> str:
    return path.as_posix()
