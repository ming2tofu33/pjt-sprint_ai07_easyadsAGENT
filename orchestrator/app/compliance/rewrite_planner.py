"""Plan safe rewrite strategies for compliance findings."""

from __future__ import annotations

from orchestrator.app.compliance.schemas import (
    ComplianceFinding,
    ComplianceRewritePlan,
    ComplianceRewriteStrategy,
    ComplianceRule,
)

_RULE_STRATEGY_BY_ID: dict[str, ComplianceRewriteStrategy] = {
    "KR-GENERAL-SUPERLATIVE-001": "soften_superlative",
    "KR-FITNESS-GUARANTEE-001": "remove_guarantee",
    "KR-FOOD-MEDICAL-001": "remove_medical_claim",
    "KR-FOOD-MEDICAL-CLAIM-001": "remove_medical_claim",
    "KR-COSMETIC-MEDICAL-001": "remove_medical_claim",
    "KR-COSMETIC-BLOCK-001": "remove_medical_claim",
    "KR-MEDICAL-CLAIM-001": "remove_medical_claim",
    "KR-MEDICAL-BLOCK-001": "remove_medical_claim",
}


class ComplianceRewritePlanner:
    def __init__(self, rules_by_id: dict[str, ComplianceRule]) -> None:
        self._rules = rules_by_id

    def plan(self, finding: ComplianceFinding) -> ComplianceRewritePlan:
        rule = self._rules.get(finding.rule_id or "")
        strategy = self._strategy_for(finding)
        return ComplianceRewritePlan(
            rule_id=finding.rule_id or "",
            field=finding.field,
            matched_text=finding.matched_text,
            strategy=strategy,
            instruction=self._instruction_for(strategy),
            safe_hints=list(rule.safe_rewrite_hints if rule else []),
            forbidden_claims=self._forbidden_claims_for(strategy),
        )

    def _strategy_for(self, finding: ComplianceFinding) -> ComplianceRewriteStrategy:
        rule_id = finding.rule_id or ""
        strategy = _RULE_STRATEGY_BY_ID.get(rule_id)
        if strategy:
            return strategy
        if finding.severity == "evidence_required":
            return "request_evidence"
        return "manual_edit_required"

    def _instruction_for(self, strategy: ComplianceRewriteStrategy) -> str:
        if strategy == "soften_superlative":
            return "근거 없는 최상급·절대 표현을 제거하고 상품 맥락을 유지한 경험 중심 문구로 바꾼다."
        if strategy == "remove_guarantee":
            return "성과 보장이나 단정 표현을 제거하고 기대·경험 중심 표현으로 바꾼다."
        if strategy == "remove_medical_claim":
            return "질병, 치료, 효능처럼 보이는 표현을 제거하고 맛, 향, 분위기, 사용 경험 중심으로 바꾼다."
        if strategy == "request_evidence":
            return "표현 유지에는 객관적 근거가 필요하므로 근거 없는 비교·수치·단정을 완화한다."
        return "자동 수정이 위험할 수 있으므로 직접 수정 가능한 안전 방향만 제안한다."

    def _forbidden_claims_for(self, strategy: ComplianceRewriteStrategy) -> list[str]:
        if strategy == "soften_superlative":
            return ["최고", "1위", "최초", "100% 보장", "완벽 보장", "무조건"]
        if strategy == "remove_guarantee":
            return ["보장", "100%", "확실한 변화", "무조건"]
        if strategy == "remove_medical_claim":
            return ["치료", "개선", "독소 배출", "감량", "효능", "효과 보장"]
        return ["근거 없는 수치", "근거 없는 비교", "단정적 효능"]
