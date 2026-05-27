"""Build T2I requests from rendered marketing prompts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from orchestrator.app.graph.state import MarketingState
from orchestrator.app.t2i.schemas import T2IRequest


def t2i_request_builder_node(state: MarketingState) -> dict[str, Any]:
    prompt_render_output = state.get("prompt_render_output") or {}
    context = state.get("context") or {}
    reserved_text_areas = (
        prompt_render_output.get("metadata", {}).get("reserved_text_areas")
        or (state.get("image_prompt_spec") or {}).get("reserved_text_areas")
        or (state.get("text_layout_spec") or {}).get("reserved_text_areas")
        or []
    )
    metadata = {
        "job_id": state.get("job_id"),
        "thread_id": state.get("thread_id"),
        "entry_mode": state.get("entry_mode"),
        "generation_route": state.get("generation_route"),
        "ad_format_spec": state.get("ad_format_spec"),
        "layout_spec": state.get("layout_spec"),
        "copy_spec": state.get("copy_spec"),
        "text_layout_spec": state.get("text_layout_spec"),
        "text_style_spec": state.get("text_style_spec"),
        "image_prompt_spec": state.get("image_prompt_spec"),
        "reserved_text_areas": reserved_text_areas,
        "business_type": context.get("business_type"),
        "item_or_service": context.get("item_or_service"),
        "engine": "mock",
        "requested_engine": prompt_render_output.get("engine"),
        "render_profile": state.get("render_profile"),
        "render_text_in_image": False,
        "text_overlay_pending": True,
        "tlfp_enabled": bool(state.get("image_prompt_spec")),
        "source_node": "t2i_request_builder",
    }
    job_id = str(state.get("job_id") or "unknown-job")
    request = T2IRequest(
        prompt=prompt_render_output["positive_prompt"],
        negative_prompt=prompt_render_output.get("negative_prompt") or "",
        width=int(prompt_render_output.get("width") or 1024),
        height=int(prompt_render_output.get("height") or 1024),
        num_images=1,
        output_dir=str(Path("data") / "outputs" / job_id),
        metadata=metadata,
    )
    return {
        "t2i_request": request.model_dump(),
        "status": "t2i_queued",
    }
