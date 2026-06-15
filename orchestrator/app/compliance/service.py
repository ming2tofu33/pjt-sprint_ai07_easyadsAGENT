"""ComplianceService — check_copy()의 단일 진입점."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from orchestrator.app.compliance.candidate_validator import ComplianceCandidateValidator
from orchestrator.app.compliance.industry_classifier import IndustryClassifier
from orchestrator.app.compliance.llm_rewriter import ComplianceLLMRewriter, ComplianceRewriteAdapter
from orchestrator.app.compliance.rewrite_planner import ComplianceRewritePlanner
from orchestrator.app.compliance.rule_engine import ComplianceChecker, PatternMatcher, aggregate_status
from orchestrator.app.compliance.rule_loader import load_rules
from orchestrator.app.compliance.rewrite_strategy import RewriteStrategy, StaticHintRewriter
from orchestrator.app.compliance.schemas import ComplianceFinding, ComplianceRewriteContext, CopyComplianceState

_PUBLICATION_READY_STATUSES = {"pass", "warn"}
_COPY_KEY_BY_FINDING_FIELD = {
    "headline": "headline",
    "sub_copy": "subcopy",
    "cta": "cta",
}


class ComplianceService:
    def __init__(
        self,
        checker: ComplianceChecker,
        rewriter: RewriteStrategy | None,
        classifier: IndustryClassifier,
        rewrite_planner: ComplianceRewritePlanner | None = None,
        llm_rewriter_adapter: ComplianceRewriteAdapter | None = None,
        candidate_validator: ComplianceCandidateValidator | None = None,
    ) -> None:
        self._checker = checker
        self._rewriter = rewriter
        self._classifier = classifier
        self._rewrite_planner = rewrite_planner
        self._llm_rewriter = ComplianceLLMRewriter(adapter=llm_rewriter_adapter)
        self._candidate_validator = candidate_validator or ComplianceCandidateValidator(checker)

    def check_copy(
        self,
        copy: dict[str, Any],
        business_type: str | None,
        *,
        enable_contextual_rewrite: bool = False,
        rewrite_context: ComplianceRewriteContext | None = None,
        state: dict[str, Any] | None = None,
    ) -> CopyComplianceState:
        domains = self._classifier.get_domains(business_type)
        findings = self._checker.scan(copy, domains)
        rewrite_attempts = self._attach_suggestions(
            copy,
            findings,
            domains,
            enable_contextual_rewrite=enable_contextual_rewrite,
            rewrite_context=rewrite_context,
            state=state,
        )
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
            rewrite_attempts=rewrite_attempts,
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
            field_copy_key = _COPY_KEY_BY_FINDING_FIELD.get(finding.field, finding.field)
            original_text = suggested.get(field_copy_key) or ""
            suggestion = finding.suggestions[0].text if finding.suggestions else finding.suggested_text
            if not suggestion and self._rewriter:
                suggestion = self._rewriter.suggest(finding, original_text, domain)
            if suggestion:
                suggested[field_copy_key] = suggestion
        return suggested if suggested != copy else None

    def _attach_suggestions(
        self,
        copy: dict[str, Any],
        findings: list[ComplianceFinding],
        domains: list[str],
        *,
        enable_contextual_rewrite: bool,
        rewrite_context: ComplianceRewriteContext | None,
        state: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        rewrite_attempts: list[dict[str, Any]] = []
        domain = domains[0] if domains else "general_ad"
        for finding in findings:
            field_copy_key = _COPY_KEY_BY_FINDING_FIELD.get(finding.field, finding.field)
            original_text = copy.get(field_copy_key) or ""
            if enable_contextual_rewrite and self._rewrite_planner:
                plan = self._rewrite_planner.plan(finding)
                finding.rewrite_plan = plan
                llm_result = self._llm_rewriter.rewrite(
                    original_text=original_text,
                    finding=finding,
                    plan=plan,
                    context=rewrite_context or ComplianceRewriteContext(business_type=domain),
                    state=state,
                )
                validated = self._candidate_validator.validate(
                    original_copy=copy,
                    field=finding.field,
                    candidates=llm_result.candidates,
                    domains=domains,
                )
                finding.suggestions = validated
                rewrite_attempts.append(
                    {
                        "rule_id": finding.rule_id,
                        "field": finding.field,
                        "matched_text": finding.matched_text,
                        "llm_attempted": llm_result.llm_attempted,
                        "fallback_used": llm_result.fallback_used,
                        "fallback_reason": llm_result.fallback_reason,
                        "candidate_count": len(llm_result.candidates),
                        "validated_count": len(validated),
                    }
                )
                if validated:
                    finding.suggested_text = validated[0].text
                    continue
            if self._rewriter:
                suggestion = self._rewriter.suggest(finding, original_text, domain)
            else:
                suggestion = None
            if suggestion:
                finding.suggested_text = suggestion
        return rewrite_attempts


@lru_cache(maxsize=1)
def _build_default_service() -> ComplianceService:
    rules = load_rules()
    rules_by_id = {r.rule_id: r for r in rules}
    checker = PatternMatcher(rules)
    return ComplianceService(
        checker=checker,
        rewriter=StaticHintRewriter(rules_by_id),
        classifier=IndustryClassifier(),
        rewrite_planner=ComplianceRewritePlanner(rules_by_id),
        candidate_validator=ComplianceCandidateValidator(checker),
    )


def get_compliance_service() -> ComplianceService:
    """싱글톤 반환. 테스트에서는 _svc()로 직접 생성할 것."""
    return _build_default_service()
