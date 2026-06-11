"""Compliance 도메인 타입 정의."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class LegalBasisRef(BaseModel):
    key: str
    law_name: str = ""
    article: str = ""
    summary: str = ""
    source_url: str = ""
    effective_date: str | None = None
    last_verified_at: str | None = None
    chunk_id: str | None = None


class RuleExample(BaseModel):
    unsafe: str
    safe: str
    index_for_rag: bool = False


class ComplianceRule(BaseModel):
    rule_id: str
    domain: str
    severity: Literal["warn", "evidence_required", "block"]
    title: str
    patterns: list[str] = Field(default_factory=list)
    legal_basis_ref: LegalBasisRef | None = None
    evidence_requirements: list[str] = Field(default_factory=list)
    safe_rewrite_hints: list[str] = Field(default_factory=list)
    hitl_question: str | None = None
    context_upgrade: dict[str, str] = Field(default_factory=dict)
    embedding_text: str = ""
    examples: list[RuleExample] = Field(default_factory=list)


class ComplianceFinding(BaseModel):
    finding_id: str
    field: Literal["headline", "sub_copy", "cta"]
    rule_id: str | None = None
    severity: Literal["warn", "evidence_required", "block"]
    matched_text: str
    reason: str
    legal_basis: list[LegalBasisRef] = Field(default_factory=list)
    suggested_text: str | None = None
    hitl_question: str | None = None
    evidence_requirements: list[str] = Field(default_factory=list)
    detection_method: Literal["pattern", "semantic", "rag"] = "pattern"
    confidence: float = 1.0
    rag_chunk_id: str | None = None
    rag_retrieval_score: float | None = None
    rag_context: dict[str, Any] | None = None


class CopyComplianceState(BaseModel):
    status: Literal["pass", "warn", "evidence_required", "blocked", "manual_review_required"]
    findings: list[ComplianceFinding] = Field(default_factory=list)
    original_copy: dict[str, Any] | None = None
    suggested_copy: dict[str, Any] | None = None
    user_decision: str | None = None
    user_acknowledged_risk: bool = False
    publication_ready: bool = True
    interrupt_payload: dict[str, Any] | None = None
    evidence_submitted: list[dict[str, Any]] = Field(default_factory=list)
    revision_count: int = 0
