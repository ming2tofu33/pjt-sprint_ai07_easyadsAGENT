"""Suggest-candidates copy branch nodes."""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from orchestrator.app.graph.state import MarketingState, context_to_model
from orchestrator.app.llm.node_runner import run_structured_node
from orchestrator.app.schemas.llm_marketing import CopyCandidate, CopyCandidateListOutput, MarketingCopy


def copy_candidate_generation_node(state: MarketingState) -> dict[str, Any]:
    output, llm_metadata = run_structured_node(
        state,
        node_name="copy_candidate_generation",
        output_schema=CopyCandidateListOutput,
        prompt=build_candidate_prompt(state),
        fallback_fn=lambda: build_rule_based_candidate_output(state),
        risk_level="medium",
        confidence=0.5,
        latency_budget="interactive",
        metadata={"prompt_summary": "copy candidate generation"},
    )
    if not isinstance(output, CopyCandidateListOutput) or not output.candidates:
        output = build_rule_based_candidate_output(state)
        llm_metadata = {**llm_metadata, "fallback_used": True, "fallback_reason": "invalid_candidate_output"}
    max_candidates = int((state.get("plan_policy") or {}).get("max_candidates") or 3)
    candidates = normalize_candidate_ids(output.candidates[: max(1, max_candidates)])
    output = CopyCandidateListOutput(
        candidates=candidates,
        recommended_candidate_id=output.recommended_candidate_id or candidates[0].id,
        metadata={**output.metadata, "source_node": "copy_candidate_generation", "llm_metadata": llm_metadata},
    )
    return {
        "copy_candidates": [candidate.model_dump() for candidate in candidates],
        "copywriting_output": output.model_dump(),
        "copy_generation_mode": "suggest_candidates",
        "copy_required": True,
        "text_overlay_pending": True,
        "model_selections": state.get("model_selections", []),
        "llm_call_results": state.get("llm_call_results", []),
        "status": "generating_copy_candidates",
    }


def build_rule_based_candidate_output(state: MarketingState) -> CopyCandidateListOutput:
    context = context_to_model(state.get("context"))
    item = context.item_or_service or "상품"
    candidates = [
        CopyCandidate(
            id="copy_1",
            headline=f"오늘 저녁, 따뜻한 {item} 한 판",
            subcopy="함께 모이기 좋은 시간",
            cta="예약 문의하기",
            tone_label="emotional",
            rationale="Warm emotional version.",
        ),
        CopyCandidate(
            id="copy_2",
            headline=f"회식은 역시 {item}",
            subcopy="든든하게 즐기는 우리 가게 대표 메뉴",
            cta="지금 예약하기",
            tone_label="direct",
            rationale="Direct benefit-first version.",
        ),
        CopyCandidate(
            id="copy_3",
            headline="오늘 자리, 미리 잡아두세요",
            subcopy=f"{item} 모임은 편하게 예약하고 즐기세요",
            cta="예약 문의하기",
            tone_label="cta",
            rationale="Action-oriented version.",
        ),
    ]
    return CopyCandidateListOutput(candidates=candidates, recommended_candidate_id="copy_1", metadata={"source_node": "copy_candidate_generation", "fallback": "rule_based"})


def normalize_candidate_ids(candidates: list[CopyCandidate]) -> list[CopyCandidate]:
    normalized: list[CopyCandidate] = []
    for index, candidate in enumerate(candidates, start=1):
        normalized.append(candidate.model_copy(update={"id": candidate.id or f"copy_{index}"}))
    return normalized


def build_candidate_prompt(state: MarketingState) -> str:
    context = context_to_model(state.get("context"))
    tone = state.get("tone_binding_output") or {}
    return (
        "Generate structured Korean ad copy candidates. "
        f"business_type={context.business_type}, item_or_service={context.item_or_service}, "
        f"promotion_goal={context.promotion_goal}, brand_tone={context.brand_tone}, "
        f"forbidden_claims={tone.get('forbidden_claims', [])}. "
        "Do not invent phone numbers, addresses, prices, discounts, or event periods."
    )


def copy_candidate_selection_interrupt_node(state: MarketingState) -> dict[str, Any]:
    candidates = list(state.get("copy_candidates", []))
    payload = {
        "type": "copy_candidate_selection",
        "job_id": state["job_id"],
        "thread_id": state["thread_id"],
        "candidates": candidates,
        "recommended_candidate_id": "copy_1",
    }
    resume_payload = interrupt(payload)
    return {"copy_selection": resume_payload, "status": "waiting_copy_selection"}


def state_update_selected_copy_node(state: MarketingState) -> dict[str, Any]:
    selection = state.get("copy_selection") or {}
    selected_id = selection.get("selected_copy_id") or "copy_1"
    candidates = list(state.get("copy_candidates", []))
    candidate = next((item for item in candidates if item.get("id") == selected_id), None)
    warnings: list[str] = []
    if candidate is None:
        candidate = next((item for item in candidates if item.get("id") == "copy_1"), None)
        selected_id = "copy_1"
        warnings.append("Invalid selected_copy_id; recommended candidate fallback applied.")
    if candidate is None:
        return {"status": "failed", "error_message": "No copy candidate available for selection."}
    copy = MarketingCopy(
        headline=candidate["headline"],
        subcopy=candidate.get("subcopy"),
        cta=candidate.get("cta"),
        hashtags=candidate.get("hashtags", []),
        metadata={"selected_copy_id": selected_id, "warnings": warnings, "source_node": "state_update_selected_copy"},
    )
    return {
        "marketing_copy": copy.model_dump(),
        "selected_copy_id": selected_id,
        "copy_required": True,
        "text_overlay_pending": True,
        "status": "applying_selected_copy",
    }
