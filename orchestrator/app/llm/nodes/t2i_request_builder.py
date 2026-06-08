"""Build T2I requests from rendered marketing prompts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from orchestrator.app.graph.state import MarketingState
from orchestrator.app.llm.metadata_builders import build_t2i_request_metadata
from orchestrator.app.t2i.schemas import T2IRequest


def t2i_request_builder_node(state: MarketingState) -> dict[str, Any]:
    prompt_render_output = state.get("prompt_render_output") or {}
    metadata = build_t2i_request_metadata(state, prompt_render_output)
    metadata.update({
        "source_asset_id": state.get("source_asset_id"),
        "reference_asset_id": state.get("reference_asset_id"),
    })
    input_image_paths = [path for path in [state.get("source_image_path")] if path]
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
