"""Prompt renderer graph node."""

from __future__ import annotations

from typing import Any

from orchestrator.app.graph.state import MarketingState
from orchestrator.app.llm.prompt_renderer import render_prompt_for_engine, render_prompt_spec_for_engine
from orchestrator.app.schemas.llm_marketing import ImagePrompt


SUPPORTED_RENDER_ENGINES = {"mock", "sd35_large", "flux", "gpt_image_2"}


def prompt_renderer_node(state: MarketingState) -> dict[str, Any]:
    ad_format_spec = state.get("ad_format_spec") or {}
    layout_spec = state.get("layout_spec") or {}
    image_prompt_spec = state.get("image_prompt_spec")
    engine = state.get("engine") if state.get("engine") in SUPPORTED_RENDER_ENGINES else "mock"
    # Local engines are still placeholders; only the API image lane is wired for real generation.
    effective_engine = "gpt_image_2" if engine == "gpt_image_2" else "mock"
    metadata = {
        "requested_engine": engine,
        "ad_format": ad_format_spec.get("ad_format"),
        "platform": ad_format_spec.get("platform"),
        "aspect_ratio": ad_format_spec.get("aspect_ratio"),
        "copy_space": layout_spec.get("copy_space"),
        "render_text_in_image": False,
    }
    if image_prompt_spec:
        output = render_prompt_spec_for_engine(
            image_prompt_spec=image_prompt_spec,
            engine=effective_engine,
            render_profile=state.get("render_profile", "balanced"),
            metadata=metadata,
        )
    else:
        image_prompt = ImagePrompt(**(state.get("image_prompt") or {}))
        output = render_prompt_for_engine(
            image_prompt=image_prompt,
            engine=effective_engine,
            width=int(ad_format_spec.get("width") or 1024),
            height=int(ad_format_spec.get("height") or 1024),
            render_profile=state.get("render_profile", "balanced"),
            metadata=metadata,
        )
    return {
        "engine": effective_engine,
        "prompt_render_output": output.model_dump(),
        "status": "rendering_prompt",
    }
