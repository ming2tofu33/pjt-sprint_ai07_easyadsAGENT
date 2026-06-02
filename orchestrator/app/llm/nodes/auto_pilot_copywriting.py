"""Auto-pilot copywriting branch."""

from __future__ import annotations

from typing import Any

from orchestrator.app.graph.state import MarketingState
from orchestrator.app.llm.metadata_builders import build_copy_generation_metadata, metadata_contract_to_prompt_json
from orchestrator.app.llm.node_runner import run_structured_node
from orchestrator.app.llm.nodes.copywriting import copywriting_node
from orchestrator.app.schemas.llm_marketing import CopywritingOutput


def auto_pilot_copywriting_node(state: MarketingState) -> dict[str, Any]:
    metadata_contract = build_copy_generation_metadata(
        state,
        node_name="auto_pilot_copywriting",
        output_schema=CopywritingOutput,
    )
    output, llm_metadata = run_structured_node(
        state,
        node_name="auto_pilot_copywriting",
        output_schema=CopywritingOutput,
        prompt=build_auto_pilot_prompt(state, metadata_contract),
        fallback_fn=lambda: CopywritingOutput(**copywriting_node(state)["copywriting_output"]),
        risk_level="medium",
        confidence=0.5,
        latency_budget="interactive",
        metadata=metadata_contract,
    )
    if isinstance(output, CopywritingOutput):
        update = {
            "marketing_copy": output.marketing_copy.model_dump(),
            "copywriting_output": output.model_dump(),
            "status": "copywriting",
        }
        update["copywriting_output"]["metadata"] = {"llm_metadata": llm_metadata}
    else:
        update = copywriting_node(state)
    update["copy_required"] = True
    update["text_overlay_pending"] = True
    update["copy_generation_mode"] = "auto_pilot"
    update["model_selections"] = state.get("model_selections", [])
    update["llm_call_results"] = state.get("llm_call_results", [])
    update["current_brief"] = {
        **state.get("current_brief", {}),
        **update.get("current_brief", {}),
        "copy_generation_mode": "auto_pilot",
    }
    return update


def build_auto_pilot_prompt(state: MarketingState, metadata_contract: dict[str, Any] | None = None) -> str:
    context = state.get("context") or {}
    tone = state.get("tone_binding_output") or {}
    metadata_contract = metadata_contract or build_copy_generation_metadata(
        state,
        node_name="auto_pilot_copywriting",
        output_schema=CopywritingOutput,
    )
    return (
        "Write one structured Korean advertising copy. "
        f"context={context}, tone_binding={tone}. "
        "Do not invent phone numbers, addresses, prices, discounts, or event periods. "
        f"metadata_contract={metadata_contract_to_prompt_json(metadata_contract)}."
    )
