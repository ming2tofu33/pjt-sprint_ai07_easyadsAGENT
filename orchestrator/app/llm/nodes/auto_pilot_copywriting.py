"""Auto-pilot copywriting branch."""

from __future__ import annotations

from typing import Any

from orchestrator.app.graph.state import MarketingState
from orchestrator.app.llm.copy_quality_v2 import generate_copy_candidates_v2, rank_copy_candidates, select_recommended_copy
from orchestrator.app.llm.copy_fallbacks import build_message_strategy
from orchestrator.app.llm.copy_prompts import build_copy_generation_v2_prompt
from orchestrator.app.llm.copy_visual_intent import resolve_copy_visual_intent
from orchestrator.app.llm.metadata_builders import build_copy_generation_metadata, metadata_contract_to_prompt_json
from orchestrator.app.llm.node_runner import run_structured_node
from orchestrator.app.llm.nodes.copywriting import copywriting_node
from orchestrator.app.schemas.llm_marketing import CopyCandidate, CopyGenerationV2Output, CopywritingOutput, MarketingContext, MarketingCopy


def auto_pilot_copywriting_node(state: MarketingState) -> dict[str, Any]:
    metadata_contract = build_copy_generation_metadata(
        state,
        node_name="auto_pilot_copywriting",
        output_schema=CopyGenerationV2Output,
    )
    output, llm_metadata = run_structured_node(
        state,
        node_name="auto_pilot_copywriting",
        output_schema=CopyGenerationV2Output,
        prompt=build_auto_pilot_prompt(state, metadata_contract),
        fallback_fn=lambda: generate_copy_candidates_v2(state),
        risk_level="medium",
        confidence=0.5,
        latency_budget="interactive",
        metadata=metadata_contract,
    )
    if isinstance(output, CopyGenerationV2Output):
        output = select_auto_pilot_v2_output(state, output)
        update = {
            "marketing_copy": output.marketing_copy.model_dump(),
            "copywriting_output": output.model_dump(),
            "status": "copywriting",
        }
        update["copywriting_output"]["metadata"] = {"llm_metadata": llm_metadata}
    elif isinstance(output, CopywritingOutput):
        output = apply_auto_pilot_v2_quality(state, output)
        update = {
            "marketing_copy": output.marketing_copy.model_dump(),
            "copywriting_output": output.model_dump(),
            "status": "copywriting",
        }
        update["copywriting_output"]["metadata"] = {"llm_metadata": llm_metadata, "compat_copywriting_output": True}
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


def apply_auto_pilot_v2_quality(state: MarketingState, output: CopywritingOutput) -> CopywritingOutput:
    candidate = CopyCandidate(
        id="auto_1",
        headline=output.marketing_copy.headline,
        subcopy=output.marketing_copy.subcopy,
        cta=output.marketing_copy.cta,
        hashtags=output.marketing_copy.hashtags,
        angle="benefit_action_first",
        metadata={"source": "auto_pilot_llm"},
    )
    ranking = rank_copy_candidates([candidate], state=state)
    blocking_warnings = set(ranking.scorecards[0].warnings if ranking.scorecards else [])
    should_replace = bool(
        ranking.scorecards
        and ranking.scorecards[0].hard_blocked
        and (
            any(warning.startswith("wrong_domain:") for warning in blocking_warnings)
            or "generic_or_meta_phrase_detected" in blocking_warnings
            or "unsupported_fact_detected" in blocking_warnings
        )
    )
    if should_replace:
        fallback = generate_copy_candidates_v2(state)
        selected = select_recommended_copy(fallback.candidates, fallback.ranking)
        if selected is not None:
            replacement = MarketingCopy(
                headline=selected.headline,
                subcopy=selected.subcopy,
                cta=selected.cta,
                hashtags=selected.hashtags,
                metadata={
                    **output.marketing_copy.metadata,
                    "copy_quality_v2_ranking": ranking.model_dump(),
                    "copy_quality_v2_fallback_used": True,
                    "recommended_candidate_id": selected.id,
                },
            )
            return output.model_copy(update={"marketing_copy": replacement})
    metadata = {
        **output.marketing_copy.metadata,
        "copy_quality_v2_ranking": ranking.model_dump(),
        "copy_quality_v2_fallback_used": False,
    }
    return output.model_copy(update={"marketing_copy": output.marketing_copy.model_copy(update={"metadata": metadata})})


def select_auto_pilot_v2_output(state: MarketingState, output: CopyGenerationV2Output) -> CopywritingOutput:
    ranking = rank_copy_candidates(output.candidates, state=state)
    selected = select_recommended_copy(output.candidates, ranking)
    if selected is None:
        fallback = generate_copy_candidates_v2(state)
        selected = select_recommended_copy(fallback.candidates, fallback.ranking)
        ranking = fallback.ranking
    if selected is None:
        return CopywritingOutput(**copywriting_node(state)["copywriting_output"])
    copy = MarketingCopy(
        headline=selected.headline,
        subcopy=selected.subcopy,
        cta=selected.cta,
        hashtags=selected.hashtags,
        metadata={
            "source_node": "auto_pilot_copywriting",
            "selected_copy_id": selected.id,
            "copy_generation_v2": output.model_dump(),
            "copy_quality_v2_ranking": ranking.model_dump(),
        },
    )
    return CopywritingOutput(
        marketing_copy=copy,
        alternatives=[
            MarketingCopy(headline=item.headline, subcopy=item.subcopy, cta=item.cta, hashtags=item.hashtags, metadata={"candidate_id": item.id, "angle": item.angle})
            for item in output.candidates
            if item.id != selected.id
        ],
        rationale="Auto-pilot selected the highest-ranked Copy Quality Core v2 candidate.",
    )


def build_auto_pilot_prompt(state: MarketingState, metadata_contract: dict[str, Any] | None = None) -> str:
    context = _context_to_model(state.get("context"))
    strategy = build_message_strategy(context)
    intent = resolve_copy_visual_intent(context, selected_reference_template=state.get("selected_reference_template"))
    metadata_contract = metadata_contract or build_copy_generation_metadata(
        state,
        node_name="auto_pilot_copywriting",
        output_schema=CopywritingOutput,
    )
    grounded_prompt = build_copy_generation_v2_prompt(
        context=context,
        strategy=strategy,
        visual_intent=intent,
    )
    return "\n".join(
        [
            grounded_prompt,
            "Return CopyGenerationV2Output JSON. Do not use fallback or placeholder text.",
            f"metadata_contract={metadata_contract_to_prompt_json(metadata_contract)}.",
        ]
    )


def _context_to_model(context: dict[str, Any] | MarketingContext | None) -> MarketingContext:
    if isinstance(context, MarketingContext):
        return context
    if isinstance(context, dict):
        return MarketingContext(**context)
    return MarketingContext()
