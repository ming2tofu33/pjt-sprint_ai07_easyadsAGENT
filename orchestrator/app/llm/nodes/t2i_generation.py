"""T2I generation node for the marketing graph."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from orchestrator.app.graph.state import MarketingState, read_model
from orchestrator.app.schemas.llm_marketing import ArtifactRef, GeneratedImageCandidate
from orchestrator.app.t2i.schemas import T2IRequest
from orchestrator.app.t2i.service import generate_image_v1
from orchestrator.app.usage import service as usage_service


logger = logging.getLogger(__name__)


def t2i_generation_node(state: MarketingState) -> dict[str, Any]:
    request = read_model(state, "t2i_request", T2IRequest)
    requested_engine = request.metadata.get("requested_engine") or request.metadata.get("engine") or state.get("engine")
    metadata = {
        **request.metadata,
        "job_id": state.get("job_id"),
        "thread_id": state.get("thread_id"),
        "requested_engine": requested_engine,
        "source_node": "t2i_generation",
    }
    result = generate_image_v1(
        prompt=request.prompt,
        input_image_paths=request.input_image_paths,
        negative_prompt=request.negative_prompt,
        engine_preference=requested_engine,
        width=request.width,
        height=request.height,
        seed=request.seed,
        num_images=1,
        output_dir=request.output_dir,
        metadata=metadata,
    )
    _record_t2i_usage(state, result)
    modal_pending = (
        result.metadata.get("execution_backend") == "modal"
        and result.metadata.get("modal_call_id_present") is True
        and not result.image_paths
        and not result.error
    )
    candidates = [
        GeneratedImageCandidate(
            image_id=f"{state.get('job_id')}_candidate_{index}",
            image_path=path,
            width=result.width,
            height=result.height,
            engine=result.engine,
            seed=result.seed,
            latency_ms=result.latency_ms,
            metadata={"source_node": "t2i_generation", "text_overlay_pending": True},
        ).model_dump()
        for index, path in enumerate(result.image_paths)
    ]
    artifacts = [
        ArtifactRef(
            artifact_id=f"{state.get('job_id')}_image_{index}",
            artifact_type="generated_background",
            path=path,
            label=Path(path).name,
            metadata={"engine": result.engine, "text_overlay_pending": True},
        ).model_dump()
        for index, path in enumerate(result.image_paths)
    ]
    return {
        "t2i_result": result.model_dump(),
        "candidates": candidates,
        "artifact_refs": artifacts,
        "final_image_path": result.image_paths[0] if result.image_paths else None,
        "status": "modal_running" if modal_pending else ("done" if not result.error else "failed"),
        "error_message": result.error,
    }


def _record_t2i_usage(state: MarketingState, result) -> None:
    if result.error or not result.image_paths or result.engine == "mock":
        return
    workspace_id = state.get("workspace_id")
    if not workspace_id:
        return
    try:
        usage_service.record_t2i_usage(
            workspace_id=str(workspace_id),
            engine=result.engine,
            model_name=(result.metadata or {}).get("model") or result.engine,
            image_count=len(result.image_paths),
            plan=str(state.get("user_plan") or "free"),
            created_by=state.get("user_id"),
            thread_id=state.get("usage_thread_db_id"),
            job_id=state.get("usage_job_db_id"),
            width=result.width,
            height=result.height,
            quality=(result.metadata or {}).get("quality"),
            request_mode=(result.metadata or {}).get("requested_run_mode") or (result.metadata or {}).get("execution_mode"),
            provider_request_id=(result.metadata or {}).get("provider_request_id"),
            attempt_index=(result.metadata or {}).get("generation_attempt"),
            generation_status="succeeded",
        )
    except Exception:
        logger.warning("Failed to record T2I usage.", exc_info=True)
