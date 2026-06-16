"""Poster component schemas for Phase 1 PoC."""

from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from orchestrator.app.schemas.text_layout import NormalizedBBox


class PosterComponent(BaseModel):
    """A generic component block for poster rendering."""
    type: Literal["headline_block", "subcopy_block", "footer_panel", "speech_bubble", "icon_feature_list", "memo_card", "decorative_sticker"]
    bbox: NormalizedBBox
    content: Any
    style: dict[str, Any] = Field(default_factory=dict)
    z_index: int = 10


class PosterLayoutSpec(BaseModel):
    """A layout specification containing a list of poster components."""
    schema_version: Literal["1.0"] = "1.0"
    spec_id: str = Field(default_factory=lambda: f"poster_layout_{uuid4().hex}")
    canvas_width: int = Field(..., ge=1)
    canvas_height: int = Field(..., ge=1)
    components: list[PosterComponent] = Field(default_factory=list)
