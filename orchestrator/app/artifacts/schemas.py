"""Result artifact contract schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ResultArtifactPayload(BaseModel):
    schema_version: Literal["result_artifact_v1"] = "result_artifact_v1"
    job_id: str
    output_dir: str | None = None
    background_image_path: str | None = None
    final_image_path: str | None = None
    metadata_path: str | None = None
    prompt_path: str | None = None
    validation_path: str | None = None
    copy_path: str | None = None
    layout_path: str | None = None
    render_result_path: str | None = None
    download_path: str | None = None
    download_url: str | None = None
    final_image_url: str | None = None
    prompt_summary: dict[str, Any] = Field(default_factory=dict)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    copy_summary: dict[str, Any] = Field(default_factory=dict)
    layout_summary: dict[str, Any] = Field(default_factory=dict)
    has_text_overlay: bool = False
    engine: str = "mock"
    render_mode: str = "deterministic_mock"

