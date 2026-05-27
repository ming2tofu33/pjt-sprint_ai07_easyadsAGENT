"""Prompt renderer graph node."""

from __future__ import annotations

from typing import Any

from orchestrator.app.graph.state import MarketingState
from orchestrator.app.llm.prompt_renderer import render_prompt_for_engine
from orchestrator.app.schemas.llm_marketing import ImagePrompt


SUPPORTED_RENDER_ENGINES = {"mock", "sd35_large", "flux", "gpt_image_2"}


def prompt_renderer_node(state: MarketingState) -> dict[str, Any]:
    image_prompt = ImagePrompt(**(state.get("image_prompt") or {}))
    ad_format_spec = state.get("ad_format_spec") or {}
    layout_spec = state.get("layout_spec") or {}
    engine = state.get("engine") if state.get("engine") in SUPPORTED_RENDER_ENGINES else "mock"
    # The 3rd LLM graph milestone renders through mock only; real engines remain disabled here.
    effective_engine = "mock"
    output = render_prompt_for_engine(
        image_prompt=image_prompt,
        engine=effective_engine,
        width=int(ad_format_spec.get("width") or 1024),
        height=int(ad_format_spec.get("height") or 1024),
        render_profile=state.get("render_profile", "balanced"),
        metadata={
            "requested_engine": engine,
            "ad_format": ad_format_spec.get("ad_format"),
            "platform": ad_format_spec.get("platform"),
            "aspect_ratio": ad_format_spec.get("aspect_ratio"),
            "copy_space": layout_spec.get("copy_space"),
            "render_text_in_image": False,
        },
    )
    return {
        "engine": effective_engine,
        "prompt_render_output": output.model_dump(),
        "status": "rendering_prompt",
    }
