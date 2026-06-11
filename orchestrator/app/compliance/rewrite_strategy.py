"""RewriteStrategy Protocol + StaticHintRewriter.

v2 RAG 확장 시 RAGExampleRewriter로 교체한다.
"""

from __future__ import annotations

from typing import Protocol

from orchestrator.app.compliance.schemas import ComplianceFinding, ComplianceRule


class RewriteStrategy(Protocol):
    def suggest(self, finding: ComplianceFinding, original_text: str, domain: str) -> str | None: ...


class StaticHintRewriter:
    """v1: rule의 examples[0].safe를 그대로 반환한다."""

    def __init__(self, rules_by_id: dict[str, ComplianceRule]) -> None:
        self._rules = rules_by_id

    def suggest(self, finding: ComplianceFinding, original_text: str, domain: str) -> str | None:
        if finding.rule_id is None:
            return None
        rule = self._rules.get(finding.rule_id)
        if rule and rule.examples:
            return rule.examples[0].safe
        return None
