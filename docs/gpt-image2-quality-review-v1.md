# GPT-image-2 Actual Quality Review v1

## 1. Review Summary

This review evaluates the first successful GPT-image-2 actual quality batch for EasyAds.

Input batch report:

```text
data/logs/gpt_image2_quality_batch_v1_20260601T140750Z.json
```

Batch result:

```text
batch_status=success
actual_generation=True
total_success=3
total_failed=0
```

Reviewed cases:

```text
cafe_dessert_001
restaurant_bbq_001
beauty_salon_001
```

Overall conclusion:

```text
GPT-image-2 is usable as the premium API lane for MVP advertising background generation.
The strongest result is restaurant_bbq_001.
The most broadly demo-safe result is cafe_dessert_001.
The case that needs the most prompt/template refinement is beauty_salon_001 because the generated image includes a human model and skincare-product context, which may be less stable for generic beauty-salon advertising.
```

Across all three images, GPT-image-2 followed the most important production constraint: it created clean advertising backgrounds without visible fake text, signs, logos, watermarks, or broken typography. It also generally reserved a usable empty area for later Korean text overlay.

The next ImagePrompt v3 work should focus less on basic generation feasibility and more on tighter control of subject placement, reference alignment, product specificity, and reusable text-safe zones.

---

## 2. Input Report

| Field | Value |
|---|---|
| Report JSON | `data/logs/gpt_image2_quality_batch_v1_20260601T140750Z.json` |
| Report MD | `data/logs/gpt_image2_quality_batch_v1_20260601T140750Z.md` |
| Actual generation | `true` |
| Total success | `3` |
| Total failed | `0` |
| Additional API/model calls during review | `none` |

Runtime artifact policy:

```text
data/logs/ and data/outputs/ are runtime artifacts and must not be committed.
Only this review document should be committed.
```

---

## 3. Case Review

### 3.1 cafe_dessert_001

| Field | Value |
|---|---|
| Job ID | `job_3b95924644ed444484549dff791aa026` |
| Status | `done` |
| Final Image Path | `data/outputs/job_3b95924644ed444484549dff791aa026/final_0.png` |
| Selected Reference Template | 확인 필요: latest JSON report의 `selected_reference_template_id` / `selected_reference_template_title` 값 사용 |
| Visual Template | expected: `cafe_dessert_soft_premium` |
| Business Type | `cafe` |
| Ad Format | `instagram_feed` |

#### Manual Score

| Metric | Score | Notes |
|---|---:|---|
| Advertising fit | 5 | 딸기라떼 신메뉴 광고 배경으로 바로 사용 가능한 수준. 상품, 색감, 계절감, 여백이 명확함. |
| Visual quality | 5 | 조명, 피사체 선명도, 색 조합, 제품 배치가 안정적임. |
| Not tacky | 5 | 저가 전단지 느낌 없이 프리미엄 카페/디저트 무드가 잘 유지됨. |
| Text safe area | 5 | 좌측 상단~중앙에 넓고 깨끗한 여백이 있어 한글 headline/subcopy overlay에 적합함. |
| Reference alignment | 4 | soft premium, dessert, pastel mood는 잘 맞음. 단, reference template id 확인 후 alignment는 재검증 필요. |
| Business fit | 5 | 카페/디저트 업종 적합성이 매우 높음. |
| Fake text/logo risk | 5 | 이미지 안에 가짜 글자, 로고, 간판, 워터마크가 보이지 않음. |
| Copy-visual fit | 5 | 딸기라떼, 신메뉴, 시즌성, 감성형 카피와 잘 맞음. |
| MVP usable | yes | MVP 대표 샘플로 사용 가능. |

#### Observations

- 가장 demo-safe한 결과다.
- 좌측 빈 공간이 넓고 배경이 단순해 post-render text overlay에 적합하다.
- 제품 피사체가 우측에 명확하게 있고, 딸기/핑크 배경/꽃 소품이 카페 디저트 광고로 읽힌다.
- 지나치게 stock-like하긴 하지만, MVP 광고 배경 기준에서는 오히려 안정적이다.

#### Failure Types

```text
[]
```

#### ImagePrompt v3 Notes

- Cafe/dessert template은 현재 방향 유지 가능.
- v3에서는 “left-side clean empty space” 또는 “large clean text-safe area on the left” 지시를 명시적으로 유지하는 것이 좋다.
- 단, 너무 유사한 pastel/strawberry stock composition만 반복되지 않도록 style variation을 2~3개로 분기할 필요가 있다.

---

### 3.2 restaurant_bbq_001

| Field | Value |
|---|---|
| Job ID | `job_f9910dae111a4c259646957f8b1ec26b` |
| Status | `done` |
| Final Image Path | `data/outputs/job_f9910dae111a4c259646957f8b1ec26b/final_0.png` |
| Selected Reference Template | 확인 필요: latest JSON report의 `selected_reference_template_id` / `selected_reference_template_title` 값 사용 |
| Visual Template | expected: `restaurant_bbq_warm_grill` |
| Business Type | `restaurant` / `bbq` |
| Ad Format | `instagram_feed` |

#### Manual Score

| Metric | Score | Notes |
|---|---:|---|
| Advertising fit | 5 | 프리미엄 고깃집 광고 배경으로 강하게 작동함. 숯불, 고기, 반찬, 따뜻한 조명 구성이 명확함. |
| Visual quality | 5 | 구도, 질감, 조명, 음식 표현이 매우 좋음. |
| Not tacky | 5 | 저가 이벤트 전단지 느낌 없이 고급 고깃집 무드가 잘 나옴. |
| Text safe area | 5 | 좌측 절반이 어두운 단색 질감 배경이라 흰색/크림색 카피 overlay에 매우 적합함. |
| Reference alignment | 4 | warm grill, premium restaurant mood는 잘 맞음. reference id 확인 후 재검증 필요. |
| Business fit | 5 | 업종 적합성이 가장 높음. |
| Fake text/logo risk | 5 | 가짜 글자, 간판, 로고, 워터마크가 보이지 않음. |
| Copy-visual fit | 5 | 회식/예약/방문 유도, 프리미엄 고깃집 카피와 매우 잘 맞음. |
| MVP usable | yes | 가장 강한 품질의 case. 대표 결과물 후보. |

#### Observations

- 세 case 중 광고 배경 완성도가 가장 높다.
- 좌측 dark empty area가 text-safe area로 매우 좋다.
- 우측 음식 피사체가 강하고, 중앙이 비어 있어 시선 흐름이 안정적이다.
- 이미지 자체가 너무 완성되어 있어서 텍스트 overlay를 크게 넣어도 잘 버틸 가능성이 높다.

#### Failure Types

```text
[]
```

#### ImagePrompt v3 Notes

- Restaurant/BBQ template은 v3에서 우선 유지할 가치가 높다.
- “dark clean negative space on the left” 패턴은 한글 overlay에 특히 적합하다.
- 후속 개선에서는 식당 업종을 `premium BBQ`, `casual Korean restaurant`, `event promotion`으로 분기하면 좋다.

---

### 3.3 beauty_salon_001

| Field | Value |
|---|---|
| Job ID | `job_184d5532e4204dc9af5709391c10788b` |
| Status | `done` |
| Final Image Path | `data/outputs/job_184d5532e4204dc9af5709391c10788b/final_0.png` |
| Selected Reference Template | 확인 필요: latest JSON report의 `selected_reference_template_id` / `selected_reference_template_title` 값 사용 |
| Visual Template | expected: `beauty_salon_clean_pastel` |
| Business Type | `beauty` / `salon` |
| Ad Format | `instagram_feed` |

#### Manual Score

| Metric | Score | Notes |
|---|---:|---|
| Advertising fit | 4 | 뷰티/스킨케어 광고로는 좋으나, “미용실/뷰티살롱” 범위에서는 스킨케어 제품 광고에 더 가까워 보임. |
| Visual quality | 5 | 인물, 조명, 피부 표현, 배경 품질이 높음. |
| Not tacky | 5 | 깨끗하고 프리미엄한 무드가 유지됨. |
| Text safe area | 4 | 좌측 상단~중앙에 넓은 여백이 있으나, 배경 광량과 곡선 요소 때문에 텍스트 대비 설계가 필요함. |
| Reference alignment | 3 | clean/pastel premium mood는 맞지만, human model 중심이라 generic salon template과는 다소 어긋날 수 있음. |
| Business fit | 4 | 뷰티 업종에는 적합. 헤어살롱보다는 피부/에스테틱/스킨케어 쪽 적합성이 더 높음. |
| Fake text/logo risk | 5 | 가짜 글자, 로고, 워터마크는 보이지 않음. |
| Copy-visual fit | 4 | “상담 예약”, “프리미엄 케어”, “피부 관리” 카피와 잘 맞음. “미용실 컷/펌” 카피와는 약함. |
| MVP usable | borderline | 뷰티/스킨케어 샘플로는 사용 가능. 미용실 범용 샘플로는 조정 필요. |

#### Observations

- 이미지 품질 자체는 매우 높다.
- 다만 인물이 너무 강한 subject가 되어, 후속 텍스트와 브랜드 맥락에 따라 광고 의도가 흔들릴 수 있다.
- 제품 오브젝트가 있어서 뷰티살롱보다는 스킨케어/에스테틱 광고에 가깝다.
- 좌측 여백은 충분하지만 밝은 배경이므로 텍스트 plate 또는 shadow 처리가 필요할 수 있다.

#### Failure Types

```text
["weak_business_fit", "weak_reference_alignment"]
```

#### ImagePrompt v3 Notes

- beauty template은 `beauty_salon`, `skin_care`, `hair_salon`, `nail_salon`을 분리하는 것이 좋다.
- 미용실/헤어살롱 case에서는 인물 얼굴 클로즈업보다 salon interior, hair care tools, clean consultation desk, mirror space 같은 소재를 명시하는 편이 낫다.
- 사람 모델 사용 여부를 metadata/option으로 제어할 필요가 있다. 기본값은 `no human face` 또는 `optional human silhouette`로 두는 편이 안정적이다.

---

## 4. Cross-case Findings

### Strengths

- GPT-image-2는 3개 업종 모두에서 광고 배경으로 쓸 수 있는 수준의 고품질 이미지를 생성했다.
- 세 case 모두 이미지 안에 가짜 텍스트, 로고, 워터마크가 보이지 않았다.
- text-safe area 지시는 잘 반영됐다. 특히 cafe와 restaurant case는 바로 headline/subcopy/CTA를 얹을 수 있는 수준이다.
- 업종별 visual tone은 대체로 잘 분리됐다.
  - Cafe: pastel, soft, dessert-focused
  - Restaurant: warm, premium, dark negative space
  - Beauty: clean, bright, premium skincare mood

### Repeated Problems

- 실제 reference template id/title이 review 문서에 자동 반영되지 않아 report JSON과 문서 간 수동 확인이 필요하다.
- Beauty case는 업종 범위가 넓어서 prompt가 “미용실”보다 “스킨케어/에스테틱” 쪽으로 치우쳤다.
- 모든 결과가 다소 stock-image스럽다. MVP에는 안정적이지만, 차별화된 광고 템플릿 느낌은 아직 부족하다.
- Reference alignment는 이미지 자체만 보고는 완전 검증이 어렵다. 선택 reference thumbnail/preview와 나란히 비교하는 review UI 또는 report field가 필요하다.

### Most Usable Case

```text
restaurant_bbq_001
```

이유:

- 상품/업종/무드/텍스트 여백이 가장 명확하다.
- 어두운 좌측 negative space가 한글 광고 카피 overlay에 매우 적합하다.
- 예약/방문 유도형 광고로 바로 사용 가능한 구도다.

### Most Demo-safe Case

```text
cafe_dessert_001
```

이유:

- 밝고 호감도가 높으며, 가짜 텍스트 리스크가 없다.
- 좌측 여백이 넓어 FE result binding / TextRenderer 시연에 가장 안전하다.
- 카페 신메뉴 광고라는 목적이 즉시 읽힌다.

### Least Usable Case

```text
beauty_salon_001
```

이유:

- 품질은 높지만, 미용실/뷰티살롱보다 스킨케어/에스테틱 광고에 더 가깝다.
- 인물 모델이 강해서 범용 비즈니스 광고 템플릿으로는 재사용성이 떨어질 수 있다.
- 텍스트 overlay는 가능하지만 밝은 배경 때문에 plate/shadow 정책이 필요하다.

### Overall MVP Readiness

```text
MVP-ready with constraints.
```

GPT-image-2 premium API lane은 MVP demo용 광고 배경 생성에 충분히 사용할 수 있다. 다만 v3에서는 업종별 prompt 세분화와 reference alignment 검증이 필요하다.

---

## 5. ImagePrompt v3 Improvement Candidates

### 1. Positive Prompt

Current issue:

- 현재 prompt는 광고 배경 생성에는 충분하지만, 업종 세부 타입을 강하게 분리하지 않는다.
- Beauty case처럼 넓은 업종에서는 모델이 스킨케어, 에스테틱, 화장품, 미용실을 혼합할 수 있다.

Suggested direction:

- `business_subtype` 또는 `visual_subtype`을 prompt에 반영한다.
- 예:
  - `beauty_salon_hair`
  - `beauty_skin_care`
  - `beauty_nail`
  - `restaurant_bbq_premium`
  - `restaurant_event_promotion`
  - `cafe_dessert_seasonal`
- 각 subtype별로 subject/material/lighting/background를 분리한다.

### 2. Negative Prompt

Current issue:

- 이번 batch에서는 fake text가 발생하지 않았지만, 계속 유지해야 하는 핵심 제약이다.
- 사람 모델이나 화장품 패키지에서 브랜드명/라벨이 생길 가능성은 여전히 있다.

Suggested direction:

- 기존 text-free negative prompt 유지.
- Beauty/human/product-heavy case에서는 아래를 강화한다.

```text
no brand labels, no product labels, no readable packaging, no signage, no typography, no letters, no numbers, no watermark, no logo
```

### 3. Business-specific Visual Templates

Cafe:

- 현재 `cafe_dessert_soft_premium` 방향 유지.
- 추가 variation:
  - `cafe_minimal_white_table`
  - `cafe_seasonal_pastel`
  - `cafe_dark_premium_coffee`
- 좌측 또는 상단 text-safe area를 명시적으로 유지한다.

Restaurant:

- `restaurant_bbq_warm_grill`은 매우 우수.
- v3에서는 아래 분기를 추가한다.
  - `restaurant_bbq_dark_negative_space`
  - `restaurant_korean_table_full_set`
  - `restaurant_event_clean_banner`
- dark background + side subject 패턴을 재사용한다.

Beauty:

- 현재 template은 스킨케어 광고에는 좋지만 hair salon에는 약함.
- 분기 필요:
  - `beauty_skin_care_clean_premium`
  - `beauty_hair_salon_interior_clean`
  - `beauty_nail_pastel_detail`
- 기본값에서는 human face 사용을 옵션화한다.
  - `include_human_model=false`
  - `include_product_packaging=false`
  - `focus_on_clean_salon_background=true`

### 4. Reference Alignment

Current issue:

- selected reference id/title이 review 문서에 바로 노출되지 않아 alignment 판단이 불완전하다.
- 생성 이미지와 reference preview를 side-by-side로 보지 않으면 alignment를 수동 평가하기 어렵다.

Suggested direction:

- quality batch report에 `selected_reference_template_id`, `selected_reference_template_title`, `thumbnail_url`, `preview_url` 또는 최소 `style_keywords`를 명확히 포함한다.
- review 문서 generator 또는 FE debug panel에서 generated image와 reference preview를 같이 보여준다.
- prompt에는 reference 전체 metadata를 넣기보다 아래 핵심만 압축한다.
  - layout hint
  - background style
  - palette
  - subject placement
  - text-safe area direction

### 5. Text Safe Area

Current issue:

- GPT-image-2는 넓은 여백을 잘 만들지만, 각 업종마다 여백 위치와 밝기가 다르다.
- Beauty case처럼 밝은 여백은 텍스트 대비가 약할 수 있다.

Suggested direction:

- prompt에 text-safe area 위치를 명시한다.
  - `large clean empty area on the left`
  - `dark clean negative space on the left`
  - `bright soft empty area with low texture`
- `TextStyleBinder` 또는 `TextRenderer`에서 배경 밝기 기반 plate/shadow를 자동 선택한다.
- result_payload의 layout_summary에 실제 recommended text color/plate 여부를 추가하는 것도 좋다.

### 6. Subject Focus / Composition

Current issue:

- Restaurant/cafe는 subject placement가 좋지만, beauty는 human model이 너무 강한 focal subject가 됐다.

Suggested direction:

- case별 subject focus를 명시한다.
  - Cafe: drink/product hero on right, empty left
  - Restaurant: grilled food on right/bottom-right, dark empty left
  - Beauty: salon interior or product-neutral clean background, optional human silhouette only
- v3에서 `subject_strength` 또는 `human_model_policy`를 metadata로 받는 구조를 고려한다.

---

## 6. Copy / Visual / Layout Improvement Candidates

### Copy

- Cafe:
  - 감성형 headline이 잘 맞는다.
  - 예: “오늘의 달콤한 한 잔”, “딸기라떼 시즌 오픈”
  - CTA는 부드럽게: “지금 만나보기”, “오늘 한 잔 예약하기”
- Restaurant:
  - 방문/예약 유도형 copy가 잘 맞는다.
  - 예: “회식은 역시 삼겹살”, “오늘 저녁, 따뜻하게 굽는 시간”
  - CTA는 직접적으로: “지금 예약하기”, “방문 예약하기”
- Beauty:
  - hair salon과 skincare copy를 분리해야 한다.
  - 현재 이미지는 “피부 케어”, “프리미엄 상담”, “나를 위한 관리” 쪽이 더 적합하다.
  - 미용실용 copy를 붙이면 visual mismatch가 생길 수 있다.

### Visual

- Cafe와 restaurant는 MVP visual template으로 채택 가능.
- Beauty는 `skin care / aesthetic` 샘플로는 사용 가능하지만, `hair salon` 범용 템플릿으로는 보류.
- 결과물의 stock-like 성격은 단점이지만, MVP에서는 안정성과 낮은 artifact risk 측면에서 장점도 있다.
- 다음 단계에서는 reference-guided uniqueness를 강화해야 한다.

### Layout

- Cafe:
  - 좌측 상단~중앙 headline, 하단 좌측 CTA가 적합.
  - 흰색/딥브라운 계열 텍스트 모두 가능.
- Restaurant:
  - 좌측 중앙 큰 headline, 좌측 하단 CTA가 적합.
  - 밝은 크림/화이트 텍스트가 어울림.
- Beauty:
  - 좌측 상단 headline은 가능하나 배경이 밝아 plate 또는 subtle shadow 필요.
  - 텍스트를 너무 크게 넣으면 프리미엄 무드가 깨질 수 있음.
- v3 이후 TextRenderer에서는 `text_safe_area_background_luminance` 기반으로 text color/plate를 자동 결정하는 것이 좋다.

---

## 7. Recommendation

### Immediate Decision

```text
GPT-image-2 premium API lane should remain the primary quality baseline for MVP advertising background generation.
```

### Recommended v3 Priority

```text
1. Keep cafe and restaurant templates mostly as-is.
2. Split beauty template into skincare / hair salon / nail salon variants.
3. Add explicit text-safe area position and brightness instructions.
4. Add human model policy for beauty-related prompts.
5. Add reference preview / generated result side-by-side review support.
```

### MVP Demo Candidates

```text
Primary:
- restaurant_bbq_001

Safe:
- cafe_dessert_001

Conditional:
- beauty_salon_001 as skincare/esthetic sample, not generic hair salon sample
```

---

## 8. Next Actions

```text
1. Commit GPT-image-2 quality batch runner and this review document.
2. Do not commit data/logs or data/outputs.
3. Start ImagePrompt v3 improvement based on this review.
4. In ImagePrompt v3, split beauty visual templates and strengthen text-safe area instructions.
5. After v3, rerun a small 3-case actual batch and compare before/after.
6. Then proceed to SD3.5 actual comparison and FLUX lane comparison.
```
