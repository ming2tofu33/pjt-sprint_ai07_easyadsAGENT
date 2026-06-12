# EasyAds 광고법 규제 게이트 설계 v1

> 목적: 한국 광고 규제 대응을 위한 `copy_compliance_gate` 도입 설계 기준을 정의한다.  
> 기준: 2026-06-10 기준 LangGraph 구조 및 기존 HITL interrupt 패턴을 기반으로 한다.  
> 적용 범위: Orchestrator LangGraph, Backend compliance 모듈, FE 규제 피드백 UI.  
> RAG 확장: v2 이후 RAG 추가 시 이 문서의 확장 설계 기준(섹션 9)을 따른다.

---

## 0. 설계 원칙 (변경 불가)

이 설계 전체는 아래 단일 원칙에서 파생된다.

```
copy_compliance_gate = 위험 분석기 + 사용자 의사결정 분기기
                     ≠ 자동 교정기
```

구체적으로:

- **자동 삭제하지 않는다.** 시스템이 사용자 문구를 몰래 바꾸지 않는다.
- **위험을 정확히 설명한다.** 이유와 법적 근거를 사용자가 이해할 수 있는 언어로 제공한다.
- **근거가 있으면 제출할 수 있게 한다.** 실제로 효과 있는 제품인 경우 증거 기반 경로를 제공한다.
- **선택권은 사용자에게 있다.** 단, 법적으로 명백히 허용 불가한 영역은 override 제공하지 않는다.
- **`user_override=true` ≠ `compliance_passed=true`** 이 둘을 절대 같은 값으로 처리하지 않는다.

---

## 1. 왜 프롬프트 제약만으로는 부족한가

실험 결과 제약 프롬프트 적용 후에도 `디톡스`, `4주 만에`, `변화` 같은 표현이 남았다. 이는 LLM이 직접적인 금칙어 일부는 줄였지만 **암시 표현과 업종별 규제 리스크까지 안정적으로 통제하지 못했다**는 뜻이다.

따라서 구조를 다음처럼 가져간다.

| 계층 | 방법 | 역할 |
|------|------|------|
| Layer 1 | 입력 사전검사 | 위험 intent 감지, 생성 방향 힌트 설정 |
| Layer 2 | 프롬프트 주입 | 업종별 금지 claim을 프롬프트에 soft constraint로 주입 |
| Layer 3 | Rule engine (핵심) | 생성된 카피를 deterministic matcher로 검사 + HITL 분기 |
| Layer 4 | 최종 OCR 재검증 | T2I 백그라운드가 텍스트를 생성한 경우 edge case 검출 |

Layer 2는 1차 예방이다. LLM이 어길 것을 전제하고 Layer 3에서 반드시 재검사한다.

---

## 2. Severity 4단계 분류

모든 compliance 판정은 다음 4단계 중 하나로 결정된다.

### `pass`
규칙에 걸리지 않는 상태. 다음 노드로 바로 진행.

```
"4주 동안 체계적으로 준비하는 바디프로필 클래스"
```

### `warn`
표현이 위험할 수 있지만 생성을 막을 수준은 아닌 상태. **non-blocking** — 배지만 붙이고 계속 진행. 최종 결과 화면에서 acknowledgment 한 번 받는다.

```
"4주 만에 변화"  (기간 설명 가능성 있음)
"최고의 선택"    (문맥에 따라 다름)
```

### `evidence_required`
객관적 근거가 있으면 사용 가능하지만 현재 시스템에 근거가 없는 상태. **blocking interrupt** 발생.

```
"판매량 1위"
"임상시험으로 확인"
"체지방 감소에 도움"
```

### `block`
근거나 사용자 확인만으로는 허용하기 어려운 고위험 표현. **blocking interrupt** 발생. 일반적인 "그래도 진행" 버튼을 제공하지 않는다.

```
"여드름 완치 보장"
"치료 효과 100% 보장"
"환자 치료 후기 기반 확실한 효과"
```

> **중요**: `warn`과 `evidence_required`/`block`은 HITL 방식이 다르다.  
> `warn` → non-blocking, 배지.  
> `evidence_required`/`block` → blocking interrupt.

---

## 3. LangGraph 노드 구조

### 3.1 전체 흐름

```
validator
→ input_compliance_precheck   # non-blocking, 방향 힌트만 설정
→ format_planner
→ tone_binding
→ copy_mode_router
   ├─ copy_candidate_generation
   │   → candidate_compliance_scan      # 배지 부착용, 후보 필터링 아님
   │   → copy_candidate_selection_interrupt
   │   → state_update_selected_copy
   │   → copy_compliance_gate
   │
   ├─ auto_pilot_copywriting
   │   → copy_compliance_gate
   │
   ├─ custom_copy_input
   │   → custom_copy_validation
   │   → copy_compliance_gate
   │
   └─ no_copy_bypass
       → copy_spec_parser

copy_compliance_gate
→ compliance_severity_router
   ├─ pass  → copy_spec_parser
   ├─ warn  → (배지 부착) → copy_spec_parser
   └─ evidence_required / block → copy_compliance_interrupt
                                   → copy_compliance_resolution
                                      ├─ use_suggestion    → copy_spec_parser
                                      ├─ edit_manually     → custom_copy_input → copy_compliance_gate
                                      ├─ submit_claim      → manual_review_required → copy_spec_parser
                                      └─ cancel            → job blocked

copy_spec_parser
→ text_style_binder → text_layout_planner
→ image_prompt_planner → prompt_renderer
→ t2i_request_builder → t2i_generation
→ background_validation / background_ocr_gate
→ text_renderer
→ final_ocr_compliance_check    # T2I 생성 텍스트 edge case 전용
→ readability_gate → final_validation
→ result
```

### 3.2 각 노드 책임

#### `input_compliance_precheck`
- 사용자 입력 텍스트에서 위험 intent 감지 (regex + 업종 분류 기반)
- state에 `input_compliance_risk` 설정
- **절대 흐름을 멈추지 않음** — 힌트만 설정하고 다음 노드로 진행

```python
# 출력 예시
{
    "input_compliance_risk": {
        "detected": True,
        "domains": ["food"],
        "hints": ["맛·분위기·경험 중심으로 생성"],
        "flagged_terms": ["붓기 제거"]
    }
}
```

#### `candidate_compliance_scan`
- 생성된 후보 카피 리스트를 스캔해서 각 후보에 compliance 메타데이터 부착
- 후보를 **제거하거나 바꾸지 않음** — 정보만 붙임
- `block` 수준 후보는 UI에서 비활성화하도록 플래그만 설정

```python
# 후보 카피 메타데이터 예시
{
    "id": "cand_002",
    "headline": "4주 만에 달라지는 나",
    "compliance": {
        "status": "warn",
        "risk_level": "medium",
        "finding_count": 1,
        "disabled": False
    }
}
```

#### `copy_compliance_gate` (핵심 노드)
- `ComplianceService.check_copy()`를 호출하는 것만 담당 (구현 세부사항 모름)
- 입력: `marketing_copy` 또는 `selected_copy`, `context.business_type`, `input_compliance_risk`
- 출력: `copy_compliance` dict (섹션 4 참고)
- **`marketing_copy`를 직접 수정하지 않음**

하지 말아야 할 것:
```
원문을 자동으로 덮어쓰기
원문을 state에서 삭제
경고 상태를 pass로 위장
모든 효능 표현을 감성 문구로 변경
```

#### `copy_compliance_interrupt`
- LangGraph `interrupt()` 사용, 기존 HITL 패턴과 동일
- payload 구조는 섹션 5 참고

#### `copy_compliance_resolution`
- interrupt resume 처리
- 사용자 선택에 따라 state 업데이트 후 다음 노드 결정

#### `final_ocr_compliance_check`
- 기존 `final_ocr_gate_node`에 compliance 패턴 체크 추가하는 수준
- T2I 백그라운드가 텍스트를 생성하는 edge case 검출 목적
- 별도 대형 노드가 아니라 기존 OCR 노드 확장

---

## 4. Schema 설계

### 4.1 `ComplianceFinding`

v2 RAG 확장을 전제한 필드를 v1부터 포함한다. v1에서 RAG 전용 필드는 `None` 또는 고정값으로 둔다.

```python
class ComplianceFinding(TypedDict):
    finding_id: str
    field: Literal["headline", "sub_copy", "cta"]

    # pattern match: str, RAG-discovered finding: None
    rule_id: str | None

    severity: Literal["warn", "evidence_required", "block"]
    matched_text: str
    reason: str
    legal_basis: list[LegalBasisRef]
    suggested_text: str | None
    hitl_question: str | None
    evidence_requirements: list[str]

    # v1: 항상 "pattern" / 1.0 — RAG 추가 시 값이 달라짐
    detection_method: Literal["pattern", "semantic", "rag"]
    confidence: float  # pattern: 1.0, RAG: cosine similarity

    # v1: None — RAG 추가 시 채워짐
    rag_chunk_id: str | None
    rag_retrieval_score: float | None
    rag_context: RagContext | None  # HITL payload에서 사용자에게 노출
```

`rule_id`를 `str | None`으로 두는 이유: RAG가 패턴에 없는 새로운 위반 표현을 발견할 경우 어떤 rule에도 매핑되지 않는 finding이 생성될 수 있다.

### 4.2 `RagContext`

v1에서는 이 타입의 인스턴스가 생성되지 않는다. 타입 정의만 해두어 HITL payload API contract가 v2에서 깨지지 않게 한다.

```python
class RagContext(TypedDict):
    retrieved_examples: list[dict]    # 유사 위반 사례
    regulatory_guidance: str | None   # 관련 행정지도 요약
    enforcement_cases: list[dict]     # 관련 시정명령 사례
    source_chunks: list[str]          # 검색에 사용된 chunk_id 목록
```

### 4.3 `LegalBasisRef`

```python
class LegalBasisRef(TypedDict):
    key: str           # legal_basis YAML의 키 (예: KR-FOOD-AD-8)
    law_name: str
    article: str
    summary: str
    # v1: None — RAG vector store 연결 시 채워짐
    chunk_id: str | None
```

### 4.4 `MarketingState` 추가 필드

```python
# top-level 추가
input_compliance_risk: dict | None

copy_compliance_status: Literal[
    "pass",
    "warn",
    "evidence_required",
    "manual_review_required",
    "blocked",
] | None

copy_compliance_publication_ready: bool  # 기본값 True

copy_compliance: CopyComplianceState | None
```

### 4.5 `CopyComplianceState`

```python
class CopyComplianceState(TypedDict):
    status: str
    findings: list[ComplianceFinding]
    original_copy: MarketingCopy | None  # 검사 시점 원문 — 삭제 금지
    suggested_copy: MarketingCopy | None # 시스템 제안 (덮어쓰기 아님)
    user_decision: str | None
    user_acknowledged_risk: bool
    publication_ready: bool
    interrupt_payload: dict | None
    evidence_submitted: list[EvidenceSubmission]
    revision_count: int
```

원칙:
```
marketing_copy는 user_decision이 "use_suggestion"인 경우에만 수정한다.
original_copy는 어떤 경우에도 삭제하지 않는다.
```

---

## 5. Interrupt Payload 설계

`copy_compliance_interrupt`가 FE에 내려보내는 payload.  
`rag_context` 필드는 v1에서 `null`이지만 API contract에 포함한다.

```json
{
    "type": "copy_compliance_review",
    "job_id": "job_xxx",
    "thread_id": "thread_xxx",
    "status": "evidence_required",
    "summary": "광고 규제 위험 표현 1개가 발견되었습니다.",
    "findings": [
        {
            "finding_id": "finding_001",
            "field": "headline",
            "matched_text": "4주 만에 10kg 감량",
            "severity": "evidence_required",
            "detection_method": "pattern",
            "confidence": 1.0,
            "reason": "특정 기간 내 감량 결과를 단정하는 표현은 객관적인 근거가 필요합니다.",
            "legal_basis": [
                {
                    "key": "KR-FAIR-AD-3",
                    "law_name": "표시·광고의 공정화에 관한 법률",
                    "article": "제3조",
                    "summary": "소비자를 오인시킬 우려가 있는 거짓·과장 광고 금지",
                    "chunk_id": null
                }
            ],
            "suggested_text": "4주 동안 체계적으로 준비하는 바디프로필 클래스",
            "evidence_requirements": ["측정 방법", "대상자 수", "조사 기간", "검증 기관"],
            "rag_context": null
        }
    ],
    "actions": [
        { "id": "use_suggestion",      "label": "안전한 문구로 수정",        "available": true },
        { "id": "edit_manually",       "label": "직접 수정",                 "available": true },
        { "id": "submit_claim",        "label": "근거자료 제출",             "available": true },
        { "id": "keep_original_draft", "label": "위험을 인지하고 초안으로 계속", "available": true },
        { "id": "cancel",              "label": "생성 취소",                 "available": true }
    ]
}
```

`block` severity인 경우 `keep_original_draft`의 `available: false`.

---

## 6. Resolution 노드 처리 로직

### `use_suggestion`
```python
state["marketing_copy"] = state["copy_compliance"]["suggested_copy"]
state["copy_compliance"]["user_decision"] = "use_suggestion"
state["copy_compliance"]["status"] = "rewritten_by_user_choice"
state["copy_compliance"]["publication_ready"] = True
# original_copy는 삭제 금지
→ next: copy_spec_parser
```

### `edit_manually`
```python
state["copy_compliance"]["user_decision"] = "edit_manually"
→ next: custom_copy_input_interrupt_node
# 수정된 카피는 copy_compliance_gate 재통과
```

### `submit_claim`
```python
state["copy_compliance"]["evidence_submitted"].append(evidence_data)
state["copy_compliance"]["user_decision"] = "submit_claim"
state["copy_compliance"]["status"] = "manual_review_required"
state["copy_compliance"]["publication_ready"] = False  # 검증 아님
# marketing_copy 변경 없음
→ next: copy_spec_parser (초안)
```

### `keep_original_draft`
```python
state["copy_compliance"]["user_decision"] = "keep_original_draft"
state["copy_compliance"]["user_acknowledged_risk"] = True
state["copy_compliance"]["status"] = "manual_review_required"
state["copy_compliance"]["publication_ready"] = False
# marketing_copy 변경 없음
→ next: copy_spec_parser (초안)
# block severity에서는 이 경로 없음
```

### `cancel`
```python
state["job_status"] = "compliance_blocked"
→ next: END
```

---

## 7. Rule Pack 설계

### 7.1 파일 구조

```
orchestrator/app/compliance/
    __init__.py
    schemas.py              # ComplianceRule, ComplianceFinding, RagContext 등
    rule_loader.py          # YAML → ComplianceRule 객체 변환
    rule_engine.py          # ComplianceChecker Protocol + PatternMatcher 구현
    rewrite_strategy.py     # RewriteStrategy Protocol + StaticHintRewriter 구현
    industry_classifier.py  # business_type → domain 매핑
    service.py              # ComplianceService (gate 노드의 유일한 진입점)

orchestrator/app/llm/nodes/
    copy_compliance.py      # LangGraph 노드 (service.py만 호출)

data/compliance/
    rules_kr_v1.yaml
    legal_basis_kr_v1.yaml

orchestrator/app/api/schemas/
    compliance.py           # FE API 응답 스키마
```

### 7.2 Rule YAML 형식

**단순 금지 표현 (문맥 불필요):**

```yaml
- rule_id: KR-MEDICAL-BLOCK-001
  domain: medical
  severity: block
  title: "치료 효과 보장·완치 표현"
  patterns:
    - "완치"
    - "치료 효과 100%"
    - "확실히 사라지는"
    - "여드름 치료 보장"
  legal_basis_ref:
    key: KR-MEDICAL-AD-56
    chunk_id: null          # v2 RAG: vector store chunk ID로 채움
  safe_rewrite_hints:
    - "치료 효과 대신 상담, 관리 과정, 편안한 경험 중심으로"
  # RAG semantic detection용 임베딩 텍스트
  # v1: indexer가 무시, v2: vector store에 올림
  embedding_text: >
    의료 광고에서 치료 결과를 보장하거나 완치를 약속하는 표현.
    환자가 치료 효과를 단정하거나 시술 결과를 확신하게 만드는 문구.
    의료법상 소비자 현혹 우려가 있는 의료광고 유형.
  examples:
    - unsafe: "여드름이 확실히 사라집니다"
      safe: "피부 고민을 차분히 상담하고 맞춤 관리를 제안합니다"
      index_for_rag: true   # v2: 이 pair를 vector store에 인덱싱
```

**근거 필요 표현 (기본값 evidence_required):**

```yaml
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
    - unsafe: "국내 유일 특허 기술"
      safe: "특허 등록 기술 (특허 제10-XXXXXXX호)"
      index_for_rag: true
```

**문맥 의존 표현 (기본값 warn, HITL에서 사용자가 context 제공):**

```yaml
- rule_id: KR-FOOD-AMBIGUOUS-001
  domain: food
  severity: warn
  title: "신체 효능 암시 가능성 표현"
  patterns:
    - "디톡스"
    - "4주 만에"
    - "다이어트"
    - "몸이 가벼워"
  legal_basis_ref:
    key: KR-FOOD-AD-8
    chunk_id: null
  hitl_question: "이 표현이 제품명이나 프로그램 기간을 설명하는 건가요, 신체 효능을 주장하는 건가요?"
  context_upgrade:
    body_effect_claim: evidence_required
    medical_claim: block
  safe_rewrite_hints:
    - "맛, 향, 분위기, 재료, 계절감 중심으로"
  embedding_text: >
    식품·음료 광고에서 신체 정화, 독소 배출, 체중 감소, 체내 노폐물 제거 효과를
    직접 또는 암시적으로 주장하는 표현. 일반 식품이 의약품이나 건강기능식품처럼
    보이게 만드는 문구.
  examples:
    - unsafe: "체내 노폐물을 걸러주는 그린 스무디"
      safe: "상큼한 채소와 과일이 어우러진 그린 스무디"
      index_for_rag: true
```

> **Context classifier는 LLM이 아니라 HITL에서 사용자가 제공한다.**  
> LLM 기반 context 분류는 rule engine 도입 목적(LLM 불안정성 제거)과 모순이므로 v1에서 사용하지 않는다.  
> `hitl_question`을 사용자에게 보여주고, 사용자 선택 결과로 severity를 upgrade 또는 유지한다.

### 7.3 Legal Basis 파일

버전 관리와 RAG chunk 연결을 위해 `effective_date`, `last_verified_at`, `chunk_id`를 포함한다.  
v1에서 `chunk_id`는 `null`이지만 필드 자체는 정의해둔다.

```yaml
# legal_basis_kr_v1.yaml
legal_basis:
  KR-FAIR-AD-3:
    law_name: "표시·광고의 공정화에 관한 법률"
    article: "제3조"
    summary: "소비자를 속이거나 소비자가 잘못 알 우려가 있는 부당한 표시·광고 행위 금지"
    source_url: "https://www.law.go.kr/"
    effective_date: "2023-09-14"
    last_verified_at: "2026-06-01"
    chunk_id: null    # v2 RAG: vector store chunk ID

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

## 8. 서비스 계층 구현 기준

### 8.1 `ComplianceChecker` Protocol

gate 노드는 이 Protocol만 의존한다. v1에서는 `PatternMatcher`를 주입하고, v2에서는 `HybridMatcher`로 교체해도 gate 노드 코드를 건드리지 않는다.

```python
# rule_engine.py
from typing import Protocol

class ComplianceChecker(Protocol):
    def scan(
        self,
        copy: MarketingCopy,
        domains: list[str],
    ) -> list[ComplianceFinding]: ...


class PatternMatcher:
    """v1 구현체: deterministic regex 매칭"""

    def __init__(self, rules: list[ComplianceRule]):
        self.rules = rules
        self._compiled = {
            r.rule_id: [re.compile(p) for p in r.patterns]
            for r in rules
        }

    def scan(
        self,
        copy: MarketingCopy,
        domains: list[str],
    ) -> list[ComplianceFinding]:
        findings = []
        text_fields = {
            "headline": copy.headline,
            "sub_copy": copy.sub_copy,
            "cta": copy.cta,
        }
        applicable = [r for r in self.rules if r.domain in domains]

        for rule in applicable:
            for field, text in text_fields.items():
                if not text:
                    continue
                for pattern in self._compiled[rule.rule_id]:
                    m = pattern.search(text)
                    if m:
                        findings.append(ComplianceFinding(
                            finding_id=_new_id(),
                            field=field,
                            rule_id=rule.rule_id,
                            severity=rule.severity,
                            matched_text=m.group(),
                            reason=rule.title,
                            legal_basis=_resolve_basis(rule.legal_basis_ref),
                            suggested_text=_pick_hint(rule),
                            hitl_question=getattr(rule, "hitl_question", None),
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
        rank = {"warn": 1, "evidence_required": 2, "block": 3}
        return max(findings, key=lambda f: rank.get(f.severity, 0)).severity
```

### 8.2 `RewriteStrategy` Protocol

rewrite 제안 생성을 checker와 분리한다. v1은 YAML hints를 사용하고, v2는 RAG로 유사 사례를 검색해 제안을 생성한다.

```python
# rewrite_strategy.py
class RewriteStrategy(Protocol):
    def suggest(
        self,
        finding: ComplianceFinding,
        original_text: str,
        domain: str,
    ) -> str | None: ...


class StaticHintRewriter:
    """v1 구현체: YAML safe_rewrite_hints 중 첫 번째 반환"""

    def __init__(self, rules_by_id: dict[str, ComplianceRule]):
        self.rules = rules_by_id

    def suggest(self, finding, original_text, domain) -> str | None:
        if finding.rule_id is None:
            return None
        rule = self.rules.get(finding.rule_id)
        if rule and rule.examples:
            return rule.examples[0].safe
        return None
```

### 8.3 `ComplianceService` (gate 노드의 유일한 진입점)

```python
# service.py
class ComplianceService:
    def __init__(
        self,
        checker: ComplianceChecker,
        rewriter: RewriteStrategy,
        classifier: IndustryClassifier,
    ):
        self.checker = checker
        self.rewriter = rewriter
        self.classifier = classifier

    def check_copy(
        self,
        copy: MarketingCopy,
        business_type: str,
        input_risk: dict | None = None,
    ) -> CopyComplianceState:
        domains = self.classifier.get_domains(business_type)
        findings = self.checker.scan(copy, domains)
        status = self.checker.aggregate_severity(findings)

        suggested_copy = None
        if status != "pass":
            suggested_copy = self._build_suggested_copy(copy, findings, domains)

        return CopyComplianceState(
            status=status,
            findings=findings,
            original_copy=copy,
            suggested_copy=suggested_copy,
            user_decision=None,
            user_acknowledged_risk=False,
            publication_ready=(status == "pass"),
            interrupt_payload=None,
            evidence_submitted=[],
            revision_count=0,
        )
```

`copy_compliance_gate` 노드는 이 메서드만 호출한다. checker나 rewriter 교체 시 노드 코드는 변경하지 않는다.

### 8.4 Industry Classifier

```python
# industry_classifier.py
BUSINESS_TYPE_TO_DOMAIN: dict[str, list[str]] = {
    "cafe":               ["food", "general_ad"],
    "restaurant":         ["food", "general_ad"],
    "fitness":            ["general_ad"],
    "skincare":           ["cosmetic", "general_ad"],
    "hospital":           ["medical", "general_ad"],
    "dental":             ["medical", "general_ad"],
    "beauty_salon":       ["cosmetic", "general_ad"],
    "health_supplement":  ["health_functional_food", "food", "general_ad"],
}

FALLBACK_DOMAINS = ["general_ad"]

class IndustryClassifier:
    def get_domains(self, business_type: str) -> list[str]:
        return BUSINESS_TYPE_TO_DOMAIN.get(business_type, FALLBACK_DOMAINS)
```

---

## 9. RAG 확장 설계 기준

> 이 섹션은 v2 이후 구현 기준이다. v1에서는 읽기만 한다.

### 9.1 RAG의 역할 구분

RAG를 추가할 때 **두 가지 use case를 반드시 분리**해서 설계한다. 혼동하면 gate 노드 내부를 통째로 재설계하게 된다.

**Use case A — Semantic Detection**  
패턴 매칭이 못 잡는 암시 표현을 semantic similarity로 탐지한다.

```
copy: "체내 노폐물을 걸러주는 그린 스무디"
pattern: "디톡스" → 매칭 안 됨
RAG: rule embedding과 semantic similarity → 탐지
```

위치: `copy_compliance_gate` 내부, checker 단계에서 작동.  
담당 컴포넌트: `HybridMatcher` (PatternMatcher + SemanticMatcher 결합)

**Use case B — Legal Enrichment**  
이미 탐지된 finding에 관련 행정지도, 유권해석, 시정명령 사례 등 풍부한 context를 추가한다.

```
pattern: "디톡스" → 탐지됨
RAG: 관련 시정명령 사례 검색 → rag_context 채움
→ HITL interrupt payload에 포함 → 사용자에게 더 풍부한 설명 제공
```

위치: `copy_compliance_interrupt` payload 생성 시점.  
담당 컴포넌트: `LegalEnrichmentService` (별도 서비스)

### 9.2 Use case A 확장: `HybridMatcher`

`ComplianceChecker` Protocol을 구현하므로 `ComplianceService`는 변경하지 않는다.

```python
class SemanticMatcher:
    """YAML embedding_text와 examples[index_for_rag=True]를 임베딩한 vector store를 검색"""

    def __init__(self, vector_store: VectorStore, rules_by_chunk: dict[str, ComplianceRule]):
        self.vs = vector_store
        self.rules = rules_by_chunk

    def scan(self, copy, domains) -> list[ComplianceFinding]:
        results = []
        for field, text in _copy_fields(copy).items():
            hits = self.vs.query(text, filter={"domains": domains}, top_k=5)
            for hit in hits:
                if hit.score < SEMANTIC_THRESHOLD:
                    continue
                rule = self.rules.get(hit.chunk_id)
                results.append(ComplianceFinding(
                    ...
                    rule_id=rule.rule_id if rule else None,
                    detection_method="semantic",
                    confidence=hit.score,
                    rag_chunk_id=hit.chunk_id,
                    rag_retrieval_score=hit.score,
                    rag_context=None,     # Use case B가 채움
                ))
        return results


class HybridMatcher:
    """PatternMatcher와 SemanticMatcher 결합, 중복 dedup"""

    def __init__(self, pattern: PatternMatcher, semantic: SemanticMatcher):
        self.pattern = pattern
        self.semantic = semantic

    def scan(self, copy, domains) -> list[ComplianceFinding]:
        pattern_findings = self.pattern.scan(copy, domains)
        # block이 있으면 semantic 검색 생략 (latency 절약)
        if any(f.severity == "block" for f in pattern_findings):
            return pattern_findings
        semantic_findings = self.semantic.scan(copy, domains)
        return _dedup(pattern_findings + semantic_findings)
```

### 9.3 Use case B 확장: `LegalEnrichmentService`

interrupt payload 생성 시점에만 호출된다. gate 노드와 무관하다.

```python
class LegalEnrichmentService:
    def __init__(self, law_store: VectorStore):
        self.law_store = law_store

    def enrich(self, finding: ComplianceFinding) -> RagContext | None:
        if not finding.legal_basis:
            return None
        query = f"{finding.matched_text} {finding.reason}"
        hits = self.law_store.query(query, top_k=3)
        return RagContext(
            retrieved_examples=[h.metadata for h in hits if h.score > ENRICH_THRESHOLD],
            regulatory_guidance=_extract_guidance(hits),
            enforcement_cases=[],
            source_chunks=[h.chunk_id for h in hits],
        )
```

`copy_compliance_interrupt` 노드에서:

```python
for finding in findings:
    if enrichment_service:
        finding["rag_context"] = enrichment_service.enrich(finding)
```

### 9.4 Vector Store 인덱싱 대상

rule YAML에서 `index_for_rag: true`로 표시된 항목과 `embedding_text`를 인덱싱한다.

```python
# indexer 의사코드 (v2 구현 시 작성)
for rule in rules:
    # rule embedding_text 인덱싱
    store.upsert(
        id=f"rule:{rule.rule_id}",
        text=rule.embedding_text,
        metadata={"rule_id": rule.rule_id, "domains": [rule.domain], "severity": rule.severity}
    )
    # examples 인덱싱
    for ex in rule.examples:
        if ex.get("index_for_rag"):
            store.upsert(
                id=f"example:{rule.rule_id}:{hash(ex.unsafe)}",
                text=ex.unsafe,
                metadata={"rule_id": rule.rule_id, "type": "unsafe_example"}
            )
```

`legal_basis`의 `chunk_id`는 법령 문서를 별도로 chunking한 뒤 여기서 채운다.

### 9.5 RAG 추가 시 변경이 필요 없는 것

RAG를 올바르게 붙이면 아래 항목은 코드 변경 없이 그대로 사용한다.

| 항목 | 이유 |
|------|------|
| `copy_compliance_gate` 노드 | `ComplianceService.check_copy()`만 호출, 내부 구현 모름 |
| `MarketingState` 필드 | `rag_chunk_id`, `rag_context` 이미 포함됨 |
| HITL interrupt payload | `rag_context` 슬롯 이미 포함됨 |
| FE API contract | `detectionMethod`, `confidence`, `ragContext` 이미 포함됨 |
| `CopyComplianceState` | 변경 없음 |
| severity 4단계 분류 | 변경 없음 |
| HITL resolution 로직 | 변경 없음 |

변경이 필요한 것:

| 항목 | 변경 내용 |
|------|-----------|
| `ComplianceService` 생성자 | `HybridMatcher` 주입 |
| `copy_compliance_interrupt` 노드 | `LegalEnrichmentService.enrich()` 호출 추가 |
| `legal_basis` YAML | `chunk_id` 채우기 |
| 인프라 | vector store 추가 (Pinecone, Weaviate 등) |

---

## 10. Evidence Flow 설계

### 10.1 범위 명확화

v1에서 EasyAds는 사용자가 제출한 근거자료의 **법적 진위를 검증하지 않는다.**

```
evidence_submitted ≠ evidence_verified ≠ compliance_passed
```

이 사실을 시스템과 UX 양쪽에서 명확히 한다.

### 10.2 Evidence 상태

| 상태 | 설명 | publication_ready |
|------|------|-------------------|
| 없음 | 근거 미제출 | - |
| `user_claim` | 사용자가 텍스트로 근거 주장 | False |
| `document_uploaded` | 사용자가 파일/URL 제출 | False |

v1에서 모든 evidence 상태는 `manual_review_required`로 처리된다.

### 10.3 Evidence 입력 데이터

```python
class EvidenceSubmission(TypedDict):
    finding_id: str
    claim_type: Literal["text_claim", "file_upload", "url_reference"]
    content: str       # 텍스트 또는 파일명/URL
    submitted_at: str  # ISO 8601
```

---

## 11. API 응답 Contract

FE가 소비하는 `copyCompliance` payload. `GenerationJob` result에 포함된다.  
v1에서 RAG 전용 필드(`detectionMethod` 외)는 기본값으로 채운다.

```json
{
    "copyCompliance": {
        "status": "manual_review_required",
        "publicationReady": false,
        "summary": "광고 규제 위험 표현이 발견되었습니다. 게시 전 확인이 필요합니다.",
        "findings": [
            {
                "findingId": "finding_001",
                "field": "headline",
                "matchedText": "4주 만에 10kg 감량",
                "severity": "evidence_required",
                "detectionMethod": "pattern",
                "confidence": 1.0,
                "message": "특정 기간 내 감량 결과를 단정하는 표현은 객관적인 근거가 필요할 수 있습니다.",
                "legalBasis": [
                    {
                        "key": "KR-FAIR-AD-3",
                        "lawName": "표시·광고의 공정화에 관한 법률",
                        "article": "제3조",
                        "summary": "소비자를 오인시킬 우려가 있는 거짓·과장 광고 금지",
                        "chunkId": null
                    }
                ],
                "suggestedText": "4주 동안 체계적으로 준비하는 바디프로필 클래스",
                "ragContext": null
            }
        ],
        "rewrites": [],
        "userDecision": "keep_original_draft",
        "userAcknowledgedRisk": true
    }
}
```

`pass` 케이스:

```json
{
    "copyCompliance": {
        "status": "pass",
        "publicationReady": true,
        "summary": "광고 규제 검토를 통과했습니다.",
        "findings": []
    }
}
```

FE 주의사항:
- `publicationReady: false`인 광고는 정상 `pass`처럼 표시하면 안 된다.
- `"이 문구는 불법입니다."` 대신 `"법 위반 위험이 있습니다."` `"사용 가능 여부를 확인해야 합니다."` 형태로 표시한다.
- `ragContext`가 채워진 경우 "관련 사례 보기" 버튼을 추가로 표시한다 (v2).

---

## 12. FE 구현 요구사항

### 12.1 카피 후보 카드 — Compliance Badge

```
pass              → 표시 없음
warn              → 주의 (노란색 배지)
evidence_required → 근거 필요 (주황색 배지)
block             → 사용 불가 (카드 비활성화, 회색)
```

### 12.2 i 버튼 Tooltip / Bottom Sheet

```
표현
"4주 만에 10kg 감량"

위험 사유
특정 기간 내 감량 결과를 단정하는 표현은 객관적인
근거가 필요할 수 있습니다.

관련 기준
표시·광고의 공정화에 관한 법률 제3조

현재 상태
객관적 근거가 확인되지 않음

가능한 조치
· 안전한 문구로 수정
· 근거자료 제출
· 직접 수정
```

### 12.3 Non-blocking Warn 처리

`warn` 케이스는 생성을 막지 않는다. 최종 결과 화면 진입 시 1회 acknowledgment.

```
주의: 일부 표현은 문맥에 따라 광고 규제 위험이 있을 수 있습니다.
게시 전 내용을 확인하세요.

[확인했어요]  [자세히 보기]
```

### 12.4 Before / After 비교 UI

```
수정 전
4주 만에 10kg 감량 보장

수정 후
4주 동안 체계적으로 준비하는 바디프로필 클래스

수정 사유: 특정 기간 내 감량 결과를 단정하는 표현
```

### 12.5 Manual Review Required 상태 표시

```
광고 문구 검토 필요

이 광고는 규제 위험 확인이 필요한 표현을 포함합니다.
게시·집행 전 관련 법령과 제품 근거자료를 확인하세요.

[법적 근거 보기]  [문구 다시 수정]
```

---

## 13. Prompt Injection 설계 (Layer 2)

`build_copy_generation_metadata()` 또는 prompt builder에 업종별 compliance summary를 soft constraint로 주입한다. 이 주입은 1차 예방이다. LLM이 어겨도 Layer 3 rule engine이 반드시 잡는다.

```json
{
    "constraints": {
        "compliance": {
            "jurisdiction": "KR",
            "domains": ["food"],
            "blocked_claims": [
                "질병 예방·치료 효능",
                "의학적 효능 암시",
                "신체 특정 부위 개선 보장"
            ],
            "blocked_terms": ["디톡스", "붓기 제거", "체지방 감소", "다이어트 효과"],
            "safe_direction": ["맛", "향", "분위기", "재료", "감성", "계절감", "경험"]
        }
    }
}
```

---

## 14. 구현 우선순위

### P0 — Rule-based Gate (핵심)

```
- rules_kr_v1.yaml, legal_basis_kr_v1.yaml (embedding_text, chunk_id, last_verified_at 포함)
- ComplianceRule, ComplianceFinding, RagContext, LegalBasisRef 스키마 (v2 필드 포함)
- ComplianceChecker Protocol + PatternMatcher
- RewriteStrategy Protocol + StaticHintRewriter
- ComplianceService
- IndustryClassifier
- copy_compliance_gate 노드
- compliance_severity_router
- copy_compliance_interrupt / copy_compliance_resolution
- candidate_compliance_scan
- MarketingState 필드 추가
- API 응답 copyCompliance payload (v2 필드 null로 포함)
```

### P1 — Prompt Injection

```
- build_copy_generation_metadata에 compliance summary 주입
- copy_candidate_generation, auto_pilot_copywriting, custom_copy_validation 프롬프트 업데이트
- input_compliance_precheck 노드
```

### P2 — Frontend

```
- candidate card compliance badge
- i 버튼 tooltip / bottom sheet
- blocking interrupt UI (actions 선택)
- warn acknowledgment
- before/after 비교 UI
- manual_review_required 상태 표시
- final result compliance summary
```

### P3 — Evidence Flow

```
- submit_claim 처리 (텍스트 입력)
- evidence_submitted state 저장
- manual_review_required 처리 흐름
```

### P4 — RAG (Use case A: Semantic Detection)

```
- SemanticMatcher 구현
- HybridMatcher 구현
- YAML embedding_text, index_for_rag 기반 인덱서
- legal_basis chunk_id 채우기
- vector store 인프라
- ComplianceService에 HybridMatcher 교체 주입
```

### P5 — RAG (Use case B: Legal Enrichment)

```
- 법령/가이드라인/행정지도 문서 수집 및 chunking
- LegalEnrichmentService 구현
- copy_compliance_interrupt 노드에 enrichment 연결
- FE ragContext UI (관련 사례 보기)
```

### P6 이후

```
P6: rule version 관리 (관리자 화면, last_verified_at 기반 staleness 알림)
P7: evidence 문서 업로드 + manual review 워크플로우
P8: RAG 검색 결과 → rule pack update 후보 제안
```

---

## 15. v1에서 의도적으로 제외하는 것

| 항목 | 이유 |
|------|------|
| LLM 기반 context classifier | rule engine 도입 목적(LLM 불안정성 제거)과 모순 |
| Evidence 진위 검증 | 구현 불가, false assurance 위험 |
| 복수 rewrite 제안 (보수/의도보존/근거필요) | UX 복잡도 과다 |
| publication_ready 집행 로직 | EasyAds가 배포를 직접 제어하지 않으면 의미 없음 |
| RAG 검색 | P4 이후. v1은 YAML rule pack으로 충분 |
| SemanticMatcher, HybridMatcher 구현 | P4 이후 |
| LegalEnrichmentService 구현 | P5 이후 |

---

## 16. 업종별 v1 Rule 커버리지

| 업종 | 도메인 | P0 커버 핵심 표현 |
|------|--------|-------------------|
| 카페/음료/식품 | `food` | 디톡스, 독소 배출, 붓기 제거, 체지방 감소, 다이어트 효과, 면역력 강화, 피로 회복, 피부 개선 |
| 피부관리/뷰티/화장품 | `cosmetic` | 여드름 치료, 완치, 피부질환 개선, 100% 개선, Before & After, 피부 재생, 탈모 방지 |
| 병원/의원/시술 | `medical` | 치료 보장, 완치, 확실히 사라지는, 치료 경험담, 전후사진, 100% 개선 |
| 헬스/다이어트/바디프로필 | `general_ad` | 4주 만에 10kg 감량, 무조건 감량, 복근 완성, 100% 성공, 단기간 보장, 확실한 변화 |
| 전 업종 공통 | `general_ad` | 최고, 1위, 최초, 국내 유일, 100% 보장, 무조건, 반드시, 의사 추천, 전문가 보장 |

헬스/다이어트는 의료법이 아닌 표시광고법(거짓·과장·실증 불가) 도메인으로 처리한다.

`최고`, `1위`, `최초`는 실증 자료가 존재할 수 있으므로 `block`이 아닌 `evidence_required`로 처리한다. v1에서 근거자료 업로드 기능이 없으므로 사용자가 claim을 제출하면 `manual_review_required`로 진행한다.
