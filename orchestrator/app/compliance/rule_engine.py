"""ComplianceChecker Protocol + PatternMatcher + aggregate_status."""

from __future__ import annotations

import re
import uuid
from typing import Any, Protocol

from orchestrator.app.compliance.schemas import (
    ComplianceFinding,
    ComplianceRule,
)

_SEVERITY_RANK: dict[str, int] = {
    "warn": 1,
    "evidence_required": 2,
    "block": 3,
}

_STATUS_FROM_SEVERITY: dict[str, str] = {
    "warn": "warn",
    "evidence_required": "evidence_required",
    "block": "blocked",
}

# finding.field → copy dict key
_TEXT_FIELDS: dict[str, str] = {
    "headline": "headline",
    "sub_copy": "subcopy",
    "cta": "cta",
}


class ComplianceChecker(Protocol):
    """v2 RAG 확장 시 HybridMatcher로 교체한다."""

    def scan(self, copy: dict[str, Any], domains: list[str]) -> list[ComplianceFinding]: ...


def aggregate_status(findings: list[ComplianceFinding]) -> str:
    """findings 중 가장 높은 severity에 해당하는 상태 문자열을 반환한다."""
    if not findings:
        return "pass"
    highest = max(findings, key=lambda f: _SEVERITY_RANK.get(f.severity, 0))
    return _STATUS_FROM_SEVERITY.get(highest.severity, "warn")


class PatternMatcher:
    """v1 구현체: deterministic regex 매칭."""

    def __init__(self, rules: list[ComplianceRule]) -> None:
        self.rules = rules
        self._compiled: dict[str, list[re.Pattern[str]]] = {
            r.rule_id: [re.compile(p) for p in r.patterns]
            for r in rules
        }

    def scan(self, copy: dict[str, Any], domains: list[str]) -> list[ComplianceFinding]:
        applicable = [r for r in self.rules if r.domain in domains]
        findings: list[ComplianceFinding] = []
        for rule in applicable:
            for field_key, copy_key in _TEXT_FIELDS.items():
                text = copy.get(copy_key)
                if not text:
                    continue
                for pattern in self._compiled[rule.rule_id]:
                    m = pattern.search(text)
                    if m:
                        findings.append(self._make_finding(rule, field_key, m.group()))
        return findings

    def _make_finding(self, rule: ComplianceRule, field: str, matched_text: str) -> ComplianceFinding:
        return ComplianceFinding(
            finding_id=f"finding_{uuid.uuid4().hex[:8]}",
            field=field,
            rule_id=rule.rule_id,
            severity=rule.severity,
            matched_text=matched_text,
            reason=rule.title,
            legal_basis=[rule.legal_basis_ref] if rule.legal_basis_ref else [],
            suggested_text=rule.examples[0].safe if rule.examples else None,
            hitl_question=rule.hitl_question,
            evidence_requirements=rule.evidence_requirements,
            detection_method="pattern",
            confidence=1.0,
        )
