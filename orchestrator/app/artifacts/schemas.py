"""Result artifact contract schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ResultArtifactAssetRef(BaseModel):
    asset_id: str | None = None
    kind: str | None = None
    storage_provider: str | None = None
    bucket: str | None = None
    object_key: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    width: int | None = None
    height: int | None = None
    public_url: str | None = None
    final_image_url: str | None = None
    download_url: str | None = None
    preview_url: str | None = None
    url_mode: str | None = None
    signed_url_expires_at: str | None = None
    public_serving: bool | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


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
    final_asset_id: str | None = None
    background_asset_id: str | None = None
    thumbnail_asset_id: str | None = None
    copy_visual_preview_asset_id: str | None = None
    storage_provider: str | None = None
    bucket: str | None = None
    object_key: str | None = None
    url_mode: str | None = None
    signed_url_expires_at: str | None = None
    assets: dict[str, ResultArtifactAssetRef] = Field(default_factory=dict)
    prompt_summary: dict[str, Any] = Field(default_factory=dict)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    copy_summary: dict[str, Any] = Field(default_factory=dict)
    layout_summary: dict[str, Any] = Field(default_factory=dict)
    has_text_overlay: bool = False
    engine: str = "mock"
    render_mode: str = "deterministic_mock"

