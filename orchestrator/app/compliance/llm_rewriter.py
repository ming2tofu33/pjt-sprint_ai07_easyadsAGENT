"""Contextual LLM rewrite for compliance suggestions."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from orchestrator.app.compliance.schemas import (
    ComplianceFinding,
    ComplianceRewriteCandidate,
    ComplianceRewriteContext,
    ComplianceRewritePlan,
)
from orchestrator.app.llm.node_runner import run_structured_node


class ComplianceRewriteLLMOutput(BaseModel):
    candidates: list[ComplianceRewriteCandidate] = Field(default_factory=list)


class ComplianceRewriteResult(BaseModel):
    candidates: list[ComplianceRewriteCandidate] = Field(default_factory=list)
    llm_attempted: bool = False
    fallback_used: bool = False
    fallback_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComplianceRewriteAdapter(Protocol):
    def rewrite(
        self,
        *,
        original_text: str,
        finding: ComplianceFinding,
        plan: ComplianceRewritePlan,
        context: ComplianceRewriteContext,
    ) -> list[ComplianceRewriteCandidate]: ...


class ComplianceLLMRewriter:
    def __init__(self, adapter: ComplianceRewriteAdapter | None = None) -> None:
        self._adapter = adapter

    def rewrite(
        self,
        *,
        original_text: str,
        finding: ComplianceFinding,
        plan: ComplianceRewritePlan,
        context: ComplianceRewriteContext,
        state: dict[str, Any] | None,
    ) -> ComplianceRewriteResult:
        if self._adapter is not None:
            candidates = self._adapter.rewrite(
                original_text=original_text,
                finding=finding,
                plan=plan,
                context=context,
            )
            return ComplianceRewriteResult(candidates=candidates)
        if state is None:
            return ComplianceRewriteResult(fallback_used=True, fallback_reason="state_missing")

        prompt = build_compliance_rewrite_prompt(
            original_text=original_text,
            finding=finding,
            plan=plan,
            context=context,
        )
        output, metadata = run_structured_node(
            state=state,
            node_name="compliance_rewrite",
            output_schema=ComplianceRewriteLLMOutput,
            prompt=prompt,
            fallback_fn=ComplianceRewriteLLMOutput,
            risk_level="high",
            latency_budget="interactive",
            metadata={
                "rule_id": finding.rule_id,
                "field": finding.field,
                "strategy": plan.strategy,
            },
        )
        return ComplianceRewriteResult(
            candidates=output.candidates,
            llm_attempted=bool(metadata.get("llm_attempted")),
            fallback_used=bool(metadata.get("fallback_used")),
            fallback_reason=metadata.get("fallback_reason"),
            metadata=metadata,
        )


def build_compliance_rewrite_prompt(
    *,
    original_text: str,
    finding: ComplianceFinding,
    plan: ComplianceRewritePlan,
    context: ComplianceRewriteContext,
) -> str:
    return (
        "You are a Korean advertising copy compliance rewrite assistant. "
        "Return JSON only. Do not make legal judgments. Rewrite only the risky expression already detected. "
        "Preserve the product, service, business context, tone, and original intent. "
        "Do not invent new facts, numbers, rankings, guarantees, health effects, medical effects, or superiority claims. "
        "Generate 2 or 3 Korean ad copy candidates.\n"
        f"Original text: {original_text}\n"
        f"Matched risky text: {finding.matched_text}\n"
        f"Rule id: {finding.rule_id}\n"
        f"Reason: {finding.reason}\n"
        f"Rewrite strategy: {plan.strategy}\n"
        f"Rewrite instruction: {plan.instruction}\n"
        f"Safe hints: {plan.safe_hints}\n"
        f"Forbidden claims: {plan.forbidden_claims}\n"
        f"Context: {context.model_dump(mode='json')}\n"
        'JSON shape: {"candidates":[{"text":"...","rationale":"..."}]}'
    )
