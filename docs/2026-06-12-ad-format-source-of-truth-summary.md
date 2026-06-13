# ad_format Source of Truth 정리 작업 요약 (2026-06-12)

> **브랜치:** `refactor/ad-format-source-of-truth` → **PR #157 (base: develop)**
> **결과:** ad_format 관련 커밋 6개. origin/develop 머지 후 전체 **1397 passed, 0 failed**
> **핵심 한 줄:** 광고 형식(ad_format) 값이 5곳에 흩어져 저장되고 읽는 코드마다 우선순위가 달라서, "어느 화면에선 인스타 피드, 어느 화면에선 네이버 블로그"로 갈라질 수 있던 버그를 단일 창구로 정리했습니다.

---

## 이 작업이 왜 필요했나 (배경)

코드 리뷰에서 "`current_brief`와 `context`가 같은 값을 중복 관리하는데 어느 게 진짜(Source of Truth)인지 불분명하다"는 지적을 받았습니다. 실제 코드를 전수 조사해 보니:

- **대부분의 필드(업종, 브랜드 톤, USP 등)는 이미 정리돼 있었습니다.** `context`가 진짜 값이고, `current_brief`에 있는 사본은 프론트엔드 화면 표시용 미러였어요. 비즈니스 로직이 `current_brief`에서 읽는 코드는 없었습니다. → 문제 없음, 그대로 유지
- **진짜 문제는 `ad_format` 딱 하나였습니다.** 이 값이 무려 **5곳**에 저장되고 있었어요:
  - `current_brief["requested_ad_format"]`
  - `current_brief["ad_format"]` (레거시 키)
  - `context.extra["ad_format"]`
  - top-level `state["selected_ad_format"]`
  - `context.extra["selected_ad_format"]`
- 게다가 **이 값을 읽는 4곳이 각자 다른 우선순위**로 읽었습니다. format_planner는 brief부터, execution은 top-level부터, chat.py는 brief만 봤어요. 5개 저장소 중 일부만 업데이트되고 일부가 옛날 값으로 남으면, 읽는 위치마다 다른 광고 형식으로 동작하는 실제 버그가 됩니다.

> 💡 **쉽게 말하면:** 한 회사의 "대표 전화번호"가 명함, 홈페이지, 간판, 영수증, 네이버 등록 정보 다섯 군데에 따로 적혀 있는데, 직원마다 "나는 명함 보고 안내해", "나는 간판 보고 안내해"라고 제각각이던 상황입니다. 하나만 바뀌고 나머지가 옛날 번호로 남으면 손님이 누구에게 묻느냐에 따라 다른 번호를 받게 되죠. 이제 "번호는 무조건 이 대장(臺帳)에서, 이 순서로 확인한다"는 규칙 하나로 통일했습니다.

---

## 1. 단일 창구 3종 세트 — 읽기·쓰기·채우기

**커밋:** `fd33d9e6` (resolver·setter), `c50f5a95` (backfill) · **파일:** `orchestrator/app/graph/state.py`

**무엇을:** ad_format을 다루는 헬퍼 함수 3개를 만들고, 모든 코드가 이걸 통해서만 ad_format을 다루도록 했습니다.

| 함수 | 역할 |
|---|---|
| `resolve_requested_ad_format(state)` | **읽기 단일 창구.** 정해진 우선순위로 5개 저장소를 훑어 하나의 값을 반환 |
| `set_requested_ad_format(brief, extra, value)` | **쓰기 단일 창구.** 두 미러(brief·extra)를 항상 같은 값으로 동시에 기록 |
| `backfill_requested_ad_format(brief, extra, default)` | **빈 칸 채우기.** 기존 값이 있으면 그걸 우선 쓰고, 없을 때만 기본값으로 채움 (reference 템플릿용) |

**확정된 읽기 우선순위:**
1. `state["selected_ad_format"]` — 이번 실행에서 사용자가 명시적으로 고른 값
2. `current_brief["requested_ad_format"]` — 확정/복원된 브리프 값
3. `context.extra["ad_format"]` — 휴리스틱/LLM 추론값
4. `current_brief["ad_format"]` — 레거시 키
5. 없으면 `None` (기본값은 호출자가 알아서 — 예: format_planner는 `instagram_feed`)

**왜:** 우선순위를 코드 한 곳(resolver 함수)에 박아두면, 앞으로 규칙이 바뀌어도 그 함수만 고치면 됩니다. 읽는 위치마다 순서가 달라지는 일이 구조적으로 불가능해집니다.

> 💡 **쉽게 말하면:** "전화번호는 (1) 오늘 손님이 직접 알려준 번호 → (2) 확정 대장 → (3) 추정 번호 → (4) 옛날 장부 순서로 확인한다"는 규칙을 안내데스크 한 곳에 못 박은 겁니다. 모든 직원은 이 데스크에 물어보기만 하면 돼요.

---

## 2. 읽는 곳 4군데를 단일 창구로 교체

**커밋:** `7ab8d665` · **파일:** `format_planner.py`, `graph/nodes.py`, `execution.py`, `api/chat.py`

**무엇을:** 각자 다른 순서로 ad_format을 읽던 4곳을 전부 `resolve_requested_ad_format(state)` 호출로 바꿨습니다.

**왜:** 이게 버그의 핵심이었습니다. 같은 상태를 보고도 화면/단계마다 다른 광고 형식이 나올 수 있던 원인을 제거합니다.

**어떻게:** 각 호출부에만 있는 고유 입력(예: `request.ad_format` 같은 이번 요청 전용 값)은 그 자리에 남기고, 상태에서 읽는 부분만 창구로 통일했습니다. 동작이 바뀌지 않음을 각 변경마다 등가성을 따져 확인했습니다.

> 💡 **쉽게 말하면:** "명함 보고 안내하던 직원, 간판 보고 안내하던 직원"을 전부 "안내데스크에 물어보고 안내"하도록 바꿨습니다.

---

## 3. 쓰는 곳 3군데를 write-through로 교체

**커밋:** `7d079a65` · **파일:** `graph/nodes.py`, `execution.py`, `copy_candidates.py`

**무엇을:** 두 미러(brief·extra)를 손으로 따로따로 기록하던 3곳을 `set_requested_ad_format()` 한 줄로 바꿨습니다.

**왜:** 미러를 손으로 각각 쓰면 한쪽만 업데이트하고 다른 쪽을 빠뜨리기 쉽습니다. 그게 바로 값이 갈라지는 원인이었어요. setter를 거치면 두 미러가 항상 같이 갱신됩니다.

**어떻게:** grep으로 "손으로 미러를 쓰는 코드"가 더 남아있지 않은지 전수 확인했습니다 (남은 건 setter 함수 본문뿐).

> 💡 **쉽게 말하면:** 번호를 바꿀 때 다섯 군데를 따로 고치던 걸, "번호 변경" 버튼 하나 누르면 명함·간판·홈페이지가 동시에 갱신되게 만든 겁니다.

---

## 4. reference 템플릿 채우기 일관화 — 유일한 의도적 동작 변경

**커밋:** `c50f5a95` · **파일:** `reference_catalog/nodes.py`

**무엇을:** 사용자가 참고 템플릿을 고르면 그 템플릿의 ad_format으로 빈 칸을 채우는데, 기존 코드는 **두 미러를 독립적으로** 채웠습니다. 그래서 "한쪽 미러엔 이미 값이 있고 다른 쪽은 비어 있을 때", 빈 쪽에만 템플릿 값이 들어가 두 미러가 **서로 다른 값**으로 갈라질 수 있었습니다. 이걸 `backfill_requested_ad_format()`로 바꿔, 이미 있는 값을 우선 복사해 두 미러를 항상 똑같이 맞춥니다.

**왜:** 이게 divergence가 실제로 발생할 수 있는 시나리오였습니다. 이 PR에서 유일하게 "동작이 의도적으로 달라진" 부분이라, 어떤 입력에서 어떻게 달라지는지 테스트로 명시했습니다.

**서브에이전트가 잡은 미묘한 함정:** 초기 상태가 `requested_ad_format`을 명시적 `None`으로 심어둡니다. 그래서 "키가 없으면 채운다"(setdefault) 방식은 `None`을 "이미 있음"으로 오인해 안 채웁니다. 헬퍼를 "값이 falsy면 채운다" 방식으로 바꿔 해결했고, 이유를 코드 주석에 남겼습니다.

> 💡 **쉽게 말하면:** 명함엔 번호가 있는데 간판이 비어 있을 때, 예전엔 간판에 "기본 번호(템플릿 값)"를 박아서 명함과 간판이 달라졌습니다. 이제는 "이미 있는 명함 번호를 간판에도 그대로 복사"해서 둘을 항상 일치시킵니다.

---

## 5. 계약 문서 — 다음 사람을 위한 규칙집

**커밋:** `52809124` · **파일:** `docs/state-source-of-truth.md`

**무엇을:** 누가 무엇의 진짜 값인지, 어떻게 읽고 써야 하는지를 문서로 못 박았습니다:
- `context` = 비즈니스 필드의 진짜 값 / `current_brief` = **UI 표시용 미러** (비즈니스 로직은 직접 읽지 말 것) / top-level = 그래프 실행 플래그
- ad_format 읽기 우선순위, write-through 규칙
- `copy_generation_mode`의 진짜 값은 top-level이라는 점도 함께 정리

**왜:** 코드만 고치면 6개월 뒤 누군가 또 `current_brief`에서 직접 읽는 코드를 추가하고 같은 버그가 재발합니다. "왜 이렇게 했는지"를 규칙으로 남기는 게 절반의 작업입니다. 이 문서는 다음 과제(④ MarketingState 정리)의 전제이기도 합니다.

> 💡 **쉽게 말하면:** 안내데스크 운영 규칙을 벽보로 붙여둔 겁니다. 새 직원이 와도 "번호는 데스크에 물어본다, 명함/간판에 직접 적지 않는다"를 바로 알 수 있어요.

---

## develop 정렬 & 충돌 해결

이 작업 중 팀의 최신 `develop`(product-copy 관련 PR #154~156)이 올라와서, 이 브랜치에 머지해 맞췄습니다.
- 충돌은 `chat.py`의 import 한 줄뿐 — 정리 후 해결
- develop의 copy 생성 작업이 제가 고친 `copy_candidates.py`를 건드렸지만, grep 감사로 ad_format setter/resolver가 온전히 살아있음을 확인
- 머지 후 전체 테스트 **1397 passed, 0 failed**

## 검증 결과 요약

- 전체 스위트: **1397 passed, 0 failed, 2 skipped** (develop 머지 후)
- grep 감사: 비즈니스 로직에 남은 brief의 ad_format 직접 읽기 **0건** (모든 매치가 state.py 헬퍼 본문 내부)

## PR 안내 (#157)

main과 develop이 갈라져 있어, 이 PR은 ad_format 6커밋 외에 **이미 main에 머지된** checkpointer·auth·debt-cleanup 36커밋도 함께 담고 있습니다 (develop이 아직 못 받은 부분). 머지하면 develop이 main을 따라잡는 효과가 있습니다. **ad_format만 보려면** 커밋 `135ef180..52809124` 또는 `docs/state-source-of-truth.md` diff를 참고하세요.

## 다음 작업 (예정)

**④ MarketingState 비대화 해소** — dict|Model union 74개, 146 필드 정리. 이번 작업의 계약 문서가 그 전제이며, "brief 전용 키를 TypedDict로 명세하는 것"부터 시작할 예정입니다. 대형 리팩터라 설계 논의부터 진행합니다.
