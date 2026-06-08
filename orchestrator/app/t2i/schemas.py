"""Request and result contracts for T2I API wrapper engines."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


T2IEngineName = Literal["mock", "gpt_image_1", "gpt_image_2", "sd35_large", "flux", "flux2_klein_4b"]


class T2IRequest(BaseModel):
    """Common request sent to all text-to-image engines."""

    prompt: str = Field(..., min_length=1)
    input_image_paths: list[str] = Field(default_factory=list)
    negative_prompt: str = ""
    width: int = Field(default=1024, ge=256, le=2048)
    height: int = Field(default=1024, ge=256, le=2048)
    seed: int | None = None
    num_images: int = Field(default=1, ge=1, le=4)
    steps: int | None = Field(default=None, ge=1, le=80)
    guidance_scale: float | None = Field(default=None, ge=0.0, le=20.0)
    quality: Literal["draft", "standard", "high"] = "standard"
    output_dir: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class T2IResult(BaseModel):
    """Common result returned by all text-to-image engines."""

    engine: T2IEngineName
    image_paths: list[str] = Field(default_factory=list)
    seed: int | None = None
    latency_ms: int = Field(..., ge=0)
    width: int = Field(..., ge=1)
    height: int = Field(..., ge=1)
    prompt: str
    negative_prompt: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
