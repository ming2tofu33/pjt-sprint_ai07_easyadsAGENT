# MarketingState Source of Truth 계약

코드 리뷰 지적 사항 "current_brief와 context가 같은 값을 중복 관리하고
어느 쪽이 SoT인지 불분명하다"에 대한 확정 계약. (2026-06-12)

## 역할 정의

| 저장소 | 역할 | 읽기 주체 |
|---|---|---|
| `context` (MarketingContext) | 비즈니스 필드의 SoT — business_type, brand_tone, usp 등 12개 코어 필드 + `extra` | 비즈니스 로직 (LLM 노드, 플래너) |
| `current_brief` | **UI read model** — 프론트엔드 표시용 미러 + UI 전용 키 (cached_options, selected_tone, copy_generation_mode_confirmed, reference_template_* 등) | 프론트엔드 (`chat-thread-state-mapper.ts`), 스냅샷 |
| top-level state 필드 | 그래프 실행 플래그/선택값 — copy_generation_mode, selected_ad_format 등 | 그래프 라우팅 |

## 규칙

1. **비즈니스 로직은 current_brief를 직접 읽지 않는다.** 코어 필드는
   `context`에서, ad_format은 `resolve_requested_ad_format(state)`로 읽는다.
2. **brief 미러 쓰기는 write-through 헬퍼로만 한다.** ad_format은
   `set_requested_ad_format` / `backfill_requested_ad_format`
   (`orchestrator/app/graph/state.py`). 손으로 두 미러를 쓰는 코드는 버그다.
3. `state_update_node`의 제네릭 미러 쓰기(`update_current_brief(state,
   {field: value})`)는 FE 표시용으로 유지한다 — 단, 그 값을 다시 읽는
   비즈니스 로직을 추가하지 말 것.

## ad_format의 canonical 우선순위

`resolve_requested_ad_format()` 내부 순서이자 유일한 계약:

1. `state["selected_ad_format"]` — 이번 실행에서의 명시적 사용자 선택
2. `current_brief["requested_ad_format"]` — 확정/복원된 브리프 값
3. `context.extra["ad_format"]` — 휴리스틱/LLM 추론값
4. `current_brief["ad_format"]` — 레거시 제네릭 키
5. `None` — 기본값은 호출자 소관 (format_planner는 `"instagram_feed"`)

이전에는 reader 4곳이 각자 다른 순서를 썼다 (format_planner: 1을 안 봄,
execution: 2·3 순서 동일하지만 별도 구현, chat.py: 2만 봄). 미러가
갈라지면 reader마다 다른 광고 형식으로 동작하는 버그였다.

빈 값 처리: 초기 상태가 brief 키를 명시적 `None`으로 심으므로, 모든
헬퍼는 "키 존재 여부"가 아니라 **falsy 여부**를 "미설정"으로 본다
(setdefault 금지 — `backfill_requested_ad_format` 구현 주석 참고).

## copy_generation_mode

SoT는 **top-level `state["copy_generation_mode"]`**. brief의 사본은
FE 표시용 write-only 미러이고, `copy_generation_mode_confirmed`는
brief 전용 키(중복 아님)다.

## 다음 단계 (리뷰 우선순위 ④와의 연결)

이 문서의 규칙은 MarketingState dict|Model union 정리(④)의 전제다.
④ 진행 시 brief 전용 키들을 TypedDict로 명세하는 것부터 시작할 것.
