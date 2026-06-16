# 업종(business_type) → 프리셋 라우팅 구조 점검

> 이슈 7(감자튀김 불판)은 증상일 뿐이고, 그 아래 **업종 분류 → 비주얼 프리셋/템플릿 선택** 구조 전반에 하드코딩·중복·택소노미 불일치가 있음. 본 문서는 그 구조적 문제를 정리함(코드 수정 아님, 합의용 진단).
>
> 작성: 2026-06-15. 범위: `orchestrator/app/llm`의 `scene_planner.py` / `visual_presets.py` / `visual_templates.py` / `schemas/image_prompt_v3.py` + 업스트림 `brief_interpreter` / `copy_tone_policy`.

---

## TL;DR (핵심 결론)

1. **업종 어휘(taxonomy)에 단일 진실원천(SSOT)이 없음.** 같은 "업종" 개념이 **최소 6개의 서로 다른 어휘**로 따로 하드코딩됨. `context.business_type`은 아예 무타입 `str`.
2. **비주얼 선택 시스템이 2개**(`visual_presets` + `visual_templates`)로 병존하고, **서로 다른 키워드/키**로 라우팅함. 입력에 따라 프리셋과 템플릿이 **불일치**할 수 있음(이슈 7의 근본).
3. **같은 라우팅 로직이 3~4곳에 중복**되고 키워드 집합이 미묘하게 다름(특히 한글 키워드).
4. **조용한 오분류·증발이 실재함**(아래 표·재현). `retail/education/service/fitness`는 전부 `generic`으로 증발하고, `beauty_salon`은 hair 프리셋으로 오변환되는 latent 경로가 있음.
5. **숨은 강결합**: 프리셋의 `business_type` 문자열은 `ScenePlan` Literal의 부분집합이어야 함 — 어기면 런타임 크래시(이슈 7에서 실제 발생). 문서·타입 가드 없음.

→ "업종이 하나 늘면 6곳을 손으로 고쳐야 하고, 컴파일러가 안 잡아줌." 이게 컨텍스트 위반의 본질.

---

## 1. 현재 데이터 흐름

```
brief LLM ──► BriefBusinessType(8종)           [schemas/brief_llm.py:10]
   │           cafe/restaurant/beauty/retail/education/fitness/service/other
   ▼
BUSINESS_TYPE_MAP (4종만 매핑)                  [nodes/brief_interpreter.py:19]
   │           cafe→cafe, restaurant→restaurant, beauty→beauty_salon, fitness→fitness
   │           (retail/education/service/other = 매핑 없음 → 드롭)
   ▼
context.business_type : str   (무타입!)         [schemas/llm_marketing.py:136]
   │
   ├──────────────► select_visual_template(context.business_type 원본)   [visual_templates.py:100]
   │                   haystack substring 매칭, business_types 리스트(어휘 C)
   │
   └─► build_scene_plan                          [scene_planner.py:90]
          │
          ├─ resolve_business_type(...)  ── 키워드 휴리스틱(어휘 D) [scene_planner.py:41]
          │     → resolved_bt
          ▼
          select_visual_preset(resolved_bt)  ── 키워드 휴리스틱(어휘 E) [visual_presets.py:134]
          │     → preset
          ▼
          ScenePlan(business_type = preset["business_type"])   [scene_planner.py:125]
                Literal 9종(어휘 F)  ◄── 프리셋 business_type가 여기 없으면 크래시
```

별도로 카피 파이프라인은 또 다른 어휘를 씀: `copy_tone_policy`(어휘 G) + 별도 alias 맵.

---

## 2. 택소노미 불일치 (어휘 6+종 대조)

| 위치 | 어휘(값) | 비고 |
|---|---|---|
| A. `BriefBusinessType` (`brief_llm.py:10`) | cafe, restaurant, beauty, retail, education, fitness, service, other | LLM이 내보내는 입력 어휘 |
| B. `BUSINESS_TYPE_MAP` (`brief_interpreter.py:19`) | cafe, restaurant, beauty→**beauty_salon**, fitness | **retail/education/service/other 매핑 없음** |
| C. `visual_templates.business_types` (`visual_templates.py`) | cafe/dessert/bakery · restaurant_bbq/bbq/korean_food/meat_restaurant · beauty/salon/hair_salon/nail/skincare · restaurant/dining/food/치킨/피자/식당/맛집 · `*` | substring 매칭용 키워드 |
| D. `resolve_business_type` 키워드 (`scene_planner.py:64`) | cafe류 · bbq류(고기/갈비/삼겹살/숯불 포함) · restaurant류(치킨/피자/식당/맛집) · beauty류 | user_input 휴리스틱 |
| E. `select_visual_preset` 키워드 (`visual_presets.py:147`) | cafe/dessert/bakery · bbq/고기/갈비/삼겹살/숯불 · restaurant/dining/food · skincare/skin · hair/salon · nail · spa/massage · beauty | resolved_bt substring |
| F. `ScenePlan.BusinessType` Literal (`image_prompt_v3.py:8`) | cafe, restaurant_bbq, restaurant, beauty_salon, beauty_skincare, beauty_hair, beauty_nail, beauty_spa, generic | 최종 산출 enum |
| G. `copy_tone_policy` 키 (`copy_tone_policy.py`) | cafe, restaurant_bbq, **macaron**, beauty_skincare, beauty_hair, beauty_nail, beauty_spa, generic (+alias) | 카피 전용, 또 다름 |
| H. (참고) legacy `marketing.py:6` (DEAD) | restaurant, cafe, beauty_salon, bar, fitness, academy, store, custom | 죽은 코드인데 또 다른 어휘 |

**핵심 모순**:
- `beauty_salon`은 B·F에만 있고 **프리셋(E)엔 없음** → 프리셋 단계에서 다른 값으로 변환됨.
- `restaurant`는 D·E·F엔 있지만 B는 `restaurant`만 주고 BBQ 구분은 user_input 키워드에 의존.
- `fitness`는 A·B엔 있지만 **프리셋·템플릿·카피·ScenePlan Literal 어디에도 없음** → 유령 카테고리.
- `retail/education/service/other`는 A에만 있고 **B에서 증발** → 전부 generic.
- `macaron`은 카피(G)에만 존재.

---

## 3. 재현된 조용한 오분류 (실측)

`select_visual_preset` / `select_visual_template` / `ScenePlan` 직접 호출 결과:

| 입력 business_type | 프리셋 결과 | 템플릿 결과 | 판정 |
|---|---|---|---|
| `beauty_salon` | **beauty_hair**(`beauty_hair_salon_clean`) | beauty_salon_clean_pastel | ⚠️ 일반 뷰티가 **헤어샵**으로 오변환(`"salon" in bt` 매칭). 프리셋≠템플릿 |
| `beauty` | beauty_skincare | beauty_salon_clean_pastel | ⚠️ 프리셋(skincare)≠템플릿(salon) |
| `fitness` | generic | generic | ❌ 유령 카테고리 → generic 증발 |
| `retail` | generic | generic | ❌ A엔 있지만 B에서 증발 |
| `education` | generic | generic | ❌ 동일 |
| `service` | generic | generic | ❌ 동일 |
| `restaurant` | restaurant_generic_clean | restaurant_generic_clean | ✅ (이슈 7 수정 후) |
| `restaurant_bbq` | restaurant_bbq_warm_grill | restaurant_bbq_warm_grill | ✅ |

> 비고: 정상 플로우에선 `resolve_beauty_subtype`가 `beauty_salon`을 `beauty_skincare`로 한 번 더 바꿔주기 때문에 `beauty_salon→beauty_hair`는 **latent**(특정 호출 경로에서만 발현). 하지만 `select_visual_preset`은 공개 함수이고 elif+substring 순서 의존이라 **지뢰**로 남음.

---

## 4. 구조적 문제 목록

### P1. 단일 진실원천(SSOT) 부재 — 무타입 `context.business_type` (구조)
- `MarketingContext.business_type: str | None`(자유 문자열). enum/Literal 없음.
- 업종 어휘가 6+곳에 흩어져 하드코딩(2장). 새 업종 추가 시 컴파일러가 누락을 못 잡음.
- CLAUDE.md의 원칙(`engine_for_render_profile`이 user↔internal 매핑을 **한 곳**에서 관리, `GenerationEngine`은 내부 전용)과 정반대. 업종에는 그 규율이 없음.

### P2. 비주얼 선택 시스템 2개 병존 (구조 / 이슈 7 근본)
- `visual_presets`(resolved_bt 기준) + `visual_templates`(raw context.business_type 기준)가 **다른 키워드 집합**으로 독립 라우팅.
- 한쪽만 고치면 다른 쪽이 어긋남(이슈 7: 템플릿 누락으로 불판 잔존). 두 시스템의 책임 경계가 문서화 안 됨.

### P3. 라우팅 로직 3~4중 중복 (DRY 위반)
- "무엇이 bbq/뷰티인가"가 `resolve_business_type`, `select_visual_preset`, `select_visual_template`, `resolve_beauty_subtype`, `copy_tone_policy` alias에 각각 하드코딩. 키워드가 미묘하게 다름(예: 템플릿 bbq엔 한글 없음·`meat_restaurant`, 프리셋 bbq엔 한글 있음·`meat`).

### P4. 카테고리 증발/유령 (ACTIVE 버그)
- `retail/education/service/other`: 분류돼도 `BUSINESS_TYPE_MAP`에서 드롭 → generic. 사용자에게 8종을 약속하나 4종만 구현.
- `fitness`: 매핑은 있으나 프리셋/템플릿/카피/Literal 전무 → 사실상 generic.

### P5. 프리셋 ↔ ScenePlan 숨은 강결합 (크래시 위험)
- `ScenePlan(business_type=preset["business_type"])`. 프리셋의 `business_type` 문자열이 `ScenePlan` Literal에 없으면 **pydantic ValidationError**. 이슈 7에서 새 프리셋(`restaurant`) 추가 시 실제 크래시함. 이 결합을 강제/문서화하는 장치 없음.

### P6. substring + elif 순서 의존 매칭 (취약)
- `select_visual_preset`이 `"salon" in bt`, `"skin" in bt` 같은 substring을 elif 체인으로 검사. `beauty_salon`이 hair로 빠지는 이유. 값 추가/이름 변경 시 순서에 따라 조용히 오라우팅.

### P7. 한글 키워드 산재 (이슈 7류 재발원)
- 업종/음식 한글 키워드가 셀렉터마다 인라인. 공유 렉시콘 없음 → 한쪽엔 있고 한쪽엔 없음(템플릿 bbq에 한글 부재). 신규 한글 케이스마다 여러 곳을 손봐야 함.

---

## 5. 권장 방향 (합의용, 구현 전 논의)

**단기(저위험, 즉시 가치)**
1. `BUSINESS_TYPE_MAP`에 `retail/education/service` 매핑 추가 또는 명시적 generic 위임을 코드/주석으로 고정(증발 = 의도임을 표시).
2. 프리셋 `business_type` 값 ↔ `ScenePlan.BusinessType` Literal 일치를 **단위 테스트로 강제**(불일치 시 fail) → P5 크래시 재발 차단.
3. `select_visual_preset`의 elif+substring을 **명시 매핑 dict**(정확 일치 우선, fallback 명시)로 교체 → P6 제거. `beauty_salon`을 명시 처리.

**중기(구조)**
4. 업종 **SSOT 도입**: 표준 `BusinessType` enum 하나를 정의하고 `context.business_type`를 그 타입으로. 모든 셀렉터가 이 enum만 소비.
5. 두 비주얼 시스템(P2)의 책임 정리: 하나로 통합하거나, "템플릿=배경/카피영역, 프리셋=피사체/무드"처럼 경계를 명문화하고 **동일 resolved_bt를 공유**(현재 raw vs resolved 분기 제거).
6. 키워드 렉시콘(한글 포함)을 **한 모듈로 추출**해 모든 셀렉터가 import(P3·P7).
7. BBQ는 "업종"이 아니라 "씬/요리" 축임을 분리 고려(restaurant는 업종, bbq는 cuisine 태그). 업종 택소노미와 비주얼 씬 택소노미를 섞지 않기.

---

## 6. 근거 파일·라인 (빠른 점프)

- `orchestrator/app/schemas/brief_llm.py:10` — BriefBusinessType(8종)
- `orchestrator/app/llm/nodes/brief_interpreter.py:19` — BUSINESS_TYPE_MAP(4종)
- `orchestrator/app/schemas/llm_marketing.py:136` — `business_type: str`(무타입)
- `orchestrator/app/llm/scene_planner.py:9,41,90` — resolve_beauty_subtype / resolve_business_type / build_scene_plan
- `orchestrator/app/llm/visual_presets.py:134` — select_visual_preset(elif+substring)
- `orchestrator/app/llm/visual_templates.py:100` — select_visual_template(haystack)
- `orchestrator/app/llm/schemas/image_prompt_v3.py:8` — ScenePlan BusinessType Literal(9종)
- `orchestrator/app/llm/copy_tone_policy.py:10,109` — copy 어휘 + alias 맵
- `orchestrator/app/schemas/marketing.py:6` — (DEAD) 또 다른 BusinessType
