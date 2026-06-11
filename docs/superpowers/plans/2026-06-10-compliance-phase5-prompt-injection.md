# Compliance Phase 5: LLM Prompt 업종별 Compliance 제약 주입

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `build_copy_generation_metadata()`에 업종별 compliance 제약(`blocked_terms`, `blocked_claims`, `safe_direction`)을 soft constraint로 주입해, LLM이 카피 생성 단계에서 위험 표현을 먼저 피하도록 한다.

**Architecture:** Phase 3의 copy_compliance_gate가 2차 방어라면, 이것은 1차 예방이다. LLM이 어겨도 gate가 반드시 잡으므로 injection 실패는 허용 가능하다. `ComplianceService.get_rules_for_domains()` 퍼블릭 메서드를 추가해 내부 구현(`_checker.rules`)에 직접 접근하는 것을 피한다. metadata builder에서 compliance import는 지연 import로 처리해 순환 의존을 방지한다.

**Tech Stack:** ComplianceService, IndustryClassifier, metadata_builders.py, pytest

---

## 파일 구조

| 파일 | 변경 종류 | 내용 |
|------|----------|------|
| `orchestrator/app/compliance/service.py` | Modify | `get_rules_for_domains(domains)` 퍼블릭 메서드 추가 |
| `orchestrator/app/llm/metadata_builders.py` | Modify | `_build_compliance_constraints()` 헬퍼 추가 + `build_copy_generation_metadata()`에 주입 |
| `orchestrator/tests/test_compliance_prompt_injection.py` | Create | 6개 테스트 |

---

### Task 1: `ComplianceService.get_rules_for_domains()` 추가

**Files:**
- Modify: `orchestrator/app/compliance/service.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# orchestrator/tests/test_compliance_prompt_injection.py (신규 파일)
from orchestrator.app.compliance.service import ComplianceService
from orchestrator.app.compliance.rule_engine import PatternMatcher
from orchestrator.app.compliance.rule_loader import load_rules
from orchestrator.app.compliance.rewrite_strategy import StaticHintRewriter
from orchestrator.app.compliance.industry_classifier import IndustryClassifier


def _svc() -> ComplianceService:
    rules = load_rules()
    return ComplianceService(
        checker=PatternMatcher(rules),
        rewriter=StaticHintRewriter({r.rule_id: r for r in rules}),
        classifier=IndustryClassifier(),
    )


def test_get_rules_for_domains_returns_food_rules():
    svc = _svc()
    food_rules = svc.get_rules_for_domains(["food"])
    assert len(food_rules) > 0
    assert all(r.domain == "food" for r in food_rules)


def test_get_rules_for_domains_returns_cosmetic_rules():
    svc = _svc()
    rules = svc.get_rules_for_domains(["cosmetic"])
    assert len(rules) > 0
    assert all(r.domain == "cosmetic" for r in rules)


def test_get_rules_for_domains_empty_returns_empty():
    svc = _svc()
    rules = svc.get_rules_for_domains([])
    assert rules == []
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd /home/spai0710/pjt-sprint_ai07_easyadsAGENT
PYTHONPATH=. .venv/bin/pytest orchestrator/tests/test_compliance_prompt_injection.py::test_get_rules_for_domains_returns_food_rules -v --tb=short
```

Expected: `AttributeError: 'ComplianceService' object has no attribute 'get_rules_for_domains'`

- [ ] **Step 3: `service.py`에 메서드 추가**

[orchestrator/app/compliance/service.py](orchestrator/app/compliance/service.py)에서 `check_copy()` 메서드 뒤에 추가:

```python
def get_rules_for_domains(self, domains: list[str]) -> list:
    """도메인에 적용 가능한 규칙 목록을 반환한다. ComplianceRule 리스트."""
    checker_rules = getattr(self._checker, "rules", [])
    return [r for r in checker_rules if r.domain in domains]
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
PYTHONPATH=. .venv/bin/pytest orchestrator/tests/test_compliance_prompt_injection.py::test_get_rules_for_domains_returns_food_rules orchestrator/tests/test_compliance_prompt_injection.py::test_get_rules_for_domains_returns_cosmetic_rules orchestrator/tests/test_compliance_prompt_injection.py::test_get_rules_for_domains_empty_returns_empty -v --tb=short
```

Expected: 3 PASSED

---

### Task 2: `metadata_builders.py` — compliance 주입

**Files:**
- Modify: `orchestrator/app/llm/metadata_builders.py`

- [ ] **Step 1: 실패 테스트 추가**

`test_compliance_prompt_injection.py`에 추가:

```python
from orchestrator.app.llm.metadata_builders import build_copy_generation_metadata


def test_build_copy_generation_metadata_has_compliance_for_food():
    state = {
        "context": {
            "business_type": "cafe",
            "item_or_service": "딸기라떼",
            "promotion_goal": "new_launch",
        }
    }
    metadata = build_copy_generation_metadata(state)
    constraints = metadata["constraints"]
    assert "compliance" in constraints


def test_compliance_blocked_terms_for_food_business():
    state = {"context": {"business_type": "cafe"}}
    metadata = build_copy_generation_metadata(state)
    compliance = metadata["constraints"]["compliance"]
    blocked = compliance["blocked_terms"]
    # 식품 규칙에서 blocked 패턴이 포함돼야 함
    assert any(term in blocked for term in ["독소 배출", "붓기 제거", "체지방 감소"])


def test_compliance_domains_for_beauty_skincare():
    state = {"context": {"business_type": "beauty_skincare"}}
    metadata = build_copy_generation_metadata(state)
    compliance = metadata["constraints"]["compliance"]
    assert "cosmetic" in compliance["domains"]
    assert len(compliance["blocked_terms"]) > 0


def test_no_compliance_without_business_type():
    state = {"context": {}}
    metadata = build_copy_generation_metadata(state)
    # business_type 없으면 compliance 키가 없거나 비어있어야 함
    compliance = metadata["constraints"].get("compliance")
    assert compliance is None or compliance == {}
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
PYTHONPATH=. .venv/bin/pytest orchestrator/tests/test_compliance_prompt_injection.py::test_build_copy_generation_metadata_has_compliance_for_food -v --tb=short
```

Expected: `AssertionError: 'compliance' not in constraints`

- [ ] **Step 3: `metadata_builders.py`에 헬퍼와 주입 추가**

파일 맨 아래(`_reserved_text_areas_from_state` 이후)에 헬퍼를 추가한다:

```python
def _build_compliance_constraints(business_type: str | None) -> dict[str, Any]:
    """업종별 compliance 제약을 생성한다. 실패 시 빈 dict를 반환해 생성 흐름에 영향 없음."""
    if not business_type:
        return {}
    try:
        from orchestrator.app.compliance.service import get_compliance_service
        from orchestrator.app.compliance.industry_classifier import IndustryClassifier

        svc = get_compliance_service()
        classifier = IndustryClassifier()
        domains = classifier.get_domains(business_type)
        rules = svc.get_rules_for_domains(domains)

        blocked_terms = [p for r in rules if r.severity == "block" for p in r.patterns][:10]
        evidence_terms = [p for r in rules if r.severity == "evidence_required" for p in r.patterns][:5]
        blocked_claims = [r.title for r in rules if r.severity == "block"][:5]
        safe_hints = list({h for r in rules for h in r.safe_rewrite_hints})[:3]

        return {
            "compliance": {
                "jurisdiction": "KR",
                "domains": domains,
                "blocked_terms": blocked_terms,
                "evidence_required_terms": evidence_terms,
                "blocked_claims": blocked_claims,
                "safe_direction": safe_hints,
            }
        }
    except Exception:
        return {}
```

그리고 `build_copy_generation_metadata` 함수를 다음처럼 수정한다:

```python
def build_copy_generation_metadata(
    state: dict[str, Any] | None,
    node_name: str = "copy_generation",
    output_schema: Any = "CopyCandidateListOutput",
) -> dict[str, Any]:
    source = state or {}
    tone = _dict(source.get("tone_binding_output"))
    plan_policy = _dict(source.get("plan_policy"))
    context = _dict(source.get("context"))
    business_type = context.get("business_type")
    compliance_constraints = _build_compliance_constraints(business_type)   # ← 추가
    return build_metadata_payload(
        source,
        node_name=node_name,
        objective="Generate or validate structured Korean advertising copy without inventing unprovided facts.",
        output_schema=output_schema,
        available_state={
            "context": source.get("context", {}),
            "ad_format_spec": source.get("ad_format_spec"),
            "layout_spec": source.get("layout_spec"),
            "tone_binding_output": tone,
            "plan_policy": {"max_candidates": plan_policy.get("max_candidates")},
            "copy_generation_mode": source.get("copy_generation_mode"),
            "current_brief": source.get("current_brief", {}),
            "messages": source.get("messages", []),
            "reference_style_profile": source.get("reference_style_profile"),
            "selected_reference_template": source.get("selected_reference_template"),
            "custom_copy_input": source.get("custom_copy_input"),
        },
        constraints={
            "forbidden_claims": tone.get("forbidden_claims", []),
            "channel_copy_rules": tone.get("channel_copy_rules", []),
            "copy_constraints": tone.get("copy_constraints", []),
            "preserve_custom_input": source.get("copy_generation_mode") == "custom_input",
            **compliance_constraints,   # ← 추가: {"compliance": {...}} 또는 {}
        },
    )
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
PYTHONPATH=. .venv/bin/pytest orchestrator/tests/test_compliance_prompt_injection.py -v --tb=short
```

Expected: 7 PASSED

- [ ] **Step 5: 기존 metadata 테스트 회귀 확인**

```bash
PYTHONPATH=. .venv/bin/pytest orchestrator/tests/ -k "metadata or copy_tone" -v --tb=short 2>&1 | tail -10
```

Expected: 모두 PASSED (compliance 주입은 constraints dict에 키를 추가할 뿐, 기존 키를 변경하지 않음)

- [ ] **Step 6: 전체 회귀 테스트**

```bash
PYTHONPATH=. .venv/bin/pytest orchestrator/tests/ -v --tb=short 2>&1 | tail -5
```

Expected: 전체 통과

- [ ] **Step 7: 커밋**

```bash
git add orchestrator/app/compliance/service.py \
        orchestrator/app/llm/metadata_builders.py \
        orchestrator/tests/test_compliance_prompt_injection.py
git commit -m "feat(compliance): Phase 5 — 카피 생성 prompt에 업종별 compliance 제약 주입

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## 완료 기준 체크리스트

- [ ] `ComplianceService.get_rules_for_domains(["food"])` 가 `domain == "food"` 규칙만 반환
- [ ] `build_copy_generation_metadata({"context": {"business_type": "cafe"}})` 결과의 `constraints.compliance`에 `blocked_terms` 포함
- [ ] `beauty_skincare` 업종에서 `compliance.domains`에 `"cosmetic"` 포함
- [ ] `business_type` 없을 때 `compliance` 키가 없거나 빈 dict (graceful degradation)
- [ ] `_build_compliance_constraints` 내부에서 예외 발생 시 빈 dict 반환 (생성 흐름 보호)
- [ ] 기존 `build_copy_generation_metadata` 호출 테스트 전부 통과 (기존 constraints 키 변경 없음)
- [ ] 전체 회귀 테스트 통과

---

## 설계 주의사항

**지연 import 이유:** `metadata_builders.py`는 여러 노드에서 import한다. `get_compliance_service()`를 모듈 레벨에서 import하면 앱 시작 시 YAML 파일이 즉시 로딩된다. 지연 import(`_build_compliance_constraints` 내부에서 import)로 처리해 import 순서 문제와 테스트 격리를 보장한다.

**blocked_terms[:10] 상한 이유:** LLM 프롬프트의 constraints JSON이 너무 길면 토큰 낭비가 발생한다. Phase 1 rule pack 기준 최대 8개 패턴이지만, 규칙이 늘어날 경우를 대비해 상한을 둔다.

**`**compliance_constraints` 패턴:** `compliance_constraints`가 `{}` 이면 spread해도 기존 constraints에 영향이 없다. `{"compliance": {...}}` 이면 `compliance` 키만 추가된다. 기존 `forbidden_claims`, `channel_copy_rules`, `copy_constraints` 키는 절대 덮어쓰지 않는다.
