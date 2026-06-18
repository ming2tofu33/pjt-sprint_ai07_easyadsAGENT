"""Deterministic intake question policy contracts."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("policy values must be strings")
    normalized = value.strip()
    return normalized or None


def _normalize_string_tuple(values: Iterable[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        candidates: Iterable[str] = [values]
    else:
        candidates = values
    normalized: list[str] = []
    seen: set[str] = set()
    for value in candidates:
        if not isinstance(value, str):
            raise ValueError("policy collections must contain strings")
        item = value.strip()
        if not item or item in seen:
            continue
        normalized.append(item)
        seen.add(item)
    return tuple(normalized)


class FieldRequirementDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str
    required: bool
    satisfied: bool
    satisfaction_source: str | None = None
    reason_code: str
    evidence_refs: tuple[str, ...] = ()
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    clarification_required: bool = False
    resolution_kind: str = "missing"

    @field_validator("field", "satisfaction_source", "reason_code", "resolution_kind", mode="before")
    @classmethod
    def _normalize_scalar(cls, value: Any) -> str | None:
        return _normalize_optional_text(value)

    @field_validator("evidence_refs", mode="before")
    @classmethod
    def _normalize_refs(cls, value: Any) -> tuple[str, ...]:
        return _normalize_string_tuple(value)


class IntakeQuestionPolicyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    required_fields: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()
    satisfied_fields: tuple[str, ...] = ()
    waived_fields: tuple[str, ...] = ()
    field_decisions: tuple[FieldRequirementDecision, ...] = ()
    advertised_subject_used: bool = False
    campaign_intent_used: bool = False
    domain_routeable: bool = False
    blocking_ambiguities: tuple[str, ...] = ()
    blocking_conflicts: tuple[str, ...] = ()
    policy_version: str

    @field_validator(
        "required_fields",
        "missing_fields",
        "satisfied_fields",
        "waived_fields",
        "blocking_ambiguities",
        "blocking_conflicts",
        mode="before",
    )
    @classmethod
    def _normalize_collections(cls, value: Any) -> tuple[str, ...]:
        return _normalize_string_tuple(value)

    @field_validator("policy_version", mode="before")
    @classmethod
    def _normalize_version(cls, value: Any) -> str | None:
        return _normalize_optional_text(value)

    @model_validator(mode="after")
    def _validate_invariants(self) -> "IntakeQuestionPolicyDecision":
        required = set(self.required_fields)
        missing = set(self.missing_fields)
        satisfied = set(self.satisfied_fields)
        waived = set(self.waived_fields)

        if not missing.issubset(required):
            raise ValueError("missing_fields must be a subset of required_fields")
        if waived & required:
            raise ValueError("waived_fields must be disjoint from required_fields")
        if satisfied & missing:
            raise ValueError("satisfied_fields must be disjoint from missing_fields")

        decisions_by_field: dict[str, FieldRequirementDecision] = {}
        for decision in self.field_decisions:
            if decision.field in decisions_by_field:
                raise ValueError(f"duplicate field_decision for {decision.field}")
            decisions_by_field[decision.field] = decision

            if decision.required != (decision.field in required):
                raise ValueError(f"required_fields summary mismatch for {decision.field}")
            if decision.required and not decision.satisfied and decision.field not in missing:
                raise ValueError(f"missing_fields summary mismatch for {decision.field}")
            if decision.satisfied and decision.field not in satisfied:
                raise ValueError(f"satisfied_fields summary mismatch for {decision.field}")
            if not decision.required and not decision.satisfied and decision.field not in waived:
                raise ValueError(f"waived_fields summary mismatch for {decision.field}")
            if decision.satisfied and not decision.satisfaction_source:
                raise ValueError(f"satisfied decision requires satisfaction_source for {decision.field}")
            if not decision.required and not decision.satisfied and decision.reason_code.startswith("missing_"):
                raise ValueError(f"waived decision requires non-missing reason_code for {decision.field}")

        summary_fields = required | missing | satisfied | waived
        if summary_fields - set(decisions_by_field):
            raise ValueError("summary fields must match field_decisions")

        return self


class IntakeQuestionPolicyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    explicit_user_evidence_min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    structured_inference_min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    blocking_conflict_severities: tuple[str, ...] = ("clarification_required", "manual_review")

    @field_validator("blocking_conflict_severities", mode="before")
    @classmethod
    def _normalize_severities(cls, value: Any) -> tuple[str, ...]:
        return _normalize_string_tuple(value)
