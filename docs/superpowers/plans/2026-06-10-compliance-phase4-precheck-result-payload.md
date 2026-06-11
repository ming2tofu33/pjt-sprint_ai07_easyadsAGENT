# Compliance Phase 4: input_compliance_precheck 노드 + Result Payload API

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 사용자 입력에서 위험 intent를 사전 감지하는 `input_compliance_precheck_node`를 validator → format_planner 사이에 삽입하고, 최종 result payload에 `copyCompliance` 필드를 추가해 FE가 소비할 수 있게 한다.

**Architecture:** `input_compliance_precheck_node`는 non-blocking 패스스루 노드다. 흐름을 절대 멈추지 않고 `input_compliance_risk` state 필드에 힌트만 남긴다. result_node는 `copy_compliance_gate` state 결과를 읽어 `copyCompliance` payload를 직렬화한다.

**Tech Stack:** LangGraph StateGraph, Pydantic v2, pytest, 기존 ComplianceService

---

## 파일 구조

| 파일 | 변경 종류 | 내용 |
|------|----------|------|
| `orchestrator/app/llm/nodes/copy_compliance.py` | Modify | `input_compliance_precheck_node` + `_build_safe_direction_hint` 추가 |
| `orchestrator/app/graph/state.py` | Modify | `input_compliance_risk` 타입 수정: `str → dict[str, Any]` |
| `orchestrator/app/graph/builder.py` | Modify | 노드 등록, validator → precheck → format_planner 엣지 변경 |
| `orchestrator/app/llm/nodes/result.py` | Modify | `copyCompliance` 필드 + `_build_copy_compliance_payload` 헬퍼 추가 |
| `orchestrator/tests/test_compliance_precheck_result_payload.py` | Create | precheck 노드 + result payload 테스트 |
| `orchestrator/tests/test_marketing_graph_node_utilization.py` | Modify | `input_compliance_precheck` 를 TRACEABLE_NODE_ATTRS + matrix 모든 시나리오에 추가 |

---

### Task 1: `input_compliance_precheck_node` 구현

**Files:**
- Modify: `orchestrator/app/llm/nodes/copy_compliance.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# orchestrator/tests/test_compliance_precheck_result_payload.py (신규 파일, 이 단계에서 일부만)
from orchestrator.app.llm.nodes.copy_compliance import input_compliance_precheck_node
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def _state(user_input="ready", business_type="cafe"):
    s = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input=user_input,
            copy_generation_mode="auto_pilot",
            context=MarketingContext(
                business_type=business_type,
                item_or_service="딸기라떼",
                promotion_goal="new_launch",
                extra={"ad_format": "instagram_feed"},
            ),
        )
    )
    return s


def test_precheck_passes_clean_input():
    state = _state(user_input="딸기라떼 신메뉴 광고")
    update = input_compliance_precheck_node(state)
    assert update["input_compliance_risk"] is None
    assert update["status"] == "input_compliance_prechecked"


def test_precheck_detects_blocked_term():
    state = _state(user_input="독소 배출 효과 있는 음료", business_type="cafe")
    update = input_compliance_precheck_node(state)
    risk = update["input_compliance_risk"]
    assert risk is not None
    assert risk["detected"] is True
    assert "독소 배출" in risk["flagged_terms"]


def test_precheck_sets_safe_direction_for_food():
    state = _state(user_input="독소 배출 딸기라떼")
    update = input_compliance_precheck_node(state)
    assert "중심으로" in update["input_compliance_risk"]["safe_direction"]


def test_precheck_does_not_block_flow_on_risk():
    state = _state(user_input="독소 배출 딸기라떼")
    update = input_compliance_precheck_node(state)
    # status가 설정돼도 흐름은 계속됨 (interrupt 없음)
    assert "input_compliance_risk" in update
    assert update["status"] == "input_compliance_prechecked"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd /home/spai0710/pjt-sprint_ai07_easyadsAGENT
PYTHONPATH=. .venv/bin/pytest orchestrator/tests/test_compliance_precheck_result_payload.py -v --tb=short 2>&1 | head -30
```

Expected: `ImportError: cannot import name 'input_compliance_precheck_node'`

- [ ] **Step 3: `copy_compliance.py`에 노드와 헬퍼 추가**

[orchestrator/app/llm/nodes/copy_compliance.py](orchestrator/app/llm/nodes/copy_compliance.py) 파일 끝의 `_serialize_findings` 아래에 다음을 추가한다:

```python
def input_compliance_precheck_node(state: MarketingState) -> dict[str, Any]:
    """사용자 입력에서 위험 intent를 사전 감지한다.
    흐름을 절대 멈추지 않는다. 힌트만 state에 저장한다."""
    user_input = state.get("user_input") or ""
    business_type = context_to_model(state.get("context")).business_type
    svc = get_compliance_service()
    result = svc.check_copy({"headline": user_input}, business_type)

    if result.status == "pass":
        return {"input_compliance_risk": None, "status": "input_compliance_prechecked"}

    risk = {
        "detected": True,
        "status": result.status,
        "domains": list({_domain_from_rule_id(f.rule_id) for f in result.findings if f.rule_id}),
        "flagged_terms": [f.matched_text for f in result.findings],
        "safe_direction": _build_safe_direction_hint(result.findings),
    }
    return {"input_compliance_risk": risk, "status": "input_compliance_prechecked"}


def _build_safe_direction_hint(findings: list) -> str:
    """findings: ComplianceFinding Pydantic 객체 또는 dict 모두 지원."""
    domains = set()
    for f in findings:
        rule_id = f.rule_id if hasattr(f, "rule_id") else (f.get("rule_id") if isinstance(f, dict) else "")
        if rule_id:
            domains.add(_domain_from_rule_id(rule_id))
    if "food" in domains:
        return "맛·향·분위기·재료·경험 중심으로 생성합니다."
    if "medical" in domains or "cosmetic" in domains:
        return "상담·경험·케어 과정 중심으로 생성합니다."
    return "표현을 완화해 생성합니다."


def _domain_from_rule_id(rule_id: str) -> str:
    parts = rule_id.split("-")
    return parts[1].lower() if len(parts) >= 2 else "general"
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
PYTHONPATH=. .venv/bin/pytest orchestrator/tests/test_compliance_precheck_result_payload.py::test_precheck_passes_clean_input orchestrator/tests/test_compliance_precheck_result_payload.py::test_precheck_detects_blocked_term orchestrator/tests/test_compliance_precheck_result_payload.py::test_precheck_sets_safe_direction_for_food orchestrator/tests/test_compliance_precheck_result_payload.py::test_precheck_does_not_block_flow_on_risk -v --tb=short
```

Expected: 4 PASSED

---

### Task 2: `state.py` 타입 수정

**Files:**
- Modify: `orchestrator/app/graph/state.py`

- [ ] **Step 1: `input_compliance_risk` 타입 수정**

[orchestrator/app/graph/state.py](orchestrator/app/graph/state.py)에서:

```python
# 변경 전
input_compliance_risk: str | None

# 변경 후
input_compliance_risk: dict[str, Any] | None
```

`create_initial_marketing_state`의 초기값은 이미 `"input_compliance_risk": None`이므로 변경 불필요.

- [ ] **Step 2: 기존 테스트 통과 확인 (타입만 변경이므로 no-op)**

```bash
PYTHONPATH=. .venv/bin/pytest orchestrator/tests/test_compliance_gate_branch.py orchestrator/tests/test_compliance_candidate_badge.py -v --tb=short 2>&1 | tail -5
```

Expected: 모두 PASSED

---

### Task 3: `builder.py` — precheck 노드 등록 및 엣지 변경

**Files:**
- Modify: `orchestrator/app/graph/builder.py`

- [ ] **Step 1: import 추가**

[orchestrator/app/graph/builder.py](orchestrator/app/graph/builder.py) 파일의 copy_compliance import에 `input_compliance_precheck_node`를 추가한다:

```python
# 변경 전
from orchestrator.app.llm.nodes.copy_compliance import (
    copy_compliance_gate_node,
    copy_compliance_interrupt_node,
    copy_compliance_resolution_node,
)

# 변경 후
from orchestrator.app.llm.nodes.copy_compliance import (
    copy_compliance_gate_node,
    copy_compliance_interrupt_node,
    copy_compliance_resolution_node,
    input_compliance_precheck_node,
)
```

- [ ] **Step 2: `build_marketing_graph()`에 노드 등록**

`no_copy_bypass` 노드 등록 바로 위에 추가한다:

```python
# 기존 no_copy_bypass 앞에 삽입
graph.add_node("input_compliance_precheck", input_compliance_precheck_node)
graph.add_node("no_copy_bypass", no_copy_bypass_node)
```

- [ ] **Step 3: validator → format_planner 엣지 변경**

```python
# 변경 전
graph.add_conditional_edges(
    "validator",
    route_after_validator_for_marketing,
    {"options": "options", "format_planner": "format_planner"},
)

# 변경 후 — router는 여전히 "format_planner" 키를 반환하지만 실제 노드는 precheck로
graph.add_conditional_edges(
    "validator",
    route_after_validator_for_marketing,
    {"options": "options", "format_planner": "input_compliance_precheck"},
)
graph.add_edge("input_compliance_precheck", "format_planner")
```

- [ ] **Step 4: 그래프 빌드 확인**

```bash
PYTHONPATH=. python3 -c "
from orchestrator.app.graph.builder import build_marketing_graph
g = build_marketing_graph()
nodes = sorted(g.get_graph().nodes)
print('input_compliance_precheck' in nodes)
print('format_planner' in nodes)
"
```

Expected:
```
True
True
```

---

### Task 4: `result.py` — `copyCompliance` payload 추가

**Files:**
- Modify: `orchestrator/app/llm/nodes/result.py`

- [ ] **Step 1: 실패 테스트 추가**

`test_compliance_precheck_result_payload.py`에 추가:

```python
from orchestrator.app.llm.nodes.result import result_node


def _result_state(copy_compliance_status="pass", gate=None, publication_ready=True):
    s = _state()
    s["copy_compliance_gate"] = gate or {"findings": [], "publication_ready": True}
    s["copy_compliance_status"] = copy_compliance_status
    s["copy_compliance_publication_ready"] = publication_ready
    s["t2i_result"] = {"image_paths": ["/tmp/fake_result.png"]}
    s["final_image_path"] = "/tmp/fake_result.png"
    return s


def test_result_payload_has_copy_compliance_key():
    s = _result_state()
    update = result_node(s)
    assert "copyCompliance" in update["result_payload"]["metadata"]


def test_result_payload_copy_compliance_pass():
    s = _result_state(copy_compliance_status="pass", publication_ready=True)
    update = result_node(s)
    cc = update["result_payload"]["metadata"]["copyCompliance"]
    assert cc["status"] == "pass"
    assert cc["publicationReady"] is True
    assert cc["findingCount"] == 0


def test_result_payload_copy_compliance_manual_review():
    gate = {
        "findings": [
            {
                "finding_id": "f1",
                "field": "headline",
                "matched_text": "독소 배출",
                "severity": "block",
                "detection_method": "pattern",
                "confidence": 1.0,
                "reason": "식품의 질병 예방·치료 또는 의학적 효능 암시",
                "legal_basis": [],
                "suggested_text": None,
            }
        ],
        "publication_ready": False,
        "user_decision": "keep_original_draft",
        "user_acknowledged_risk": True,
    }
    s = _result_state(
        copy_compliance_status="manual_review_required",
        gate=gate,
        publication_ready=False,
    )
    update = result_node(s)
    cc = update["result_payload"]["metadata"]["copyCompliance"]
    assert cc["publicationReady"] is False
    assert cc["userAcknowledgedRisk"] is True
    assert cc["findingCount"] == 1
    assert cc["userDecision"] == "keep_original_draft"


def test_result_payload_copy_compliance_warn():
    s = _result_state(copy_compliance_status="warn", publication_ready=True)
    update = result_node(s)
    cc = update["result_payload"]["metadata"]["copyCompliance"]
    assert cc["status"] == "warn"
    assert cc["publicationReady"] is True


def test_result_payload_copy_compliance_findings_serialized():
    gate = {
        "findings": [
            {
                "finding_id": "f1",
                "field": "headline",
                "matched_text": "1위",
                "severity": "evidence_required",
                "detection_method": "pattern",
                "confidence": 1.0,
                "reason": "실증 없는 최상급 표현",
                "legal_basis": [
                    {"key": "KR-FAIR-AD-3", "law_name": "표시·광고의 공정화에 관한 법률",
                     "article": "제3조", "summary": "부당한 표시·광고 금지"},
                ],
                "suggested_text": "고객 만족 코칭 프로그램",
            }
        ],
        "publication_ready": False,
    }
    s = _result_state(copy_compliance_status="evidence_required", gate=gate, publication_ready=False)
    update = result_node(s)
    cc = update["result_payload"]["metadata"]["copyCompliance"]
    assert len(cc["findings"]) == 1
    finding = cc["findings"][0]
    assert finding["matchedText"] == "1위"
    assert finding["legalBasis"][0]["lawName"] == "표시·광고의 공정화에 관한 법률"
    assert finding["suggestedText"] == "고객 만족 코칭 프로그램"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
PYTHONPATH=. .venv/bin/pytest orchestrator/tests/test_compliance_precheck_result_payload.py::test_result_payload_has_copy_compliance_key -v --tb=short 2>&1 | tail -10
```

Expected: `FAILED — KeyError: 'copyCompliance'`

- [ ] **Step 3: `result.py`에 `copyCompliance` 추가**

[orchestrator/app/llm/nodes/result.py](orchestrator/app/llm/nodes/result.py)에서 `metadata=` dict의 `"qualityDecision": ocr_decision,` 아래에 추가:

```python
        metadata={
            "source_node": "result",
            "render_text_in_image": False,
            "tlfp_enabled": True,
            "error": None if output_path else upstream_error,
            "ocr_gate": ocr_gate_payload,
            "requiresManualReview": requires_manual_review,
            "qualityRejected": quality_rejected,
            "qualityDecision": ocr_decision,
            "copyCompliance": _build_copy_compliance_payload(state),   # 추가
        },
```

파일 맨 아래에 헬퍼를 추가한다:

```python
def _build_copy_compliance_payload(state: MarketingState) -> dict:
    gate = state.get("copy_compliance_gate") or {}
    status = state.get("copy_compliance_status") or "pass"
    publication_ready = state.get("copy_compliance_publication_ready", True)

    findings_raw = gate.get("findings") or []
    findings = [
        {
            "findingId": f.get("finding_id"),
            "field": f.get("field"),
            "matchedText": f.get("matched_text"),
            "severity": f.get("severity"),
            "detectionMethod": f.get("detection_method", "pattern"),
            "confidence": f.get("confidence", 1.0),
            "message": f.get("reason"),
            "legalBasis": [
                {
                    "key": b.get("key"),
                    "lawName": b.get("law_name"),
                    "article": b.get("article"),
                    "summary": b.get("summary"),
                }
                for b in (f.get("legal_basis") or [])
            ],
            "suggestedText": f.get("suggested_text"),
            "ragContext": f.get("rag_context"),
        }
        for f in findings_raw
    ]

    if status == "pass":
        summary = "광고 규제 검토를 통과했습니다."
    elif status == "warn":
        summary = f"광고 규제 주의 표현 {len(findings)}개가 발견되었습니다. 게시 가능합니다."
    elif status == "manual_review_required":
        summary = "광고 규제 위험 표현이 발견되었습니다. 게시 전 확인이 필요합니다."
    else:
        summary = f"광고 규제 위험 표현 {len(findings)}개가 발견되었습니다."

    return {
        "status": status,
        "publicationReady": publication_ready,
        "summary": summary,
        "findingCount": len(findings),
        "findings": findings,
        "userDecision": gate.get("user_decision"),
        "userAcknowledgedRisk": gate.get("user_acknowledged_risk", False),
    }
```

`from orchestrator.app.graph.state import MarketingState` import는 이미 있으므로 추가 불필요.

- [ ] **Step 4: 테스트 통과 확인**

```bash
PYTHONPATH=. .venv/bin/pytest orchestrator/tests/test_compliance_precheck_result_payload.py -v --tb=short
```

Expected: 9 PASSED

- [ ] **Step 5: 커밋**

```bash
git add orchestrator/app/llm/nodes/copy_compliance.py \
        orchestrator/app/graph/state.py \
        orchestrator/app/graph/builder.py \
        orchestrator/app/llm/nodes/result.py \
        orchestrator/tests/test_compliance_precheck_result_payload.py
git commit -m "feat(compliance): Phase 4 — input_compliance_precheck 노드 + result payload copyCompliance 필드

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 5: 노드 활용도 매트릭스 업데이트

**Files:**
- Modify: `orchestrator/tests/test_marketing_graph_node_utilization.py`

- [ ] **Step 1: `TRACEABLE_NODE_ATTRS`에 항목 추가**

```python
# no_copy_bypass 항목 바로 위에 추가
"input_compliance_precheck": "input_compliance_precheck_node",
"no_copy_bypass": "no_copy_bypass_node",
```

- [ ] **Step 2: `NODE_UTILIZATION_MATRIX` — `missing_context_question` excludes에 추가**

```python
"missing_context_question": {
    "includes": ["input", "validator", "options", "state_update"],
    "excludes": ["format_planner", "input_compliance_precheck", "t2i_generation", "result"],
},
```

- [ ] **Step 3: `NODE_UTILIZATION_MATRIX` — 나머지 7개 시나리오 includes에 추가**

`auto_pilot_text_overlay` — `"validator"` 다음에 `"input_compliance_precheck"` 추가:
```python
"auto_pilot_text_overlay": {
    "includes": [
        "input", "validator", "input_compliance_precheck", "format_planner",
        "tone_binding", "auto_pilot_copywriting", "copy_compliance_gate",
        "copy_spec_parser", "image_layout_analyzer", "post_t2i_layout_refiner",
        "text_renderer", "final_ocr_gate", "readability_gate", "final_validation", "result",
    ],
    "excludes": ["copy_candidate_generation", "custom_copy_input", "no_copy_bypass"],
},
```

`photo_suggest_candidates` — `"input"` 다음에 `"input_compliance_precheck"` 추가:
```python
"photo_suggest_candidates": {
    "includes": [
        "input", "product_preprocess", "input_compliance_precheck",
        "copy_candidate_generation", "copy_candidate_selection_interrupt",
        "state_update_selected_copy", "copy_compliance_gate",
        "t2i_request_builder", "t2i_generation", "background_ocr_gate",
        "image_layout_analyzer", "post_t2i_layout_refiner", "result",
    ],
    "excludes": ["reference_template_resolve", "custom_copy_input", "no_copy_bypass"],
},
```

`custom_copy_direct`:
```python
"custom_copy_direct": {
    "includes": [
        "input_compliance_precheck", "custom_copy_input", "custom_copy_validation",
        "copy_compliance_gate", "copy_spec_parser", "text_renderer", "result",
    ],
    "excludes": ["copy_candidate_generation", "auto_pilot_copywriting", "no_copy_bypass"],
},
```

`no_copy_image_only`:
```python
"no_copy_image_only": {
    "includes": [
        "input_compliance_precheck", "no_copy_bypass", "copy_spec_parser",
        "image_layout_analyzer", "post_t2i_layout_refiner", "safe_area_gate", "result",
    ],
    "excludes": ["text_renderer", "final_ocr_gate", "readability_gate", "final_validation"],
},
```

`reference_template`:
```python
"reference_template": {
    "includes": [
        "input_compliance_precheck", "reference_template_resolve",
        "image_prompt_planner", "t2i_request_builder", "image_layout_analyzer",
        "post_t2i_layout_refiner", "result",
    ],
    "excludes": ["product_preprocess", "reference_preprocess"],
},
```

`reference_image`:
```python
"reference_image": {
    "includes": [
        "input_compliance_precheck", "reference_preprocess",
        "image_prompt_planner", "t2i_request_builder", "image_layout_analyzer",
        "post_t2i_layout_refiner", "result",
    ],
    "excludes": ["product_preprocess", "reference_template_resolve"],
},
```

`ocr_revision_loop`:
```python
"ocr_revision_loop": {
    "includes": [
        "input_compliance_precheck", "background_ocr_gate", "ocr_image_revision",
        "final_ocr_gate", "ocr_layout_revision", "copy_compliance_gate", "result",
    ],
    "excludes": ["copy_candidate_generation", "custom_copy_input", "no_copy_bypass"],
},
```

`compliance_blocked_and_resolved`:
```python
"compliance_blocked_and_resolved": {
    "includes": [
        "input_compliance_precheck", "custom_copy_input", "custom_copy_validation",
        "copy_compliance_gate", "copy_compliance_interrupt", "copy_compliance_resolution",
        "copy_spec_parser", "result",
    ],
    "excludes": ["copy_candidate_generation", "auto_pilot_copywriting", "no_copy_bypass"],
},
```

- [ ] **Step 4: 노드 활용도 테스트 실행**

```bash
PYTHONPATH=. .venv/bin/pytest orchestrator/tests/test_marketing_graph_node_utilization.py -v --tb=short
```

Expected: 1 PASSED

- [ ] **Step 5: 전체 회귀 테스트**

```bash
PYTHONPATH=. .venv/bin/pytest orchestrator/tests/ -v --tb=short 2>&1 | tail -5
```

Expected: `N passed` (기존 대비 precheck 테스트 9개 증가)

- [ ] **Step 6: 커밋**

```bash
git add orchestrator/tests/test_marketing_graph_node_utilization.py
git commit -m "test(compliance): Phase 4 — 노드 활용도 매트릭스에 input_compliance_precheck 커버리지 추가

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## 완료 기준 체크리스트

- [ ] `input_compliance_precheck_node`가 그래프에 등록되고 validator → precheck → format_planner 경로로 연결됨
- [ ] 위험 입력(`독소 배출`)에서 `input_compliance_risk` dict가 state에 기록됨
- [ ] 안전 입력에서 `input_compliance_risk is None`
- [ ] 어떤 경우에도 흐름이 interrupt 없이 format_planner로 계속됨
- [ ] result payload `metadata.copyCompliance`에 status, publicationReady, findings가 포함됨
- [ ] pass 케이스: `copyCompliance.publicationReady == true`, `findingCount == 0`
- [ ] manual_review 케이스: `publicationReady == false`, `userAcknowledgedRisk` 정확히 전달됨
- [ ] 노드 활용도 매트릭스 커버리지 테스트 통과 (모든 그래프 노드 커버)
- [ ] 전체 회귀 테스트 통과
