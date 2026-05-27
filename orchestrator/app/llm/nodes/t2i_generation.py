"""Mock T2I generation node for the marketing graph."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from orchestrator.app.graph.state import MarketingState
from orchestrator.app.schemas.llm_marketing import ArtifactRef, GeneratedImageCandidate
from orchestrator.app.t2i.schemas import T2IRequest
from orchestrator.app.t2i.service import generate_image_v1


def t2i_generation_node(state: MarketingState) -> dict[str, Any]:
    request = T2IRequest(**(state.get("t2i_request") or {}))
    metadata = {
        **request.metadata,
        "job_id": state.get("job_id"),
        "thread_id": state.get("thread_id"),
        "engine_override": "mock",
        "source_node": "t2i_generation",
    }
    result = generate_image_v1(
        prompt=request.prompt,
        negative_prompt=request.negative_prompt,
        engine_preference="mock",
        width=request.width,
        height=request.height,
        seed=request.seed,
        num_images=1,
        output_dir=request.output_dir,
        metadata=metadata,
    )
    candidates = [
        GeneratedImageCandidate(
            image_id=f"{state.get('job_id')}_candidate_{index}",
            image_path=path,
            width=result.width,
            height=result.height,
            engine="mock",
            seed=result.seed,
            latency_ms=result.latency_ms,
            metadata={"source_node": "t2i_generation", "text_overlay_pending": True},
        ).model_dump()
        for index, path in enumerate(result.image_paths)
    ]
    artifacts = [
        ArtifactRef(
            artifact_id=f"{state.get('job_id')}_image_{index}",
            artifact_type="mock_background",
            path=path,
            label=Path(path).name,
            metadata={"engine": "mock", "text_overlay_pending": True},
        ).model_dump()
        for index, path in enumerate(result.image_paths)
    ]
    return {
        "t2i_result": result.model_dump(),
        "candidates": candidates,
        "artifact_refs": artifacts,
        "final_image_path": result.image_paths[0] if result.image_paths else None,
        "status": "done" if not result.error else "failed",
        "error_message": result.error,
    }
