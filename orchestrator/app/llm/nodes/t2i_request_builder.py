"""Build T2I requests from rendered marketing prompts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from orchestrator.app.graph.state import MarketingState, write_model
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
    positive_prompt = prompt_render_output["positive_prompt"]
    negative_prompt = prompt_render_output.get("negative_prompt") or ""
    seed = None
    patch = state.get("regeneration_patch") or {}
    patch_items = patch.get("patches") if isinstance(patch, dict) else {}
    for item in (patch_items or {}).values():
        if not isinstance(item, dict):
            continue
        if item.get("target") == "image_prompt":
            constraints = item.get("addNegativeConstraints") or []
            if constraints:
                negative_prompt = _append_terms(negative_prompt, constraints)
            if item.get("simplifyBackground"):
                positive_prompt = _append_terms(positive_prompt, ["clean simple background", "reduced visual clutter"])
            if item.get("strengthenBusinessCues"):
                positive_prompt = _append_terms(positive_prompt, ["clear business-relevant visual cues"])
            if item.get("changeSeed"):
                seed = _derive_seed(job_id)
        elif item.get("target") == "promptPolicy" and item.get("promptVersion"):
            metadata["prompt_policy_version"] = item.get("promptVersion")
    request = T2IRequest(
        prompt=positive_prompt,
        input_image_paths=input_image_paths,
        negative_prompt=negative_prompt,
        width=int(prompt_render_output.get("width") or 1024),
        height=int(prompt_render_output.get("height") or 1024),
        num_images=1,
        output_dir=str(Path("data") / "outputs" / job_id),
        seed=seed,
        metadata=metadata,
    )
    return {
        "t2i_request": write_model(request),
        "status": "t2i_queued",
    }


def _append_terms(text: str, terms: list[str]) -> str:
    current = str(text or "").strip()
    additions = [str(term) for term in terms if str(term) and str(term).lower() not in current.lower()]
    if not additions:
        return current
    return f"{current}, {', '.join(additions)}" if current else ", ".join(additions)


def _derive_seed(job_id: str) -> int:
    import hashlib

    return int(hashlib.sha256(job_id.encode("utf-8")).hexdigest()[:8], 16)
