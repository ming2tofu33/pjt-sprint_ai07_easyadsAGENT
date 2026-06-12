# EasyAds 광고법 규제 게이트 — 테스트 계획 v1

> 기준: 2026-06-10 / 구현 계획 문서: [ad-compliance-implementation-phases-v1.md](./ad-compliance-implementation-phases-v1.md)

---

## 0. 전제: 기존 테스트 패턴

구현 전 파악한 기존 패턴 두 가지를 compliance 테스트도 그대로 따른다.

### 패턴 A — 노드 직접 호출 (`test_copy_candidates_branch.py` 방식)

```python
# _state() 헬퍼로 초기 상태 생성
def _state():
    return create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            copy_generation_mode="auto_pilot",
            context=MarketingContext(
                business_type="cafe",
                item_or_service="딸기라떼",
                promotion_goal="new_launch",
                extra={"ad_format": "instagram_feed"},
            ),
        )
    )

# 노드를 직접 호출하고 state를 수동으로 머지
state = _state()
update = some_node(state)
state.update(update)
assert state["some_field"] == expected
```

### 패턴 B — 그래프 e2e + HITL resume (`test_marketing_graph_e2e_mock.py` 방식)

```python
# build_marketing_graph()는 내장 checkpointer가 있으므로
# MemorySaver를 별도로 만들 필요 없음
graph = build_marketing_graph()
config = {"configurable": {"thread_id": "test-001"}}

# Step 1: 첫 invoke — interrupt 발생 시 __interrupt__ 키 존재
result = graph.invoke(initial_state, config=config)
assert "__interrupt__" in result

# Step 2: 같은 graph, 같은 config로 resume
from langgraph.types import Command
result = graph.invoke(Command(resume={...}), config=config)
assert result["status"] == "done"
```

---

## 1. 테스트 파일 맵

| 파일 | 담당 Phase | 성격 |
|------|-----------|------|
| `tests/test_compliance_rule_engine.py` | Phase 1 | Unit — rule engine, service |
| `tests/test_compliance_industry_classifier.py` | Phase 1 | Unit — 업종 도메인 매핑 |
| `tests/test_compliance_yaml_contracts.py` | Phase 1 | Contract — YAML 스키마 검증 |
| `tests/test_compliance_candidate_badge.py` | Phase 2 | Integration — candidate 배지 |
| `tests/test_compliance_gate_node.py` | Phase 3 | Integration — 노드 직접 호출 |
| `tests/test_compliance_gate_e2e.py` | Phase 3 | E2E — 전체 그래프 + HITL |
| `tests/test_compliance_result_payload.py` | Phase 4 | Integration — result_node 출력 |
| `tests/test_compliance_prompt_injection.py` | Phase 5 | Integration — metadata 검증 |

---

## 2. Phase 1 — Rule Engine Unit Tests

### `tests/test_compliance_rule_engine.py`

```python
"""Rule engine 단위 테스트.
그래프 없음. ComplianceService를 직접 생성해 호출한다."""

import pytest
from orchestrator.app.compliance.rule_loader import load_rules
from orchestrator.app.compliance.rule_engine import PatternMatcher
from orchestrator.app.compliance.industry_classifier import IndustryClassifier
from orchestrator.app.compliance.rewrite_strategy import StaticHintRewriter
from orchestrator.app.compliance.service import ComplianceService


def _svc() -> ComplianceService:
    """get_compliance_service() 대신 직접 생성. 테스트마다 독립성 보장."""
    rules = load_rules()
    return ComplianceService(
        checker=PatternMatcher(rules),
        rewriter=StaticHintRewriter({r.rule_id: r for r in rules}),
        classifier=IndustryClassifier(),
    )


# ── pass ─────────────────────────────────────────────────────────────────────

class TestPass:
    def test_safe_cafe_copy(self):
        result = _svc().check_copy(
            {"headline": "기분 좋은 딸기라떼 한 잔", "subcopy": "오늘의 카페 타임"},
            business_type="cafe",
        )
        assert result.status == "pass"
        assert result.findings == []
        assert result.publication_ready is True

    def test_safe_restaurant_copy(self):
        result = _svc().check_copy(
            {"headline": "오늘 저녁 삼겹살 어떠세요", "subcopy": "신선한 국내산 돼지고기"},
            business_type="restaurant",
        )
        assert result.status == "pass"

    def test_safe_fitness_program_description(self):
        # "4주 동안"은 기간 설명 — 보장 아님
        result = _svc().check_copy(
            {"headline": "4주 동안 체계적으로 준비하는 바디프로필 코칭"},
            business_type="fitness",
        )
        assert result.status == "pass"

    def test_safe_skincare_copy(self):
        result = _svc().check_copy(
            {"headline": "피부 고민을 차분히 상담하고 맞춤 관리를 제안합니다"},
            business_type="beauty_skincare",
        )
        assert result.status == "pass"


# ── warn ─────────────────────────────────────────────────────────────────────

class TestWarn:
    def test_detox_term_is_warn_for_cafe(self):
        result = _svc().check_copy(
            {"headline": "디톡스 그린 스무디"},
            business_type="cafe",
        )
        assert result.status == "warn"
        # warn은 논블로킹
        assert result.publication_ready is True

    def test_diet_term_is_warn_for_cafe(self):
        result = _svc().check_copy(
            {"headline": "다이어트 딸기 요거트"},
            business_type="cafe",
        )
        assert result.status == "warn"
        assert result.publication_ready is True

    def test_warn_finding_has_hitl_question(self):
        result = _svc().check_copy(
            {"headline": "디톡스 그린 스무디"},
            business_type="cafe",
        )
        warn_findings = [f for f in result.findings if f.severity == "warn"]
        assert len(warn_findings) > 0
        # warn 규칙은 반드시 HITL 질문을 포함해야 함
        assert any(f.hitl_question for f in warn_findings)

    def test_duration_term_is_warn_for_fitness(self):
        # "4주 만에"는 결과 보장과 결합 전까지 warn
        result = _svc().check_copy(
            {"headline": "4주 만에 달라진 나를 만나세요"},
            business_type="fitness",
        )
        assert result.status == "warn"


# ── evidence_required ─────────────────────────────────────────────────────────

class TestEvidenceRequired:
    def test_superlative_requires_evidence(self):
        result = _svc().check_copy(
            {"headline": "국내 1위 헬스장"},
            business_type="fitness",
        )
        assert result.status == "evidence_required"
        assert result.publication_ready is False

    def test_finding_has_evidence_requirements(self):
        result = _svc().check_copy(
            {"headline": "국내 1위 헬스장"},
            business_type="fitness",
        )
        finding = next(f for f in result.findings if f.severity == "evidence_required")
        assert len(finding.evidence_requirements) > 0

    def test_guarantee_with_number_requires_evidence(self):
        result = _svc().check_copy(
            {"headline": "4주 만에 10kg 감량 보장"},
            business_type="fitness",
        )
        assert result.status == "evidence_required"

    def test_perfect_guarantee_expression_requires_evidence(self):
        result = _svc().check_copy(
            {"headline": "100% 보장되는 결과"},
            business_type="restaurant",
        )
        assert result.status == "evidence_required"


# ── block ─────────────────────────────────────────────────────────────────────

class TestBlock:
    def test_food_medical_claim_is_blocked(self):
        result = _svc().check_copy(
            {"headline": "독소 배출에 도움을 주는 딸기라떼"},
            business_type="cafe",
        )
        assert result.status == "block"
        assert result.publication_ready is False

    def test_medical_treatment_guarantee_is_blocked(self):
        result = _svc().check_copy(
            {"headline": "여드름 완치 보장"},
            business_type="beauty_skincare",
        )
        assert result.status == "block"

    def test_cosmetic_medical_claim_is_blocked(self):
        result = _svc().check_copy(
            {"headline": "피부 재생 100% 개선"},
            business_type="beauty_skincare",
        )
        assert result.status == "block"

    def test_hospital_before_after_is_blocked(self):
        result = _svc().check_copy(
            {"headline": "Before & After로 확인하는 시술 효과"},
            business_type="hospital",
        )
        assert result.status == "block"

    def test_block_finding_has_legal_basis(self):
        result = _svc().check_copy(
            {"headline": "독소 배출에 도움을 주는 딸기라떼"},
            business_type="cafe",
        )
        block_finding = next(f for f in result.findings if f.severity == "block")
        assert len(block_finding.legal_basis) > 0
        assert block_finding.legal_basis[0].law_name != ""


# ── severity 집계: 여러 finding 중 가장 높은 severity ──────────────────────────

class TestSeverityAggregation:
    def test_block_wins_over_warn(self):
        # headline: warn, subcopy: block
        result = _svc().check_copy(
            {"headline": "디톡스 딸기라떼", "subcopy": "독소 배출 효과"},
            business_type="cafe",
        )
        assert result.status == "block"

    def test_evidence_required_wins_over_warn(self):
        result = _svc().check_copy(
            {"headline": "디톡스 딸기라떼", "subcopy": "국내 1위 맛"},
            business_type="cafe",
        )
        assert result.status == "evidence_required"

    def test_multiple_fields_all_scanned(self):
        result = _svc().check_copy(
            {
                "headline": "기분 좋은 한 잔",
                "subcopy": "독소 배출 효과",
                "cta": "지금 주문",
            },
            business_type="cafe",
        )
        assert result.status == "block"
        # cta는 깨끗하고, subcopy에서 찾아야 함
        blocked_fields = {f.field for f in result.findings if f.severity == "block"}
        assert "sub_copy" in blocked_fields


# ── original_copy 보존 (핵심 불변 조건) ──────────────────────────────────────

class TestOriginalCopyPreservation:
    def test_original_copy_is_never_modified(self):
        original = {"headline": "독소 배출에 도움을 주는 딸기라떼"}
        result = _svc().check_copy(original, business_type="cafe")
        # service 내부에서 어떤 일이 있어도 original_copy는 변하지 않아야 함
        assert result.original_copy == {"headline": "독소 배출에 도움을 주는 딸기라떼"}

    def test_suggested_copy_is_different_from_original(self):
        result = _svc().check_copy(
            {"headline": "독소 배출에 도움을 주는 딸기라떼"},
            business_type="cafe",
        )
        assert result.suggested_copy is not None
        assert result.suggested_copy.get("headline") != "독소 배출에 도움을 주는 딸기라떼"

    def test_pass_result_has_no_suggested_copy(self):
        result = _svc().check_copy(
            {"headline": "기분 좋은 딸기라떼 한 잔"},
            business_type="cafe",
        )
        assert result.suggested_copy is None


# ── user_override ≠ publication_ready (핵심 안전 불변 조건) ──────────────────

class TestPublicationReadyInvariant:
    def test_pass_is_publication_ready(self):
        result = _svc().check_copy(
            {"headline": "기분 좋은 딸기라떼"},
            business_type="cafe",
        )
        assert result.publication_ready is True

    def test_warn_is_publication_ready(self):
        # warn은 비차단이므로 게시 가능
        result = _svc().check_copy(
            {"headline": "디톡스 딸기라떼"},
            business_type="cafe",
        )
        assert result.status == "warn"
        assert result.publication_ready is True

    def test_evidence_required_is_not_publication_ready(self):
        result = _svc().check_copy(
            {"headline": "국내 1위 헬스장"},
            business_type="fitness",
        )
        assert result.publication_ready is False

    def test_block_is_not_publication_ready(self):
        result = _svc().check_copy(
            {"headline": "독소 배출에 도움을 주는 딸기라떼"},
            business_type="cafe",
        )
        assert result.publication_ready is False
```

---

### `tests/test_compliance_industry_classifier.py`

```python
"""업종 → 도메인 매핑 테스트."""

from orchestrator.app.compliance.industry_classifier import IndustryClassifier


def _cls():
    return IndustryClassifier()


class TestDomainMapping:
    def test_cafe_maps_to_food_and_general(self):
        domains = _cls().get_domains("cafe")
        assert "food" in domains
        assert "general_ad" in domains

    def test_beauty_skincare_maps_to_cosmetic(self):
        domains = _cls().get_domains("beauty_skincare")
        assert "cosmetic" in domains

    def test_hospital_maps_to_medical(self):
        domains = _cls().get_domains("hospital")
        assert "medical" in domains

    def test_unknown_type_falls_back_to_general(self):
        domains = _cls().get_domains("unknown_type_xyz")
        assert domains == ["general_ad"]

    def test_none_falls_back_to_general(self):
        domains = _cls().get_domains(None)
        assert domains == ["general_ad"]

    def test_all_food_types_include_food_domain(self):
        food_types = ["cafe", "restaurant", "restaurant_bbq", "restaurant_japanese", "restaurant_korean"]
        cls = _cls()
        for biz_type in food_types:
            assert "food" in cls.get_domains(biz_type), f"{biz_type} should map to food domain"
```

---

### `tests/test_compliance_yaml_contracts.py`

```python
"""YAML 스키마 계약 테스트 — rule pack 형식 오류를 조기에 잡는다."""

import pytest
from orchestrator.app.compliance.rule_loader import load_rules, load_legal_basis


class TestYamlContracts:
    def test_rules_load_without_error(self):
        rules = load_rules()
        assert len(rules) > 0

    def test_legal_basis_loads_without_error(self):
        basis = load_legal_basis()
        assert len(basis) > 0

    def test_every_rule_has_rule_id(self):
        for rule in load_rules():
            assert rule.rule_id, f"rule_id missing: {rule}"

    def test_every_rule_has_valid_severity(self):
        valid = {"warn", "evidence_required", "block"}
        for rule in load_rules():
            assert rule.severity in valid, f"{rule.rule_id}: invalid severity '{rule.severity}'"

    def test_every_block_rule_has_legal_basis(self):
        for rule in load_rules():
            if rule.severity == "block":
                assert rule.legal_basis_ref is not None, \
                    f"{rule.rule_id}: block rule must have legal_basis_ref"

    def test_every_block_rule_has_at_least_one_example(self):
        for rule in load_rules():
            if rule.severity == "block":
                assert len(rule.examples) > 0, \
                    f"{rule.rule_id}: block rule must have at least one example (for suggested_copy)"

    def test_every_warn_rule_has_hitl_question(self):
        for rule in load_rules():
            if rule.severity == "warn":
                assert rule.hitl_question, \
                    f"{rule.rule_id}: warn rule must have hitl_question"

    def test_every_evidence_required_rule_has_evidence_requirements(self):
        for rule in load_rules():
            if rule.severity == "evidence_required":
                assert len(rule.evidence_requirements) > 0, \
                    f"{rule.rule_id}: evidence_required rule must list evidence_requirements"

    def test_every_rule_has_embedding_text(self):
        # RAG 확장 준비: embedding_text 없으면 인덱싱 불가
        for rule in load_rules():
            assert rule.embedding_text.strip(), \
                f"{rule.rule_id}: embedding_text must not be empty"

    def test_no_duplicate_rule_ids(self):
        rule_ids = [r.rule_id for r in load_rules()]
        assert len(rule_ids) == len(set(rule_ids)), "Duplicate rule_id found"
```

---

## 3. Phase 2 — Candidate 배지 Integration Tests

### `tests/test_compliance_candidate_badge.py`

```python
"""copy_candidate_generation_node 배지 부착 테스트.
노드를 직접 호출하므로 그래프 변경과 무관하다."""

from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.nodes.copy_candidates import copy_candidate_generation_node
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def _state(business_type="restaurant", item_or_service="삼겹살"):
    return create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            copy_generation_mode="suggest_candidates",
            context=MarketingContext(
                business_type=business_type,
                item_or_service=item_or_service,
                promotion_goal="reservation_cta",
                extra={"ad_format": "instagram_feed"},
            ),
        )
    )


class TestCandidateBadge:
    def test_every_candidate_has_compliance_badge(self):
        update = copy_candidate_generation_node(_state())
        for candidate in update["copy_candidates"]:
            assert "compliance" in candidate["metadata"], \
                f"candidate {candidate['id']} is missing compliance badge"

    def test_compliance_badge_has_required_fields(self):
        update = copy_candidate_generation_node(_state())
        for candidate in update["copy_candidates"]:
            badge = candidate["metadata"]["compliance"]
            assert "status" in badge
            assert "finding_count" in badge
            assert "disabled" in badge

    def test_safe_copy_badge_is_not_disabled(self):
        update = copy_candidate_generation_node(_state("restaurant", "삼겹살"))
        for candidate in update["copy_candidates"]:
            badge = candidate["metadata"]["compliance"]
            # 삼겹살 레스토랑 카피는 안전해야 함
            assert badge["disabled"] is False, \
                f"safe copy should not be disabled: {candidate['metadata']['compliance']}"

    def test_badge_does_not_remove_or_reorder_candidates(self):
        update = copy_candidate_generation_node(_state())
        # 배지 부착이 후보 수를 변경하면 안 됨
        assert len(update["copy_candidates"]) >= 1
        # id 순서도 유지
        ids = [c["id"] for c in update["copy_candidates"]]
        assert ids == sorted(ids, key=lambda x: int(x.split("_")[1]))

    def test_badge_status_reflects_actual_compliance(self):
        """배지 status가 실제 rule engine 결과와 일치하는지 확인."""
        from orchestrator.app.compliance.service import get_compliance_service

        update = copy_candidate_generation_node(_state())
        svc = get_compliance_service()

        for candidate in update["copy_candidates"]:
            badge = candidate["metadata"]["compliance"]
            expected = svc.check_copy(
                {"headline": candidate.get("headline"), "subcopy": candidate.get("subcopy")},
                business_type="restaurant",
            )
            assert badge["status"] == expected.status
```

---

## 4. Phase 3 — Gate 노드 Integration + E2E Tests

### `tests/test_compliance_gate_node.py` — 노드 직접 호출

```python
"""copy_compliance_gate_node / resolution_node 단위 테스트.
그래프 없이 노드를 직접 호출한다."""

from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.nodes.copy_compliance import (
    copy_compliance_gate_node,
    copy_compliance_resolution_node,
)
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def _state(business_type="cafe", headline="기분 좋은 딸기라떼"):
    s = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            copy_generation_mode="auto_pilot",
            context=MarketingContext(
                business_type=business_type,
                item_or_service="딸기라떼",
                promotion_goal="new_launch",
                extra={"ad_format": "instagram_feed"},
            ),
        )
    )
    s["marketing_copy"] = {"headline": headline, "subcopy": "오늘의 카페 타임", "cta": "지금 주문"}
    return s


# ── Gate 노드 반환값 ──────────────────────────────────────────────────────────

class TestGateNodeOutput:
    def test_safe_copy_returns_pass(self):
        update = copy_compliance_gate_node(_state(headline="기분 좋은 딸기라떼"))
        assert update["copy_compliance_status"] == "pass"
        assert update["copy_compliance"]["publication_ready"] is True

    def test_detox_copy_returns_warn(self):
        update = copy_compliance_gate_node(_state(headline="디톡스 딸기라떼"))
        assert update["copy_compliance_status"] == "warn"
        assert update["copy_compliance"]["publication_ready"] is True

    def test_blocked_copy_returns_block(self):
        update = copy_compliance_gate_node(_state(headline="독소 배출 딸기라떼"))
        assert update["copy_compliance_status"] == "block"
        assert update["copy_compliance"]["publication_ready"] is False

    def test_gate_never_modifies_marketing_copy(self):
        original_headline = "독소 배출 딸기라떼"
        state = _state(headline=original_headline)
        update = copy_compliance_gate_node(state)
        # gate 노드 반환값에 marketing_copy가 없어야 함
        assert "marketing_copy" not in update

    def test_gate_stores_findings_in_state(self):
        update = copy_compliance_gate_node(_state(headline="독소 배출 딸기라떼"))
        findings = update["copy_compliance"]["findings"]
        assert len(findings) > 0
        assert all("finding_id" in f for f in findings)

    def test_gate_stores_original_copy_for_audit(self):
        state = _state(headline="독소 배출 딸기라떼")
        update = copy_compliance_gate_node(state)
        original = update["copy_compliance"]["original_copy"]
        assert original["headline"] == "독소 배출 딸기라떼"


# ── Resolution 노드 — use_suggestion ─────────────────────────────────────────

class TestResolutionUseSuggestion:
    def _blocked_state(self):
        state = _state(headline="독소 배출 딸기라떼")
        state.update(copy_compliance_gate_node(state))
        return state

    def test_use_suggestion_updates_marketing_copy(self):
        state = self._blocked_state()
        state["copy_compliance_resolution"] = {"action": "use_suggestion"}
        update = copy_compliance_resolution_node(state)
        # marketing_copy가 교체되어야 함
        assert "marketing_copy" in update
        assert update["marketing_copy"]["headline"] != "독소 배출 딸기라떼"

    def test_use_suggestion_sets_publication_ready_true(self):
        state = self._blocked_state()
        state["copy_compliance_resolution"] = {"action": "use_suggestion"}
        update = copy_compliance_resolution_node(state)
        assert update["copy_compliance_publication_ready"] is True

    def test_use_suggestion_records_user_decision(self):
        state = self._blocked_state()
        state["copy_compliance_resolution"] = {"action": "use_suggestion"}
        update = copy_compliance_resolution_node(state)
        assert update["copy_compliance"]["user_decision"] == "use_suggestion"


# ── Resolution 노드 — keep_original_draft ────────────────────────────────────

class TestResolutionKeepOriginal:
    def _blocked_state(self):
        state = _state(headline="독소 배출 딸기라떼")
        state.update(copy_compliance_gate_node(state))
        return state

    def test_keep_original_sets_manual_review(self):
        state = self._blocked_state()
        state["copy_compliance_resolution"] = {"action": "keep_original_draft"}
        update = copy_compliance_resolution_node(state)
        assert update["copy_compliance_status"] == "manual_review_required"

    def test_keep_original_sets_publication_ready_false(self):
        state = self._blocked_state()
        state["copy_compliance_resolution"] = {"action": "keep_original_draft"}
        update = copy_compliance_resolution_node(state)
        assert update["copy_compliance_publication_ready"] is False

    def test_keep_original_sets_user_acknowledged_risk(self):
        state = self._blocked_state()
        state["copy_compliance_resolution"] = {"action": "keep_original_draft"}
        update = copy_compliance_resolution_node(state)
        assert update["copy_compliance"]["user_acknowledged_risk"] is True

    def test_keep_original_does_not_modify_marketing_copy(self):
        """user_override ≠ publication_ready — 원문 그대로 유지."""
        state = self._blocked_state()
        state["copy_compliance_resolution"] = {"action": "keep_original_draft"}
        update = copy_compliance_resolution_node(state)
        # marketing_copy 필드가 반환값에 없거나, 있어도 원문과 동일해야 함
        if "marketing_copy" in update:
            assert update["marketing_copy"]["headline"] == "독소 배출 딸기라떼"


# ── Resolution 노드 — submit_claim ───────────────────────────────────────────

class TestResolutionSubmitClaim:
    def _evidence_state(self):
        state = _state(headline="국내 1위 카페")
        state.update(copy_compliance_gate_node(state))
        return state

    def test_submit_claim_stores_evidence(self):
        state = self._evidence_state()
        evidence = {"type": "survey", "source": "한국리서치", "date": "2025-01"}
        state["copy_compliance_resolution"] = {"action": "submit_claim", "evidence": evidence}
        update = copy_compliance_resolution_node(state)
        assert len(update["copy_compliance"]["evidence_submitted"]) == 1
        assert update["copy_compliance"]["evidence_submitted"][0] == evidence

    def test_submit_claim_requires_manual_review(self):
        state = self._evidence_state()
        state["copy_compliance_resolution"] = {
            "action": "submit_claim",
            "evidence": {"type": "certificate", "source": "인증기관"},
        }
        update = copy_compliance_resolution_node(state)
        assert update["copy_compliance_status"] == "manual_review_required"
        assert update["copy_compliance_publication_ready"] is False
```

---

### `tests/test_compliance_gate_e2e.py` — 전체 그래프 HITL

```python
"""E2E 테스트: 전체 그래프 실행 + HITL interrupt/resume.
build_marketing_graph()의 내장 checkpointer를 사용한다.
같은 config로 두 번 invoke하면 resume된다."""

import pytest
from langgraph.types import Command
from orchestrator.app.graph.builder import build_marketing_graph


def _base_input(thread_id: str, business_type: str, item: str, headline_override: str | None = None):
    base = {
        "user_input": "ready",
        "job_id": thread_id,
        "thread_id": thread_id,
        "copy_generation_mode": "auto_pilot",
        "context": {
            "business_type": business_type,
            "item_or_service": item,
            "promotion_goal": "new_launch",
            "extra": {"ad_format": "instagram_feed"},
        },
    }
    if headline_override:
        # auto_pilot 모드에서 특정 카피로 강제하려면 marketing_copy를 미리 세팅
        base["marketing_copy"] = {"headline": headline_override}
    return base


# ── 안전한 카피: interrupt 없이 통과 ─────────────────────────────────────────

class TestPassesWithoutInterrupt:
    def test_safe_restaurant_copy_completes_without_interrupt(self):
        """기존 e2e mock 테스트가 Phase 3 이후에도 통과하는지 확인."""
        graph = build_marketing_graph()
        result = graph.invoke(
            {
                "user_input": "ready",
                "job_id": "compliance-e2e-pass-restaurant",
                "thread_id": "compliance-e2e-pass-restaurant",
                "copy_generation_mode": "auto_pilot",
                "context": {
                    "business_type": "restaurant",
                    "item_or_service": "삼겹살",
                    "promotion_goal": "reservation_cta",
                    "extra": {"ad_format": "instagram_feed"},
                },
            },
            config={"configurable": {"thread_id": "compliance-e2e-pass-restaurant"}},
        )
        assert "__interrupt__" not in result
        assert result["status"] == "done"
        assert result.get("copy_compliance_status") in {None, "pass", "warn"}

    def test_warn_severity_does_not_interrupt(self):
        """warn은 논블로킹 — 카피를 세팅해도 interrupt 없이 진행."""
        graph = build_marketing_graph()
        thread = "compliance-e2e-warn"
        result = graph.invoke(
            {
                "user_input": "ready",
                "job_id": thread,
                "thread_id": thread,
                "copy_generation_mode": "custom",
                "marketing_copy": {"headline": "디톡스 딸기라떼", "subcopy": "상큼한 한 잔"},
                "context": {
                    "business_type": "cafe",
                    "item_or_service": "딸기라떼",
                    "promotion_goal": "new_launch",
                    "extra": {"ad_format": "instagram_feed"},
                },
            },
            config={"configurable": {"thread_id": thread}},
        )
        # warn은 통과
        assert "__interrupt__" not in result
        assert result.get("copy_compliance_status") == "warn"
        assert result.get("copy_compliance_publication_ready") is True


# ── Interrupt 발생 확인 ────────────────────────────────────────────────────────

class TestInterruptFires:
    def test_blocked_copy_fires_compliance_interrupt(self):
        graph = build_marketing_graph()
        thread = "compliance-e2e-block-fires"
        result = graph.invoke(
            {
                "user_input": "ready",
                "job_id": thread,
                "thread_id": thread,
                "copy_generation_mode": "custom",
                "marketing_copy": {"headline": "독소 배출 딸기라떼"},
                "context": {
                    "business_type": "cafe",
                    "item_or_service": "딸기라떼",
                    "promotion_goal": "new_launch",
                    "extra": {"ad_format": "instagram_feed"},
                },
            },
            config={"configurable": {"thread_id": thread}},
        )
        assert "__interrupt__" in result
        payload = result["__interrupt__"][0].value
        assert payload["type"] == "copy_compliance_review"
        assert payload["status"] in {"evidence_required", "blocked"}

    def test_interrupt_payload_has_findings(self):
        graph = build_marketing_graph()
        thread = "compliance-e2e-payload-check"
        result = graph.invoke(
            {
                "user_input": "ready",
                "job_id": thread,
                "thread_id": thread,
                "copy_generation_mode": "custom",
                "marketing_copy": {"headline": "독소 배출 딸기라떼"},
                "context": {
                    "business_type": "cafe",
                    "item_or_service": "딸기라떼",
                    "promotion_goal": "new_launch",
                    "extra": {"ad_format": "instagram_feed"},
                },
            },
            config={"configurable": {"thread_id": thread}},
        )
        payload = result["__interrupt__"][0].value
        assert len(payload["findings"]) > 0
        # FE가 소비할 필드 존재 확인
        finding = payload["findings"][0]
        assert "finding_id" in finding
        assert "matched_text" in finding
        assert "severity" in finding
        assert "legal_basis" in finding

    def test_interrupt_payload_has_all_action_options(self):
        graph = build_marketing_graph()
        thread = "compliance-e2e-actions-check"
        result = graph.invoke(
            {
                "user_input": "ready",
                "job_id": thread,
                "thread_id": thread,
                "copy_generation_mode": "custom",
                "marketing_copy": {"headline": "독소 배출 딸기라떼"},
                "context": {
                    "business_type": "cafe",
                    "item_or_service": "딸기라떼",
                    "promotion_goal": "new_launch",
                    "extra": {"ad_format": "instagram_feed"},
                },
            },
            config={"configurable": {"thread_id": thread}},
        )
        payload = result["__interrupt__"][0].value
        action_ids = {a["id"] for a in payload["actions"]}
        assert "use_suggestion" in action_ids
        assert "edit_manually" in action_ids
        assert "submit_claim" in action_ids
        assert "keep_original_draft" in action_ids
        assert "cancel" in action_ids


# ── HITL Resume — use_suggestion ─────────────────────────────────────────────

class TestResumeUseSuggestion:
    """핵심 HITL 흐름: interrupt → use_suggestion → 카피 교체 → done."""

    def test_resume_use_suggestion_completes_to_done(self):
        graph = build_marketing_graph()
        config = {"configurable": {"thread_id": "compliance-resume-use-suggestion"}}

        # Step 1: interrupt 발생
        result = graph.invoke(
            {
                "user_input": "ready",
                "job_id": "compliance-resume-use-suggestion",
                "thread_id": "compliance-resume-use-suggestion",
                "copy_generation_mode": "custom",
                "marketing_copy": {"headline": "독소 배출 딸기라떼"},
                "context": {
                    "business_type": "cafe",
                    "item_or_service": "딸기라떼",
                    "promotion_goal": "new_launch",
                    "extra": {"ad_format": "instagram_feed"},
                },
            },
            config=config,
        )
        assert "__interrupt__" in result

        # Step 2: use_suggestion 선택 후 resume
        result = graph.invoke(
            Command(resume={"action": "use_suggestion"}),
            config=config,
        )

        assert result["status"] == "done"
        assert result["copy_compliance_publication_ready"] is True
        # marketing_copy가 safe한 문구로 교체됨
        assert result["marketing_copy"]["headline"] != "독소 배출 딸기라떼"

    def test_resumed_copy_passes_compliance_check(self):
        """use_suggestion 후 최종 카피가 실제로 안전한지 재검증."""
        from orchestrator.app.compliance.service import get_compliance_service

        graph = build_marketing_graph()
        config = {"configurable": {"thread_id": "compliance-resume-verify-safe"}}

        result = graph.invoke(
            {
                "user_input": "ready",
                "job_id": "compliance-resume-verify-safe",
                "thread_id": "compliance-resume-verify-safe",
                "copy_generation_mode": "custom",
                "marketing_copy": {"headline": "독소 배출 딸기라떼"},
                "context": {
                    "business_type": "cafe",
                    "item_or_service": "딸기라떼",
                    "promotion_goal": "new_launch",
                    "extra": {"ad_format": "instagram_feed"},
                },
            },
            config=config,
        )
        graph.invoke(Command(resume={"action": "use_suggestion"}), config=config)

        final_copy = result["marketing_copy"]
        svc = get_compliance_service()
        final_check = svc.check_copy(final_copy, business_type="cafe")
        assert final_check.status in {"pass", "warn"}


# ── HITL Resume — keep_original_draft ────────────────────────────────────────

class TestResumeKeepOriginal:
    """user_override ≠ publication_ready 불변 조건의 E2E 검증."""

    def test_keep_original_draft_completes_but_not_publication_ready(self):
        graph = build_marketing_graph()
        config = {"configurable": {"thread_id": "compliance-resume-keep-draft"}}

        result = graph.invoke(
            {
                "user_input": "ready",
                "job_id": "compliance-resume-keep-draft",
                "thread_id": "compliance-resume-keep-draft",
                "copy_generation_mode": "custom",
                "marketing_copy": {"headline": "독소 배출 딸기라떼"},
                "context": {
                    "business_type": "cafe",
                    "item_or_service": "딸기라떼",
                    "promotion_goal": "new_launch",
                    "extra": {"ad_format": "instagram_feed"},
                },
            },
            config=config,
        )
        assert "__interrupt__" in result

        result = graph.invoke(
            Command(resume={"action": "keep_original_draft"}),
            config=config,
        )

        # 흐름은 계속되어야 함
        assert result["status"] == "done"
        # 하지만 게시 불가 상태
        assert result["copy_compliance_publication_ready"] is False
        assert result["copy_compliance"]["user_acknowledged_risk"] is True
        # 원문 카피가 그대로 유지됨
        assert result["marketing_copy"]["headline"] == "독소 배출 딸기라떼"


# ── HITL Resume — cancel ──────────────────────────────────────────────────────

class TestResumeCancel:
    def test_cancel_terminates_flow(self):
        graph = build_marketing_graph()
        config = {"configurable": {"thread_id": "compliance-resume-cancel"}}

        result = graph.invoke(
            {
                "user_input": "ready",
                "job_id": "compliance-resume-cancel",
                "thread_id": "compliance-resume-cancel",
                "copy_generation_mode": "custom",
                "marketing_copy": {"headline": "독소 배출 딸기라떼"},
                "context": {
                    "business_type": "cafe",
                    "item_or_service": "딸기라떼",
                    "promotion_goal": "new_launch",
                    "extra": {"ad_format": "instagram_feed"},
                },
            },
            config=config,
        )
        assert "__interrupt__" in result

        result = graph.invoke(
            Command(resume={"action": "cancel"}),
            config=config,
        )

        assert result["status"] == "compliance_blocked"
        assert result.get("t2i_result") is None


# ── HITL Resume — edit_manually ───────────────────────────────────────────────

class TestResumeEditManually:
    def test_edit_manually_routes_to_custom_copy_input(self):
        """edit_manually → custom_copy_input interrupt 발생 확인."""
        graph = build_marketing_graph()
        config = {"configurable": {"thread_id": "compliance-resume-edit-manually"}}

        result = graph.invoke(
            {
                "user_input": "ready",
                "job_id": "compliance-resume-edit-manually",
                "thread_id": "compliance-resume-edit-manually",
                "copy_generation_mode": "custom",
                "marketing_copy": {"headline": "독소 배출 딸기라떼"},
                "context": {
                    "business_type": "cafe",
                    "item_or_service": "딸기라떼",
                    "promotion_goal": "new_launch",
                    "extra": {"ad_format": "instagram_feed"},
                },
            },
            config=config,
        )

        result = graph.invoke(
            Command(resume={"action": "edit_manually"}),
            config=config,
        )

        # custom_copy_input interrupt가 다시 발생해야 함
        assert "__interrupt__" in result
        payload = result["__interrupt__"][0].value
        assert payload["type"] != "copy_compliance_review"  # compliance interrupt가 아님


# ── 기존 테스트 회귀 ────────────────────────────────────────────────────────────

class TestRegressionExistingTests:
    """Phase 3 이후 기존 e2e 테스트가 깨지지 않는지 확인하는 smoke test."""

    def test_existing_restaurant_e2e_still_works(self):
        """test_marketing_graph_runs_to_mock_t2i_when_context_is_complete 동일 조건."""
        graph = build_marketing_graph()
        result = graph.invoke(
            {
                "user_input": "ready",
                "job_id": "regression-restaurant",
                "thread_id": "regression-restaurant",
                "copy_generation_mode": "auto_pilot",
                "context": {
                    "business_type": "restaurant",
                    "item_or_service": "삼겹살",
                    "promotion_goal": "reservation_cta",
                    "extra": {"ad_format": "instagram_feed"},
                },
            },
            config={"configurable": {"thread_id": "regression-restaurant"}},
        )
        assert "__interrupt__" not in result
        assert result["status"] == "done"
        assert result["t2i_result"]["engine"] == "mock"
```

---

## 5. Phase 4 — Result Payload Tests

### `tests/test_compliance_result_payload.py`

```python
"""result_node 출력에 copyCompliance 필드가 올바르게 포함되는지 검증."""

from orchestrator.app.graph.builder import build_marketing_graph
from langgraph.types import Command


class TestResultPayloadCompliance:
    def _run_to_done(self, thread_id, headline, business_type="cafe"):
        graph = build_marketing_graph()
        config = {"configurable": {"thread_id": thread_id}}
        result = graph.invoke(
            {
                "user_input": "ready",
                "job_id": thread_id,
                "thread_id": thread_id,
                "copy_generation_mode": "custom",
                "marketing_copy": {"headline": headline},
                "context": {
                    "business_type": business_type,
                    "item_or_service": "딸기라떼",
                    "promotion_goal": "new_launch",
                    "extra": {"ad_format": "instagram_feed"},
                },
            },
            config=config,
        )
        if "__interrupt__" in result:
            result = graph.invoke(
                Command(resume={"action": "use_suggestion"}),
                config=config,
            )
        return result

    def test_result_payload_has_copy_compliance(self):
        result = self._run_to_done("payload-has-compliance", "기분 좋은 딸기라떼")
        payload = result.get("result_payload") or {}
        metadata = payload.get("metadata") or {}
        assert "copyCompliance" in metadata

    def test_pass_result_has_correct_payload(self):
        result = self._run_to_done("payload-pass", "기분 좋은 딸기라떼")
        compliance = result["result_payload"]["metadata"]["copyCompliance"]
        assert compliance["status"] == "pass"
        assert compliance["publicationReady"] is True
        assert compliance["findings"] == []

    def test_warn_result_has_findings_in_payload(self):
        result = self._run_to_done("payload-warn", "디톡스 딸기라떼")
        compliance = result["result_payload"]["metadata"]["copyCompliance"]
        assert compliance["status"] == "warn"
        assert len(compliance["findings"]) > 0

    def test_manual_review_result_not_publication_ready(self):
        graph = build_marketing_graph()
        config = {"configurable": {"thread_id": "payload-manual-review"}}
        result = graph.invoke(
            {
                "user_input": "ready",
                "job_id": "payload-manual-review",
                "thread_id": "payload-manual-review",
                "copy_generation_mode": "custom",
                "marketing_copy": {"headline": "독소 배출 딸기라떼"},
                "context": {
                    "business_type": "cafe",
                    "item_or_service": "딸기라떼",
                    "promotion_goal": "new_launch",
                    "extra": {"ad_format": "instagram_feed"},
                },
            },
            config=config,
        )
        result = graph.invoke(
            Command(resume={"action": "keep_original_draft"}),
            config=config,
        )
        compliance = result["result_payload"]["metadata"]["copyCompliance"]
        assert compliance["publicationReady"] is False
        assert compliance["userAcknowledgedRisk"] is True

    def test_finding_has_detection_method_and_legal_basis(self):
        """FE 계약 검증 — 필수 필드가 모두 포함되어야 함."""
        result = self._run_to_done("payload-finding-fields", "디톡스 딸기라떼")
        findings = result["result_payload"]["metadata"]["copyCompliance"]["findings"]
        if not findings:
            return  # warn이 findings 없으면 스킵
        finding = findings[0]
        assert "findingId" in finding
        assert "matchedText" in finding
        assert "severity" in finding
        assert "detectionMethod" in finding
        assert "confidence" in finding
        assert "legalBasis" in finding
        assert "ragContext" in finding  # v1: null이어야 함
        assert finding["ragContext"] is None
```

---

## 6. Phase 5 — Prompt Injection Tests

### `tests/test_compliance_prompt_injection.py`

```python
"""metadata_builders에 compliance hints가 올바르게 주입되는지 검증."""

from orchestrator.app.llm.metadata_builders import build_common_constraints_metadata


class TestCompliancePromptInjection:
    def _metadata(self, business_type: str) -> dict:
        return build_common_constraints_metadata({
            "context": {"business_type": business_type},
            "tone_binding_output": None,
        })

    def test_metadata_has_compliance_key(self):
        meta = self._metadata("cafe")
        assert "compliance" in meta

    def test_cafe_metadata_has_food_domain(self):
        compliance = self._metadata("cafe")["compliance"]
        assert "food" in compliance.get("domains", [])

    def test_cafe_metadata_has_blocked_terms(self):
        compliance = self._metadata("cafe")["compliance"]
        blocked = compliance.get("blocked_terms", [])
        assert len(blocked) > 0
        # 식품 의료 주장 표현이 차단 목록에 있어야 함
        assert any("독소" in t or "배출" in t or "면역" in t for t in blocked)

    def test_skincare_metadata_has_cosmetic_domain(self):
        compliance = self._metadata("beauty_skincare")["compliance"]
        assert "cosmetic" in compliance.get("domains", [])

    def test_hospital_metadata_has_medical_domain(self):
        compliance = self._metadata("hospital")["compliance"]
        assert "medical" in compliance.get("domains", [])

    def test_unknown_type_does_not_crash(self):
        meta = self._metadata("unknown_type_xyz")
        # 크래시 없이 빈 dict 또는 general_ad 반환
        compliance = meta.get("compliance", {})
        assert isinstance(compliance, dict)

    def test_compliance_constraints_do_not_bloat_metadata(self):
        """blocked_terms가 너무 많으면 프롬프트 낭비 — 최대 10개 제한 확인."""
        compliance = self._metadata("cafe")["compliance"]
        assert len(compliance.get("blocked_terms", [])) <= 10
```

---

## 7. 테스트 실행 순서

### Phase별 실행 명령

```bash
# Phase 1: 그래프 변경 없이 먼저 rule engine 검증
pytest orchestrator/tests/test_compliance_yaml_contracts.py -v
pytest orchestrator/tests/test_compliance_industry_classifier.py -v
pytest orchestrator/tests/test_compliance_rule_engine.py -v

# Phase 2: candidate 배지
pytest orchestrator/tests/test_compliance_candidate_badge.py -v

# Phase 3: gate 노드 (노드 직접 호출 먼저, e2e 나중에)
pytest orchestrator/tests/test_compliance_gate_node.py -v
pytest orchestrator/tests/test_compliance_gate_e2e.py -v

# Phase 3: 기존 테스트 회귀 확인 (엣지 변경 후 반드시 실행)
pytest orchestrator/tests/test_marketing_graph_e2e_mock.py -v
pytest orchestrator/tests/test_copy_candidates_branch.py -v

# Phase 4
pytest orchestrator/tests/test_compliance_result_payload.py -v

# Phase 5
pytest orchestrator/tests/test_compliance_prompt_injection.py -v

# 전체 실행
pytest orchestrator/tests/ -v --tb=short
```

---

## 8. 주의사항: 실수하기 쉬운 포인트

### A. Thread ID 충돌 — E2E 테스트 실패의 가장 흔한 원인

```python
# 잘못된 패턴: 여러 테스트가 같은 thread_id 사용
def test_a():
    graph.invoke({..., "thread_id": "test-1"}, config={"configurable": {"thread_id": "test-1"}})

def test_b():
    # "test-1" checkpointer에 이전 테스트 상태가 남아있음
    graph.invoke(Command(resume=...), config={"configurable": {"thread_id": "test-1"}})
```

```python
# 올바른 패턴: 테스트마다 고유한 thread_id
def test_a():
    thread = "compliance-use-suggestion-001"
    config = {"configurable": {"thread_id": thread}}
    graph.invoke({..., "job_id": thread, "thread_id": thread}, config=config)
    graph.invoke(Command(resume=...), config=config)
```

### B. `marketing_copy` 원문 수정 확인

```python
# gate 노드 실행 후 marketing_copy가 바뀌었다면 잘못된 구현
state = _state(headline="독소 배출 딸기라떼")
update = copy_compliance_gate_node(state)

# gate 노드는 marketing_copy를 반환하면 안 됨
assert "marketing_copy" not in update
# state 내 marketing_copy도 그대로
assert state["marketing_copy"]["headline"] == "독소 배출 딸기라떼"
```

### C. `warn` 이 interrupt를 발생시키면 안 됨

```python
# warn은 배지만 보이고 흐름은 계속돼야 함
# 이 테스트가 실패하면 router 로직 버그
result = graph.invoke({"marketing_copy": {"headline": "디톡스 딸기라떼"}, ...})
assert "__interrupt__" not in result  # warn은 통과
```

### D. `block` 이후 `use_suggestion` 선택 시 suggested_copy가 없는 경우

YAML rule에 `examples`가 없으면 `suggested_copy=None` → `use_suggestion` 선택해도 카피가 바뀌지 않음.
이런 경우 resolution_node가 `marketing_copy`를 반환하지 않아야 하고, 테스트도 그에 맞게 작성해야 함.

```python
# YAML에 examples가 없는 rule의 경우
def test_use_suggestion_without_example_is_handled_gracefully():
    ...
    update = copy_compliance_resolution_node(state)
    # suggested_copy가 None이면 marketing_copy 업데이트 없어도 크래시 없어야 함
    if "marketing_copy" not in update:
        assert update["copy_compliance"]["user_decision"] == "use_suggestion"
```

### E. `keep_original_draft` 후 `publication_ready=True`가 되면 안 됨

```python
# 이 조건이 실패하면 "user_override ≠ publication_ready" 불변 조건 위반
result = graph.invoke(Command(resume={"action": "keep_original_draft"}), config=config)
assert result["copy_compliance_publication_ready"] is False  # 절대로 True가 되면 안 됨
```
