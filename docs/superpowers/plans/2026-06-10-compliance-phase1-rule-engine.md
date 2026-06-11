# Compliance Phase 1 — Rule Engine 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 광고법 위반 표현을 탐지하는 독립 모듈 `orchestrator/app/compliance/`를 구현한다. 그래프, State, builder.py는 건드리지 않는다.

**Architecture:** YAML로 정의된 규칙(패턴 + severity + 법적 근거)을 `PatternMatcher`가 로드해 카피 텍스트에서 위반 표현을 탐지한다. `ComplianceService`가 단일 진입점이며 `check_copy(copy, business_type)` 한 번 호출로 결과를 반환한다. Protocol 기반 설계로 v2에서 RAG 확장 시 구현체만 교체하면 된다.

**Tech Stack:** Python 3.12, Pydantic v2, PyYAML 6.x (모두 `pyproject.toml`에 이미 포함)

---

## 파일 맵

```
data/compliance/
    legal_basis_kr_v1.yaml          새로 생성 — 법령 메타데이터 (rule이 참조)
    rules_kr_v1.yaml                새로 생성 — 도메인별 규칙 pack

orchestrator/app/compliance/
    __init__.py                     새로 생성 — 빈 파일
    schemas.py                      새로 생성 — Pydantic 모델 (ComplianceFinding, CopyComplianceState 등)
    rule_loader.py                  새로 생성 — YAML → ComplianceRule 객체 변환
    industry_classifier.py          새로 생성 — business_type → compliance domain 리스트
    rule_engine.py                  새로 생성 — ComplianceChecker Protocol + PatternMatcher
    rewrite_strategy.py             새로 생성 — RewriteStrategy Protocol + StaticHintRewriter
    service.py                      새로 생성 — ComplianceService + get_compliance_service()

orchestrator/tests/
    test_compliance_schemas.py      새로 생성 — import smoke test
    test_compliance_rule_loader.py  새로 생성 — YAML 로딩 + 계약 검증
    test_compliance_classifier.py   새로 생성 — 업종 도메인 매핑
    test_compliance_rule_engine.py  새로 생성 — PatternMatcher 핵심 케이스
    test_compliance_service.py      새로 생성 — ComplianceService end-to-end
```

---

## Task 1: 디렉토리 스캐폴드 + schemas.py

**Files:**
- Create: `orchestrator/app/compliance/__init__.py`
- Create: `orchestrator/app/compliance/schemas.py`
- Create: `orchestrator/tests/test_compliance_schemas.py`

- [ ] **Step 1: 디렉토리 생성 + `__init__.py`**

```bash
mkdir -p orchestrator/app/compliance
touch orchestrator/app/compliance/__init__.py
mkdir -p data/compliance
```

- [ ] **Step 2: `schemas.py` 작성**

`orchestrator/app/compliance/schemas.py`:

```python
"""Compliance 도메인 타입 정의."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class LegalBasisRef(BaseModel):
    key: str
    law_name: str = ""
    article: str = ""
    summary: str = ""
    source_url: str = ""
    effective_date: str | None = None
    last_verified_at: str | None = None
    chunk_id: str | None = None


class RuleExample(BaseModel):
    unsafe: str
    safe: str
    index_for_rag: bool = False


class ComplianceRule(BaseModel):
    rule_id: str
    domain: str
    severity: Literal["warn", "evidence_required", "block"]
    title: str
    patterns: list[str] = Field(default_factory=list)
    legal_basis_ref: LegalBasisRef | None = None
    evidence_requirements: list[str] = Field(default_factory=list)
    safe_rewrite_hints: list[str] = Field(default_factory=list)
    hitl_question: str | None = None
    context_upgrade: dict[str, str] = Field(default_factory=dict)
    embedding_text: str = ""
    examples: list[RuleExample] = Field(default_factory=list)


class ComplianceFinding(BaseModel):
    finding_id: str
    field: Literal["headline", "sub_copy", "cta"]
    rule_id: str | None = None
    severity: Literal["warn", "evidence_required", "block"]
    matched_text: str
    reason: str
    legal_basis: list[LegalBasisRef] = Field(default_factory=list)
    suggested_text: str | None = None
    hitl_question: str | None = None
    evidence_requirements: list[str] = Field(default_factory=list)
    detection_method: Literal["pattern", "semantic", "rag"] = "pattern"
    confidence: float = 1.0
    rag_chunk_id: str | None = None
    rag_retrieval_score: float | None = None
    rag_context: dict[str, Any] | None = None


class CopyComplianceState(BaseModel):
    status: Literal["pass", "warn", "evidence_required", "blocked", "manual_review_required"]
    findings: list[ComplianceFinding] = Field(default_factory=list)
    original_copy: dict[str, Any] | None = None
    suggested_copy: dict[str, Any] | None = None
    user_decision: str | None = None
    user_acknowledged_risk: bool = False
    publication_ready: bool = True
    interrupt_payload: dict[str, Any] | None = None
    evidence_submitted: list[dict[str, Any]] = Field(default_factory=list)
    revision_count: int = 0
```

- [ ] **Step 3: import smoke test 작성**

`orchestrator/tests/test_compliance_schemas.py`:

```python
"""schemas.py import + 기본 인스턴스 생성 테스트."""


def test_compliance_finding_instantiates():
    from orchestrator.app.compliance.schemas import ComplianceFinding

    f = ComplianceFinding(
        finding_id="test-001",
        field="headline",
        severity="block",
        matched_text="독소 배출",
        reason="식품 의료 효능 주장",
    )
    assert f.finding_id == "test-001"
    assert f.detection_method == "pattern"
    assert f.confidence == 1.0
    assert f.rag_context is None


def test_copy_compliance_state_defaults():
    from orchestrator.app.compliance.schemas import CopyComplianceState

    state = CopyComplianceState(status="pass")
    assert state.findings == []
    assert state.publication_ready is True
    assert state.user_acknowledged_risk is False
```

- [ ] **Step 4: 테스트 실행 — FAIL 확인**

```bash
uv run python -m pytest orchestrator/tests/test_compliance_schemas.py -v
```

Expected: `ModuleNotFoundError: No module named 'orchestrator.app.compliance'` 또는 import 오류

- [ ] **Step 5: 테스트 재실행 — PASS 확인**

`schemas.py`를 작성했으니 이제 통과해야 함.

```bash
uv run python -m pytest orchestrator/tests/test_compliance_schemas.py -v
```

Expected:
```
test_compliance_schemas.py::test_compliance_finding_instantiates PASSED
test_compliance_schemas.py::test_copy_compliance_state_defaults PASSED
2 passed
```

- [ ] **Step 6: 커밋**

```bash
git add orchestrator/app/compliance/__init__.py \
        orchestrator/app/compliance/schemas.py \
        orchestrator/tests/test_compliance_schemas.py \
        data/compliance/
git commit -m "feat(compliance): scaffold module + Pydantic schemas"
```

---

## Task 2: YAML 데이터 파일 (초기 food 도메인 규칙 3개)

**Files:**
- Create: `data/compliance/legal_basis_kr_v1.yaml`
- Create: `data/compliance/rules_kr_v1.yaml`

이 태스크에서는 rule_loader.py 테스트에 쓸 최소 규칙만 정의한다.
food 도메인 3개: `block` 1개, `warn` 1개, `evidence_required` 1개.
나머지 도메인(fitness, medical, cosmetic)은 Task 9에서 추가한다.

- [ ] **Step 1: `data/compliance/legal_basis_kr_v1.yaml` 작성**

```yaml
version: "kr_legal_basis_v1"
updated_at: "2026-06-10"

legal_basis:
  KR-FAIR-AD-3:
    law_name: "표시·광고의 공정화에 관한 법률"
    article: "제3조"
    summary: "소비자를 속이거나 소비자가 잘못 알 우려가 있는 부당한 표시·광고 행위 금지"
    source_url: "https://www.law.go.kr/"
    effective_date: "2023-09-14"
    last_verified_at: "2026-06-01"
    chunk_id: null

  KR-FOOD-AD-8:
    law_name: "식품 등의 표시ㆍ광고에 관한 법률"
    article: "제8조"
    summary: "식품 등에 대해 질병 예방·치료 효능 또는 의약품 오인 우려가 있는 표시·광고 금지"
    source_url: "https://www.law.go.kr/"
    effective_date: "2024-01-01"
    last_verified_at: "2026-06-01"
    chunk_id: null

  KR-MEDICAL-AD-56:
    law_name: "의료법"
    article: "제56조"
    summary: "의료광고에서 치료 효과 보장, 소비자 현혹 우려가 있는 내용 금지"
    source_url: "https://www.law.go.kr/"
    effective_date: "2023-06-13"
    last_verified_at: "2026-06-01"
    chunk_id: null

  KR-COSMETIC-AD-13:
    law_name: "화장품법"
    article: "제13조"
    summary: "의약품 오인, 기능성 오인, 사실과 다른 표시·광고 금지"
    source_url: "https://www.law.go.kr/"
    effective_date: "2024-02-20"
    last_verified_at: "2026-06-01"
    chunk_id: null
```

- [ ] **Step 2: `data/compliance/rules_kr_v1.yaml` 작성 (초기 3개 규칙)**

```yaml
version: "kr_ad_compliance_v1"
jurisdiction: "KR"
updated_at: "2026-06-10"

rules:
  - rule_id: KR-FOOD-MEDICAL-CLAIM-001
    domain: food
    severity: block
    title: "식품의 질병 예방·치료 또는 의학적 효능 암시"
    patterns:
      - "독소 배출"
      - "면역력 강화"
      - "체지방 감소"
      - "다이어트 효과"
      - "혈당 조절"
      - "피로 회복 보장"
    legal_basis_ref:
      key: KR-FOOD-AD-8
    evidence_requirements: []
    safe_rewrite_hints:
      - "맛, 향, 분위기, 재료, 계절감 중심으로"
      - "신체 변화나 의학적 효과 표현 제거"
    embedding_text: >
      식품·음료 광고에서 신체 질환 개선, 독소 제거, 체중 감소,
      면역 향상 같은 의학적 효능을 직접 또는 암시적으로 주장하는 표현.
    examples:
      - unsafe: "독소 배출에 도움을 주는 그린 스무디"
        safe: "신선한 채소와 과일이 어우러진 그린 스무디"
        index_for_rag: true

  - rule_id: KR-FOOD-AMBIGUOUS-001
    domain: food
    severity: warn
    title: "신체 효능 암시 가능성 표현 (문맥 의존)"
    patterns:
      - "디톡스"
      - "몸이 가벼워"
    legal_basis_ref:
      key: KR-FOOD-AD-8
    evidence_requirements: []
    safe_rewrite_hints:
      - "맛, 향, 분위기, 재료, 감성 중심으로"
    hitl_question: "이 표현이 제품명이나 프로그램 기간을 설명하는 건가요, 신체 효능을 주장하는 건가요?"
    context_upgrade:
      body_effect_claim: "evidence_required"
      medical_claim: "block"
    embedding_text: >
      식품·음료 광고에서 신체 정화, 다이어트, 피부 개선처럼
      의학적 효능을 암시할 수 있는 표현.
    examples:
      - unsafe: "디톡스 딸기라떼로 몸이 가벼워지는 경험"
        safe: "상큼한 딸기와 부드러운 라떼가 만난 기분 좋은 한 잔"
        index_for_rag: true

  - rule_id: KR-GENERAL-SUPERLATIVE-001
    domain: general_ad
    severity: evidence_required
    title: "실증 없는 최상급·절대 표현"
    patterns:
      - "1위"
      - "최고"
      - "최초"
      - "100% 보장"
      - "완벽 보장"
      - "무조건"
    legal_basis_ref:
      key: KR-FAIR-AD-3
    evidence_requirements:
      - "비교 기준"
      - "조사 기관"
      - "조사 기간"
    safe_rewrite_hints:
      - "보장·절대 표현 대신 경험·기대·제안 표현으로"
    embedding_text: >
      광고에서 객관적 근거 없이 최상급 또는 절대적 성과를 주장하는 표현.
    examples:
      - unsafe: "국내 1위 헬스장"
        safe: "고객 만족 코칭 프로그램"
        index_for_rag: true
```

- [ ] **Step 3: YAML 수동 검증**

```bash
uv run python -c "
import yaml
from pathlib import Path
legal = yaml.safe_load(Path('data/compliance/legal_basis_kr_v1.yaml').read_text())
rules = yaml.safe_load(Path('data/compliance/rules_kr_v1.yaml').read_text())
print('legal_basis keys:', list(legal['legal_basis'].keys()))
print('rule count:', len(rules['rules']))
print('rule_ids:', [r['rule_id'] for r in rules['rules']])
"
```

Expected:
```
legal_basis keys: ['KR-FAIR-AD-3', 'KR-FOOD-AD-8', 'KR-MEDICAL-AD-56', 'KR-COSMETIC-AD-13']
rule count: 3
rule_ids: ['KR-FOOD-MEDICAL-CLAIM-001', 'KR-FOOD-AMBIGUOUS-001', 'KR-GENERAL-SUPERLATIVE-001']
```

- [ ] **Step 4: 커밋**

```bash
git add data/compliance/
git commit -m "feat(compliance): add initial KR ad law YAML rule pack (food domain)"
```

---

## Task 3: rule_loader.py

**Files:**
- Create: `orchestrator/app/compliance/rule_loader.py`
- Create: `orchestrator/tests/test_compliance_rule_loader.py`

- [ ] **Step 1: 테스트 작성**

`orchestrator/tests/test_compliance_rule_loader.py`:

```python
"""rule_loader.py — YAML 로딩 및 계약 검증 테스트."""

import pytest


def test_load_legal_basis_returns_dict():
    from orchestrator.app.compliance.rule_loader import load_legal_basis

    basis = load_legal_basis()
    assert isinstance(basis, dict)
    assert len(basis) > 0


def test_legal_basis_has_expected_keys():
    from orchestrator.app.compliance.rule_loader import load_legal_basis

    basis = load_legal_basis()
    assert "KR-FOOD-AD-8" in basis
    assert "KR-FAIR-AD-3" in basis


def test_legal_basis_entry_has_law_name():
    from orchestrator.app.compliance.rule_loader import load_legal_basis

    basis = load_legal_basis()
    entry = basis["KR-FOOD-AD-8"]
    assert entry.law_name != ""
    assert entry.article != ""


def test_load_rules_returns_list():
    from orchestrator.app.compliance.rule_loader import load_rules

    rules = load_rules()
    assert isinstance(rules, list)
    assert len(rules) >= 3


def test_rules_have_required_fields():
    from orchestrator.app.compliance.rule_loader import load_rules
    from orchestrator.app.compliance.schemas import ComplianceRule

    for rule in load_rules():
        assert isinstance(rule, ComplianceRule)
        assert rule.rule_id != ""
        assert rule.severity in {"warn", "evidence_required", "block"}
        assert len(rule.patterns) > 0


def test_rules_legal_basis_ref_resolved():
    """legal_basis_ref의 key가 법령 메타데이터로 실제로 연결되는지 확인."""
    from orchestrator.app.compliance.rule_loader import load_rules

    for rule in load_rules():
        if rule.legal_basis_ref is not None:
            assert rule.legal_basis_ref.law_name != "", (
                f"{rule.rule_id}: legal_basis_ref.key가 legal_basis_kr_v1.yaml에 존재하지 않음"
            )


def test_no_duplicate_rule_ids():
    from orchestrator.app.compliance.rule_loader import load_rules

    ids = [r.rule_id for r in load_rules()]
    assert len(ids) == len(set(ids)), f"중복 rule_id 발견: {[x for x in ids if ids.count(x) > 1]}"


def test_yaml_contract_block_rules_have_examples():
    """block 규칙은 반드시 examples가 있어야 suggested_copy를 생성할 수 있다."""
    from orchestrator.app.compliance.rule_loader import load_rules

    for rule in load_rules():
        if rule.severity == "block":
            assert len(rule.examples) > 0, f"{rule.rule_id}: block 규칙에 examples 누락"


def test_yaml_contract_warn_rules_have_hitl_question():
    """warn 규칙은 사용자에게 맥락 확인 질문이 있어야 한다."""
    from orchestrator.app.compliance.rule_loader import load_rules

    for rule in load_rules():
        if rule.severity == "warn":
            assert rule.hitl_question, f"{rule.rule_id}: warn 규칙에 hitl_question 누락"


def test_yaml_contract_evidence_required_rules_have_requirements():
    """evidence_required 규칙은 어떤 근거를 제출해야 하는지 명시해야 한다."""
    from orchestrator.app.compliance.rule_loader import load_rules

    for rule in load_rules():
        if rule.severity == "evidence_required":
            assert len(rule.evidence_requirements) > 0, (
                f"{rule.rule_id}: evidence_required 규칙에 evidence_requirements 누락"
            )


def test_yaml_contract_all_rules_have_embedding_text():
    """RAG 확장 준비: embedding_text 없으면 벡터 인덱싱 불가."""
    from orchestrator.app.compliance.rule_loader import load_rules

    for rule in load_rules():
        assert rule.embedding_text.strip(), f"{rule.rule_id}: embedding_text 누락"
```

- [ ] **Step 2: 테스트 실행 — FAIL 확인**

```bash
uv run python -m pytest orchestrator/tests/test_compliance_rule_loader.py -v
```

Expected: `ModuleNotFoundError` 또는 `ImportError` (rule_loader.py 없음)

- [ ] **Step 3: `rule_loader.py` 작성**

`orchestrator/app/compliance/rule_loader.py`:

```python
"""YAML rule pack → ComplianceRule / LegalBasisRef 객체 변환."""

from __future__ import annotations

from pathlib import Path

import yaml

from orchestrator.app.compliance.schemas import ComplianceRule, LegalBasisRef

_RULES_PATH = Path(__file__).parents[3] / "data" / "compliance" / "rules_kr_v1.yaml"
_LEGAL_BASIS_PATH = Path(__file__).parents[3] / "data" / "compliance" / "legal_basis_kr_v1.yaml"


def load_legal_basis(path: Path = _LEGAL_BASIS_PATH) -> dict[str, LegalBasisRef]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {
        key: LegalBasisRef(key=key, **{k: v for k, v in entry.items() if v is not None})
        for key, entry in (raw.get("legal_basis") or {}).items()
    }


def load_rules(path: Path = _RULES_PATH) -> list[ComplianceRule]:
    legal_basis_map = load_legal_basis()
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    rules = []
    for entry in raw.get("rules") or []:
        entry = dict(entry)
        ref_raw = entry.pop("legal_basis_ref", None) or {}
        ref_key = ref_raw.get("key") if isinstance(ref_raw, dict) else None
        ref = legal_basis_map.get(ref_key) if ref_key else None
        rules.append(ComplianceRule(**entry, legal_basis_ref=ref))
    return rules
```

- [ ] **Step 4: 테스트 재실행 — PASS 확인**

```bash
uv run python -m pytest orchestrator/tests/test_compliance_rule_loader.py -v
```

Expected: 전부 PASSED

- [ ] **Step 5: 커밋**

```bash
git add orchestrator/app/compliance/rule_loader.py \
        orchestrator/tests/test_compliance_rule_loader.py
git commit -m "feat(compliance): rule_loader — YAML to ComplianceRule objects"
```

---

## Task 4: industry_classifier.py

**Files:**
- Create: `orchestrator/app/compliance/industry_classifier.py`
- Create: `orchestrator/tests/test_compliance_classifier.py`

- [ ] **Step 1: 테스트 작성**

`orchestrator/tests/test_compliance_classifier.py`:

```python
"""IndustryClassifier — business_type → compliance domain 매핑 테스트."""


def _cls():
    from orchestrator.app.compliance.industry_classifier import IndustryClassifier
    return IndustryClassifier()


def test_cafe_maps_to_food_and_general():
    domains = _cls().get_domains("cafe")
    assert "food" in domains
    assert "general_ad" in domains


def test_restaurant_maps_to_food():
    domains = _cls().get_domains("restaurant")
    assert "food" in domains


def test_beauty_skincare_maps_to_cosmetic():
    domains = _cls().get_domains("beauty_skincare")
    assert "cosmetic" in domains
    assert "general_ad" in domains


def test_hospital_maps_to_medical():
    domains = _cls().get_domains("hospital")
    assert "medical" in domains


def test_fitness_maps_to_general_ad():
    domains = _cls().get_domains("fitness")
    assert "general_ad" in domains


def test_unknown_type_falls_back_to_general_ad():
    domains = _cls().get_domains("unknown_xyz")
    assert domains == ["general_ad"]


def test_none_falls_back_to_general_ad():
    domains = _cls().get_domains(None)
    assert domains == ["general_ad"]


def test_all_food_business_types_include_food_domain():
    from orchestrator.app.compliance.industry_classifier import BUSINESS_TYPE_TO_DOMAIN

    food_types = [bt for bt, domains in BUSINESS_TYPE_TO_DOMAIN.items() if "food" in domains]
    assert len(food_types) >= 3, "카페, 식당 등 최소 3개 업종이 food 도메인 포함해야 함"


def test_get_domains_always_returns_list():
    cls = _cls()
    for biz_type in ["cafe", "hospital", "unknown", None]:
        result = cls.get_domains(biz_type)
        assert isinstance(result, list)
        assert len(result) > 0
```

- [ ] **Step 2: 테스트 실행 — FAIL 확인**

```bash
uv run python -m pytest orchestrator/tests/test_compliance_classifier.py -v
```

Expected: `ModuleNotFoundError` (industry_classifier.py 없음)

- [ ] **Step 3: `industry_classifier.py` 작성**

`orchestrator/app/compliance/industry_classifier.py`:

```python
"""business_type → compliance domain 매핑."""

from __future__ import annotations

BUSINESS_TYPE_TO_DOMAIN: dict[str, list[str]] = {
    "cafe":                 ["food", "general_ad"],
    "restaurant":           ["food", "general_ad"],
    "restaurant_bbq":       ["food", "general_ad"],
    "restaurant_japanese":  ["food", "general_ad"],
    "restaurant_korean":    ["food", "general_ad"],
    "fitness":              ["general_ad"],
    "pilates":              ["general_ad"],
    "yoga":                 ["general_ad"],
    "beauty_skincare":      ["cosmetic", "general_ad"],
    "beauty_hair":          ["cosmetic", "general_ad"],
    "beauty_nail":          ["cosmetic", "general_ad"],
    "beauty_spa":           ["cosmetic", "general_ad"],
    "hospital":             ["medical", "general_ad"],
    "dental":               ["medical", "general_ad"],
    "plastic_surgery":      ["medical", "general_ad"],
    "oriental_medicine":    ["medical", "general_ad"],
    "health_supplement":    ["health_functional_food", "food", "general_ad"],
}

_FALLBACK = ["general_ad"]


class IndustryClassifier:
    def get_domains(self, business_type: str | None) -> list[str]:
        if not business_type:
            return _FALLBACK
        return BUSINESS_TYPE_TO_DOMAIN.get(business_type, _FALLBACK)
```

- [ ] **Step 4: 테스트 재실행 — PASS 확인**

```bash
uv run python -m pytest orchestrator/tests/test_compliance_classifier.py -v
```

Expected: 전부 PASSED

- [ ] **Step 5: 커밋**

```bash
git add orchestrator/app/compliance/industry_classifier.py \
        orchestrator/tests/test_compliance_classifier.py
git commit -m "feat(compliance): IndustryClassifier — business_type to domain mapping"
```

---

## Task 5: rule_engine.py — PatternMatcher

**Files:**
- Create: `orchestrator/app/compliance/rule_engine.py`
- Create: `orchestrator/tests/test_compliance_rule_engine.py`

- [ ] **Step 1: 테스트 작성**

`orchestrator/tests/test_compliance_rule_engine.py`:

```python
"""PatternMatcher — scan() 및 aggregate_status() 테스트.

이 파일은 rule_loader + rule_engine만 테스트한다.
service.py는 test_compliance_service.py에서 따로 테스트한다.
"""

import pytest


def _matcher():
    from orchestrator.app.compliance.rule_loader import load_rules
    from orchestrator.app.compliance.rule_engine import PatternMatcher
    return PatternMatcher(load_rules())


# ── scan(): 매칭 기본 ─────────────────────────────────────────────────────────

def test_scan_returns_empty_for_safe_copy():
    findings = _matcher().scan(
        {"headline": "기분 좋은 딸기라떼 한 잔"},
        domains=["food", "general_ad"],
    )
    assert findings == []


def test_scan_detects_block_pattern_in_headline():
    findings = _matcher().scan(
        {"headline": "독소 배출에 도움을 주는 딸기라떼"},
        domains=["food"],
    )
    assert len(findings) == 1
    assert findings[0].severity == "block"
    assert findings[0].matched_text == "독소 배출"
    assert findings[0].field == "headline"


def test_scan_detects_warn_pattern():
    findings = _matcher().scan(
        {"headline": "디톡스 딸기라떼"},
        domains=["food"],
    )
    assert len(findings) >= 1
    assert any(f.severity == "warn" for f in findings)


def test_scan_detects_evidence_required_pattern():
    findings = _matcher().scan(
        {"headline": "국내 1위 카페"},
        domains=["general_ad"],
    )
    assert len(findings) >= 1
    assert any(f.severity == "evidence_required" for f in findings)


def test_scan_checks_subcopy_field():
    findings = _matcher().scan(
        {"headline": "안전한 헤드라인", "subcopy": "독소 배출 효과"},
        domains=["food"],
    )
    assert any(f.field == "sub_copy" for f in findings)


def test_scan_checks_cta_field():
    findings = _matcher().scan(
        {"headline": "안전한 문구", "cta": "독소 배출"},
        domains=["food"],
    )
    assert any(f.field == "cta" for f in findings)


def test_scan_only_applies_rules_matching_domain():
    """food 도메인 규칙은 general_ad만 요청하면 적용되지 않아야 한다."""
    findings = _matcher().scan(
        {"headline": "독소 배출 딸기라떼"},
        domains=["general_ad"],  # food 도메인 제외
    )
    # KR-FOOD-MEDICAL-CLAIM-001는 food 도메인 — 적용 안 됨
    food_block = [f for f in findings if f.rule_id == "KR-FOOD-MEDICAL-CLAIM-001"]
    assert food_block == []


def test_scan_finding_has_legal_basis_for_block_rule():
    findings = _matcher().scan(
        {"headline": "독소 배출 딸기라떼"},
        domains=["food"],
    )
    block_findings = [f for f in findings if f.severity == "block"]
    assert len(block_findings) > 0
    assert len(block_findings[0].legal_basis) > 0
    assert block_findings[0].legal_basis[0].law_name != ""


def test_scan_finding_has_rule_id():
    findings = _matcher().scan(
        {"headline": "독소 배출"},
        domains=["food"],
    )
    assert all(f.rule_id is not None for f in findings)


def test_scan_finding_has_unique_finding_id():
    findings = _matcher().scan(
        {"headline": "독소 배출", "subcopy": "면역력 강화"},
        domains=["food"],
    )
    ids = [f.finding_id for f in findings]
    assert len(ids) == len(set(ids)), "finding_id가 중복됨"


# ── aggregate_status() ────────────────────────────────────────────────────────

def test_aggregate_status_empty_findings_returns_pass():
    from orchestrator.app.compliance.rule_engine import aggregate_status
    assert aggregate_status([]) == "pass"


def test_aggregate_status_warn_only_returns_warn():
    from orchestrator.app.compliance.rule_engine import aggregate_status
    from orchestrator.app.compliance.schemas import ComplianceFinding

    findings = [ComplianceFinding(finding_id="x", field="headline", severity="warn", matched_text="디톡스", reason="warn test")]
    assert aggregate_status(findings) == "warn"


def test_aggregate_status_block_wins_over_warn():
    from orchestrator.app.compliance.rule_engine import aggregate_status
    from orchestrator.app.compliance.schemas import ComplianceFinding

    findings = [
        ComplianceFinding(finding_id="a", field="headline", severity="warn", matched_text="디톡스", reason="warn"),
        ComplianceFinding(finding_id="b", field="sub_copy", severity="block", matched_text="독소 배출", reason="block"),
    ]
    assert aggregate_status(findings) == "blocked"


def test_aggregate_status_evidence_required_wins_over_warn():
    from orchestrator.app.compliance.rule_engine import aggregate_status
    from orchestrator.app.compliance.schemas import ComplianceFinding

    findings = [
        ComplianceFinding(finding_id="a", field="headline", severity="warn", matched_text="디톡스", reason="warn"),
        ComplianceFinding(finding_id="b", field="sub_copy", severity="evidence_required", matched_text="1위", reason="ev"),
    ]
    assert aggregate_status(findings) == "evidence_required"


def test_aggregate_status_block_wins_over_evidence_required():
    from orchestrator.app.compliance.rule_engine import aggregate_status
    from orchestrator.app.compliance.schemas import ComplianceFinding

    findings = [
        ComplianceFinding(finding_id="a", field="headline", severity="evidence_required", matched_text="1위", reason="ev"),
        ComplianceFinding(finding_id="b", field="sub_copy", severity="block", matched_text="독소 배출", reason="block"),
    ]
    assert aggregate_status(findings) == "blocked"
```

- [ ] **Step 2: 테스트 실행 — FAIL 확인**

```bash
uv run python -m pytest orchestrator/tests/test_compliance_rule_engine.py -v
```

Expected: `ModuleNotFoundError` (rule_engine.py 없음)

- [ ] **Step 3: `rule_engine.py` 작성**

`orchestrator/app/compliance/rule_engine.py`:

```python
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

_TEXT_FIELDS: dict[str, str] = {
    "headline": "headline",
    "sub_copy": "subcopy",
    "cta": "cta",
}


class ComplianceChecker(Protocol):
    """v2 RAG 확장 시 HybridMatcher로 교체한다."""

    def scan(self, copy: dict[str, Any], domains: list[str]) -> list[ComplianceFinding]: ...


def aggregate_status(findings: list[ComplianceFinding]) -> str:
    """findings 중 가장 높은 severity에 해당하는 상태 문자열을 반환한다.
    findings가 비어있으면 'pass'를 반환한다."""
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

    def _make_finding(
        self,
        rule: ComplianceRule,
        field: str,
        matched_text: str,
    ) -> ComplianceFinding:
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
```

- [ ] **Step 4: 테스트 재실행 — PASS 확인**

```bash
uv run python -m pytest orchestrator/tests/test_compliance_rule_engine.py -v
```

Expected: 전부 PASSED

- [ ] **Step 5: 커밋**

```bash
git add orchestrator/app/compliance/rule_engine.py \
        orchestrator/tests/test_compliance_rule_engine.py
git commit -m "feat(compliance): PatternMatcher + aggregate_status"
```

---

## Task 6: rewrite_strategy.py — StaticHintRewriter

**Files:**
- Create: `orchestrator/app/compliance/rewrite_strategy.py`

rewrite_strategy는 service 테스트에서 간접 검증되므로 별도 테스트 파일 없이 task 7 service 테스트에서 함께 검증한다.

- [ ] **Step 1: `rewrite_strategy.py` 작성**

`orchestrator/app/compliance/rewrite_strategy.py`:

```python
"""RewriteStrategy Protocol + StaticHintRewriter.

v2 RAG 확장 시 RAGExampleRewriter로 교체한다.
"""

from __future__ import annotations

from typing import Any, Protocol

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
```

- [ ] **Step 2: import 확인**

```bash
uv run python -c "from orchestrator.app.compliance.rewrite_strategy import StaticHintRewriter; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: 커밋**

```bash
git add orchestrator/app/compliance/rewrite_strategy.py
git commit -m "feat(compliance): StaticHintRewriter — static safe text suggestion"
```

---

## Task 7: service.py — ComplianceService

**Files:**
- Create: `orchestrator/app/compliance/service.py`
- Create: `orchestrator/tests/test_compliance_service.py`

- [ ] **Step 1: 테스트 작성**

`orchestrator/tests/test_compliance_service.py`:

```python
"""ComplianceService end-to-end 테스트.

get_compliance_service()의 lru_cache 오염을 막기 위해
모든 테스트에서 _svc()로 직접 인스턴스를 생성한다.
"""


def _svc():
    from orchestrator.app.compliance.rule_loader import load_rules
    from orchestrator.app.compliance.rule_engine import PatternMatcher
    from orchestrator.app.compliance.rewrite_strategy import StaticHintRewriter
    from orchestrator.app.compliance.industry_classifier import IndustryClassifier
    from orchestrator.app.compliance.service import ComplianceService

    rules = load_rules()
    return ComplianceService(
        checker=PatternMatcher(rules),
        rewriter=StaticHintRewriter({r.rule_id: r for r in rules}),
        classifier=IndustryClassifier(),
    )


# ── status 반환값 ──────────────────────────────────────────────────────────────

def test_safe_copy_returns_pass():
    result = _svc().check_copy(
        {"headline": "기분 좋은 딸기라떼 한 잔", "subcopy": "오늘의 카페 타임"},
        business_type="cafe",
    )
    assert result.status == "pass"


def test_food_ambiguous_returns_warn():
    result = _svc().check_copy(
        {"headline": "디톡스 딸기라떼"},
        business_type="cafe",
    )
    assert result.status == "warn"


def test_food_medical_claim_returns_blocked():
    result = _svc().check_copy(
        {"headline": "독소 배출에 도움을 주는 딸기라떼"},
        business_type="cafe",
    )
    assert result.status == "blocked"


def test_superlative_returns_evidence_required():
    result = _svc().check_copy(
        {"headline": "국내 1위 카페"},
        business_type="cafe",
    )
    assert result.status == "evidence_required"


# ── publication_ready 불변 조건 ────────────────────────────────────────────────

def test_pass_is_publication_ready():
    result = _svc().check_copy({"headline": "기분 좋은 딸기라떼"}, business_type="cafe")
    assert result.publication_ready is True


def test_warn_is_publication_ready():
    """warn은 논블로킹이므로 게시 가능해야 한다."""
    result = _svc().check_copy({"headline": "디톡스 딸기라떼"}, business_type="cafe")
    assert result.status == "warn"
    assert result.publication_ready is True


def test_evidence_required_is_not_publication_ready():
    result = _svc().check_copy({"headline": "국내 1위 카페"}, business_type="cafe")
    assert result.publication_ready is False


def test_blocked_is_not_publication_ready():
    result = _svc().check_copy({"headline": "독소 배출 딸기라떼"}, business_type="cafe")
    assert result.publication_ready is False


# ── original_copy 보존 ─────────────────────────────────────────────────────────

def test_original_copy_is_stored_and_unchanged():
    """check_copy는 입력 카피를 절대 수정하지 않는다."""
    original = {"headline": "독소 배출 딸기라떼", "subcopy": "좋은 한 잔"}
    result = _svc().check_copy(original, business_type="cafe")
    assert result.original_copy == {"headline": "독소 배출 딸기라떼", "subcopy": "좋은 한 잔"}


def test_original_copy_is_not_the_same_object_as_input():
    """원본 dict가 service 내부에서 변형되지 않도록 복사본이어야 한다."""
    original = {"headline": "독소 배출 딸기라떼"}
    result = _svc().check_copy(original, business_type="cafe")
    # result.original_copy를 수정해도 original에 영향 없어야 함
    result.original_copy["headline"] = "변경됨"
    assert original["headline"] == "독소 배출 딸기라떼"


# ── suggested_copy ─────────────────────────────────────────────────────────────

def test_blocked_copy_has_suggested_copy():
    result = _svc().check_copy({"headline": "독소 배출 딸기라떼"}, business_type="cafe")
    assert result.suggested_copy is not None
    assert result.suggested_copy.get("headline") != "독소 배출 딸기라떼"


def test_pass_copy_has_no_suggested_copy():
    result = _svc().check_copy({"headline": "기분 좋은 딸기라떼"}, business_type="cafe")
    assert result.suggested_copy is None


# ── findings 내용 ──────────────────────────────────────────────────────────────

def test_findings_contain_detection_method_pattern():
    result = _svc().check_copy({"headline": "독소 배출 딸기라떼"}, business_type="cafe")
    assert all(f.detection_method == "pattern" for f in result.findings)


def test_findings_contain_confidence_1_for_pattern():
    result = _svc().check_copy({"headline": "독소 배출 딸기라떼"}, business_type="cafe")
    assert all(f.confidence == 1.0 for f in result.findings)


def test_findings_rag_context_is_none_in_v1():
    """v1에서는 RAG context가 없어야 한다."""
    result = _svc().check_copy({"headline": "독소 배출 딸기라떼"}, business_type="cafe")
    assert all(f.rag_context is None for f in result.findings)


# ── 업종 fallback ─────────────────────────────────────────────────────────────

def test_unknown_business_type_uses_general_ad_rules():
    """알 수 없는 업종은 general_ad 규칙을 적용한다."""
    result = _svc().check_copy({"headline": "국내 1위 서비스"}, business_type="unknown_type_xyz")
    assert result.status == "evidence_required"


def test_none_business_type_uses_general_ad_rules():
    result = _svc().check_copy({"headline": "국내 1위 서비스"}, business_type=None)
    assert result.status == "evidence_required"


# ── get_compliance_service() singleton ────────────────────────────────────────

def test_get_compliance_service_returns_instance():
    from orchestrator.app.compliance.service import get_compliance_service

    svc = get_compliance_service()
    result = svc.check_copy({"headline": "기분 좋은 딸기라떼"}, business_type="cafe")
    assert result.status == "pass"
```

- [ ] **Step 2: 테스트 실행 — FAIL 확인**

```bash
uv run python -m pytest orchestrator/tests/test_compliance_service.py -v
```

Expected: `ModuleNotFoundError` (service.py 없음)

- [ ] **Step 3: `service.py` 작성**

`orchestrator/app/compliance/service.py`:

```python
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
```

- [ ] **Step 4: 테스트 재실행 — PASS 확인**

```bash
uv run python -m pytest orchestrator/tests/test_compliance_service.py -v
```

Expected: 전부 PASSED

- [ ] **Step 5: 커밋**

```bash
git add orchestrator/app/compliance/service.py \
        orchestrator/tests/test_compliance_service.py
git commit -m "feat(compliance): ComplianceService — check_copy entry point"
```

---

## Task 8: YAML 규칙 확장 (fitness / medical / cosmetic 도메인)

**Files:**
- Modify: `data/compliance/rules_kr_v1.yaml` — 규칙 5개 추가

현재 YAML에는 food/general_ad 도메인만 있다.
fitness, medical, cosmetic 도메인 규칙을 추가해 IndustryClassifier의 매핑이 실제로 작동하는지 검증한다.

- [ ] **Step 1: 테스트 먼저 작성 (새 도메인 규칙 검증)**

`orchestrator/tests/test_compliance_service.py` 파일 하단에 다음 테스트를 **추가**한다.

```python
# ── fitness 도메인 ─────────────────────────────────────────────────────────────

def test_fitness_guarantee_is_evidence_required():
    result = _svc().check_copy(
        {"headline": "4주 만에 10kg 감량 보장"},
        business_type="fitness",
    )
    assert result.status == "evidence_required"


# ── medical 도메인 ─────────────────────────────────────────────────────────────

def test_medical_treatment_guarantee_is_blocked():
    result = _svc().check_copy(
        {"headline": "여드름 완치 보장"},
        business_type="hospital",
    )
    assert result.status == "blocked"


def test_medical_before_after_is_blocked():
    result = _svc().check_copy(
        {"headline": "Before & After로 확인하는 시술 효과"},
        business_type="hospital",
    )
    assert result.status == "blocked"


# ── cosmetic 도메인 ────────────────────────────────────────────────────────────

def test_cosmetic_medical_claim_is_blocked():
    result = _svc().check_copy(
        {"headline": "여드름 치료 100% 보장"},
        business_type="beauty_skincare",
    )
    assert result.status == "blocked"


# ── 도메인 격리: 다른 업종엔 적용 안 됨 ─────────────────────────────────────────

def test_medical_rule_does_not_apply_to_cafe():
    """병원 전용 규칙은 카페 업종에 적용되지 않아야 한다."""
    result = _svc().check_copy(
        {"headline": "여드름 완치 보장"},
        business_type="cafe",
    )
    # cafe는 medical 도메인 규칙 없음
    # KR-MEDICAL-BLOCK-001가 없으면 pass 또는 다른 이유로 blocked일 수 있음
    # general_ad 규칙(보장)은 걸릴 수 있으므로 medical 특정 rule_id로 확인
    medical_findings = [f for f in result.findings if f.rule_id and "MEDICAL" in f.rule_id]
    assert medical_findings == []
```

- [ ] **Step 2: 테스트 실행 — FAIL 확인**

```bash
uv run python -m pytest orchestrator/tests/test_compliance_service.py::test_fitness_guarantee_is_evidence_required \
    orchestrator/tests/test_compliance_service.py::test_medical_treatment_guarantee_is_blocked \
    orchestrator/tests/test_compliance_service.py::test_cosmetic_medical_claim_is_blocked -v
```

Expected: FAIL (규칙이 YAML에 없으므로 pass 반환)

- [ ] **Step 3: `rules_kr_v1.yaml`에 규칙 5개 추가**

기존 `data/compliance/rules_kr_v1.yaml`의 `rules:` 리스트 끝에 추가한다.

```yaml
  - rule_id: KR-FITNESS-GUARANTEE-001
    domain: general_ad
    severity: evidence_required
    title: "특정 수치·기간 결과 보장 표현"
    patterns:
      - "10kg 감량 보장"
      - "감량 보장"
      - "복근 완성"
      - "100% 성공"
      - "확실한 변화"
      - "몸이 바뀌는 기적"
    legal_basis_ref:
      key: KR-FAIR-AD-3
    evidence_requirements:
      - "측정 방법"
      - "대상자 조건"
      - "성과 산정 기준"
    safe_rewrite_hints:
      - "체계적인 준비, 운동 루틴, 맞춤 코칭 중심으로"
    embedding_text: >
      헬스·다이어트 광고에서 특정 기간 내 체중 감량, 복근 완성,
      체형 변화를 보장하는 표현. 실증 자료 없이 확실한 결과를 단정하는 과장 광고.
    examples:
      - unsafe: "4주 만에 10kg 감량 보장"
        safe: "4주 동안 체계적으로 준비하는 바디프로필 맞춤 코칭"
        index_for_rag: true

  - rule_id: KR-MEDICAL-BLOCK-001
    domain: medical
    severity: block
    title: "치료 효과 보장·완치·Before&After 표현"
    patterns:
      - "완치"
      - "여드름 완치"
      - "Before & After"
      - "비포 애프터"
      - "치료 효과 100%"
      - "확실히 사라지는"
    legal_basis_ref:
      key: KR-MEDICAL-AD-56
    evidence_requirements: []
    safe_rewrite_hints:
      - "치료 효과 대신 상담, 관리 과정, 편안한 경험 중심으로"
    embedding_text: >
      의료 광고에서 치료 결과를 보장하거나 완치를 약속하는 표현.
      의료법상 소비자 현혹 우려가 있는 의료광고 유형.
    examples:
      - unsafe: "여드름이 확실히 사라집니다"
        safe: "피부 고민을 차분히 상담하고 맞춤 관리를 제안합니다"
        index_for_rag: true

  - rule_id: KR-COSMETIC-BLOCK-001
    domain: cosmetic
    severity: block
    title: "화장품의 의약품·의료행위 오인 표현"
    patterns:
      - "여드름 치료"
      - "100% 개선"
      - "피부 재생"
      - "흉터 치료"
      - "탈모 방지"
    legal_basis_ref:
      key: KR-COSMETIC-AD-13
    evidence_requirements: []
    safe_rewrite_hints:
      - "피부 고민 상담, 편안한 관리, 피부결 케어 중심으로"
    embedding_text: >
      화장품·뷰티샵 광고에서 피부 질환 치료, 의학적 개선,
      의약품이나 의료행위로 오인될 수 있는 표현.
    examples:
      - unsafe: "여드름 치료 100% 보장"
        safe: "피부결을 가꾸는 맞춤 관리"
        index_for_rag: true
```

- [ ] **Step 4: 테스트 재실행 — PASS 확인**

```bash
uv run python -m pytest orchestrator/tests/test_compliance_service.py -v
```

Expected: 전부 PASSED (새로 추가한 5개 테스트 포함)

- [ ] **Step 5: 커밋**

```bash
git add data/compliance/rules_kr_v1.yaml \
        orchestrator/tests/test_compliance_service.py
git commit -m "feat(compliance): extend YAML rule pack with medical/cosmetic/fitness domains"
```

---

## Task 9: 전체 테스트 스위트 실행 + 기존 테스트 회귀 확인

Phase 1은 그래프를 건드리지 않으므로 기존 테스트가 모두 통과해야 한다.

- [ ] **Step 1: compliance 테스트 전체 실행**

```bash
uv run python -m pytest orchestrator/tests/test_compliance_schemas.py \
    orchestrator/tests/test_compliance_rule_loader.py \
    orchestrator/tests/test_compliance_classifier.py \
    orchestrator/tests/test_compliance_rule_engine.py \
    orchestrator/tests/test_compliance_service.py \
    -v --tb=short
```

Expected: 전부 PASSED, 0 errors

- [ ] **Step 2: 기존 핵심 테스트 회귀 확인**

```bash
uv run python -m pytest \
    orchestrator/tests/test_marketing_graph_e2e_mock.py \
    orchestrator/tests/test_copy_candidates_branch.py \
    orchestrator/tests/test_langgraph_state.py \
    -v --tb=short
```

Expected: 전부 PASSED (compliance 모듈은 아직 graph에 연결되지 않았으므로 영향 없음)

- [ ] **Step 3: 실패하는 테스트가 있다면**

실패 내용을 확인하고 수정한다. 가능한 원인:
- `test_marketing_graph_node_utilization.py` — develop 브랜치에서 노드 목록이 변경됐을 수 있음 (image_layout_analyzer, post_t2i_layout_refiner 등). 이 테스트는 compliance와 무관하므로 실패 시 원인을 확인만 한다.
- `rule_loader.py`의 `Path(__file__).parents[3]` 경로 — 실행 위치에 따라 달라질 수 있으므로 절대 경로로 테스트 확인

- [ ] **Step 4: 최종 커밋**

```bash
git add .
git commit -m "test(compliance): full Phase 1 test suite passes, no regressions"
```

---

## 완료 기준 체크리스트

- [ ] `uv run python -m pytest orchestrator/tests/test_compliance_*.py -v` 전부 PASSED
- [ ] `from orchestrator.app.compliance.service import get_compliance_service` 오류 없음
- [ ] `get_compliance_service().check_copy({"headline": "독소 배출 딸기라떼"}, "cafe").status == "blocked"`
- [ ] `get_compliance_service().check_copy({"headline": "기분 좋은 딸기라떼"}, "cafe").status == "pass"`
- [ ] `get_compliance_service().check_copy({"headline": "디톡스 딸기라떼"}, "cafe").publication_ready is True` (warn은 논블로킹)
- [ ] 기존 `test_marketing_graph_e2e_mock.py`, `test_copy_candidates_branch.py` 전부 PASSED
- [ ] `orchestrator/app/graph/`, `orchestrator/app/graph/builder.py`, `orchestrator/app/graph/state.py` 변경 없음

---

## 브랜치 정보

- 작업 브랜치: `feat/compliance/phase1-rule-engine`
- 베이스: `origin/develop`
- PR 대상: `develop`
