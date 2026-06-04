"""Modal request/result schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ModalT2IRequest(BaseModel):
    job_id: str
    thread_id: str | None = None
    workspace_id: str
    run_mode: str
    engine: str
    prompt: str
    negative_prompt: str | None = None
    width: int = 1024
    height: int = 1024
    num_images: int = 1
    seed: int | None = None
    model_name: str | None = None
    model_version: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModalSubmitResult(BaseModel):
    submitted: bool
    modal_call_id: str | None = None
    provider_job_id: str | None = None
    status: Literal["submitted", "blocked", "failed"]
    message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModalPollResult(BaseModel):
    status: Literal["pending", "running", "succeeded", "failed", "canceled", "unknown"]
    modal_call_id: str
    image_b64: str | None = None
    image_bytes: bytes | None = None
    mime_type: str | None = "image/png"
    filename: str = "final_0.png"
    result_payload: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
