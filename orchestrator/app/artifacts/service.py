"""Safe artifact path and payload helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orchestrator.app.artifacts.schemas import ResultArtifactPayload


OUTPUTS_ROOT = Path("data") / "outputs"


def get_job_output_dir(job_id: str) -> Path:
    if not job_id.startswith("job_") or ".." in job_id or "/" in job_id or "\\" in job_id or Path(job_id).is_absolute():
        raise ValueError("invalid generation job id")
    path = OUTPUTS_ROOT / job_id
    root = OUTPUTS_ROOT.resolve()
    resolved = path.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("generation job output path escaped outputs root")
    return path


def ensure_job_output_dir(job_id: str) -> Path:
    output_dir = get_job_output_dir(job_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def write_json_artifact(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_result_artifact_payload(
    job_id: str,
    background_image_path: Path,
    final_image_path: Path,
    metadata_path: Path,
    prompt_path: Path,
    validation_path: Path,
    copy_path: Path | None = None,
    layout_path: Path | None = None,
    render_result_path: Path | None = None,
    prompt_summary: dict[str, Any] | None = None,
    validation_summary: dict[str, Any] | None = None,
    copy_summary: dict[str, Any] | None = None,
    layout_summary: dict[str, Any] | None = None,
    has_text_overlay: bool = True,
    engine: str = "mock",
    render_mode: str = "deterministic_mock",
) -> ResultArtifactPayload:
    output_dir = get_job_output_dir(job_id)
    return ResultArtifactPayload(
        job_id=job_id,
        output_dir=output_dir.as_posix(),
        background_image_path=background_image_path.as_posix(),
        final_image_path=final_image_path.as_posix(),
        metadata_path=metadata_path.as_posix(),
        prompt_path=prompt_path.as_posix(),
        validation_path=validation_path.as_posix(),
        copy_path=copy_path.as_posix() if copy_path else None,
        layout_path=layout_path.as_posix() if layout_path else None,
        render_result_path=render_result_path.as_posix() if render_result_path else None,
        download_path=final_image_path.as_posix(),
        download_url=None,
        final_image_url=None,
        prompt_summary=prompt_summary or {},
        validation_summary=validation_summary or {},
        copy_summary=copy_summary or {},
        layout_summary=layout_summary or {},
        has_text_overlay=has_text_overlay,
        engine=engine,
        render_mode=render_mode,
    )
