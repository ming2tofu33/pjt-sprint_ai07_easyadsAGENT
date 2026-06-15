"""Graph node for GPT Image 2 native typography single-shot generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from orchestrator.app.graph.state import read_model
from orchestrator.app.llm.native_copy_policy import mark_image_call_completed, mark_image_call_started, reserve_image_call
from orchestrator.app.schemas.native_creative import NativeCreativePromptPackage, NativeGenerationBudget
from orchestrator.app.t2i.engines.gpt_image_2 import GPTImage2ActualEngine


def gpt_image_2_native_single_shot_node(state: dict[str, Any]) -> dict[str, Any]:
    package = read_model(state, "native_creative_prompt_package", NativeCreativePromptPackage)
    budget = read_model(state, "native_generation_budget", NativeGenerationBudget)
    reserved = reserve_image_call(budget)
    if reserved.status == "uncertain":
        return {"native_generation_budget": reserved.model_dump(), "native_generation_status": "manual_review"}
    started = mark_image_call_started(reserved)
    output_dir = Path(str(state.get("output_dir") or "data/outputs/gpt_image2_native_single_shot_v1_actual")) / str(state.get("case_id") or state.get("job_id") or "native_case")
    output = GPTImage2ActualEngine().generate_native_single_shot(prompt_package=package, output_dir=output_dir)
    completed = mark_image_call_completed(started)
    return {
        "native_generation_budget": completed.model_dump(),
        "native_generation_result": output,
        "native_generation_status": "generated",
    }
