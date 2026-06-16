# 도메인 라우팅 SSOT 정리 필요성과 다음 단계

> 작성일: 2026-06-16  
> 배경 문서: `docs/PRESET_ROUTING_AUDIT.md`  
> 목적: 광고 이미지 생성이 사용자 요청과 업종/상품 맥락에 맞게 유연하게 동작하도록, 현재 하드코딩 라우팅 구조를 왜 정리해야 하는지와 어떤 순서로 다음 단계에 들어가야 하는지 팀 공유용으로 정리한다.

## 한 줄 결론

현재 문제는 프리셋 몇 개가 부족한 정도가 아니라, **사용자 요청을 표준 도메인/상품/씬/무드로 해석한 뒤 일관된 비주얼 전략으로 연결하는 중앙 라우팅 레이어가 없다는 것**이다.

SSOT는 이 문제를 해결하기 위한 바닥 공사다. 다만 SSOT만으로 이미지 생성 품질이 자동으로 좋아지는 것은 아니며, 그 위에 도메인 해석, 씬 분리, fallback 정책, 테스트, 실제 생성 평가가 함께 올라가야 한다.

## 왜 이 공사가 필요한가

### 1. 제품이 약속하는 동작과 실제 구조가 다르다

우리가 만들고 싶은 것은 사용자의 광고 요청을 읽고, 업종과 상품/서비스에 맞는 이미지를 유연하게 생성하는 시스템이다.

하지만 현재 구조는 다음에 가깝다.

```text
사용자 요청
  -> 여러 파일의 문자열 분기
  -> 우연히 맞으면 도메인 프리셋 선택
  -> 조금만 어휘가 달라지면 generic 또는 오분류
```

즉, 지금은 "도메인 이해 기반 생성"이라기보다 "흩어진 하드코딩 분기 모음"이다. 이 상태에서는 도메인을 추가하거나 사용자 표현이 다양해질수록 품질이 자연스럽게 좋아지는 대신, 누락과 충돌이 계속 늘어난다.

### 2. 기능적으로 이미 사용자 영향이 있다

현재 코드 기준으로 확인된 대표 증상은 다음과 같다.

- `retail`, `education`, `service`, `other`는 LLM brief schema에는 있지만 context 업데이트에서 빠진다.
- `fitness`는 context에는 들어올 수 있지만, 프리셋/템플릿/ScenePlan/copy tone 쪽에서는 대부분 `generic`으로 떨어진다.
- `beauty_salon`은 프리셋 단독 호출 시 `salon` substring 때문에 `beauty_hair`로 오분류될 수 있다.
- `beauty_salon`은 템플릿에서는 beauty template, 프리셋에서는 skincare 또는 hair, copy policy에서는 generic으로 갈 수 있다.
- `restaurant`는 비주얼에서는 일반 음식점으로 가는데, copy tone policy에서는 `restaurant_bbq`로 alias되어 카피 톤이 불판/예약 중심으로 기울 수 있다.
- 실제 `image_prompt_planner` 경로에서는 `metadata.business_type`이 우선이라, user input의 `삼겹살/참숯` 같은 BBQ 키워드가 `restaurant_bbq` 휴리스틱으로 이어지지 않는 경로가 있다.

이런 문제는 단순히 내부 코드 품질 문제가 아니라, 사용자가 "헬스 PT 광고", "교육 클래스 광고", "리테일 상품 광고"를 요청했을 때 이미지가 도메인답게 나오지 않는 문제로 이어진다.

### 3. 근본적으로 확장이 어렵다

지금은 같은 "업종" 개념이 여러 레이어에 따로 존재한다.

- brief LLM 출력 taxonomy
- context business_type 문자열
- scene planner 휴리스틱
- visual preset selector
- visual template selector
- copy tone policy alias
- copy grounding domain map
- T2I negative prompt industry map
- reference catalog alias
- legacy/graph inference heuristic

이 상태에서 새 도메인 하나를 추가하려면 여러 파일을 손으로 맞춰야 한다. 어느 하나라도 빠지면 컴파일러나 테스트가 구조적으로 잡아주지 못하고, 런타임에서 조용히 `generic`으로 떨어진다.

### 4. 이미지 생성 프롬프트에 충돌 신호가 들어갈 수 있다

이미지 생성은 최종 프롬프트가 중요하다. 그런데 현재는 template, preset, scene_plan, copy policy가 서로 다른 도메인 판단을 할 수 있다.

예를 들어 한 요청 안에서:

- template metadata는 beauty salon
- scene_plan은 beauty skincare
- preset은 beauty skincare
- copy policy는 generic

처럼 갈라질 수 있다. 모델 입장에서는 명확한 전략이 아니라 섞인 신호를 받게 된다. 이 상태에서 생성 품질을 모델 탓으로만 보기 어렵다.

### 5. 테스트가 현재 구조의 핵심 위험을 강제하지 않는다

현재 관련 테스트는 통과하지만, 아래 계약을 충분히 강제하지 않는다.

- 지원 도메인은 context, ScenePlan, preset, template, copy, T2I policy에서 모두 처리되어야 한다.
- preset의 `business_type`은 `ScenePlan.BusinessType`과 항상 호환되어야 한다.
- `generic` fallback은 의도된 fallback인지, 누락으로 인한 증발인지 구분되어야 한다.
- 같은 요청에서 template과 preset이 서로 다른 도메인을 가리키면 테스트가 실패해야 한다.

따라서 현재 테스트 통과는 "구조가 안전하다"는 의미가 아니라, "구조적 불일치를 검출하는 테스트가 아직 부족하다"는 의미에 가깝다.

## SSOT가 해결하는 것과 해결하지 못하는 것

### SSOT가 해결하는 것

SSOT는 다음 문제를 줄인다.

- 업종 값이 파일마다 다르게 쓰이는 문제
- 지원 도메인이 어떤 레이어에서는 있고 어떤 레이어에서는 사라지는 문제
- 새 도메인 추가 시 수정 누락이 생기는 문제
- `generic` fallback이 의도인지 누락인지 알 수 없는 문제
- 프리셋, 템플릿, 카피, negative prompt가 서로 다른 키로 움직이는 문제
- 테스트로 지원 도메인의 최소 연결성을 강제할 수 없는 문제

즉, SSOT는 "같은 말을 같은 이름으로 부르게 만드는 기반"이다.

### SSOT만으로 해결되지 않는 것

SSOT만 한다고 이미지가 자동으로 유연해지는 것은 아니다.

별도로 해결해야 하는 문제가 있다.

- 사용자 요청을 정확히 해석하는 문제
- 업종, 상품/서비스, 씬, 요리 종류, 무드, 광고 목적을 분리하는 문제
- 예: `restaurant` 안에서도 BBQ, 파스타, 도시락, 디저트, 한식은 서로 다른 비주얼 전략이 필요하다.
- 예: `beauty` 안에서도 헤어, 네일, 스킨케어, 스파는 다른 피사체와 금지 요소가 필요하다.
- reference image와 사용자 업로드 이미지를 얼마나 우선할지 정하는 문제
- 생성 모델이 프롬프트를 실제 이미지에서 잘 따르는지 평가하는 문제
- 프리셋 자체가 충분히 풍부한지 검증하는 문제

따라서 SSOT는 충분조건이 아니라 필요조건이다.

## 목표 구조

목표는 단일 `business_type` 문자열 하나로 모든 것을 해결하려는 구조가 아니다. 최소한 아래 축을 분리해야 한다.

```text
User request / context / reference
  -> DomainResolution
       canonical_business_type
       product_or_service
       visual_scene_type
       style_or_mood
       ad_goal
       confidence
       fallback_reason
       evidence
  -> VisualStrategy
       template
       preset
       subject strategy
       composition
       forbidden elements
       negative prompt policy
  -> Prompt / Copy / T2I adapters
```

핵심은 `business_type`을 만능 키로 쓰지 않는 것이다.

권장 분리:

- `canonical_business_type`: cafe, restaurant, beauty, fitness, retail, education, service, etc.
- `business_subtype`: beauty_hair, beauty_nail, beauty_skincare, gym_pt, language_class 등
- `visual_scene_type`: bbq_grill, plated_food, product_packshot, salon_interior, skincare_product, fitness_training 등
- `ad_goal`: reservation, product_detail, visit_increase, discount_event, brand_awareness 등
- `style_profile`: premium, clean, cute, bold, editorial 등

이렇게 해야 "음식점"이라는 업종과 "숯불구이"라는 씬을 섞지 않고 다룰 수 있다.

## 권장 진행 순서

### Phase 0. 현재 동작을 고정하는 진단 테스트 추가

먼저 현재 버그를 고치기 전에, 지금 구조의 위험을 재현하는 테스트를 만든다.

필수 테스트:

- `BriefBusinessType` 전체 값이 context 라우팅에서 어떻게 처리되는지 표로 검증
- 모든 visual preset의 `business_type`이 `ScenePlan.BusinessType`과 호환되는지 검증
- 대표 입력별 preset/template/copy policy 결과가 같은 canonical domain을 공유하는지 검증
- `generic` fallback이 발생할 때 fallback reason이 남는지 검증
- 실제 `image_prompt_planner` 경로에서 `restaurant + 삼겹살/참숯`이 기대한 scene으로 가는지 검증

목표는 "리팩터링 전에 깨지는 지점을 눈으로 보이게 만드는 것"이다.

### Phase 1. Canonical taxonomy와 alias SSOT 도입

새 모듈을 만든다.

예시:

```text
orchestrator/app/llm/domain_routing.py
```

여기에는 다음을 둔다.

- canonical business type enum 또는 Literal
- alias map
- 지원 도메인 목록
- `normalize_business_type(value)` 함수
- `is_supported_business_type(value)` 함수
- fallback policy

처음부터 모든 라우팅을 갈아엎지 말고, 기존 값들을 이 모듈을 통해 normalize하도록 만든다.

중요 원칙:

- 정확 일치 우선
- substring 매칭은 fallback에서만 제한적으로 사용
- fallback은 조용히 `generic`으로 보내지 말고 reason을 남김
- `beauty_salon`, `beauty`, `salon` 같은 애매한 값은 명시적으로 처리

### Phase 2. Visual preset/template 입력을 같은 resolved key로 통일

현재는 template은 raw `context.business_type`을 보고, preset은 `resolve_business_type` 결과를 본다. 이 차이가 불일치의 핵심이다.

개선 방향:

```text
resolve_domain_context(...)
  -> resolved domain object
  -> select_visual_template(resolved)
  -> select_visual_preset(resolved)
```

즉 template과 preset이 같은 resolved object를 소비해야 한다.

이 단계에서는 두 시스템을 당장 하나로 합치지 않아도 된다. 다만 둘이 같은 기준을 보도록 만들어야 한다.

### Phase 3. 업종과 비주얼 씬을 분리

`restaurant_bbq`처럼 업종과 씬이 섞인 값은 장기적으로 분리해야 한다.

권장 모델:

```text
canonical_business_type = "restaurant"
visual_scene_type = "bbq_grill"
```

마찬가지로:

```text
canonical_business_type = "beauty"
business_subtype = "hair"
visual_scene_type = "salon_interior"
```

이렇게 분리하면 `restaurant`의 카피 정책은 음식점 일반을 유지하면서, 비주얼만 BBQ grill scene으로 보낼 수 있다.

### Phase 4. 도메인별 최소 비주얼 전략 채우기

SSOT가 생긴 뒤에는 지원 도메인별 최소 전략을 채워야 한다.

우선순위 후보:

- cafe
- restaurant
- beauty
- fitness
- retail
- education
- service

각 도메인마다 최소한 다음이 있어야 한다.

- visual template
- visual preset 또는 visual strategy
- negative prompt policy
- copy tone policy
- grounding domain terms
- 대표 fixture 입력
- expected metadata

도메인을 완벽하게 많이 늘리는 것보다, 적은 도메인이라도 end-to-end로 빠짐없이 연결하는 것이 먼저다.

### Phase 5. 실제 생성 평가 루프 추가

라우팅이 정리되어도 모델 출력이 원하는 방향으로 나오는지는 별도 문제다.

따라서 대표 fixture를 두고 주기적으로 확인해야 한다.

예시 fixture:

- cafe: 딸기라떼 신메뉴
- restaurant: 파스타 런치 세트
- restaurant + bbq scene: 참숯 삼겹살
- beauty hair: 헤어 스타일링 예약
- beauty skincare: 피부관리 앰플 케어
- fitness: PT 모집
- retail: 상품 할인
- education: 원데이 클래스

검증 항목:

- metadata 라우팅이 기대값과 일치하는가
- prompt에 도메인/상품/씬 신호가 명확한가
- 금지 요소가 도메인에 맞는가
- 실제 이미지가 도메인답게 보이는가
- 텍스트 오버레이 영역이 유지되는가

## 다음 작업의 성공 기준

이 공사의 1차 성공 기준은 "이미지 품질이 즉시 좋아졌다"가 아니다. 1차 성공 기준은 다음이다.

- 지원 도메인 목록이 한 곳에서 확인된다.
- 새 도메인을 추가할 때 수정해야 할 위치가 명확하다.
- 각 도메인이 preset/template/copy/T2I policy 중 어디까지 지원되는지 테스트로 확인된다.
- 누락된 도메인은 조용히 `generic`으로 증발하지 않고 reason을 남긴다.
- 같은 요청에서 template과 preset이 서로 다른 도메인으로 갈라지는 일이 테스트에서 잡힌다.
- `business_type`과 `visual_scene_type`의 책임이 분리되기 시작한다.

2차 성공 기준은 다음이다.

- `fitness`, `retail`, `education`, `service` 요청이 generic이 아니라 각 도메인다운 기본 이미지 전략으로 간다.
- `restaurant + BBQ 키워드`는 업종은 restaurant, 비주얼 씬은 bbq_grill로 처리된다.
- `beauty_salon` 같은 애매한 값은 hair/skincare/nail/spa 중 evidence 기반으로 결정되거나, fallback reason이 남는다.
- reference template 선택 시 context와 비주얼 전략이 서로 충돌하지 않는다.

## 팀에서 먼저 합의해야 할 결정

아래 결정이 필요하다.

1. `business_type`의 canonical 목록을 어디까지 1차 지원할 것인가?
2. `restaurant_bbq`를 유지할 것인가, 아니면 `restaurant + bbq_grill scene`으로 분리할 것인가?
3. `beauty_salon`의 기본 fallback을 skincare로 둘 것인가, ambiguous로 두고 추가 evidence를 요구할 것인가?
4. `fitness`, `retail`, `education`, `service`를 당장 지원 도메인으로 볼 것인가, 아니면 명시적 generic 위임으로 둘 것인가?
5. reference template의 `business_types`는 canonical business type만 담을 것인가, scene/style tag도 함께 담을 것인가?

## 추천안

추천은 큰 리팩터링 한 번으로 갈아엎는 방식이 아니다.

가장 좋은 순서는 다음이다.

1. 현재 불일치를 재현하는 contract test를 먼저 추가한다.
2. `domain_routing.py` 같은 작은 SSOT 모듈을 만든다.
3. 기존 라우터들을 바로 삭제하지 말고, normalize 함수와 resolved object를 경유하게 만든다.
4. template과 preset이 같은 resolved object를 보게 만든다.
5. `business_type`과 `visual_scene_type`을 분리한다.
6. 도메인별 fixture로 실제 prompt와 이미지 결과를 검증한다.

이 순서가 좋은 이유는, 기능을 한 번에 멈추지 않으면서도 지금의 구조적 혼선을 테스트 가능한 계약으로 바꿀 수 있기 때문이다.

## 최종 정리

이 공사의 목적은 "하드코딩을 모두 없애자"가 아니다. 광고 생성 시스템에는 도메인별 정책과 프리셋이 어느 정도 필요하다.

진짜 목적은 다음이다.

- 하드코딩을 흩어진 문자열 분기에서 관리 가능한 정책 레이어로 올린다.
- 업종, 상품, 씬, 무드, 광고 목적을 분리한다.
- fallback을 숨기지 않고 관측 가능하게 만든다.
- 새 도메인을 추가할 때 누락을 테스트가 잡게 만든다.
- 최종 이미지 프롬프트가 하나의 일관된 비주얼 전략을 갖게 만든다.

그래야 이후에 모델 개선, 레퍼런스 이미지, 도메인 확장, 카피 정책 개선이 서로 발목을 잡지 않고 같은 방향으로 쌓일 수 있다.
