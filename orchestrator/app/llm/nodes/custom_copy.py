"""Custom user-provided copy branch nodes."""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from orchestrator.app.graph.state import MarketingState
from orchestrator.app.llm.copy_quality import score_copy_quality
from orchestrator.app.llm.metadata_builders import build_custom_copy_validation_metadata, build_metadata_contract_summary
from orchestrator.app.schemas.llm_marketing import CustomCopyInput, MarketingCopy


def custom_copy_input_interrupt_node(state: MarketingState) -> dict[str, Any]:
    if state.get("user_custom_headline"):
        return {"custom_copy_input": None, "status": "waiting_custom_copy_input"}
    payload = {
        "type": "custom_copy_input",
        "job_id": state["job_id"],
        "thread_id": state["thread_id"],
        "fields": [
            {
                "field": "user_custom_headline",
                "type": "text",
                "placeholder": "포스터 메인 카피를 입력해주세요 (추천: 15자 이내)",
                "required": True,
                "max_recommended_chars": 15,
            },
            {
                "field": "user_custom_subcopy",
                "type": "text",
                "placeholder": "서브 카피 또는 이벤트 상세 내용을 입력해주세요",
                "required": False,
            },
        ],
    }
    resume_payload = interrupt(payload)
    return {"custom_copy_input": resume_payload, "status": "waiting_custom_copy_input"}


def custom_copy_validation_node(state: MarketingState) -> dict[str, Any]:
    metadata_contract = build_custom_copy_validation_metadata(state)
    metadata_summary = build_metadata_contract_summary(metadata_contract)
    raw_input = state.get("custom_copy_input") or {}
    headline = state.get("user_custom_headline") or raw_input.get("user_custom_headline") or raw_input.get("headline")
    subcopy = state.get("user_custom_subcopy") or raw_input.get("user_custom_subcopy") or raw_input.get("subcopy")
    cta = raw_input.get("cta")
    if not headline or not str(headline).strip():
        return {"status": "waiting_custom_copy_input", "error_message": "user_custom_headline is required"}
    warnings = []
    if len(str(headline)) > 15:
        warnings.append("headline exceeds recommended 15 characters")
    warnings.append("custom_copy_not_rewritten")
    custom = CustomCopyInput(
        headline=str(headline),
        subcopy=subcopy,
        cta=cta,
        metadata={"warnings": warnings, "llm_metadata_summary": metadata_summary},
    )
    quality = score_copy_quality({"headline": custom.headline, "subcopy": custom.subcopy, "cta": custom.cta})
    copy = MarketingCopy(
        headline=custom.headline,
        subcopy=custom.subcopy,
        cta=custom.cta or "지금 확인하기",
        hashtags=custom.hashtags,
        metadata={
            "source_node": "custom_copy_validation",
            "warnings": warnings,
            "copy_quality": quality,
            "preserved_user_copy": True,
            "llm_metadata_summary": metadata_summary,
        },
    )
    return {
        "marketing_copy": copy.model_dump(),
        "user_custom_headline": custom.headline,
        "user_custom_subcopy": custom.subcopy,
        "copy_required": True,
        "text_overlay_pending": True,
        "status": "validating_custom_copy",
    }
