# MarketingState union 정리 작업 요약 (2026-06-14)

> **브랜치:** `refactor/marketing-state-union-cleanup` (최신 develop 기준)
> **결과:** 커밋 9개. 전체 테스트 **1416 passed / 0 failed / 2 skipped**
> **핵심 한 줄:** "이 상태 필드가 직렬화된 dict인지 Pydantic 모델인지 모르겠다"는 타입 모호함을, **읽기 단일 창구(`read_model`)** 하나로 정리하고 타입 주석을 실제 저장 형태(dict)에 맞췄습니다.

---

## 이 작업이 왜 필요했나 (배경)

코드 리뷰에서 "MarketingState 필드 상당수가 `dict[str, Any] | SomeModel | None` 유니온이라, 그 값이 직렬화된 dict인지 Pydantic 모델인지 알 수 없고, 그래서 타입 체커가 사실상 무력화된다"는 지적을 받았습니다.

실제로 이런 패턴이었습니다:

```python
# 상태 정의
validator_output: dict[str, Any] | ValidatorOutput | None
copy_spec: dict[str, Any] | CopySpec | None
# ... 이런 필드가 80여 개

# 노드마다 제각각 변환 (24+ 곳)
copy_spec = CopySpec(**(state.get("copy_spec") or {}))
marketing_copy = MarketingCopy(**(state.get("marketing_copy") or {}))
```

문제는 두 가지였습니다:
1. **타입이 거짓말을 한다** — 유니온이 "dict일 수도, 모델일 수도"라고 해서 타입 체커가 어느 쪽도 보장하지 못합니다.
2. **변환 규칙이 흩어져 있다** — 같은 "dict→모델" 변환을 노드마다 손으로 반복하고, 표준 헬퍼는 `context_to_model` 하나뿐이었습니다.

핵심 통찰: LangGraph가 상태를 직렬화(특히 이번에 도입한 Postgres checkpointer)하므로 **저장 형태는 항상 dict여야** 합니다. 모델은 "노드가 읽을 때 잠깐 파싱하는 뷰"일 뿐입니다. 그렇다면 타입도 dict로 적고, 변환은 한 곳에서만 하면 됩니다.

> 💡 **쉽게 말하면:** 창고(상태)에는 물건을 항상 "납작하게 분해된 부품 상자(dict)" 형태로 보관합니다. 작업자(노드)가 쓸 때만 잠깐 조립(모델)해서 쓰고요. 그런데 지금까지는 ① 상자 라벨에 "부품 상자일 수도, 완제품일 수도"라고 애매하게 적혀 있었고, ② 작업자마다 조립 방법을 제각각 손으로 했습니다. 이걸 "라벨은 부품 상자로 통일 + 조립은 표준 공구 하나로"로 정리한 겁니다.

---

## 1. 읽기 단일 창구 `read_model` 도입

**커밋:** `90f61705` · **파일:** `orchestrator/app/graph/state.py`

**무엇을:** 어떤 상태 필드든 모델로 읽어주는 제너릭 헬퍼 하나를 만들었습니다.

```python
def read_model(state, key, model_cls, *, default=_UNSET):
    value = state.get(key)
    if isinstance(value, model_cls):   # 이미 모델이면 그대로
        return value
    if not value:                       # 없으면 빈 모델 (또는 default=None 시 None)
        return None if default is None else model_cls()
    return model_cls(**value)           # dict면 파싱
```

기존 `context_to_model`도 이 헬퍼에 위임하도록 바꿔서, 변환 로직이 진짜 한 곳에만 존재하게 했습니다.

**왜:** "dict인지 모델인지 모름"이라는 이중성을 함수 하나에 가둡니다. 방어적으로 동작(이미 모델이면 통과, 없으면 빈 모델)해서 호출부가 단순해집니다.

> 💡 **쉽게 말하면:** 부품을 조립하는 표준 공구를 하나 만들었습니다. "상자를 넣으면 완제품이 나오고, 이미 완제품이면 그대로 통과"하는 만능 조립기예요.

---

## 2~3. 흩어진 변환 24+곳을 단일 창구로 교체

**커밋:** `8efa7d1e`, `5a3b94ef`, `f51a2eb0`, `d3e672c1` · **파일:** 노드 11개

**무엇을:** `Model(**(state.get("필드") or {}))` 식으로 손으로 변환하던 모든 **상태 읽기**를 `read_model(state, "필드", Model)`로 교체했습니다. 대상 모델:
- 카피/레이아웃/스타일: `CopySpec`, `TextLayoutSpec`, `TextStyleSpec`, `MarketingCopy`
- 이미지/생성: `ImagePrompt`, `T2IRequest`
- 사용자 입력: `UserSelectionRequest`
- 네이티브 생성: `NativeCreativePromptPackage`, `NativeGenerationBudget`, `ApprovedNativeCopyBrief`, `CreativeExecutionPlan`, `InputEvidenceBundle`, `ProductUnderstanding`
- `CopyVisualIntent` ("상태값 OR 계산된 기본값" 형태도 `read_model(..., default=None) or 계산식`으로 등가 변환)

**왜:** 변환 규칙을 한 곳(read_model)으로 모으면, 동작이 노드마다 미묘하게 달라지는 일이 사라지고 코드가 짧아집니다.

**어떻게:** 각 교체가 동작 등가임을 확인했습니다. 예를 들어 `CopySpec()`는 빈 입력 시 ValidationError를 던지는데, 기존 `CopySpec(**{})`도 똑같이 던지므로 read_model의 빈 모델 동작이 등가입니다.

> 💡 **쉽게 말하면:** 작업자 24명이 각자 다른 방법으로 조립하던 걸, 전부 "표준 조립기에 넣기"로 통일했습니다.

---

## 4. 타입 주석을 실제 저장 형태(dict)로 정규화

**커밋:** `b7747699`, `f7665ab6` · **파일:** `orchestrator/app/graph/state.py`

**무엇을:** model-backed 필드 ~30개의 주석을 `dict[str, Any] | SomeModel | None` → `dict[str, Any] | None`으로 바꾸고, 그로 인해 쓸모없어진 모델 import를 제거했습니다.

**왜:** 이 필드들은 실제로 **항상 dict로 저장**되고(노드가 `.model_dump()`로 씀), 모델로 다시 읽히지 않습니다(읽을 땐 read_model이 변환). 그러니 주석도 dict로 적는 게 정직하고, 그래야 타입 체커가 다시 신호를 줍니다.

**어떻게 (안전 검증):** 정규화 전에 세 가지를 전수 확인했습니다 — ① raw 모델로 저장하는 곳 없음, ② 모델로 재구성하는 곳은 read_model로 이미 이전됨, ③ 속성 접근(`state["x"].attr`)으로 모델 가정하는 곳 없음.

**의도적으로 남긴 2개 예외:**
- `context: dict | MarketingContext` — 읽기 빈도가 높고 `context_to_model` 전용 경로 사용, non-null
- `plan_policy: dict | PlanPolicy` — `normalize_plan_policy` 전용 정규화 함수 사용, non-null

> 💡 **쉽게 말하면:** 애매했던 상자 라벨을 전부 "부품 상자"로 정정했습니다. 단, 늘 완제품으로 다루는 특별한 두 상자는 기존 라벨을 유지했고요. 라벨을 바꾸기 전에 "이 상자를 완제품으로 꺼내 쓰는 데가 정말 없는지" 세 방향으로 확인했습니다.

---

## 5. 계약 문서화

**커밋:** `b5de65f9` · **파일:** `docs/state-source-of-truth.md`

**무엇을:** 기존 source-of-truth 문서(③ 작업)에 "dict ↔ 모델 경계" 규칙을 추가했습니다: 저장은 항상 dict, 읽을 때만 read_model로 파싱, 손으로 `Model(**state.get())` 금지.

**왜:** 코드만 고치면 6개월 뒤 누군가 또 손으로 변환하는 코드를 추가합니다. 규칙을 문서로 박아야 재발을 막습니다.

> 💡 **쉽게 말하면:** "부품은 표준 조립기로만 조립할 것"이라는 작업 수칙을 벽에 붙였습니다.

---

## 의도적으로 범위에서 제외한 것

정직하게 남겨둔 부분:
- **함수 파라미터/로컬 변수 coercion** (`llm/prompt_renderer.py`의 `ImagePromptSpec(**param)`, `text_renderer.py`/`safe_area_gate.py`의 patch된 로컬 변수). 이건 **상태 읽기가 아니라** 함수 인자 정규화라 read_model(상태 키 기반) 범위 밖이고, 순수 라이브러리에 graph.state 의존을 넣지 않기 위해 그대로 뒀습니다.
- **MarketingState의 sub-state 분리** (intake/copy/image/render 그룹화). 리뷰가 언급한 더 큰 아키텍처 변경으로, 이번 "union 정리" 범위 밖의 별도 과제입니다.

## 참고: 기존 import 사이클 특성

graph.state를 import하는 노드는 `python -c "import 노드"` 단독 실행 시 순환 import 에러가 납니다. 이는 `graph/__init__.py`가 builder를 eager import하는 **기존 설계 특성**이며(이번에 새로 생긴 게 아님), pytest와 프로덕션(builder 경유) 경로는 모두 정상입니다.

## 검증 결과 요약

- 전체 스위트: **1416 passed, 0 failed, 2 skipped**
- 최종 grep 감사: **ad-hoc `Model(**state.get(...))` 0건** (모든 상태→모델 변환이 read_model 경유)
- `import orchestrator.app.graph.builder` 정상 (제거한 import로 인한 깨짐 없음)

## 리뷰 우선순위 진행 현황

| | 상태 |
|---|---|
| ① Postgres checkpointer | ✅ main 머지 (#149) |
| ② 인증 경계 | ✅ main 머지 (#150) |
| ③ current_brief vs context SoT | ✅ develop 머지 (#157) |
| ④ MarketingState union 정리 | ✅ 이번 작업 (read_model 통일 + 주석 정규화 완료) |

남은 더 큰 과제는 **MarketingState sub-state 분리** 하나이며, 이는 별도 설계가 필요한 아키텍처 작업입니다.
