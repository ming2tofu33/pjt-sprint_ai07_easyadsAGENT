"""Base contracts for guarded T2I engines."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class T2IGenerationInput(BaseModel):
    job_id: str
    prompt: str
    negative_prompt: str | None = None
    width: int = 1024
    height: int = 1024
    num_images: int = Field(default=1, ge=1, le=4)
    seed: int | None = None
    output_dir: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class T2IGenerationOutput(BaseModel):
    engine: str
    image_paths: list[str] = Field(default_factory=list)
    latency_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseT2IEngine(Protocol):
    engine_name: str

    def generate(self, request: T2IGenerationInput) -> T2IGenerationOutput:
        ...

