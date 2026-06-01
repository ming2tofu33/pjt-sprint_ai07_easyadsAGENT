"""Deterministic GenerationJob execution bridge."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from orchestrator.app.artifacts.service import (
    build_result_artifact_payload,
    ensure_job_output_dir,
    get_job_output_dir,
    write_json_artifact,
)
from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest, GenerationJobResponse
from orchestrator.app.generation_jobs.service import (
    get_generation_job,
    mark_generation_job_done,
    mark_generation_job_failed,
    mark_generation_job_running,
)

def get_generation_job_output_dir(job_id: str) -> Path:
    return get_job_output_dir(job_id)


def execute_generation_job_immediate(job_id: str, request: GenerationJobCreateRequest) -> GenerationJobResponse:
    job = get_generation_job(job_id)
    if not job:
        raise ValueError("generation job was not found")

    try:
        mark_generation_job_running(job_id, stage="rendering")
        output_dir = ensure_job_output_dir(job_id)

        background_path = output_dir / "background_0.png"
        final_path = output_dir / "final_0.png"
        metadata_path = output_dir / "metadata.json"
        prompt_path = output_dir / "prompt.json"
        validation_path = output_dir / "validation.json"
        copy_path = output_dir / "copy.json"
        layout_path = output_dir / "layout.json"
        render_result_path = output_dir / "render_result.json"

        _write_mock_images(background_path, final_path, request)
        prompt_summary = {"user_input_preview": " ".join(request.user_input.split())[:120]}
        validation_summary = {"overall_pass": True, "checks": ["mock_artifacts_written"]}
        copy_summary = {
            "schema_version": "mock_copy_v1",
            "headline": "EasyAds Mock Result",
            "subcopy": "deterministic mock output",
            "cta": "미리보기",
        }
        layout_summary = {
            "schema_version": "mock_layout_v1",
            "canvas": {"width": 1024, "height": 1024},
            "reserved_text_areas": [],
        }
        render_summary = {"schema_version": "mock_render_result_v1", "rendered_slot_count": 2, "warnings": []}
        write_json_artifact(
            metadata_path,
            {
                "schema_version": "result_artifact_metadata_v1",
                "job_id": job_id,
                "engine": "mock",
                "render_mode": "deterministic_mock",
                "requested_run_mode": request.run_mode,
                "effective_run_mode": "mock_immediate",
                "execution_mode": "deterministic_mock",
            },
        )
        write_json_artifact(prompt_path, prompt_summary)
        write_json_artifact(validation_path, validation_summary)
        write_json_artifact(copy_path, copy_summary)
        write_json_artifact(layout_path, layout_summary)
        write_json_artifact(render_result_path, render_summary)

        result_payload = build_result_artifact_payload(
            job_id=job_id,
            background_image_path=background_path,
            final_image_path=final_path,
            metadata_path=metadata_path,
            prompt_path=prompt_path,
            validation_path=validation_path,
            copy_path=copy_path,
            layout_path=layout_path,
            render_result_path=render_result_path,
            prompt_summary=prompt_summary,
            validation_summary=validation_summary,
            copy_summary=copy_summary,
            layout_summary=layout_summary,
            has_text_overlay=True,
            engine="mock",
            render_mode="deterministic_mock",
        ).model_dump(mode="json")
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

def _as_posix(path: Path) -> str:
    return path.as_posix()
