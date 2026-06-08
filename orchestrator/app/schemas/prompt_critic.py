"""Structured prompt critic and rewrite proposal schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


PromptIssueCode = Literal[
    "weak_business_fit",
    "weak_subject_hierarchy",
    "weak_commercial_realism",
    "insufficient_text_safe_area",
    "visual_clutter",
    "fake_text_risk",
    "fake_logo_risk",
    "tacky_style_risk",
    "weak_reference_alignment",
    "model_adapter_mismatch",
    "unsafe_rewrite_request",
]
PromptIssueSeverity = Literal["info", "warning", "critical"]


class PromptCriticIssue(BaseModel):
    # forbid 유지(안전 가드): prompt_critic이 render_text_in_image 등 spec-override 필드를 밀어넣어
    # TLFP no-text 불변식을 깨는 것을 막는다(test_prompt_critic_schema_rejects_spec_override_fields).
    # 모델이 stray 필드를 붙이면 의도적으로 전체 critique를 폐기(fail-closed)→원본 프롬프트 유지. fix.md #16.
    model_config = ConfigDict(extra="forbid")
    code: PromptIssueCode
    severity: PromptIssueSeverity
    target: str | None = None
    message: str
    suggested_action: str | None = None


class PromptRewriteProposal(BaseModel):
    # forbid 유지(안전 가드): prompt_critic이 render_text_in_image 등 spec-override 필드를 밀어넣어
    # TLFP no-text 불변식을 깨는 것을 막는다(test_prompt_critic_schema_rejects_spec_override_fields).
    # 모델이 stray 필드를 붙이면 의도적으로 전체 critique를 폐기(fail-closed)→원본 프롬프트 유지. fix.md #16.
    model_config = ConfigDict(extra="forbid")
    add_fragments: list[str] = Field(default_factory=list)
    remove_fragments: list[str] = Field(default_factory=list)
    replace_fragments: dict[str, str] = Field(default_factory=dict)
    rewritten_prompt: str | None = None


class PromptCriticOutput(BaseModel):
    # forbid 유지(안전 가드): prompt_critic이 render_text_in_image 등 spec-override 필드를 밀어넣어
    # TLFP no-text 불변식을 깨는 것을 막는다(test_prompt_critic_schema_rejects_spec_override_fields).
    # 모델이 stray 필드를 붙이면 의도적으로 전체 critique를 폐기(fail-closed)→원본 프롬프트 유지. fix.md #16.
    model_config = ConfigDict(extra="forbid")
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    issues: list[PromptCriticIssue] = Field(default_factory=list)
    rewrite: PromptRewriteProposal = Field(default_factory=PromptRewriteProposal)
    preserve_no_text_policy: bool = True
    preserve_reference_alignment: bool = True
    preserve_business_context: bool = True
    warnings: list[str] = Field(default_factory=list)
    source: str = "prompt_critic_llm"
