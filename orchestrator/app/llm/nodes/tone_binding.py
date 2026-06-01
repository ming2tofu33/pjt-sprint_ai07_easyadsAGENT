"""Deterministic copy tone binding node."""

from __future__ import annotations

from typing import Any

from orchestrator.app.graph.state import MarketingState, context_to_model
from orchestrator.app.llm.copy_tone import get_copy_tone_profile
from orchestrator.app.llm.metadata_builders import build_tone_binding_metadata
from orchestrator.app.llm.node_runner import run_structured_node
from orchestrator.app.schemas.llm_marketing import ToneBindingOutput


FORBIDDEN_CLAIMS = [
    "입력에 없는 전화번호 생성 금지",
    "입력에 없는 주소 생성 금지",
    "입력에 없는 가격 생성 금지",
    "입력에 없는 할인율 생성 금지",
    "입력에 없는 행사 기간 생성 금지",
    "과장 표현 금지: 전국 1등, 최고, 무조건, 100% 보장",
]

CHANNEL_RULES = {
    "instagram_feed": "짧고 감성적인 문장 우선",
    "instagram_story": "짧은 headline + CTA 우선",
    "flyer": "정보 밀도 높게, 가격/기간/연락처가 있으면 별도 line으로 분리",
    "banner": "클릭 유도 CTA 중심",
    "product_detail": "설명형/섹션형 문장 허용",
}


def tone_binding_node(state: MarketingState) -> dict[str, Any]:
    output, llm_metadata = run_structured_node(
        state,
        node_name="tone_binding",
        output_schema=ToneBindingOutput,
        prompt=build_tone_binding_prompt(state),
        fallback_fn=lambda: build_deterministic_tone_binding_output(state),
        risk_level="low",
        confidence=0.6,
        latency_budget="interactive",
        metadata=build_tone_binding_metadata(state),
    )
    if not isinstance(output, ToneBindingOutput):
        output = build_deterministic_tone_binding_output(state)
        llm_metadata = {**llm_metadata, "fallback_used": True, "fallback_reason": "invalid_tone_binding_output"}
    output = output.model_copy(
        update={
            "metadata": {
                **output.metadata,
                "source_node": "tone_binding",
                "llm_metadata": llm_metadata,
            }
        }
    )
    return {
        "tone_binding_output": output.model_dump(),
        "current_brief": {**state.get("current_brief", {}), "tone_binding_ready": True},
        "model_selections": state.get("model_selections", []),
        "llm_call_results": state.get("llm_call_results", []),
        "status": "binding_tone",
    }


def build_deterministic_tone_binding_output(state: MarketingState) -> ToneBindingOutput:
    context = context_to_model(state.get("context"))
    ad_format = (state.get("ad_format_spec") or {}).get("ad_format", "instagram_feed")
    tone = get_copy_tone_profile(context.business_type, context.target_persona)
    return ToneBindingOutput(
        tone_profile=str(tone.get("voice", "friendly_clear")),
        copy_constraints=["no_hallucinated_contact", "no_unprovided_discount", "no_unprovided_period"],
        recommended_copy_mode=state.get("copy_generation_mode") or "auto_pilot",
        forbidden_claims=FORBIDDEN_CLAIMS,
        channel_copy_rules=[CHANNEL_RULES.get(ad_format, "간결한 benefit-first 문장 우선")],
        typography_hint=context.brand_tone,
        metadata={"business_type": context.business_type, "ad_format": ad_format, "tone_profile": tone},
    )


def build_tone_binding_prompt(state: MarketingState) -> str:
    metadata = build_tone_binding_metadata(state)
    return (
        "Create a structured ToneBindingOutput for Korean advertising copy policy. "
        f"metadata_contract={metadata}. "
        "Return only fields that match ToneBindingOutput. "
        "Do not write final ad copy. "
        "Do not invent phone numbers, addresses, prices, discounts, or event periods."
    )
