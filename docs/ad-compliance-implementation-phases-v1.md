# EasyAds 광고법 규제 게이트 — 구현 Phase 계획 v1

> 목적: `copy_compliance_gate` 구현을 단계별로 정의한다.  
> 기준: 2026-06-10 기준 `orchestrator/` 코드 구조 분석 결과를 반영한다.  
> 설계 기준 문서: [ad-compliance-gate-design-v1.md](./ad-compliance-gate-design-v1.md)

---

## 사전 파악: 기존 코드 패턴 요약

구현 전 확인한 기존 패턴이다. 각 Phase는 이 패턴을 그대로 따른다.

### HITL interrupt 패턴
`custom_copy_input_interrupt_node`와 `copy_candidate_selection_interrupt_node`가 구현 기준이다.
```python
# 기존 패턴 (custom_copy.py)
resume_payload = interrupt(payload)
return {"custom_copy_input": resume_payload, "status": "waiting_custom_copy_input"}
```
compliance interrupt도 동일하게 `interrupt(payload)`를 호출하고 resume 값을 state에 저장한다.

### router 패턴
`routers.py`의 `route_after_tone_binding`이 기준이다.
```python
def route_after_tone_binding(state: MarketingState) -> str:
    mode = state.get("copy_generation_mode")
    if mode == "suggest_candidates":
        return "copy_candidate_generation"
    ...
```
compliance router도 `state.get("copy_compliance_status")`로 분기한다.

### 노드 후처리 훅 패턴
`copy_candidate_generation_node`의 `validate_or_fallback_candidate_output`이 기준이다.
생성 결과에 post-processing을 추가할 때 기존 노드 내부에 함수 호출을 추가한다.

### State 업데이트 패턴
노드 함수는 `dict[str, Any]`를 반환하고, 반환 키가 state 필드에 머지된다.
`MarketingState`는 `total=False`라 새 필드 추가가 backward compatible하다.

### 테스트 패턴
```python
# test_copy_candidates_branch.py 패턴
def _state():
    return create_initial_marketing_state(InitialMarketingRequest(...))

def test_xxx():
    state = _state()
    update = some_node(state)
    state.update(update)
    assert state["some_field"] == expected
```
노드 함수를 직접 호출해 unit test하고, graph 전체는 `build_marketing_graph()`로 e2e test한다.

---

## Phase 1: Schema + Rule Pack (그래프 무관)

### 목표
Rule engine을 그래프와 완전히 분리된 독립 모듈로 구축한다.
이 Phase가 끝나면 다른 Phase의 기반이 완성된다.
그래프, State, builder.py는 **일절 건드리지 않는다.**

### 만들 파일

```
orchestrator/app/compliance/
    __init__.py
    schemas.py
    rule_loader.py
    rule_engine.py
    rewrite_strategy.py
    industry_classifier.py
    service.py

data/compliance/
    rules_kr_v1.yaml
    legal_basis_kr_v1.yaml

orchestrator/tests/
    test_compliance_rule_engine.py
    test_compliance_service.py
```

---

### 1-1. `data/compliance/legal_basis_kr_v1.yaml`

가장 먼저 만든다. Rule YAML이 이 파일을 참조한다.

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

---

### 1-2. `data/compliance/rules_kr_v1.yaml`

업종별로 핵심 표현만 담는다. v1은 coverage보다 정확도가 중요하다.
`embedding_text`와 `index_for_rag`는 값을 비워두지 말고 반드시 작성한다.

```yaml
version: "kr_ad_compliance_v1"
jurisdiction: "KR"
updated_at: "2026-06-10"

rules:
  # ── 전 업종 공통 ─────────────────────────────────────

  - rule_id: KR-GENERAL-SUPERLATIVE-001
    domain: general_ad
    severity: evidence_required
    title: "실증 없는 최상급·절대 표현"
    patterns:
      - "1위"
      - "최고"
      - "최초"
      - "국내 유일"
      - "100% 보장"
      - "완벽 보장"
      - "무조건"
      - "반드시"
    legal_basis_ref:
      key: KR-FAIR-AD-3
      chunk_id: null
    evidence_requirements:
      - "비교 기준"
      - "조사 기관"
      - "조사 기간"
    safe_rewrite_hints:
      - "보장·절대 표현 대신 경험·기대·제안 표현으로"
    embedding_text: >
      광고에서 객관적 근거 없이 최상급 또는 절대적 성과를 주장하는 표현.
      1위, 최고, 최초, 유일, 보장처럼 비교 기준이나 실증 자료 없이
      소비자가 사실로 믿게 만드는 문구.
    examples:
      - unsafe: "국내 1위 헬스장"
        safe: "고객 만족 코칭 프로그램"
        index_for_rag: true

  # ── 식품/카페/음료 ───────────────────────────────────

  - rule_id: KR-FOOD-MEDICAL-CLAIM-001
    domain: food
    severity: block
    title: "식품의 질병 예방·치료 또는 의학적 효능 암시"
    patterns:
      - "독소 배출"
      - "붓기 제거"
      - "체지방 감소"
      - "다이어트 효과"
      - "면역력 강화"
      - "통증 개선"
      - "피로 회복 보장"
      - "혈당 조절"
    legal_basis_ref:
      key: KR-FOOD-AD-8
      chunk_id: null
    safe_rewrite_hints:
      - "맛, 향, 분위기, 재료, 계절감 중심으로"
      - "신체 변화나 의학적 효과 표현 제거"
    embedding_text: >
      식품·음료 광고에서 신체 질환 개선, 독소 제거, 체중 감소,
      면역 향상 같은 의학적 효능을 직접 또는 암시적으로 주장하는 표현.
      일반 식품이 의약품이나 건강기능식품처럼 보이게 만드는 문구.
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
      - "다이어트"
      - "몸이 가벼워"
      - "피부 개선"
    legal_basis_ref:
      key: KR-FOOD-AD-8
      chunk_id: null
    hitl_question: "이 표현이 제품명이나 프로그램 기간을 설명하는 건가요, 신체 효능을 주장하는 건가요?"
    context_upgrade:
      body_effect_claim: evidence_required
      medical_claim: block
    safe_rewrite_hints:
      - "맛, 향, 분위기, 재료, 감성, 계절감 중심으로"
    embedding_text: >
      식품·음료 광고에서 신체 정화, 다이어트, 피부 개선처럼
      의학적 효능을 암시할 수 있는 표현. 제품명이나 단순 기간 설명인 경우
      문맥에 따라 허용될 수 있어 사용자 확인이 필요한 표현.
    examples:
      - unsafe: "디톡스 딸기라떼로 몸이 가벼워지는 경험"
        safe: "상큼한 딸기와 부드러운 라떼가 만난 기분 좋은 한 잔"
        index_for_rag: true

  # ── 의료/병원/시술 ────────────────────────────────────

  - rule_id: KR-MEDICAL-BLOCK-001
    domain: medical
    severity: block
    title: "치료 효과 보장·완치·Before&After 표현"
    patterns:
      - "완치"
      - "치료 효과 100%"
      - "확실히 사라지는"
      - "여드름 치료 보장"
      - "Before & After"
      - "비포 애프터"
      - "치료 경험담"
      - "전후사진"
    legal_basis_ref:
      key: KR-MEDICAL-AD-56
      chunk_id: null
    safe_rewrite_hints:
      - "치료 효과 대신 상담, 관리 과정, 편안한 경험 중심으로"
    embedding_text: >
      의료 광고에서 치료 결과를 보장하거나 완치를 약속하는 표현.
      환자가 치료 효과를 단정하거나 시술 결과를 확신하게 만드는 문구.
      의료법상 소비자 현혹 우려가 있는 의료광고 유형.
    examples:
      - unsafe: "여드름이 확실히 사라집니다"
        safe: "피부 고민을 차분히 상담하고 맞춤 관리를 제안합니다"
        index_for_rag: true

  # ── 화장품/뷰티/피부관리샵 ──────────────────────────

  - rule_id: KR-COSMETIC-BLOCK-001
    domain: cosmetic
    severity: block
    title: "화장품의 의약품·의료행위 오인 표현"
    patterns:
      - "여드름 치료"
      - "여드름 완치"
      - "100% 개선"
      - "피부질환 개선"
      - "염증 완화"
      - "흉터 치료"
      - "피부 재생"
      - "탈모 방지"
    legal_basis_ref:
      key: KR-COSMETIC-AD-13
      chunk_id: null
    safe_rewrite_hints:
      - "피부 고민 상담, 편안한 관리, 피부결 케어 중심으로"
    embedding_text: >
      화장품·뷰티샵 광고에서 피부 질환 치료, 의학적 개선,
      염증·흉터 치료처럼 의약품이나 의료행위로 오인될 수 있는 표현.
      화장품법상 의약품 오인 광고로 제한되는 문구.
    examples:
      - unsafe: "여드름 100% 개선"
        safe: "피부결을 가꾸는 맞춤 관리"
        index_for_rag: true

  # ── 헬스/다이어트/바디프로필 ────────────────────────

  - rule_id: KR-FITNESS-GUARANTEE-001
    domain: general_ad
    severity: evidence_required
    title: "특정 수치·기간 결과 보장 표현"
    patterns:
      - "4주 만에 10kg"
      - "무조건 감량"
      - "감량 보장"
      - "복근 완성"
      - "100% 성공"
      - "단기간 보장"
      - "확실한 변화"
      - "몸이 바뀌는 기적"
    legal_basis_ref:
      key: KR-FAIR-AD-3
      chunk_id: null
    evidence_requirements:
      - "측정 방법"
      - "대상자 조건"
      - "성과 산정 기준"
    safe_rewrite_hints:
      - "체계적인 준비, 운동 루틴, 맞춤 코칭 중심으로"
    embedding_text: >
      헬스·다이어트 광고에서 특정 기간 내 체중 감량, 복근 완성,
      체형 변화를 보장하는 표현. 실증 자료 없이 소비자에게
      확실한 결과를 단정하는 과장 광고 문구.
    examples:
      - unsafe: "4주 만에 10kg 감량 보장"
        safe: "4주 동안 체계적으로 준비하는 바디프로필 맞춤 코칭"
        index_for_rag: true

  - rule_id: KR-FITNESS-AMBIGUOUS-001
    domain: general_ad
    severity: warn
    title: "기간·변화 표현 (문맥 의존)"
    patterns:
      - "4주 만에"
      - "4주 안에"
    legal_basis_ref:
      key: KR-FAIR-AD-3
      chunk_id: null
    hitl_question: "이 표현이 프로그램 기간을 설명하는 건가요, 특정 결과를 보장하는 건가요?"
    context_upgrade:
      guaranteed_result: evidence_required
    safe_rewrite_hints:
      - "4주 동안 준비하는, 4주 과정의 처럼 기간 설명으로"
    embedding_text: >
      헬스·다이어트 광고에서 4주 만에, 4주 안에처럼 기간을 명시하는 표현.
      단순 프로그램 기간 설명인 경우 허용 가능하지만,
      결과 보장과 결합되면 과장 광고 리스크가 있음.
    examples:
      - unsafe: "4주 만에 복근 완성"
        safe: "4주 동안 바디프로필을 준비하는 코칭 프로그램"
        index_for_rag: true
```

---

### 1-3. `orchestrator/app/compliance/schemas.py`

```python
"""Compliance 관련 타입 정의."""

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


class RagContext(BaseModel):
    retrieved_examples: list[dict[str, Any]] = Field(default_factory=list)
    regulatory_guidance: str | None = None
    enforcement_cases: list[dict[str, Any]] = Field(default_factory=list)
    source_chunks: list[str] = Field(default_factory=list)


class ComplianceFinding(BaseModel):
    finding_id: str
    field: Literal["headline", "sub_copy", "cta"]
    rule_id: str | None = None          # pattern: rule_id, RAG discovery: None
    severity: Literal["warn", "evidence_required", "block"]
    matched_text: str
    reason: str
    legal_basis: list[LegalBasisRef] = Field(default_factory=list)
    suggested_text: str | None = None
    hitl_question: str | None = None
    evidence_requirements: list[str] = Field(default_factory=list)
    detection_method: Literal["pattern", "semantic", "rag"] = "pattern"
    confidence: float = 1.0             # pattern: 1.0, RAG: cosine similarity
    rag_chunk_id: str | None = None
    rag_retrieval_score: float | None = None
    rag_context: RagContext | None = None  # v1: None, v2: 채워짐


SEVERITY_RANK: dict[str, int] = {"warn": 1, "evidence_required": 2, "block": 3}


class CopyComplianceState(BaseModel):
    status: Literal["pass", "warn", "evidence_required", "blocked", "manual_review_required"]
    findings: list[ComplianceFinding] = Field(default_factory=list)
    original_copy: dict[str, Any] | None = None  # 검사 시점 원문, 삭제 금지
    suggested_copy: dict[str, Any] | None = None  # 덮어쓰지 않음
    user_decision: str | None = None
    user_acknowledged_risk: bool = False
    publication_ready: bool = True
    interrupt_payload: dict[str, Any] | None = None
    evidence_submitted: list[dict[str, Any]] = Field(default_factory=list)
    revision_count: int = 0
```

---

### 1-4. `orchestrator/app/compliance/rule_loader.py`

```python
"""YAML rule pack → ComplianceRule 객체 변환."""

from __future__ import annotations

from pathlib import Path

import yaml

from orchestrator.app.compliance.schemas import ComplianceRule, LegalBasisRef

_RULES_PATH = Path(__file__).parents[3] / "data" / "compliance" / "rules_kr_v1.yaml"
_LEGAL_BASIS_PATH = Path(__file__).parents[3] / "data" / "compliance" / "legal_basis_kr_v1.yaml"


def load_legal_basis(path: Path = _LEGAL_BASIS_PATH) -> dict[str, LegalBasisRef]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {
        key: LegalBasisRef(key=key, **entry)
        for key, entry in (raw.get("legal_basis") or {}).items()
    }


def load_rules(path: Path = _RULES_PATH) -> list[ComplianceRule]:
    legal_basis_map = load_legal_basis()
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    rules = []
    for entry in raw.get("rules") or []:
        ref_raw = entry.get("legal_basis_ref") or {}
        ref_key = ref_raw.get("key") if isinstance(ref_raw, dict) else None
        ref = legal_basis_map.get(ref_key) if ref_key else None
        rules.append(ComplianceRule(**{**entry, "legal_basis_ref": ref}))
    return rules
```

---

### 1-5. `orchestrator/app/compliance/rule_engine.py`

```python
"""ComplianceChecker Protocol + PatternMatcher 구현."""

from __future__ import annotations

import re
import uuid
from typing import Any, Protocol

from orchestrator.app.compliance.schemas import (
    SEVERITY_RANK,
    ComplianceFinding,
    ComplianceRule,
    CopyComplianceState,
    LegalBasisRef,
)


class ComplianceChecker(Protocol):
    """v2 RAG 확장 시 이 Protocol을 구현하는 HybridMatcher로 교체한다."""

    def scan(self, copy: dict[str, Any], domains: list[str]) -> list[ComplianceFinding]: ...


class PatternMatcher:
    """v1 구현체: deterministic regex 매칭."""

    def __init__(self, rules: list[ComplianceRule]) -> None:
        self.rules = rules
        self._compiled: dict[str, list[re.Pattern[str]]] = {
            r.rule_id: [re.compile(p) for p in r.patterns]
            for r in rules
        }

    def scan(self, copy: dict[str, Any], domains: list[str]) -> list[ComplianceFinding]:
        text_fields: dict[str, str | None] = {
            "headline": copy.get("headline"),
            "sub_copy": copy.get("subcopy") or copy.get("sub_copy"),
            "cta": copy.get("cta"),
        }
        applicable = [r for r in self.rules if r.domain in domains]
        findings: list[ComplianceFinding] = []

        for rule in applicable:
            for field, text in text_fields.items():
                if not text:
                    continue
                for pattern in self._compiled[rule.rule_id]:
                    m = pattern.search(text)
                    if m:
                        findings.append(ComplianceFinding(
                            finding_id=f"finding_{uuid.uuid4().hex[:8]}",
                            field=field,
                            rule_id=rule.rule_id,
                            severity=rule.severity,
                            matched_text=m.group(),
                            reason=rule.title,
                            legal_basis=[rule.legal_basis_ref] if rule.legal_basis_ref else [],
                            suggested_text=rule.examples[0].safe if rule.examples else None,
                            hitl_question=rule.hitl_question,
                            evidence_requirements=rule.evidence_requirements,
                            detection_method="pattern",
                            confidence=1.0,
                            rag_chunk_id=None,
                            rag_retrieval_score=None,
                            rag_context=None,
                        ))
        return findings

    def aggregate_severity(self, findings: list[ComplianceFinding]) -> str:
        if not findings:
            return "pass"
        return max(findings, key=lambda f: SEVERITY_RANK.get(f.severity, 0)).severity
```

---

### 1-6. `orchestrator/app/compliance/rewrite_strategy.py`

```python
"""RewriteStrategy Protocol + StaticHintRewriter."""

from __future__ import annotations

from typing import Any, Protocol

from orchestrator.app.compliance.schemas import ComplianceFinding, ComplianceRule


class RewriteStrategy(Protocol):
    """v2 RAG 확장 시 RAGExampleRewriter로 교체한다."""

    def suggest(self, finding: ComplianceFinding, original_text: str, domain: str) -> str | None: ...


class StaticHintRewriter:
    """v1: YAML examples[0].safe 반환."""

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

---

### 1-7. `orchestrator/app/compliance/industry_classifier.py`

```python
"""business_type → compliance domain 매핑."""

from __future__ import annotations

BUSINESS_TYPE_TO_DOMAIN: dict[str, list[str]] = {
    "cafe":               ["food", "general_ad"],
    "restaurant":         ["food", "general_ad"],
    "restaurant_bbq":     ["food", "general_ad"],
    "restaurant_japanese":["food", "general_ad"],
    "restaurant_korean":  ["food", "general_ad"],
    "fitness":            ["general_ad"],
    "pilates":            ["general_ad"],
    "yoga":               ["general_ad"],
    "beauty_skincare":    ["cosmetic", "general_ad"],
    "beauty_hair":        ["cosmetic", "general_ad"],
    "beauty_nail":        ["cosmetic", "general_ad"],
    "beauty_spa":         ["cosmetic", "general_ad"],
    "hospital":           ["medical", "general_ad"],
    "dental":             ["medical", "general_ad"],
    "plastic_surgery":    ["medical", "general_ad"],
    "oriental_medicine":  ["medical", "general_ad"],
    "health_supplement":  ["health_functional_food", "food", "general_ad"],
}

_FALLBACK = ["general_ad"]


class IndustryClassifier:
    def get_domains(self, business_type: str | None) -> list[str]:
        if not business_type:
            return _FALLBACK
        return BUSINESS_TYPE_TO_DOMAIN.get(business_type, _FALLBACK)
```

---

### 1-8. `orchestrator/app/compliance/service.py`

```python
"""ComplianceService: copy_compliance_gate 노드의 유일한 진입점."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from orchestrator.app.compliance.industry_classifier import IndustryClassifier
from orchestrator.app.compliance.rule_engine import ComplianceChecker, PatternMatcher
from orchestrator.app.compliance.rule_loader import load_rules
from orchestrator.app.compliance.rewrite_strategy import RewriteStrategy, StaticHintRewriter
from orchestrator.app.compliance.schemas import (
    ComplianceFinding,
    CopyComplianceState,
)


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
        status = self._checker.aggregate_severity(findings)

        suggested_copy = None
        if status != "pass" and findings:
            suggested_copy = self._build_suggested_copy(copy, findings, business_type or "")

        return CopyComplianceState(
            status=status,
            findings=findings,
            original_copy=dict(copy),
            suggested_copy=suggested_copy,
            publication_ready=(status in {"pass", "warn"}),
        )

    def _build_suggested_copy(
        self,
        copy: dict[str, Any],
        findings: list[ComplianceFinding],
        business_type: str,
    ) -> dict[str, Any] | None:
        suggested = dict(copy)
        domains = self._classifier.get_domains(business_type)
        for finding in findings:
            field_key = "subcopy" if finding.field == "sub_copy" else finding.field
            original = suggested.get(field_key) or ""
            suggestion = self._rewriter.suggest(finding, original, domains[0] if domains else "")
            if suggestion:
                suggested[field_key] = suggestion
        return suggested if suggested != copy else None


@lru_cache(maxsize=1)
def _build_default_service() -> ComplianceService:
    rules = load_rules()
    rules_by_id = {r.rule_id: r for r in rules}
    classifier = IndustryClassifier()
    checker = PatternMatcher(rules)
    rewriter = StaticHintRewriter(rules_by_id)
    return ComplianceService(checker=checker, rewriter=rewriter, classifier=classifier)


def get_compliance_service() -> ComplianceService:
    """앱 전체에서 singleton을 공유한다. 테스트에서는 직접 생성한다."""
    return _build_default_service()
```

---

### 1-9. 테스트 `orchestrator/tests/test_compliance_rule_engine.py`

```python
"""Rule engine unit tests."""

import pytest

from orchestrator.app.compliance.rule_loader import load_rules
from orchestrator.app.compliance.rule_engine import PatternMatcher
from orchestrator.app.compliance.industry_classifier import IndustryClassifier
from orchestrator.app.compliance.service import ComplianceService
from orchestrator.app.compliance.rewrite_strategy import StaticHintRewriter


def _service() -> ComplianceService:
    rules = load_rules()
    classifier = IndustryClassifier()
    checker = PatternMatcher(rules)
    rewriter = StaticHintRewriter({r.rule_id: r for r in rules})
    return ComplianceService(checker=checker, rewriter=rewriter, classifier=classifier)


# ── pass ────────────────────────────────────────────────────

def test_clean_cafe_copy_passes():
    svc = _service()
    result = svc.check_copy(
        {"headline": "상큼한 딸기라떼 한 잔의 여유", "subcopy": "오늘의 기분 좋은 카페 타임"},
        business_type="cafe",
    )
    assert result.status == "pass"
    assert result.publication_ready is True
    assert result.findings == []


def test_clean_fitness_copy_passes():
    svc = _service()
    result = svc.check_copy(
        {"headline": "4주 동안 체계적으로 준비하는 바디프로필 코칭"},
        business_type="fitness",
    )
    assert result.status == "pass"


# ── warn ────────────────────────────────────────────────────

def test_food_ambiguous_term_is_warn():
    svc = _service()
    result = svc.check_copy(
        {"headline": "디톡스 그린 스무디"},
        business_type="cafe",
    )
    assert result.status == "warn"
    assert result.publication_ready is True  # warn은 non-blocking
    assert any(f.matched_text == "디톡스" for f in result.findings)


# ── evidence_required ────────────────────────────────────────

def test_superlative_requires_evidence():
    svc = _service()
    result = svc.check_copy(
        {"headline": "국내 1위 헬스장"},
        business_type="fitness",
    )
    assert result.status == "evidence_required"
    assert result.publication_ready is False


def test_fitness_guarantee_requires_evidence():
    svc = _service()
    result = svc.check_copy(
        {"headline": "4주 만에 10kg 감량 보장"},
        business_type="fitness",
    )
    assert result.status == "evidence_required"
    assert any(f.evidence_requirements for f in result.findings)


# ── block ────────────────────────────────────────────────────

def test_food_medical_claim_is_blocked():
    svc = _service()
    result = svc.check_copy(
        {"headline": "독소 배출에 도움을 주는 딸기라떼"},
        business_type="cafe",
    )
    assert result.status == "block"
    assert result.publication_ready is False


def test_medical_treatment_guarantee_is_blocked():
    svc = _service()
    result = svc.check_copy(
        {"headline": "여드름 완치 보장"},
        business_type="beauty_skincare",
    )
    assert result.status == "block"


# ── suggested_copy ────────────────────────────────────────────

def test_blocked_copy_generates_suggestion():
    svc = _service()
    result = svc.check_copy(
        {"headline": "여드름 완치 보장"},
        business_type="beauty_skincare",
    )
    assert result.suggested_copy is not None
    assert result.suggested_copy.get("headline") != "여드름 완치 보장"


# ── original_copy 보존 ─────────────────────────────────────

def test_original_copy_is_preserved():
    svc = _service()
    original = {"headline": "독소 배출에 도움을 주는 딸기라떼"}
    result = svc.check_copy(original, business_type="cafe")
    assert result.original_copy == original


# ── 업종 fallback ─────────────────────────────────────────

def test_unknown_business_type_uses_general_ad():
    svc = _service()
    result = svc.check_copy(
        {"headline": "국내 1위 서비스"},
        business_type="unknown_type",
    )
    # general_ad 룰은 적용돼야 함
    assert result.status == "evidence_required"
```

### Phase 1 완료 기준

- [ ] `pytest orchestrator/tests/test_compliance_rule_engine.py` 전부 통과
- [ ] `load_rules()` 실행 시 YAML 파일 로딩 오류 없음
- [ ] 기존 테스트 전부 통과 (graph 미변경이므로 당연)

---

## Phase 2: State 필드 추가 + Candidate 배지 (엣지 변경 없음)

### 목표
`MarketingState`에 compliance 필드를 추가하고,
기존 `copy_candidate_generation_node` 내부에 배지 로직을 추가한다.
builder.py 엣지는 **건드리지 않는다.**

### 건드릴 파일

| 파일 | 변경 내용 |
|------|-----------|
| [orchestrator/app/graph/state.py](orchestrator/app/graph/state.py) | 필드 3개 추가, `create_initial_marketing_state` 초기값 추가 |
| [orchestrator/app/llm/nodes/copy_candidates.py](orchestrator/app/llm/nodes/copy_candidates.py) | `_attach_compliance_badges()` 추가 |

---

### 2-1. `state.py` — 필드 추가

`MarketingState` class body에 다음 3개 필드를 추가한다.

```python
# 기존 copy_selection: dict[str, Any] | None 아래에 추가
input_compliance_risk: dict[str, Any] | None
copy_compliance: dict[str, Any] | None
copy_compliance_status: str | None
copy_compliance_publication_ready: bool
```

`create_initial_marketing_state()` 안의 `state` dict에 초기값을 추가한다.

```python
# result_payload: None 근처에 추가
"input_compliance_risk": None,
"copy_compliance": None,
"copy_compliance_status": None,
"copy_compliance_publication_ready": True,
```

---

### 2-2. `copy_candidates.py` — 배지 부착

`copy_candidate_generation_node`의 `candidates` 리스트가 확정된 직후,
`return` 문 바로 전에 `_attach_compliance_badges(candidates, state)` 호출을 추가한다.

```python
# copy_candidate_generation_node 내부
# 기존: candidates = [apply_candidate_quality_policy(...) for ...]
candidates = [apply_candidate_quality_policy(candidate) for candidate in normalize_candidate_ids(output.candidates[: max(1, max_candidates)])]

# 추가: compliance 배지 부착 (import 추가 필요)
candidates = _attach_compliance_badges(candidates, state)
```

`_attach_compliance_badges` 구현을 파일 하단에 추가한다.

```python
def _attach_compliance_badges(
    candidates: list[CopyCandidate],
    state: MarketingState,
) -> list[CopyCandidate]:
    """후보 카피 각각에 compliance 메타데이터를 부착한다. 후보를 제거하거나 바꾸지 않는다."""
    from orchestrator.app.compliance.service import get_compliance_service

    svc = get_compliance_service()
    business_type = (state.get("context") or {}).get("business_type")
    result = []
    for candidate in candidates:
        copy_dict = {
            "headline": candidate.headline,
            "subcopy": candidate.subcopy,
            "cta": candidate.cta,
        }
        compliance = svc.check_copy(copy_dict, business_type)
        badge = {
            "status": compliance.status,
            "finding_count": len(compliance.findings),
            "disabled": compliance.status == "block",
        }
        result.append(candidate.model_copy(
            update={"metadata": {**candidate.metadata, "compliance": badge}}
        ))
    return result
```

---

### Phase 2 완료 기준

- [ ] 기존 `test_copy_candidates_branch.py` 전부 통과
- [ ] `copy_candidate_generation_node` 반환값의 각 candidate에 `metadata.compliance` 존재 확인
- [ ] `block` 수준 candidate의 `compliance.disabled == True` 확인

테스트 추가:
```python
# test_copy_candidates_branch.py에 추가
def test_copy_candidates_have_compliance_badge():
    update = copy_candidate_generation_node(_state())
    for candidate in update["copy_candidates"]:
        assert "compliance" in candidate["metadata"]
        assert "status" in candidate["metadata"]["compliance"]
        assert "disabled" in candidate["metadata"]["compliance"]
```

---

## Phase 3: copy_compliance_gate 노드 + Graph 연결 (핵심)

### 목표
실제 compliance gate 노드를 만들고 graph에 연결한다.
기존 `state_update_selected_copy → copy_spec_parser` 엣지가 변경된다.
**기존 e2e mock 테스트가 깨지지 않아야 한다.**

### 건드릴 파일

| 파일 | 변경 내용 |
|------|-----------|
| `orchestrator/app/llm/nodes/copy_compliance.py` | **신규 생성** |
| [orchestrator/app/graph/builder.py](orchestrator/app/graph/builder.py) | 노드 3개 추가, 엣지 4개 변경 |
| [orchestrator/app/graph/routers.py](orchestrator/app/graph/routers.py) | router 2개 추가 |
| `orchestrator/tests/test_compliance_gate_branch.py` | **신규 생성** |

---

### 3-1. `orchestrator/app/llm/nodes/copy_compliance.py` — 신규 생성

```python
"""Compliance gate 노드 구현."""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from orchestrator.app.compliance.service import get_compliance_service
from orchestrator.app.graph.state import MarketingState


# ── Gate 노드 ────────────────────────────────────────────────

def copy_compliance_gate_node(state: MarketingState) -> dict[str, Any]:
    """marketing_copy를 검사해 compliance 결과를 state에 저장한다.
    marketing_copy를 절대 직접 수정하지 않는다."""
    copy = dict(state.get("marketing_copy") or {})
    business_type = (state.get("context") or {}).get("business_type")

    svc = get_compliance_service()
    result = svc.check_copy(copy, business_type)

    return {
        "copy_compliance": result.model_dump(),
        "copy_compliance_status": result.status,
        "copy_compliance_publication_ready": result.publication_ready,
        "status": "copy_compliance_checked",
    }


# ── Interrupt 노드 ───────────────────────────────────────────

def copy_compliance_interrupt_node(state: MarketingState) -> dict[str, Any]:
    """evidence_required / block severity일 때 사용자 입력을 받는다."""
    compliance = state.get("copy_compliance") or {}
    findings = compliance.get("findings") or []
    status = state.get("copy_compliance_status") or "evidence_required"

    actions = [
        {"id": "use_suggestion",      "label": "안전한 문구로 수정",          "available": True},
        {"id": "edit_manually",       "label": "직접 수정",                   "available": True},
        {"id": "submit_claim",        "label": "근거자료 제출",               "available": True},
        {"id": "keep_original_draft", "label": "위험을 인지하고 초안으로 계속", "available": status != "blocked"},
        {"id": "cancel",              "label": "생성 취소",                   "available": True},
    ]

    payload = {
        "type": "copy_compliance_review",
        "job_id": state["job_id"],
        "thread_id": state["thread_id"],
        "status": status,
        "summary": _build_summary(findings),
        "findings": _serialize_findings_for_fe(findings),
        "actions": actions,
    }

    resume_payload = interrupt(payload)

    compliance_with_payload = {**compliance, "interrupt_payload": payload}
    return {
        "copy_compliance": compliance_with_payload,
        "copy_compliance_resolution": resume_payload,
        "status": "waiting_compliance_decision",
    }


# ── Resolution 노드 ──────────────────────────────────────────

def copy_compliance_resolution_node(state: MarketingState) -> dict[str, Any]:
    """사용자 결정을 처리하고 다음 노드 방향을 결정한다."""
    resolution = dict(state.get("copy_compliance_resolution") or {})
    decision = resolution.get("action") or resolution.get("user_decision")
    compliance = dict(state.get("copy_compliance") or {})

    if decision == "use_suggestion":
        suggested = compliance.get("suggested_copy")
        if suggested:
            compliance["user_decision"] = "use_suggestion"
            compliance["status"] = "rewritten_by_user_choice"
            compliance["publication_ready"] = True
            return {
                "marketing_copy": suggested,
                "copy_compliance": compliance,
                "copy_compliance_status": "rewritten_by_user_choice",
                "copy_compliance_publication_ready": True,
                "copy_compliance_resolution": resolution,
            }

    if decision == "submit_claim":
        evidence = resolution.get("evidence") or {}
        submitted = list(compliance.get("evidence_submitted") or [])
        submitted.append(evidence)
        compliance["user_decision"] = "submit_claim"
        compliance["status"] = "manual_review_required"
        compliance["publication_ready"] = False
        compliance["evidence_submitted"] = submitted
        return {
            "copy_compliance": compliance,
            "copy_compliance_status": "manual_review_required",
            "copy_compliance_publication_ready": False,
            "copy_compliance_resolution": resolution,
        }

    if decision == "keep_original_draft":
        compliance["user_decision"] = "keep_original_draft"
        compliance["user_acknowledged_risk"] = True
        compliance["status"] = "manual_review_required"
        compliance["publication_ready"] = False
        return {
            "copy_compliance": compliance,
            "copy_compliance_status": "manual_review_required",
            "copy_compliance_publication_ready": False,
            "copy_compliance_resolution": resolution,
        }

    if decision == "cancel":
        return {
            "copy_compliance_resolution": resolution,
            "status": "compliance_blocked",
        }

    # edit_manually: custom_copy_input으로 라우팅 (router가 처리)
    compliance["user_decision"] = "edit_manually"
    return {
        "copy_compliance": compliance,
        "copy_compliance_resolution": resolution,
    }


# ── 내부 헬퍼 ────────────────────────────────────────────────

def _build_summary(findings: list[dict[str, Any]]) -> str:
    count = len(findings)
    if count == 0:
        return "광고 규제 검토를 통과했습니다."
    return f"광고 규제 위험 표현 {count}개가 발견되었습니다."


def _serialize_findings_for_fe(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for f in findings:
        legal_basis = f.get("legal_basis") or []
        result.append({
            "finding_id": f.get("finding_id"),
            "field": f.get("field"),
            "matched_text": f.get("matched_text"),
            "severity": f.get("severity"),
            "detection_method": f.get("detection_method", "pattern"),
            "confidence": f.get("confidence", 1.0),
            "reason": f.get("reason"),
            "legal_basis": [
                {
                    "key": b.get("key"),
                    "law_name": b.get("law_name"),
                    "article": b.get("article"),
                    "summary": b.get("summary"),
                    "chunk_id": b.get("chunk_id"),
                }
                for b in legal_basis
            ],
            "suggested_text": f.get("suggested_text"),
            "evidence_requirements": f.get("evidence_requirements") or [],
            "hitl_question": f.get("hitl_question"),
            "rag_context": f.get("rag_context"),  # v1: None
        })
    return result
```

---

### 3-2. `routers.py` — router 2개 추가

파일 하단에 추가한다.

```python
def route_after_compliance_gate(state: MarketingState) -> str:
    """pass / warn → copy_spec_parser로 통과.
    evidence_required / blocked → interrupt 발생."""
    status = state.get("copy_compliance_status")
    if status in {None, "pass", "warn", "rewritten_by_user_choice"}:
        return "copy_spec_parser"
    return "copy_compliance_interrupt"


def route_after_compliance_resolution(state: MarketingState) -> str:
    """사용자 결정 후 다음 노드 결정."""
    resolution = state.get("copy_compliance_resolution") or {}
    decision = resolution.get("action") or resolution.get("user_decision")

    if decision == "cancel":
        return END  # noqa: F821 — builder에서 import
    if decision == "edit_manually":
        return "custom_copy_input"
    # use_suggestion / submit_claim / keep_original_draft / None
    return "copy_spec_parser"
```

> `END`를 router에서 사용하려면 `from langgraph.graph import END`를 `routers.py` 상단에 추가한다.

---

### 3-3. `builder.py` — 노드 추가 및 엣지 변경

**import 추가:**
```python
from orchestrator.app.llm.nodes.copy_compliance import (
    copy_compliance_gate_node,
    copy_compliance_interrupt_node,
    copy_compliance_resolution_node,
)
from orchestrator.app.graph.routers import (
    ...
    route_after_compliance_gate,      # 추가
    route_after_compliance_resolution, # 추가
)
```

**`build_marketing_graph()` 내부 — 노드 추가:**
```python
# 기존 no_copy_bypass 노드 선언 아래에 추가
graph.add_node("copy_compliance_gate", copy_compliance_gate_node)
graph.add_node("copy_compliance_interrupt", copy_compliance_interrupt_node)
graph.add_node("copy_compliance_resolution", copy_compliance_resolution_node)
```

**엣지 변경:**

기존 코드를 아래처럼 교체한다. 3곳의 `copy_spec_parser` 직접 연결을 `copy_compliance_gate`를 거치도록 변경한다.

```python
# ── 변경 전 ──────────────────────────────────────────────
graph.add_edge("state_update_selected_copy", "copy_spec_parser")
graph.add_edge("auto_pilot_copywriting", "copy_spec_parser")
graph.add_edge("custom_copy_validation", "copy_spec_parser")

# ── 변경 후 ──────────────────────────────────────────────
graph.add_edge("state_update_selected_copy", "copy_compliance_gate")
graph.add_edge("auto_pilot_copywriting", "copy_compliance_gate")
graph.add_edge("custom_copy_validation", "copy_compliance_gate")

graph.add_conditional_edges(
    "copy_compliance_gate",
    route_after_compliance_gate,
    {
        "copy_spec_parser": "copy_spec_parser",
        "copy_compliance_interrupt": "copy_compliance_interrupt",
    },
)
graph.add_edge("copy_compliance_interrupt", "copy_compliance_resolution")
graph.add_conditional_edges(
    "copy_compliance_resolution",
    route_after_compliance_resolution,
    {
        "copy_spec_parser": "copy_spec_parser",
        "custom_copy_input": "custom_copy_input",
        END: END,
    },
)
```

`no_copy_bypass`는 카피가 없으므로 compliance gate를 거치지 않는다. 기존 엣지 유지:
```python
graph.add_edge("no_copy_bypass", "copy_spec_parser")  # 변경 없음
```

---

### 3-4. Phase 3에서 기존 테스트가 깨지지 않는 이유

`test_marketing_graph_e2e_mock.py`의 `auto_pilot` 케이스:
- `business_type="restaurant"`, `item_or_service="삼겹살"`, 카피 내용 안전 → compliance `pass` → `copy_spec_parser`로 통과
- 기존 테스트 결과 변화 없음

단, **테스트 내 state 검증 항목에 compliance 필드 추가** 없이도 통과한다.

**주의**: `test_marketing_graph_node_utilization.py`같이 그래프 노드 목록을 검증하는 테스트가 있다면 새 노드 3개를 추가해야 할 수 있다. 먼저 확인한다.

```bash
pytest orchestrator/tests/test_marketing_graph_node_utilization.py -v
```

---

### 3-5. 신규 테스트 `test_compliance_gate_branch.py`

```python
"""compliance gate branch 통합 테스트."""

from langgraph.types import Command

from orchestrator.app.graph.builder import build_marketing_graph
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.nodes.copy_compliance import copy_compliance_gate_node, copy_compliance_resolution_node
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def _state(business_type="cafe", headline="상큼한 딸기라떼"):
    return create_initial_marketing_state(
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


# ── 노드 단위 테스트 ──────────────────────────────────────

def test_compliance_gate_passes_clean_copy():
    state = _state()
    state["marketing_copy"] = {"headline": "기분 좋은 딸기라떼 한 잔", "subcopy": "오늘의 카페 타임"}
    update = copy_compliance_gate_node(state)
    assert update["copy_compliance_status"] == "pass"
    assert update["copy_compliance"]["publication_ready"] is True


def test_compliance_gate_warns_on_ambiguous():
    state = _state()
    state["marketing_copy"] = {"headline": "디톡스 딸기라떼", "subcopy": "상큼한 한 잔"}
    update = copy_compliance_gate_node(state)
    assert update["copy_compliance_status"] == "warn"
    assert update["copy_compliance"]["publication_ready"] is True  # warn은 통과


def test_compliance_gate_blocks_medical_claim():
    state = _state(business_type="beauty_skincare")
    state["marketing_copy"] = {"headline": "여드름 완치 보장"}
    update = copy_compliance_gate_node(state)
    assert update["copy_compliance_status"] == "blocked"
    assert update["copy_compliance"]["publication_ready"] is False


def test_resolution_use_suggestion_updates_marketing_copy():
    state = _state()
    state["marketing_copy"] = {"headline": "독소 배출 딸기라떼"}
    state.update(copy_compliance_gate_node(state))
    state["copy_compliance_resolution"] = {"action": "use_suggestion"}
    update = copy_compliance_resolution_node(state)
    # marketing_copy가 suggested_copy로 교체됨
    assert update.get("marketing_copy") is not None
    assert update["marketing_copy"]["headline"] != "독소 배출 딸기라떼"


def test_resolution_keep_original_sets_manual_review():
    state = _state()
    state["marketing_copy"] = {"headline": "독소 배출 딸기라떼"}
    state.update(copy_compliance_gate_node(state))
    state["copy_compliance_resolution"] = {"action": "keep_original_draft"}
    update = copy_compliance_resolution_node(state)
    assert update["copy_compliance_status"] == "manual_review_required"
    assert update["copy_compliance_publication_ready"] is False


# ── Graph e2e 테스트 ────────────────────────────────────────

def test_e2e_safe_copy_does_not_interrupt_at_compliance():
    graph = build_marketing_graph()
    result = graph.invoke(
        {
            "user_input": "ready",
            "job_id": "compliance-e2e-pass",
            "thread_id": "compliance-e2e-pass",
            "copy_generation_mode": "auto_pilot",
            "context": {
                "business_type": "restaurant",
                "item_or_service": "삼겹살",
                "promotion_goal": "reservation_cta",
                "extra": {"ad_format": "instagram_feed"},
            },
        },
        config={"configurable": {"thread_id": "compliance-e2e-pass"}},
    )
    assert result["status"] == "done"
    assert result.get("copy_compliance_status") in {None, "pass", "warn"}
```

### Phase 3 완료 기준

- [ ] 기존 `test_marketing_graph_e2e_mock.py` 전부 통과
- [ ] `test_compliance_gate_branch.py` 전부 통과
- [ ] pass/warn 케이스는 interrupt 없이 `done` 상태로 완료
- [ ] block 케이스는 `__interrupt__`가 `copy_compliance_review` type으로 발생

---

## Phase 4: input_compliance_precheck + Result Payload API

### 목표
- Layer 1: `validator` 이후 위험 입력 사전 감지 (non-blocking)
- Result payload에 `copy_compliance` 추가 → FE가 소비 가능

### 건드릴 파일

| 파일 | 변경 내용 |
|------|-----------|
| `orchestrator/app/llm/nodes/copy_compliance.py` | `input_compliance_precheck_node` 추가 |
| [orchestrator/app/graph/builder.py](orchestrator/app/graph/builder.py) | precheck 노드 추가, 엣지 1개 변경 |
| [orchestrator/app/llm/nodes/result.py](orchestrator/app/llm/nodes/result.py) | `copy_compliance` 필드 추가 |
| [orchestrator/app/schemas/text_layout.py](orchestrator/app/schemas/text_layout.py) | `ResultPayload`에 필드 추가 |

---

### 4-1. `input_compliance_precheck_node`

`copy_compliance.py`에 추가한다.

```python
def input_compliance_precheck_node(state: MarketingState) -> dict[str, Any]:
    """사용자 입력에서 위험 intent를 사전 감지한다.
    절대 흐름을 멈추지 않는다. 힌트만 state에 저장한다."""
    from orchestrator.app.compliance.service import get_compliance_service

    user_input = state.get("user_input") or ""
    business_type = (state.get("context") or {}).get("business_type")

    # user_input을 headline처럼 취급해 스캔
    svc = get_compliance_service()
    result = svc.check_copy({"headline": user_input}, business_type)

    if result.status == "pass":
        return {"input_compliance_risk": None}

    flagged = [f.matched_text for f in result.findings]
    domains = [f.rule_id.split("-")[1].lower() for f in result.findings if f.rule_id]
    hints = list({h for f in result.findings for r in [svc._checker] for h in []})  # safe hints (v1: 빈 리스트)

    risk = {
        "detected": True,
        "domains": list(set(domains)),
        "flagged_terms": flagged,
        "safe_direction": _build_safe_direction_hint(result.findings),
    }
    return {"input_compliance_risk": risk}


def _build_safe_direction_hint(findings) -> str:
    domains = {f.rule_id.split("-")[1].lower() if f.rule_id else "" for f in findings}
    if "food" in domains:
        return "맛·향·분위기·재료·경험 중심으로 생성합니다."
    if "medical" in domains or "cosmetic" in domains:
        return "상담·경험·케어 과정 중심으로 생성합니다."
    return "표현을 완화해 생성합니다."
```

---

### 4-2. `builder.py` — precheck 노드 추가

```python
# import 추가
from orchestrator.app.llm.nodes.copy_compliance import (
    ...
    input_compliance_precheck_node,  # 추가
)

# build_marketing_graph() 내부
graph.add_node("input_compliance_precheck", input_compliance_precheck_node)

# 엣지: format_planner 앞에 삽입
# 기존: graph.add_edge("validator → format_planner") 구간에서
# route_after_validator_for_marketing의 "format_planner" 반환 대신
# "input_compliance_precheck"를 거치도록 변경

# 변경 전
graph.add_conditional_edges(
    "validator",
    route_after_validator_for_marketing,
    {"options": "options", "format_planner": "format_planner"},
)

# 변경 후
graph.add_conditional_edges(
    "validator",
    route_after_validator_for_marketing,
    {"options": "options", "format_planner": "input_compliance_precheck"},
)
graph.add_edge("input_compliance_precheck", "format_planner")
```

---

### 4-3. `result.py` — compliance 필드 추가

`result_node`의 `payload` 생성 부분에서 `metadata` dict에 compliance를 추가한다.

```python
# 기존 metadata dict
metadata={
    "source_node": "result",
    ...
    "qualityDecision": ocr_decision,
    # 추가
    "copyCompliance": _build_copy_compliance_payload(state),
},

# 파일 하단에 헬퍼 추가
def _build_copy_compliance_payload(state: MarketingState) -> dict[str, Any]:
    compliance = state.get("copy_compliance") or {}
    status = state.get("copy_compliance_status") or "pass"
    publication_ready = state.get("copy_compliance_publication_ready", True)

    findings_raw = compliance.get("findings") or []
    findings = [
        {
            "findingId": f.get("finding_id"),
            "field": f.get("field"),
            "matchedText": f.get("matched_text"),
            "severity": f.get("severity"),
            "detectionMethod": f.get("detection_method", "pattern"),
            "confidence": f.get("confidence", 1.0),
            "message": f.get("reason"),
            "legalBasis": f.get("legal_basis") or [],
            "suggestedText": f.get("suggested_text"),
            "ragContext": f.get("rag_context"),  # v1: null
        }
        for f in findings_raw
    ]

    summary = "광고 규제 검토를 통과했습니다." if status == "pass" else \
              f"광고 규제 위험 표현 {len(findings)}개가 발견되었습니다."
    if status in {"manual_review_required"}:
        summary = "광고 규제 위험 표현이 발견되었습니다. 게시 전 확인이 필요합니다."

    return {
        "status": status,
        "publicationReady": publication_ready,
        "summary": summary,
        "findings": findings,
        "userDecision": compliance.get("user_decision"),
        "userAcknowledgedRisk": compliance.get("user_acknowledged_risk", False),
    }
```

### Phase 4 완료 기준

- [ ] `result_payload.metadata.copyCompliance` 필드가 API 응답에 포함됨
- [ ] pass 케이스: `copyCompliance.status == "pass"`, `publicationReady == true`
- [ ] manual_review 케이스: `publicationReady == false`
- [ ] `input_compliance_risk`가 위험 입력에서 state에 설정됨

---

## Phase 5: Prompt Injection (Layer 2)

### 목표
`build_copy_generation_metadata()`에 업종별 compliance hints를 soft constraint로 주입한다.
이것은 1차 예방이다. LLM이 어겨도 Phase 3 gate가 반드시 잡는다.

### 건드릴 파일

| 파일 | 변경 내용 |
|------|-----------|
| [orchestrator/app/llm/metadata_builders.py](orchestrator/app/llm/metadata_builders.py) | `build_common_constraints_metadata`에 compliance 추가 |

---

### 5-1. `metadata_builders.py` — compliance 주입

`build_common_constraints_metadata` 함수의 `sanitize_metadata()` 호출에 `compliance` 항목을 추가한다.

```python
from orchestrator.app.compliance.service import get_compliance_service
from orchestrator.app.compliance.industry_classifier import IndustryClassifier

def build_common_constraints_metadata(state: dict[str, Any] | None) -> dict[str, Any]:
    source = state or {}
    tone = _dict(source.get("tone_binding_output"))
    business_type = _dict(source.get("context")).get("business_type")

    # compliance hints 생성
    compliance_constraints = _build_compliance_constraints(business_type)

    return sanitize_metadata(
        {
            ...  # 기존 항목 유지
            "forbidden_claims": tone.get("forbidden_claims", []),
            "compliance": compliance_constraints,  # 추가
        }
    )


def _build_compliance_constraints(business_type: str | None) -> dict[str, Any]:
    if not business_type:
        return {}
    try:
        svc = get_compliance_service()
        classifier = IndustryClassifier()
        domains = classifier.get_domains(business_type)
        rules = [r for r in svc._checker.rules if r.domain in domains]

        blocked_terms = [p for r in rules if r.severity == "block" for p in r.patterns]
        blocked_claims = [r.title for r in rules if r.severity == "block"]
        safe_hints = list({h for r in rules for h in r.safe_rewrite_hints})[:3]

        return {
            "jurisdiction": "KR",
            "domains": domains,
            "blocked_terms": blocked_terms[:10],   # 너무 길면 프롬프트 낭비
            "blocked_claims": blocked_claims[:5],
            "safe_direction": safe_hints,
        }
    except Exception:
        return {}
```

### Phase 5 완료 기준

- [ ] `build_copy_generation_metadata()` 결과에 `compliance` 키 존재
- [ ] `food` 업종에서 `디톡스`, `독소 배출` 등이 `blocked_terms`에 포함
- [ ] 기존 `test_copy_tone_metadata_contracts.py` 통과

---

## 전체 Phase 요약

| Phase | 그래프 변경 | 주요 파일 | 완료 기준 |
|-------|-----------|-----------|-----------|
| **1. Schema + Rule Pack** | 없음 | `compliance/` 모듈 신규, YAML 2개 | rule engine unit test 통과 |
| **2. State + Candidate 배지** | 없음 (노드 내부) | `state.py`, `copy_candidates.py` | 배지 metadata 확인, 기존 테스트 유지 |
| **3. Gate 노드 + Graph 연결** | 있음 (엣지 변경) | `copy_compliance.py`, `builder.py`, `routers.py` | e2e mock 통과, interrupt 발생 확인 |
| **4. Precheck + Result Payload** | 있음 (노드 추가) | `result.py`, `builder.py` | API 응답에 copyCompliance 포함 |
| **5. Prompt Injection** | 없음 (metadata) | `metadata_builders.py` | metadata에 compliance hints 확인 |

### 리스크 관리

**Phase 3에서 가장 높은 위험**: 엣지 변경으로 기존 e2e 테스트가 새 노드를 알지 못해 실패할 수 있음.  
→ Phase 3 시작 전 `test_marketing_graph_node_utilization.py` 먼저 실행해 노드 목록 검증 테스트 유무 확인.

**`PatternMatcher._checker.rules` 직접 접근**: Phase 5에서 `svc._checker.rules`에 직접 접근하는 게 캡슐화 위반.  
→ `ComplianceService`에 `get_rules_for_domains(domains)` 메서드를 추가해 사용하는 것이 더 나음.

**YAML 파일 경로**: `rule_loader.py`의 `Path(__file__).parents[3]` 기준 경로가 배포 환경에서 달라질 수 있음.  
→ `orchestrator/app/core/config.py` 패턴을 따라 환경변수 또는 설정으로 경로를 관리하는 것이 장기적으로 안전함.
