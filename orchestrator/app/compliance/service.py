"""ComplianceService — check_copy()의 단일 진입점."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from orchestrator.app.compliance.industry_classifier import IndustryClassifier
from orchestrator.app.compliance.rule_engine import ComplianceChecker, PatternMatcher, aggregate_status
from orchestrator.app.compliance.rule_loader import load_rules
from orchestrator.app.compliance.rewrite_strategy import RewriteStrategy, StaticHintRewriter
from orchestrator.app.compliance.schemas import ComplianceFinding, CopyComplianceState

_PUBLICATION_READY_STATUSES = {"pass", "warn"}


class ComplianceService:
    def __init__(
        self,
        checker: ComplianceChecker,
        rewriter: RewriteStrategy,
        classifier: IndustryClassifier,
    ) -> None:
        self._checker = checker
        self._rewriter = rewriter
        self._classifier = classifier

    def check_copy(
        self,
        copy: dict[str, Any],
        business_type: str | None,
    ) -> CopyComplianceState:
        domains = self._classifier.get_domains(business_type)
        findings = self._checker.scan(copy, domains)
        status = aggregate_status(findings)

        suggested_copy = None
        if status not in _PUBLICATION_READY_STATUSES and findings:
            suggested_copy = self._build_suggested_copy(copy, findings, domains)

        return CopyComplianceState(
            status=status,
            findings=findings,
            original_copy=dict(copy),  # 반드시 복사본 저장
            suggested_copy=suggested_copy,
            publication_ready=(status in _PUBLICATION_READY_STATUSES),
        )

    def get_rules_for_domains(self, domains: list[str]) -> list:
        """도메인에 적용 가능한 규칙 목록을 반환한다."""
        checker_rules = getattr(self._checker, "rules", [])
        return [r for r in checker_rules if r.domain in domains]

    def _build_suggested_copy(
        self,
        copy: dict[str, Any],
        findings: list[ComplianceFinding],
        domains: list[str],
    ) -> dict[str, Any] | None:
        suggested = dict(copy)
        domain = domains[0] if domains else "general_ad"
        for finding in findings:
            field_copy_key = "subcopy" if finding.field == "sub_copy" else finding.field
            original_text = suggested.get(field_copy_key) or ""
            suggestion = self._rewriter.suggest(finding, original_text, domain)
            if suggestion:
                suggested[field_copy_key] = suggestion
        return suggested if suggested != copy else None


@lru_cache(maxsize=1)
def _build_default_service() -> ComplianceService:
    rules = load_rules()
    rules_by_id = {r.rule_id: r for r in rules}
    return ComplianceService(
        checker=PatternMatcher(rules),
        rewriter=StaticHintRewriter(rules_by_id),
        classifier=IndustryClassifier(),
    )


def get_compliance_service() -> ComplianceService:
    """싱글톤 반환. 테스트에서는 _svc()로 직접 생성할 것."""
    return _build_default_service()
