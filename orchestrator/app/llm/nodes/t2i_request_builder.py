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
    reference_style_profile = state.get("reference_style_profile")
    product_preserve_spec = state.get("product_preserve_spec")
    selected_reference_template = state.get("selected_reference_template")
    reference_template_selection = state.get("reference_template_selection")
    template_style_hint = (reference_template_selection or {}).get("style_profile_hint") or {}
    current_brief = state.get("current_brief") or {}
    vision_pipeline_enabled = bool(
        state.get("source_image_path")
        or state.get("reference_image_path")
        or state.get("vision_pipeline_results")
        or reference_style_profile
        or product_preserve_spec
        or selected_reference_template
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
        "engine": state.get("engine"),
        "requested_engine": prompt_render_output.get("engine") or state.get("engine"),
        "render_profile": state.get("render_profile"),
        "render_text_in_image": False,
        "text_overlay_pending": bool(state.get("text_overlay_pending", True)),
        "tlfp_enabled": bool(state.get("image_prompt_spec")),
        "vision_pipeline_enabled": vision_pipeline_enabled,
        "source_image_path": state.get("source_image_path"),
        "reference_image_path": state.get("reference_image_path"),
        "reference_style_profile": reference_style_profile,
        "product_preserve_spec": product_preserve_spec,
        "selected_reference_template_id": state.get("selected_reference_template_id"),
        "selected_reference_template": selected_reference_template,
        "reference_template_selection": reference_template_selection,
        "selected_channel_id": state.get("selected_channel_id") or current_brief.get("selected_channel_id"),
        "selected_tone": state.get("selected_tone") or current_brief.get("selected_tone"),
        "custom_direction": state.get("custom_direction") or current_brief.get("custom_direction"),
        "reference_template_style_keywords": template_style_hint.get("style_keywords"),
        "reference_template_color_palette": template_style_hint.get("color_palette"),
        "reference_template_layout_hint": template_style_hint.get("layout_hint"),
        "reference_template_typography_hint": template_style_hint.get("typography_hint"),
        "source_node": "t2i_request_builder",
    }
    input_image_paths = [path for path in [state.get("source_image_path")] if path]
    if input_image_paths:
        metadata["input_image_paths"] = input_image_paths
    job_id = str(state.get("job_id") or "unknown-job")
    request = T2IRequest(
        prompt=prompt_render_output["positive_prompt"],
        input_image_paths=input_image_paths,
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
