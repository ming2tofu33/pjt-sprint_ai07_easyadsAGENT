"""Validate rewrite candidates through the existing compliance checker."""

from __future__ import annotations

from typing import Any

from orchestrator.app.compliance.rule_engine import ComplianceChecker, aggregate_status
from orchestrator.app.compliance.schemas import (
    ComplianceCopyField,
    ComplianceRewriteCandidate,
    ComplianceValidatedSuggestion,
)


_COPY_KEY_BY_FINDING_FIELD: dict[ComplianceCopyField, str] = {
    "headline": "headline",
    "sub_copy": "subcopy",
    "cta": "cta",
}


class ComplianceCandidateValidator:
    def __init__(self, checker: ComplianceChecker) -> None:
        self._checker = checker

    def validate(
        self,
        *,
        original_copy: dict[str, Any],
        field: ComplianceCopyField,
        candidates: list[ComplianceRewriteCandidate],
        domains: list[str],
    ) -> list[ComplianceValidatedSuggestion]:
        field_key = _COPY_KEY_BY_FINDING_FIELD[field]
        accepted: list[ComplianceValidatedSuggestion] = []
        seen: set[str] = set()
        for candidate in candidates:
            text = candidate.text.strip()
            if not text or text in seen:
                continue
            seen.add(text)
            candidate_copy = {field_key: text}
            status = aggregate_status(self._checker.scan(candidate_copy, domains))
            if status in {"pass", "warn"}:
                accepted.append(
                    ComplianceValidatedSuggestion(
                        id=f"suggestion_{len(accepted) + 1}",
                        text=text,
                        validation_status=status,
                        rationale=candidate.rationale,
                    )
                )
        return accepted
