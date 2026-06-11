"""Final result payload node for TLFP graphs."""

from __future__ import annotations

from typing import Any

from orchestrator.app.graph.state import MarketingState
from orchestrator.app.schemas.text_layout import ResultPayload


def result_node(state: MarketingState) -> dict[str, Any]:
    t2i_result = state.get("t2i_result") or {}
    background_path = (t2i_result.get("image_paths") or [None])[0]
    upstream_error = t2i_result.get("error") or state.get("error_message") or "missing output path"
    no_copy = (
        state.get("copy_generation_mode") == "no_copy"
        or state.get("copy_required") is False
        or (state.get("copy_spec") or {}).get("copy_mode") == "no_copy"
    )
    if no_copy:
        output_path = background_path
        final_image_path = state.get("final_image_path") if state.get("final_image_path") != background_path else None
        has_text_overlay = False
    else:
        output_path = state.get("final_image_path")
        final_image_path = state.get("final_image_path")
        has_text_overlay = bool(output_path)

    status = "done" if output_path else "failed"
    render_result = state.get("render_result") or {}
    render_metadata = dict(render_result.get("metadata") or {})
    result_metadata = {
        "source_node": "result",
        "render_text_in_image": False,
        "tlfp_enabled": True,
        "error": None if output_path else upstream_error,
    }
    if render_metadata:
        result_metadata["render_metadata"] = render_metadata
    artifacts = list(state.get("artifact_refs") or [])
    if output_path:
        artifacts.append(
            {
                "type": "result_image",
                "path": output_path,
                "metadata": {"source": "result_node", "has_text_overlay": has_text_overlay},
            }
        )

    payload = ResultPayload(
        job_id=str(state.get("job_id") or ""),
        thread_id=str(state.get("thread_id") or ""),
        status=status,
        output_path=output_path,
        background_image_path=background_path,
        final_image_path=final_image_path,
        copy_generation_mode=state.get("copy_generation_mode"),
        has_text_overlay=has_text_overlay,
        validation_summary={
            "background": state.get("background_validation_report"),
            "safe_area": state.get("safe_area_report"),
            "readability": state.get("readability_report"),
            "final": state.get("final_validation_report"),
        },
        artifact_refs=artifacts,
        metadata=result_metadata,
    )
    return {
        "result_payload": payload.model_dump(),
        "artifact_refs": artifacts,
        "status": status,
        "error_message": None if output_path else upstream_error,
    }
