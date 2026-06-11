"""Option suggester LLM node for dynamically generating context options."""

from __future__ import annotations

from typing import Any

from orchestrator.app.core.config import _get_env
from orchestrator.app.graph.state import MarketingState
from orchestrator.app.llm.node_runner import run_structured_node
from orchestrator.app.llm.settings import get_llm_settings
from orchestrator.app.schemas.llm_marketing import OptionQuestion
from orchestrator.app.schemas.option_suggestion import OptionSuggestionOutput


ALLOWED_OPTION_LLM_PLANS = {"economic", "premium", "internal_benchmark"}


def suggest_options(
    state: MarketingState, field: str, static_question: OptionQuestion
) -> tuple[OptionSuggestionOutput | None, dict[str, Any]]:
    if not should_attempt_option_suggester(state):
        return None, {"llm_attempted": False, "fallback_used": True, "fallback_reason": "option_suggester_not_enabled"}
    
    metadata = build_option_suggester_metadata(state, field)
    prompt = build_option_suggester_prompt(state, field, static_question)
    
    output, llm_metadata = run_structured_node(
        state,
        node_name="option_suggester",
        output_schema=OptionSuggestionOutput,
        prompt=prompt,
        fallback_fn=lambda: None,
        risk_level="low",
        confidence=0.4,
        latency_budget="interactive",
        metadata=metadata,
    )
    
    if not isinstance(output, OptionSuggestionOutput):
        return None, {**llm_metadata, "fallback_used": True, "fallback_reason": "invalid_option_suggester_output"}
        
    return output, llm_metadata


def should_attempt_option_suggester(state: MarketingState) -> bool:
    plan = str(state.get("user_plan") or "free")
    settings = get_llm_settings()
    if plan in ALLOWED_OPTION_LLM_PLANS:
        return settings.enable_api_call is True
    if plan == "free":
        return (
            _get_env("EASYADS_FREE_USE_LOCAL", "") == "1"
            and bool(settings.local_llm_base_url)
            and bool(settings.local_llm_model)
        )
    return False


def build_option_suggester_prompt(state: MarketingState, field: str, static_question: OptionQuestion) -> str:
    user_input = state.get("user_input") or ""
    context = state.get("context") or {}
    
    # Format existing context
    context_lines = []
    for k, v in context.items():
        if k != "extra" and v:
            context_lines.append(f"- {k}: {v}")
    context_str = "\n".join(context_lines) if context_lines else "None provided yet."
    
    static_labels = [opt.label for opt in static_question.options if opt.value != "custom"]
    static_labels_str = ", ".join(static_labels)
    
    return f"""You are helping a Korean small-business owner create an advertisement.
They said: "{user_input}"

Known context so far:
{context_str}

We need to ask them about: {field}
Question: {static_question.question}

Current static options: [{static_labels_str}]

Suggest 2-4 additional context-specific options that would be relevant
for THIS particular business. Each option needs:
- label: concise Korean text (≤ 40 chars), natural for a chip button
- value: ASCII snake_case slug (e.g. "summer_drink", "hair_coloring")

Do NOT duplicate any of the existing static options.
Do NOT suggest "직접 입력" or "custom".
Return OptionSuggestionOutput with confidence 0.0-1.0.
"""

def build_option_suggester_metadata(state: MarketingState, field: str) -> dict[str, Any]:
    return {
        "node": "option_suggester",
        "target_field": field,
        "user_plan": state.get("user_plan"),
    }
