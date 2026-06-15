"""RewriteStrategy Protocol + StaticHintRewriter.

v2 RAG 확장 시 RAGExampleRewriter로 교체한다.
"""

from __future__ import annotations

import re
from typing import Protocol

from orchestrator.app.compliance.schemas import ComplianceFinding, ComplianceRule


class RewriteStrategy(Protocol):
    def suggest(self, finding: ComplianceFinding, original_text: str, domain: str) -> str | None: ...


class StaticHintRewriter:
    """v1: 규칙 예시를 기본값으로 쓰되 일부 표현은 원문 맥락을 보존해 순화한다."""

    _SUPERLATIVE_RULE_ID = "KR-GENERAL-SUPERLATIVE-001"
    _SUPERLATIVE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
        (r"국내\s*1위", "많이 찾는"),
        (r"1위", "많이 찾는"),
        (r"최고급", "엄선한"),
        (r"최고의", "좋은"),
        (r"최고다\s*", "좋은 "),
        (r"최고", "좋은"),
        (r"최초", "새롭게 선보이는"),
        (r"100%\s*보장", "기대할 수 있는"),
        (r"완벽\s*보장", "꼼꼼히 준비한"),
        (r"무조건", "편하게"),
    )

    def __init__(self, rules_by_id: dict[str, ComplianceRule]) -> None:
        self._rules = rules_by_id

    def suggest(self, finding: ComplianceFinding, original_text: str, domain: str) -> str | None:
        if finding.rule_id is None:
            return None
        rule = self._rules.get(finding.rule_id)
        if rule and rule.rule_id == self._SUPERLATIVE_RULE_ID:
            contextual = self._rewrite_superlative_phrase(original_text or finding.matched_text)
            if contextual:
                return contextual
        if rule and rule.examples:
            return rule.examples[0].safe
        return None

    def _rewrite_superlative_phrase(self, text: str) -> str | None:
        source = text.strip()
        if not source:
            return None

        rewritten = source
        for pattern, replacement in self._SUPERLATIVE_REPLACEMENTS:
            rewritten = re.sub(pattern, replacement, rewritten)

        rewritten = self._normalize_spacing(rewritten)
        if rewritten and rewritten != source:
            return rewritten
        return None

    @staticmethod
    def _normalize_spacing(text: str) -> str:
        normalized = re.sub(r"\s+", " ", text).strip()
        normalized = re.sub(r"\s+([!?,.])", r"\1", normalized)
        return normalized
