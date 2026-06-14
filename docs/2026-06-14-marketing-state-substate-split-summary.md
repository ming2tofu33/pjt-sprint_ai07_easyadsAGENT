# MarketingState sub-state 분리 작업 요약 (2026-06-14)

> **브랜치:** `refactor/marketing-state-substate-split` (최신 develop 동기화 완료)
> **결과:** 커밋 4개. 전체 **1434 passed / 0 failed / 2 skipped**
> **핵심 한 줄:** 161개 필드가 한 덩어리로 평평하게 늘어서 있던 `MarketingState`를, **런타임 동작은 1바이트도 안 바꾸면서** 파이프라인 단계별 10개 그룹으로 소스에서만 정리했습니다.

---

## 이 작업이 왜 필요했나 (배경)

코드 리뷰에서 "MarketingState가 너무 비대하다(필드가 너무 많다), 필드 그룹별로 sub-state로 분리하는 걸 검토하라"는 지적을 받았습니다. 실제로 한 TypedDict에 **161개 필드**가 평평하게 나열돼 있어서, 어떤 필드가 어느 파이프라인 단계에 속하는지 한눈에 안 들어왔습니다.

"sub-state 분리"는 두 가지로 해석됩니다:
1. **진짜 중첩** — `state["copy"]["copy_spec"]`처럼 실제로 dict를 중첩. 가장 "제대로"지만, 이 필드들을 읽고 쓰는 **557곳을 전부 재작성**해야 하고, LangGraph의 상태 병합 방식(top-level 키 덮어쓰기)을 커스텀 reducer로 바꿔야 합니다 → 고위험·대공사.
2. **조직화** — 런타임은 평평한 dict 그대로 두고, **소스 코드에서만** 161필드를 그룹별 TypedDict로 나눠 다중 상속으로 합침. 가독성/탐색성은 얻으면서 동작은 0 변경.

팀 논의 결과 **②(조직화)** 를 선택했습니다. 리뷰가 실제로 원한 "그룹별 정리" 효과를 거의 무위험으로 달성하는 방식입니다.

> 💡 **쉽게 말하면:** 서랍 하나에 161개 물건이 뒤섞여 있던 걸, 서랍 안에 **칸막이 10개**를 넣어 종류별로 정리한 겁니다. 서랍 위치도, 물건 위치도, 꺼내 쓰는 방법(557곳)도 그대로 — 안을 들여다봤을 때 정리돼 보이기만 달라졌습니다. "물건마다 별도 서랍으로 옮기기(진짜 중첩)"는 이사 비용이 너무 커서 안 했고요.

---

## 1. 안전장치 먼저 — 161필드 특성화 테스트

**커밋:** `2a68998a` · **파일:** `orchestrator/tests/test_marketing_state_shape.py`

**무엇을:** 분리에 손대기 **전에**, MarketingState가 정확히 어떤 161개 필드를 갖는지 고정하는 테스트를 만들었습니다. 필드가 하나라도 누락/중복/이름변경되면 즉시 실패합니다.

**왜:** 161개 필드를 10개 클래스로 옮기는 작업에서 가장 큰 위험은 "필드 하나를 빠뜨리거나 두 그룹에 중복으로 넣는 것"입니다. 이걸 기계가 잡아주게 먼저 깔았습니다.

> 💡 **쉽게 말하면:** 칸막이를 넣기 전에 "원래 물건이 161개"라고 사진을 찍어둔 겁니다. 정리 후 물건 수가 안 맞으면 바로 알 수 있죠.

---

## 2. 10개 그룹으로 분리 + 다중 상속 재조립

**커밋:** `87566df6` · **파일:** `orchestrator/app/graph/state.py`

**무엇을:** flat한 `MarketingState`를 파이프라인 단계별 10개 TypedDict로 쪼개고, 다중 상속으로 다시 합쳤습니다:

```python
class MarketingState(
    JobMetaState, IntakeState, ReferenceVisionState, ContextValidationState,
    CopyState, NativeCreativeState, TypographyLayoutState, ImagePromptT2IState,
    QualityGateState, RenderFinalizeState, total=False,
):
    ...
```

| 그룹 | 책임 |
|---|---|
| `JobMetaState` | 신원/테넌시/라우팅/플랜/실행 회계 |
| `IntakeState` | 사용자 입력·브리프·에셋·product understanding |
| `ReferenceVisionState` | 레퍼런스 템플릿·비전 전처리 |
| `ContextValidationState` | context·validator·옵션 질문 |
| `CopyState` | 광고 형식·카피 생성·컴플라이언스·카피/텍스트 스펙 |
| `NativeCreativeState` | GPT-Image 네이티브 타이포 single-shot |
| `TypographyLayoutState` | 타이포 아트디렉션·레이아웃 핏 refinement |
| `ImagePromptT2IState` | 이미지 프롬프트·T2I 요청/결과 |
| `QualityGateState` | 품질/OCR 게이트·재생성·후보 |
| `RenderFinalizeState` | 렌더·검증 리포트·최종 합성·결과 |

**왜:** TypedDict 다중 상속은 부모들의 필드를 모두 합친 `__annotations__`를 만듭니다 — 즉 합쳐진 결과는 기존 flat 클래스와 완전히 동일합니다. LangGraph도, 모든 노드도, 557개 접근 지점도 전혀 영향받지 않습니다.

**어떻게 (3중 안전 검증):**
1. 분리 전 `__annotations__`를 통째로 스냅샷 → 분리 후와 **byte-identical** 확인 (161필드 이름+타입 전부 동일)
2. 특성화 테스트 통과 유지
3. "각 그룹 필드 합계 = 합집합 = 161" (중복 0, 누락 0) 자동 검증

> 💡 **쉽게 말하면:** 칸막이를 넣되, 넣기 전후로 "서랍을 통째로 쏟았을 때 나오는 물건 목록"이 토씨 하나 안 틀리게 같은지 대조했습니다. 같다는 게 증명됐으니 사용하는 쪽은 아무것도 안 바뀝니다.

---

## 3. 그룹 구조 문서화

**커밋:** `f0ba1a38` · **파일:** `docs/state-source-of-truth.md`

**무엇을:** 10개 그룹의 책임 표와 규칙(새 필드는 맞는 그룹에 추가, 런타임은 여전히 flat이라 read_model 컨벤션 그대로 적용, 진짜 중첩은 왜 안 했는지)을 기존 SoT 문서에 이어 붙였습니다.

**왜:** 다음 사람이 새 필드를 추가할 때 "어느 그룹에?"를 바로 알 수 있게, 그리고 "왜 진짜 중첩으로 안 했지?"라는 질문에 미리 답하기 위해서입니다.

> 💡 **쉽게 말하면:** 칸막이마다 라벨을 붙이고 "새 물건은 맞는 칸에 넣으세요"라고 적어둔 겁니다.

---

## 의도적으로 안 한 것

- **런타임 중첩 분리** (`state["copy"][...]`): 557개 접근 지점 재작성 + LangGraph 병합 reducer 커스텀이 필요해 리스크 대비 효용이 낮습니다. 문서에 이유를 명시했고, 필요하면 향후 별도 과제로 분리 가능합니다.

## 검증 결과 요약

- 전체 스위트: **1434 passed, 0 failed, 2 skipped**
- `__annotations__` 분리 전후 **byte-identical** (161필드)
- disjoint + exhaustive 검증: 그룹 합계 = 합집합 = 161 (중복/누락 0)
- `import builder` + `create_app()` 정상

## 리뷰 우선순위 진행 현황 (최종)

| | 상태 |
|---|---|
| ① Postgres checkpointer | ✅ main 머지 (#149) |
| ② 인증 경계 | ✅ main 머지 (#150) |
| ③ current_brief vs context SoT | ✅ develop 머지 (#157) |
| ④ MarketingState union 정리 | ✅ develop 머지 (#180) |
| ④+ MarketingState sub-state 분리 | ✅ 이번 작업 (조직화 방식) |

리뷰에서 지적된 핵심 항목이 모두 처리됐습니다.
