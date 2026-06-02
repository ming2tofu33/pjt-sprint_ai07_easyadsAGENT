"""Deterministic GenerationJob execution bridge."""

from __future__ import annotations

from pathlib import Path
from shutil import copyfile

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
from orchestrator.app.t2i.engines.base import T2IGenerationInput
from orchestrator.app.t2i.engines.registry import get_t2i_engine
from orchestrator.app.t2i.execution import TEXT_FREE_NEGATIVE_PROMPT, build_generation_job_prompt, prompt_summary
from orchestrator.app.t2i.settings import T2IEngineNotEnabledError, T2IEngineUnavailableError

_EFFECTIVE_RUN_MODE_BY_ENGINE = {
    "gpt_image_2": "gpt_image_2_actual",
    "sd35_large": "sd35_local",
    "flux": "flux_local",
    "flux_local": "flux_local",
}


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


def execute_generation_job_t2i(job_id: str, request: GenerationJobCreateRequest, engine_name: str) -> GenerationJobResponse:
    job = get_generation_job(job_id)
    if not job:
        raise ValueError("generation job was not found")
    try:
        mark_generation_job_running(job_id, stage="t2i_running")
        output_dir = ensure_job_output_dir(job_id)
        prompt = build_generation_job_prompt(request.user_input)
        negative_prompt = TEXT_FREE_NEGATIVE_PROMPT
        engine = get_t2i_engine(engine_name)
        generation = engine.generate(
            T2IGenerationInput(
                job_id=job_id,
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=1024,
                height=1024,
                num_images=1,
                output_dir=output_dir.as_posix(),
                metadata={
                    "requested_run_mode": request.run_mode,
                    "render_text_in_image": False,
                    "must_not_include_text": True,
                },
            )
        )
        if not generation.image_paths:
            raise T2IEngineUnavailableError(f"{engine_name} did not return an image.")

        background_path = output_dir / "background_0.png"
        final_path = output_dir / "final_0.png"
        _copy_generated_image(Path(generation.image_paths[0]), background_path)
        _copy_generated_image(background_path, final_path)

        metadata_path = output_dir / "metadata.json"
        prompt_path = output_dir / "prompt.json"
        validation_path = output_dir / "validation.json"
        prompt_data = prompt_summary(prompt, negative_prompt, engine_name)
        validation_summary = {"overall_pass": True, "checks": ["t2i_image_saved"], "engine": engine_name}
        write_json_artifact(prompt_path, prompt_data)
        write_json_artifact(validation_path, validation_summary)
        write_json_artifact(
            metadata_path,
            {
                "schema_version": "t2i_actual_metadata_v1",
                "job_id": job_id,
                "engine": engine_name,
                "requested_run_mode": request.run_mode,
                "effective_run_mode": _effective_run_mode(engine_name),
                "execution_mode": "t2i_actual",
                "latency_ms": generation.latency_ms,
                "render_text_in_image": False,
                "must_not_include_text": True,
                "engine_metadata": _safe_engine_metadata(generation.metadata),
            },
        )
        result_payload = build_result_artifact_payload(
            job_id=job_id,
            background_image_path=background_path,
            final_image_path=final_path,
            metadata_path=metadata_path,
            prompt_path=prompt_path,
            validation_path=validation_path,
            prompt_summary=prompt_data,
            validation_summary=validation_summary,
            has_text_overlay=False,
            engine=engine_name,
            render_mode="t2i_actual",
        ).model_dump(mode="json")
        done = mark_generation_job_done(
            job_id,
            result_payload=result_payload,
            output_path=_as_posix(final_path),
            metadata={
                "requested_run_mode": request.run_mode,
                "effective_run_mode": _effective_run_mode(engine_name),
                "execution_mode": "t2i_actual",
                "engine": engine_name,
                "engine_preference": engine_name,
                "t2i_engine": engine_name,
                "render_text_in_image": False,
                "must_not_include_text": True,
            },
        )
        if not done:
            raise ValueError("generation job was not found")
        return done
    except T2IEngineNotEnabledError as exc:
        return _mark_t2i_failed(job_id, "t2i_engine_not_enabled", str(exc), engine_name, request.run_mode)
    except T2IEngineUnavailableError as exc:
        return _mark_t2i_failed(job_id, "t2i_engine_unavailable", str(exc), engine_name, request.run_mode)
    except Exception as exc:
        return _mark_t2i_failed(job_id, "t2i_engine_unavailable", "T2I generation failed.", engine_name, request.run_mode, detail=str(exc))


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


def _copy_generated_image(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)

    source_resolved = source.resolve()
    destination_resolved = destination.resolve()

    if source_resolved == destination_resolved:
        return

    copyfile(source, destination)


def _safe_engine_metadata(metadata: dict) -> dict:
    blocked = {"api_key", "openai_api_key", "hf_token", "huggingface_token", "token"}
    return {key: value for key, value in metadata.items() if key.lower() not in blocked}


def _mark_t2i_failed(
    job_id: str,
    error_code: str,
    message: str,
    engine_name: str,
    run_mode: str,
    detail: str | None = None,
) -> GenerationJobResponse:
    failed = mark_generation_job_failed(
        job_id,
        {"error_code": error_code, "message": message, "detail": detail},
        metadata={
            "requested_run_mode": run_mode,
            "effective_run_mode": _effective_run_mode(engine_name),
            "execution_mode": "t2i_actual_failed",
            "engine": engine_name,
            "engine_preference": engine_name,
            "t2i_engine": engine_name,
        },
    )
    if not failed:
        raise ValueError("generation job was not found")
    return failed


def _as_posix(path: Path) -> str:
    return path.as_posix()


def _effective_run_mode(engine_name: str) -> str:
    return _EFFECTIVE_RUN_MODE_BY_ENGINE.get(engine_name, engine_name)
