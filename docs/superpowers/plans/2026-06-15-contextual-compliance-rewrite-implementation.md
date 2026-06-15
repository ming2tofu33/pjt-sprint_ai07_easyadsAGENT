# Contextual Compliance Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a compliance rewrite flow that calls an LLM only when compliance findings exist, generates context-aware safe copy candidates, validates those candidates through the existing rule engine, and sends only validated suggestions to the UI.

**Architecture:** Keep the current deterministic pattern matcher as the legal-risk detector. Add a planner, optional LLM rewriter, and validator around it so LLM output never becomes authoritative until it passes the existing `ComplianceService` rule checks. Preserve current `suggested_text`/`suggested_copy` fields for compatibility while adding structured `suggestions[]`.

**Tech Stack:** Python 3.12, Pydantic, LangGraph state, existing `run_structured_node()` LLM runner, pytest, Next.js/React, Vitest.

---

## File Structure

### Backend Compliance

- Modify: `orchestrator/app/compliance/schemas.py`
  - Add rewrite plan, rewrite candidate, validated suggestion, and rewrite context schemas.
  - Extend `ComplianceFinding` with `suggestions`.
  - Extend `CopyComplianceState` with `rewrite_attempts`.

- Create: `orchestrator/app/compliance/rewrite_planner.py`
  - Convert findings and rules into structured rewrite strategies.

- Create: `orchestrator/app/compliance/llm_rewriter.py`
  - Build safe LLM prompts.
  - Call existing `run_structured_node()` only when enabled and state is available.
  - Return typed candidate output.

- Create: `orchestrator/app/compliance/candidate_validator.py`
  - Re-scan candidate copy with existing `ComplianceChecker`.
  - Keep only `pass` and `warn` candidates.

- Modify: `orchestrator/app/compliance/rewrite_strategy.py`
  - Keep deterministic rewrite as fallback.

- Modify: `orchestrator/app/compliance/service.py`
  - Integrate planner, optional LLM rewriter, validator, and fallback.
  - Default behavior stays deterministic unless `enable_contextual_rewrite=True`.

### Backend Graph

- Modify: `orchestrator/app/llm/nodes/copy_compliance.py`
  - Enable contextual rewrite only in `copy_compliance_gate_node`.
  - Keep `input_compliance_precheck_node` cheap and deterministic.
  - Serialize `suggestions[]` into interrupt payload.

- Modify: `orchestrator/app/schemas/llm_model_policy.py`
  - Add `compliance_rewrite` to `NodeModelName`.

- Modify: `orchestrator/app/llm/plan_policy.py`
  - Add model policy defaults for `compliance_rewrite`.

### Frontend

- Modify: `apps/web/lib/generation-job-interrupt.ts`
  - Add typed `suggestions[]` to `ComplianceFindingFE`.

- Modify: `apps/web/components/generate/GenerationJobInterruptStep.tsx`
  - Prefer validated `suggestions[0].text` over legacy `suggested_text`.
  - Render multiple suggestions if provided.

- Modify: `apps/web/types/contracts/generation-job-interrupt.fixtures.json`
  - Add a fixture suggestion to the compliance review contract.

### Tests

- Modify: `orchestrator/tests/test_compliance.py`
  - Add unit tests for planner, LLM call gating, candidate validation, fallback, and graph payload.

- Modify: `orchestrator/tests/test_llm_services.py`
  - Add policy/router coverage for `compliance_rewrite`.

- Modify: `apps/web/lib/generation-job-interrupt.contract.test.ts`
  - Add parsing assertions for `suggestions[]`.

- Modify: `apps/web/components/generate/GenerationJobInterruptStep.test.tsx`
  - Add rendering assertions for contextual suggestions.

---

## Task 1: Commit Current Deterministic Fallback Baseline

**Files:**
- Modify: `orchestrator/app/compliance/rewrite_strategy.py`
- Modify: `orchestrator/app/compliance/service.py`
- Test: `orchestrator/tests/test_compliance.py`

- [ ] **Step 1: Confirm fallback tests exist**

Check that `orchestrator/tests/test_compliance.py` contains these tests:

```python
def test_superlative_suggestion_preserves_original_product_context():
    result = _svc__test_compliance_service().check_copy(
        {"headline": "최고다 고기!", "subcopy": "맛도 좋고 보기도 좋은 1등급 고기"},
        business_type="restaurant",
    )

    assert result.status == "evidence_required"
    assert result.suggested_copy is not None
    suggested_headline = result.suggested_copy.get("headline", "")
    assert "고기" in suggested_headline
    assert "최고" not in suggested_headline
    assert "고객 만족 코칭 프로그램" not in suggested_headline


def test_superlative_finding_suggested_text_uses_contextual_rewrite():
    result = _svc__test_compliance_service().check_copy(
        {"headline": "최고다 고기!", "subcopy": "맛도 좋고 보기도 좋은 1등급 고기"},
        business_type="restaurant",
    )

    finding = result.findings[0]
    assert finding.matched_text == "최고"
    assert finding.suggested_text is not None
    assert "고기" in finding.suggested_text
    assert "최고" not in finding.suggested_text
    assert "고객 만족 코칭 프로그램" not in finding.suggested_text
```

- [ ] **Step 2: Run focused baseline tests**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_compliance.py -k "superlative" -q
```

Expected:

```text
4 passed
```

- [ ] **Step 3: Run full compliance tests**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_compliance.py -q
```

Expected:

```text
130 passed
```

- [ ] **Step 4: Commit the fallback baseline**

Run:

```bash
git add orchestrator/app/compliance/rewrite_strategy.py orchestrator/app/compliance/service.py orchestrator/tests/test_compliance.py
git commit -m "fix: preserve compliance rewrite context"
```

Expected: a commit containing only deterministic fallback and compliance tests.

---

## Task 2: Add Compliance Rewrite Schemas

**Files:**
- Modify: `orchestrator/app/compliance/schemas.py`
- Test: `orchestrator/tests/test_compliance.py`

- [ ] **Step 1: Write failing schema tests**

Add these tests near the schema section in `orchestrator/tests/test_compliance.py`:

```python
def test_compliance_rewrite_candidate_instantiates():
    from orchestrator.app.compliance.schemas import ComplianceRewriteCandidate

    candidate = ComplianceRewriteCandidate(
        text="정성껏 준비한 고기 한 접시",
        rationale="최상급 표현을 제거하고 상품 맥락을 유지했습니다.",
    )

    assert candidate.text == "정성껏 준비한 고기 한 접시"
    assert candidate.rationale.startswith("최상급")


def test_compliance_validated_suggestion_instantiates():
    from orchestrator.app.compliance.schemas import ComplianceValidatedSuggestion

    suggestion = ComplianceValidatedSuggestion(
        id="suggestion_1",
        text="정성껏 준비한 고기 한 접시",
        validation_status="pass",
        rationale="재검수를 통과했습니다.",
    )

    assert suggestion.id == "suggestion_1"
    assert suggestion.validation_status == "pass"


def test_compliance_finding_accepts_suggestions():
    from orchestrator.app.compliance.schemas import ComplianceFinding, ComplianceValidatedSuggestion

    finding = ComplianceFinding(
        finding_id="finding_1",
        field="headline",
        rule_id="KR-GENERAL-SUPERLATIVE-001",
        severity="evidence_required",
        matched_text="최고",
        reason="실증 없는 최상급 표현",
        suggestions=[
            ComplianceValidatedSuggestion(
                id="suggestion_1",
                text="좋은 고기",
                validation_status="pass",
                rationale="위험 표현을 완화했습니다.",
            )
        ],
    )

    assert finding.suggestions[0].text == "좋은 고기"
```

- [ ] **Step 2: Run schema tests and verify failure**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_compliance.py -k "rewrite_candidate or validated_suggestion or finding_accepts_suggestions" -q
```

Expected: FAIL because the schema classes and field do not exist.

- [ ] **Step 3: Add schema classes and fields**

Modify `orchestrator/app/compliance/schemas.py`:

```python
ComplianceRewriteStrategy = Literal[
    "soften_superlative",
    "remove_guarantee",
    "remove_medical_claim",
    "request_evidence",
    "manual_edit_required",
]


class ComplianceRewriteContext(BaseModel):
    business_type: str | None = None
    item_or_service: str | None = None
    promotion_goal: str | None = None
    ad_format: str | None = None
    channel: str | None = None


class ComplianceRewritePlan(BaseModel):
    rule_id: str
    field: str
    matched_text: str
    strategy: ComplianceRewriteStrategy
    instruction: str
    safe_hints: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)


class ComplianceRewriteCandidate(BaseModel):
    text: str
    rationale: str = ""


class ComplianceValidatedSuggestion(BaseModel):
    id: str
    text: str
    validation_status: Literal["pass", "warn"]
    rationale: str = ""
```

Then extend `ComplianceFinding`:

```python
    suggestions: list[ComplianceValidatedSuggestion] = Field(default_factory=list)
    rewrite_plan: ComplianceRewritePlan | None = None
```

Then extend `CopyComplianceState`:

```python
    rewrite_attempts: list[dict[str, Any]] = Field(default_factory=list)
```

- [ ] **Step 4: Run schema tests and verify pass**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_compliance.py -k "rewrite_candidate or validated_suggestion or finding_accepts_suggestions" -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit schemas**

Run:

```bash
git add orchestrator/app/compliance/schemas.py orchestrator/tests/test_compliance.py
git commit -m "feat: add compliance rewrite schemas"
```

---

## Task 3: Add Compliance Rewrite Planner

**Files:**
- Create: `orchestrator/app/compliance/rewrite_planner.py`
- Test: `orchestrator/tests/test_compliance.py`

- [ ] **Step 1: Write failing planner tests**

Add:

```python
def test_rewrite_planner_maps_superlative_rule_to_softening_strategy():
    from orchestrator.app.compliance.rewrite_planner import ComplianceRewritePlanner
    from orchestrator.app.compliance.rule_loader import load_rules
    from orchestrator.app.compliance.rule_engine import PatternMatcher

    rules = load_rules()
    checker = PatternMatcher(rules)
    findings = checker.scan({"headline": "최고다 고기!"}, ["general_ad"])
    rules_by_id = {rule.rule_id: rule for rule in rules}

    plan = ComplianceRewritePlanner(rules_by_id).plan(findings[0])

    assert plan.rule_id == "KR-GENERAL-SUPERLATIVE-001"
    assert plan.strategy == "soften_superlative"
    assert "최상급" in plan.instruction


def test_rewrite_planner_preserves_rule_safe_hints():
    from orchestrator.app.compliance.rewrite_planner import ComplianceRewritePlanner
    from orchestrator.app.compliance.rule_loader import load_rules
    from orchestrator.app.compliance.rule_engine import PatternMatcher

    rules = load_rules()
    checker = PatternMatcher(rules)
    findings = checker.scan({"headline": "국내 1위 카페"}, ["general_ad"])
    rules_by_id = {rule.rule_id: rule for rule in rules}

    plan = ComplianceRewritePlanner(rules_by_id).plan(findings[0])

    assert "보장·절대 표현 대신 경험·기대·제안 표현으로" in plan.safe_hints
```

- [ ] **Step 2: Run planner tests and verify failure**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_compliance.py -k "rewrite_planner" -q
```

Expected: FAIL because `rewrite_planner.py` does not exist.

- [ ] **Step 3: Create planner implementation**

Create `orchestrator/app/compliance/rewrite_planner.py`:

```python
"""Plan safe rewrite strategies for compliance findings."""

from __future__ import annotations

from orchestrator.app.compliance.schemas import ComplianceFinding, ComplianceRewritePlan, ComplianceRule


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

    def _strategy_for(self, finding: ComplianceFinding):
        rule_id = finding.rule_id or ""
        if rule_id == "KR-GENERAL-SUPERLATIVE-001":
            return "soften_superlative"
        if "GUARANTEE" in rule_id:
            return "remove_guarantee"
        if "FOOD" in rule_id or "COSMETIC" in rule_id or "MEDICAL" in rule_id:
            return "remove_medical_claim"
        if finding.severity == "evidence_required":
            return "request_evidence"
        return "manual_edit_required"

    def _instruction_for(self, strategy: str) -> str:
        if strategy == "soften_superlative":
            return "근거 없는 최상급·절대 표현을 제거하고 상품 맥락을 유지한 경험 중심 문구로 바꾼다."
        if strategy == "remove_guarantee":
            return "성과 보장이나 단정 표현을 제거하고 기대·경험 중심 표현으로 바꾼다."
        if strategy == "remove_medical_claim":
            return "질병, 치료, 효능처럼 보이는 표현을 제거하고 맛, 향, 분위기, 사용 경험 중심으로 바꾼다."
        if strategy == "request_evidence":
            return "표현 유지에는 객관적 근거가 필요하므로 근거 없는 비교·수치·단정을 완화한다."
        return "자동 수정이 위험할 수 있으므로 직접 수정 가능한 안전 방향만 제안한다."

    def _forbidden_claims_for(self, strategy: str) -> list[str]:
        if strategy == "soften_superlative":
            return ["최고", "1위", "최초", "100% 보장", "완벽 보장", "무조건"]
        if strategy == "remove_guarantee":
            return ["보장", "100%", "확실한 변화", "무조건"]
        if strategy == "remove_medical_claim":
            return ["치료", "개선", "독소 배출", "감량", "효능", "효과 보장"]
        return ["근거 없는 수치", "근거 없는 비교", "단정적 효능"]
```

- [ ] **Step 4: Run planner tests and verify pass**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_compliance.py -k "rewrite_planner" -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit planner**

Run:

```bash
git add orchestrator/app/compliance/rewrite_planner.py orchestrator/tests/test_compliance.py
git commit -m "feat: plan compliance rewrite strategies"
```

---

## Task 4: Add LLM Rewriter With Deterministic Fallback

**Files:**
- Create: `orchestrator/app/compliance/llm_rewriter.py`
- Modify: `orchestrator/app/schemas/llm_model_policy.py`
- Modify: `orchestrator/app/llm/plan_policy.py`
- Test: `orchestrator/tests/test_compliance.py`
- Test: `orchestrator/tests/test_llm_services.py`

- [ ] **Step 1: Write failing rewriter tests**

Add to `orchestrator/tests/test_compliance.py`:

```python
def test_compliance_llm_rewriter_falls_back_without_state():
    from orchestrator.app.compliance.llm_rewriter import ComplianceLLMRewriter
    from orchestrator.app.compliance.schemas import ComplianceRewriteContext
    from orchestrator.app.compliance.rewrite_planner import ComplianceRewritePlanner
    from orchestrator.app.compliance.rule_loader import load_rules
    from orchestrator.app.compliance.rule_engine import PatternMatcher

    rules = load_rules()
    finding = PatternMatcher(rules).scan({"headline": "최고다 고기!"}, ["general_ad"])[0]
    plan = ComplianceRewritePlanner({rule.rule_id: rule for rule in rules}).plan(finding)

    output = ComplianceLLMRewriter().rewrite(
        original_text="최고다 고기!",
        finding=finding,
        plan=plan,
        context=ComplianceRewriteContext(business_type="restaurant", item_or_service="고기"),
        state=None,
    )

    assert output.candidates == []
    assert output.fallback_reason == "state_missing"


def test_compliance_llm_rewriter_uses_injected_adapter():
    from orchestrator.app.compliance.llm_rewriter import ComplianceLLMRewriter
    from orchestrator.app.compliance.schemas import ComplianceRewriteCandidate, ComplianceRewriteContext
    from orchestrator.app.compliance.rewrite_planner import ComplianceRewritePlanner
    from orchestrator.app.compliance.rule_loader import load_rules
    from orchestrator.app.compliance.rule_engine import PatternMatcher

    class Adapter:
        def rewrite(self, **kwargs):
            return [ComplianceRewriteCandidate(text="정성껏 준비한 고기 한 접시", rationale="맥락 유지")]

    rules = load_rules()
    finding = PatternMatcher(rules).scan({"headline": "최고다 고기!"}, ["general_ad"])[0]
    plan = ComplianceRewritePlanner({rule.rule_id: rule for rule in rules}).plan(finding)

    output = ComplianceLLMRewriter(adapter=Adapter()).rewrite(
        original_text="최고다 고기!",
        finding=finding,
        plan=plan,
        context=ComplianceRewriteContext(business_type="restaurant", item_or_service="고기"),
        state={"user_plan": "premium"},
    )

    assert output.candidates[0].text == "정성껏 준비한 고기 한 접시"
```

Add to `orchestrator/tests/test_llm_services.py`:

```python
def test_default_policy_contains_compliance_rewrite_node():
    from orchestrator.app.llm.plan_policy import build_default_plan_policy

    policy = build_default_plan_policy("premium")

    assert "compliance_rewrite" in policy.node_policies
    assert policy.node_policies["compliance_rewrite"].default_model_class == "api_mini"
```

- [ ] **Step 2: Run rewriter and policy tests and verify failure**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_compliance.py -k "compliance_llm_rewriter" -q
uv run python -m pytest orchestrator/tests/test_llm_services.py -k "compliance_rewrite_node" -q
```

Expected: FAIL because the rewriter and node policy do not exist.

- [ ] **Step 3: Add `compliance_rewrite` node policy type**

Modify `orchestrator/app/schemas/llm_model_policy.py` and add `"compliance_rewrite"` to `NodeModelName`:

```python
    "compliance_rewrite",
```

Modify `orchestrator/app/llm/plan_policy.py` and add defaults:

```python
            "compliance_rewrite": "local_fast",
```

in the free plan block, add:

```python
            "compliance_rewrite": "api_nano",
```

in the economic plan block, add:

```python
            "compliance_rewrite": "api_mini",
```

in the premium plan block, and add:

```python
        "compliance_rewrite": "api_full",
```

in the internal benchmark fallback block.

- [ ] **Step 4: Create LLM rewriter implementation**

Create `orchestrator/app/compliance/llm_rewriter.py`:

```python
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
            return ComplianceRewriteResult(candidates=self._adapter.rewrite(original_text=original_text, finding=finding, plan=plan, context=context))
        if state is None:
            return ComplianceRewriteResult(fallback_used=True, fallback_reason="state_missing")

        prompt = build_compliance_rewrite_prompt(original_text=original_text, finding=finding, plan=plan, context=context)
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
        "JSON shape: {\"candidates\":[{\"text\":\"...\",\"rationale\":\"...\"}]}"
    )
```

- [ ] **Step 5: Run tests and verify pass**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_compliance.py -k "compliance_llm_rewriter" -q
uv run python -m pytest orchestrator/tests/test_llm_services.py -k "compliance_rewrite_node" -q
```

Expected:

```text
2 passed
1 passed
```

- [ ] **Step 6: Commit LLM rewriter**

Run:

```bash
git add orchestrator/app/compliance/llm_rewriter.py orchestrator/app/schemas/llm_model_policy.py orchestrator/app/llm/plan_policy.py orchestrator/tests/test_compliance.py orchestrator/tests/test_llm_services.py
git commit -m "feat: add contextual compliance llm rewriter"
```

---

## Task 5: Add Candidate Re-Validation

**Files:**
- Create: `orchestrator/app/compliance/candidate_validator.py`
- Test: `orchestrator/tests/test_compliance.py`

- [ ] **Step 1: Write failing validator tests**

Add:

```python
def test_candidate_validator_keeps_pass_candidate():
    from orchestrator.app.compliance.candidate_validator import ComplianceCandidateValidator
    from orchestrator.app.compliance.schemas import ComplianceRewriteCandidate
    from orchestrator.app.compliance.rule_loader import load_rules
    from orchestrator.app.compliance.rule_engine import PatternMatcher

    rules = load_rules()
    validator = ComplianceCandidateValidator(PatternMatcher(rules))

    suggestions = validator.validate(
        original_copy={"headline": "최고다 고기!"},
        field="headline",
        candidates=[ComplianceRewriteCandidate(text="정성껏 준비한 고기 한 접시", rationale="맥락 유지")],
        domains=["general_ad"],
    )

    assert suggestions[0].text == "정성껏 준비한 고기 한 접시"
    assert suggestions[0].validation_status == "pass"


def test_candidate_validator_drops_candidate_with_same_risk():
    from orchestrator.app.compliance.candidate_validator import ComplianceCandidateValidator
    from orchestrator.app.compliance.schemas import ComplianceRewriteCandidate
    from orchestrator.app.compliance.rule_loader import load_rules
    from orchestrator.app.compliance.rule_engine import PatternMatcher

    rules = load_rules()
    validator = ComplianceCandidateValidator(PatternMatcher(rules))

    suggestions = validator.validate(
        original_copy={"headline": "최고의 고기"},
        field="headline",
        candidates=[ComplianceRewriteCandidate(text="최고의 고기", rationale="위험 표현 유지")],
        domains=["general_ad"],
    )

    assert suggestions == []
```

- [ ] **Step 2: Run validator tests and verify failure**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_compliance.py -k "candidate_validator" -q
```

Expected: FAIL because `candidate_validator.py` does not exist.

- [ ] **Step 3: Create validator implementation**

Create `orchestrator/app/compliance/candidate_validator.py`:

```python
"""Validate LLM rewrite candidates through the existing compliance checker."""

from __future__ import annotations

from orchestrator.app.compliance.rule_engine import ComplianceChecker, aggregate_status
from orchestrator.app.compliance.schemas import ComplianceRewriteCandidate, ComplianceValidatedSuggestion


_COPY_KEY_BY_FINDING_FIELD = {
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
        original_copy: dict,
        field: str,
        candidates: list[ComplianceRewriteCandidate],
        domains: list[str],
    ) -> list[ComplianceValidatedSuggestion]:
        field_key = _COPY_KEY_BY_FINDING_FIELD.get(field, field)
        accepted: list[ComplianceValidatedSuggestion] = []
        seen: set[str] = set()
        for candidate in candidates:
            text = candidate.text.strip()
            if not text or text in seen:
                continue
            seen.add(text)
            candidate_copy = dict(original_copy)
            candidate_copy[field_key] = text
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
```

- [ ] **Step 4: Run validator tests and verify pass**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_compliance.py -k "candidate_validator" -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit validator**

Run:

```bash
git add orchestrator/app/compliance/candidate_validator.py orchestrator/tests/test_compliance.py
git commit -m "feat: validate compliance rewrite candidates"
```

---

## Task 6: Integrate Rewrite Planner, LLM Rewriter, and Validator Into ComplianceService

**Files:**
- Modify: `orchestrator/app/compliance/service.py`
- Test: `orchestrator/tests/test_compliance.py`

- [ ] **Step 1: Write failing service tests**

Add:

```python
def test_compliance_service_does_not_call_llm_when_copy_passes():
    from orchestrator.app.compliance.candidate_validator import ComplianceCandidateValidator
    from orchestrator.app.compliance.industry_classifier import IndustryClassifier
    from orchestrator.app.compliance.rewrite_planner import ComplianceRewritePlanner
    from orchestrator.app.compliance.rule_engine import PatternMatcher
    from orchestrator.app.compliance.rule_loader import load_rules
    from orchestrator.app.compliance.schemas import ComplianceRewriteCandidate
    from orchestrator.app.compliance.service import ComplianceService

    class Adapter:
        calls = 0
        def rewrite(self, **kwargs):
            self.calls += 1
            return [ComplianceRewriteCandidate(text="불필요한 호출", rationale="호출되면 안 됨")]

    rules = load_rules()
    checker = PatternMatcher(rules)
    adapter = Adapter()
    service = ComplianceService(
        checker=checker,
        rewriter=None,
        classifier=IndustryClassifier(),
        rewrite_planner=ComplianceRewritePlanner({rule.rule_id: rule for rule in rules}),
        llm_rewriter_adapter=adapter,
        candidate_validator=ComplianceCandidateValidator(checker),
    )

    result = service.check_copy(
        {"headline": "기분 좋은 고기 한 접시"},
        business_type="restaurant",
        enable_contextual_rewrite=True,
        state={"user_plan": "premium"},
    )

    assert result.status == "pass"
    assert adapter.calls == 0


def test_compliance_service_attaches_validated_llm_suggestion_when_finding_exists():
    from orchestrator.app.compliance.candidate_validator import ComplianceCandidateValidator
    from orchestrator.app.compliance.industry_classifier import IndustryClassifier
    from orchestrator.app.compliance.rewrite_planner import ComplianceRewritePlanner
    from orchestrator.app.compliance.rule_engine import PatternMatcher
    from orchestrator.app.compliance.rule_loader import load_rules
    from orchestrator.app.compliance.schemas import ComplianceRewriteCandidate, ComplianceRewriteContext
    from orchestrator.app.compliance.service import ComplianceService

    class Adapter:
        def rewrite(self, **kwargs):
            return [
                ComplianceRewriteCandidate(text="최고의 고기", rationale="아직 위험함"),
                ComplianceRewriteCandidate(text="정성껏 준비한 고기 한 접시", rationale="위험 표현 제거"),
            ]

    rules = load_rules()
    checker = PatternMatcher(rules)
    service = ComplianceService(
        checker=checker,
        rewriter=None,
        classifier=IndustryClassifier(),
        rewrite_planner=ComplianceRewritePlanner({rule.rule_id: rule for rule in rules}),
        llm_rewriter_adapter=Adapter(),
        candidate_validator=ComplianceCandidateValidator(checker),
    )

    result = service.check_copy(
        {"headline": "최고다 고기!"},
        business_type="restaurant",
        enable_contextual_rewrite=True,
        rewrite_context=ComplianceRewriteContext(business_type="restaurant", item_or_service="고기"),
        state={"user_plan": "premium"},
    )

    assert result.findings[0].suggestions[0].text == "정성껏 준비한 고기 한 접시"
    assert result.suggested_copy == {"headline": "정성껏 준비한 고기 한 접시"}
```

- [ ] **Step 2: Run service tests and verify failure**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_compliance.py -k "service_does_not_call_llm or attaches_validated_llm" -q
```

Expected: FAIL because `ComplianceService` does not accept contextual rewrite dependencies yet.

- [ ] **Step 3: Update service constructor and default builder**

Modify imports in `orchestrator/app/compliance/service.py`:

```python
from orchestrator.app.compliance.candidate_validator import ComplianceCandidateValidator
from orchestrator.app.compliance.llm_rewriter import ComplianceLLMRewriter, ComplianceRewriteAdapter
from orchestrator.app.compliance.rewrite_planner import ComplianceRewritePlanner
from orchestrator.app.compliance.schemas import ComplianceFinding, ComplianceRewriteContext, CopyComplianceState
```

Change constructor:

```python
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
```

Change `check_copy` signature:

```python
    def check_copy(
        self,
        copy: dict[str, Any],
        business_type: str | None,
        *,
        enable_contextual_rewrite: bool = False,
        rewrite_context: ComplianceRewriteContext | None = None,
        state: dict[str, Any] | None = None,
    ) -> CopyComplianceState:
```

In `_build_default_service()`, construct shared dependencies:

```python
    checker = PatternMatcher(rules)
    return ComplianceService(
        checker=checker,
        rewriter=StaticHintRewriter(rules_by_id),
        classifier=IndustryClassifier(),
        rewrite_planner=ComplianceRewritePlanner(rules_by_id),
        candidate_validator=ComplianceCandidateValidator(checker),
    )
```

- [ ] **Step 4: Add contextual suggestion attachment**

In `ComplianceService`, replace `_attach_suggestions(...)` with:

```python
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
                rewrite_attempts.append({
                    "rule_id": finding.rule_id,
                    "field": finding.field,
                    "matched_text": finding.matched_text,
                    "llm_attempted": llm_result.llm_attempted,
                    "fallback_used": llm_result.fallback_used,
                    "fallback_reason": llm_result.fallback_reason,
                    "candidate_count": len(llm_result.candidates),
                    "validated_count": len(validated),
                })
                if validated:
                    finding.suggested_text = validated[0].text
                    continue
            if self._rewriter:
                suggestion = self._rewriter.suggest(finding, original_text, domain)
                if suggestion:
                    finding.suggested_text = suggestion
        return rewrite_attempts
```

Update `check_copy` to capture attempts:

```python
        rewrite_attempts = self._attach_suggestions(
            copy,
            findings,
            domains,
            enable_contextual_rewrite=enable_contextual_rewrite,
            rewrite_context=rewrite_context,
            state=state,
        )
```

And include it in `CopyComplianceState`:

```python
            rewrite_attempts=rewrite_attempts,
```

- [ ] **Step 5: Ensure suggested_copy uses validated suggestions first**

In `_build_suggested_copy`, use:

```python
            suggestion = (
                finding.suggestions[0].text
                if finding.suggestions
                else finding.suggested_text
            )
            if not suggestion and self._rewriter:
                suggestion = self._rewriter.suggest(finding, original_text, domain)
```

- [ ] **Step 6: Run service tests and verify pass**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_compliance.py -k "service_does_not_call_llm or attaches_validated_llm" -q
```

Expected:

```text
2 passed
```

- [ ] **Step 7: Commit service integration**

Run:

```bash
git add orchestrator/app/compliance/service.py orchestrator/tests/test_compliance.py
git commit -m "feat: integrate contextual compliance rewrites"
```

---

## Task 7: Connect Graph Gate and Interrupt Payload

**Files:**
- Modify: `orchestrator/app/llm/nodes/copy_compliance.py`
- Test: `orchestrator/tests/test_compliance.py`

- [ ] **Step 1: Write failing graph payload tests**

Add:

```python
def test_copy_compliance_gate_enables_contextual_rewrite_only_for_gate():
    from orchestrator.app.llm.nodes.copy_compliance import copy_compliance_gate_node

    state = _state__test_compliance_gate_branch(business_type="restaurant", headline="최고다 고기!")
    state["context"]["item_or_service"] = "고기"
    state["context"]["promotion_goal"] = "방문 유도"
    state["user_plan"] = "premium"

    update = copy_compliance_gate_node(state)

    gate = update["copy_compliance_gate"]
    assert gate["findings"][0]["suggested_text"]
    assert "rewrite_attempts" in gate


def test_copy_compliance_interrupt_serializes_suggestions(monkeypatch):
    from orchestrator.app.llm.nodes import copy_compliance as node

    captured = {}
    def fake_interrupt(payload):
        captured["payload"] = payload
        return {"action": "use_suggestion"}

    monkeypatch.setattr(node, "interrupt", fake_interrupt)
    state = _state__test_compliance_gate_branch(business_type="restaurant", headline="최고다 고기!")
    state.update({
        "job_id": "job_1",
        "thread_id": "thread_1",
        "copy_compliance_status": "evidence_required",
        "copy_compliance_gate": {
            "findings": [
                {
                    "finding_id": "finding_1",
                    "field": "headline",
                    "matched_text": "최고",
                    "severity": "evidence_required",
                    "detection_method": "pattern",
                    "confidence": 1.0,
                    "reason": "실증 없는 최상급 표현",
                    "legal_basis": [],
                    "suggested_text": "정성껏 준비한 고기 한 접시",
                    "suggestions": [
                        {
                            "id": "suggestion_1",
                            "text": "정성껏 준비한 고기 한 접시",
                            "validation_status": "pass",
                            "rationale": "재검수 통과",
                        }
                    ],
                }
            ],
            "publication_ready": False,
        },
    })

    node.copy_compliance_interrupt_node(state)

    finding = captured["payload"]["findings"][0]
    assert finding["suggestions"][0]["text"] == "정성껏 준비한 고기 한 접시"
```

- [ ] **Step 2: Run graph payload tests and verify failure**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_compliance.py -k "gate_enables_contextual or interrupt_serializes_suggestions" -q
```

Expected: FAIL because graph node does not pass rewrite context and serialization omits `suggestions`.

- [ ] **Step 3: Build rewrite context in gate node**

Modify imports:

```python
from orchestrator.app.compliance.schemas import ComplianceRewriteContext
from orchestrator.app.graph.state import MarketingState, context_to_model, resolve_requested_ad_format
```

Add helper:

```python
def _rewrite_context_from_state(state: MarketingState) -> ComplianceRewriteContext:
    context = context_to_model(state.get("context"))
    return ComplianceRewriteContext(
        business_type=context.business_type,
        item_or_service=context.item_or_service,
        promotion_goal=context.promotion_goal,
        ad_format=resolve_requested_ad_format(state),
        channel=(state.get("current_brief") or {}).get("channel"),
    )
```

Change `copy_compliance_gate_node` service call:

```python
    result = svc.check_copy(
        copy,
        business_type,
        enable_contextual_rewrite=True,
        rewrite_context=_rewrite_context_from_state(state),
        state=dict(state),
    )
```

Do not change `input_compliance_precheck_node`; it must keep:

```python
    result = svc.check_copy({"headline": user_input}, business_type)
```

- [ ] **Step 4: Serialize suggestions**

In `_serialize_findings`, add:

```python
            "suggestions": [
                {
                    "id": s.get("id"),
                    "text": s.get("text"),
                    "validation_status": s.get("validation_status"),
                    "rationale": s.get("rationale"),
                }
                for s in (f.get("suggestions") or [])
                if isinstance(s, dict)
            ],
```

- [ ] **Step 5: Run graph tests and verify pass**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_compliance.py -k "gate_enables_contextual or interrupt_serializes_suggestions" -q
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Commit graph integration**

Run:

```bash
git add orchestrator/app/llm/nodes/copy_compliance.py orchestrator/tests/test_compliance.py
git commit -m "feat: expose validated compliance suggestions in graph"
```

---

## Task 8: Render Validated Suggestions in the Frontend

**Files:**
- Modify: `apps/web/lib/generation-job-interrupt.ts`
- Modify: `apps/web/components/generate/GenerationJobInterruptStep.tsx`
- Modify: `apps/web/types/contracts/generation-job-interrupt.fixtures.json`
- Test: `apps/web/lib/generation-job-interrupt.contract.test.ts`
- Test: `apps/web/components/generate/GenerationJobInterruptStep.test.tsx`

- [ ] **Step 1: Write failing parser test**

Modify `apps/web/types/contracts/generation-job-interrupt.fixtures.json` compliance finding:

```json
        "suggestions": [
          {
            "id": "suggestion_1",
            "text": "정성껏 준비한 고기 한 접시",
            "validation_status": "pass",
            "rationale": "최상급 표현을 제거하고 상품 맥락을 유지했어요."
          }
        ]
```

Add to `apps/web/lib/generation-job-interrupt.contract.test.ts`:

```ts
it("parses compliance rewrite suggestions", () => {
  const parsed = parseGenerationJobInterrupt(fixtures.copyComplianceReview);

  expect(parsed?.type).toBe("copy_compliance_review");
  if (parsed?.type !== "copy_compliance_review") return;
  expect(parsed.findings[0]?.suggestions?.[0]?.text).toBe("정성껏 준비한 고기 한 접시");
});
```

- [ ] **Step 2: Run parser test and verify failure**

Run:

```bash
npm test -- --run lib/generation-job-interrupt.contract.test.ts
```

from `apps/web`.

Expected: FAIL because `ComplianceFindingFE` has no `suggestions` field.

- [ ] **Step 3: Add frontend suggestion types**

Modify `apps/web/lib/generation-job-interrupt.ts`:

```ts
export type ComplianceSuggestionFE = {
  id?: string | null;
  text?: string | null;
  validation_status?: "pass" | "warn" | string | null;
  rationale?: string | null;
};
```

Extend `ComplianceFindingFE`:

```ts
  suggestions?: ComplianceSuggestionFE[];
```

- [ ] **Step 4: Write failing render test**

Add to `apps/web/components/generate/GenerationJobInterruptStep.test.tsx`:

```tsx
it("renders validated compliance suggestions before legacy suggested text", () => {
  const interrupt: ParsedGenerationJobInterrupt = {
    type: "copy_compliance_review",
    status: "evidence_required",
    summary: "광고 문구에 확인이 필요한 표현이 있어요.",
    actions: [{ id: "use_suggestion", label: "안전한 문구로 수정", available: true }],
    findings: [
      {
        finding_id: "finding_1",
        field: "headline",
        matched_text: "최고",
        severity: "evidence_required",
        reason: "객관적 근거가 필요한 최상급 표현입니다.",
        suggested_text: "고객 만족 코칭 프로그램",
        suggestions: [
          {
            id: "suggestion_1",
            text: "정성껏 준비한 고기 한 접시",
            validation_status: "pass",
            rationale: "재검수를 통과했어요.",
          },
        ],
      },
    ],
    raw: { type: "copy_compliance_review" },
  };

  render(
    <GenerationJobInterruptStep
      interrupt={interrupt}
      onBack={vi.fn()}
      onSelectCopyCandidate={vi.fn()}
      onSubmitCustomCopy={vi.fn()}
      onComplianceAction={vi.fn()}
    />
  );

  expect(screen.getByText("정성껏 준비한 고기 한 접시")).toBeTruthy();
  expect(screen.queryByText("고객 만족 코칭 프로그램")).toBeNull();
});
```

- [ ] **Step 5: Update component rendering**

In `GenerationJobInterruptStep.tsx`, inside `ComplianceFinding`, add:

```tsx
  const validatedSuggestions = (finding.suggestions ?? []).filter((suggestion) => suggestion.text?.trim());
  const legacySuggestion = finding.suggested_text && validatedSuggestions.length === 0 ? finding.suggested_text : null;
```

Replace the legacy suggestion block with:

```tsx
      {validatedSuggestions.length > 0 ? (
        <div className={styles.complianceSuggestion}>
          <span className={styles.complianceSuggestionLabel}>제안</span>
          <div>
            {validatedSuggestions.map((suggestion, index) => (
              <p key={suggestion.id ?? index}>{suggestion.text}</p>
            ))}
          </div>
        </div>
      ) : null}
      {legacySuggestion ? (
        <div className={styles.complianceSuggestion}>
          <span className={styles.complianceSuggestionLabel}>제안</span>
          <span>{legacySuggestion}</span>
        </div>
      ) : null}
```

- [ ] **Step 6: Run frontend tests**

Run from `apps/web`:

```bash
npm test -- --run lib/generation-job-interrupt.contract.test.ts components/generate/GenerationJobInterruptStep.test.tsx
```

Expected: both files pass.

- [ ] **Step 7: Commit frontend rendering**

Run from repo root:

```bash
git add apps/web/lib/generation-job-interrupt.ts apps/web/components/generate/GenerationJobInterruptStep.tsx apps/web/types/contracts/generation-job-interrupt.fixtures.json apps/web/lib/generation-job-interrupt.contract.test.ts apps/web/components/generate/GenerationJobInterruptStep.test.tsx
git commit -m "feat: show validated compliance rewrite suggestions"
```

---

## Task 9: Final Regression Tests and PR-Ready Commit Check

**Files:**
- No new files.
- Validate all files touched by Tasks 1-8.

- [ ] **Step 1: Run backend compliance tests**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_compliance.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run LLM service policy tests**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_llm_services.py -k "compliance_rewrite_node or model_policy or node_runner" -q
```

Expected: selected tests pass.

- [ ] **Step 3: Run frontend interrupt tests**

Run from `apps/web`:

```bash
npm test -- --run lib/generation-job-interrupt.contract.test.ts components/generate/GenerationJobInterruptStep.test.tsx
```

Expected: selected tests pass.

- [ ] **Step 4: Run TypeScript check**

Run from `apps/web`:

```bash
npm run typecheck
```

Expected: typecheck passes.

- [ ] **Step 5: Manual backend smoke check**

Run:

```bash
uv run python - <<'PY'
from orchestrator.app.compliance.service import get_compliance_service

svc = get_compliance_service()
result = svc.check_copy(
    {"headline": "최고다 고기!", "subcopy": "맛도 좋고 보기도 좋은 1등급 고기"},
    business_type="restaurant",
)
print(result.status)
print(result.suggested_copy)
print(result.findings[0].suggested_text)
PY
```

Expected:

```text
evidence_required
{'headline': '좋은 고기!', 'subcopy': '맛도 좋고 보기도 좋은 1등급 고기'}
좋은 고기!
```

This smoke check intentionally verifies deterministic fallback. LLM candidate behavior is covered by injected-adapter tests so it does not require paid API calls.

- [ ] **Step 6: Inspect git state**

Run:

```bash
git status --short --branch
```

Expected: only intentional files are modified or the tree is clean after commits. Ignore the pre-existing untracked file:

```text
?? docs/superpowers/plans/2026-06-13-generation-job-background-resume-reliability.md
```

- [ ] **Step 7: Push branch**

Run:

```bash
git push -u origin fix/srv/ad-compliance-suggestions
```

Expected: branch pushed successfully.

---

## PR Summary Template

```markdown
## 작업 요약

- 광고 규제 표현이 발견된 경우에만 문맥형 LLM 리라이터를 호출하도록 설계/구현했습니다.
- LLM 후보 문구를 기존 규제 엔진으로 다시 검수하고, 통과한 후보만 UI payload에 전달합니다.
- 기존 `suggested_text`/`suggested_copy` 호환성은 유지하면서 `suggestions[]`를 추가했습니다.
- LLM 호출이 불가능하거나 후보가 실패하면 deterministic fallback rewrite를 사용합니다.

## 변경 범위

- Orchestrator compliance schemas/planner/rewriter/validator/service
- LangGraph copy compliance gate interrupt payload
- Web interrupt parser and compliance review UI
- Backend/Frontend regression tests

## 테스트

- `uv run python -m pytest orchestrator/tests/test_compliance.py -q`
- `uv run python -m pytest orchestrator/tests/test_llm_services.py -k "compliance_rewrite_node or model_policy or node_runner" -q`
- `npm test -- --run lib/generation-job-interrupt.contract.test.ts components/generate/GenerationJobInterruptStep.test.tsx`
- `npm run typecheck`

## 확인 포인트

- `최고다 고기!` 입력 시 고기 맥락을 유지한 안전 문구가 제안되는지
- 규제 finding이 없는 문구에서 LLM 호출이 발생하지 않는지
- UI에서 하드코딩 예시 문구보다 검수 통과 suggestion이 우선 표시되는지
```

---

## Self-Review

- Spec coverage:
  - LLM is called only when compliance findings exist: Task 6 service tests and graph integration.
  - LLM is not the legal judge: Task 5 validates candidates through `PatternMatcher`.
  - Pass/warn candidates only reach UI: Task 5 validator and Task 7 serialization.
  - Fallback remains deterministic: Task 1 baseline and Task 6 fallback behavior.
  - UI payload gains `suggestions[]`: Task 7 and Task 8.

- Placeholder scan:
  - No unresolved marker text, open-ended implementation notes, or unspecified file paths remain.

- Type consistency:
  - `ComplianceRewriteCandidate`, `ComplianceValidatedSuggestion`, `ComplianceRewriteContext`, and `ComplianceRewritePlan` are defined in Task 2 and reused consistently in Tasks 3-8.
  - Frontend uses snake_case `validation_status` to match backend payload serialization.
