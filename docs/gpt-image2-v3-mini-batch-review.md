# GPT-image-2 v3 Mini Batch Review

**문서 목적:** GPT-image-2 v1과 v3 이미지 결과를 비교해, ImagePrompt v3가 실제 광고 배경 품질과 카피 후합성 가능성을 얼마나 개선했는지 평가한다.  
**범위:** `cafe`, `restaurant_bbq`, `beauty` 3개 case  
**중요 전제:** 이 문서는 정성 평가 문서이며, `data/logs/`, `data/outputs/`에 있는 런타임 산출물은 커밋하지 않는다.

---

## 1. Review Setup

이번 리뷰는 GPT-image-2로 생성한 v1/v3 결과를 비교한다. 단순히 “이미지가 예쁜가”가 아니라, 실제 광고 시안으로 쓸 수 있는지를 기준으로 평가한다.

평가 기준은 다음과 같다.

| Criterion | 의미 |
|---|---|
| `text_safe_area` | 한글 카피를 얹을 수 있는 안전한 여백이 충분한가 |
| `copy_overlay_usability` | headline/subcopy/CTA를 실제로 얹었을 때 읽기 쉬운가 |
| `business_fit` | 업종과 상품/서비스 맥락이 명확한가 |
| `fake_text_logo_risk` | 가짜 글자, 로고, 간판, 워터마크 위험이 낮은가 |
| `not_tacky` | 촌스럽거나 저가 전단지처럼 보이지 않는가 |
| `reference_alignment` | 의도한 reference/template 방향과 잘 맞는가 |
| `copy_visual_fit` | 카피 톤과 이미지 분위기가 자연스럽게 결합되는가 |
| `mvp_usable` | 현재 MVP 결과물로 바로 보여줄 수 있는가 |

---

## 2. Version Mapping

### v1 Outputs

| Case | v1 이미지 성격 |
|---|---|
| `beauty` | 모델, 거울, 화장품 병, 밝은 좌측 여백이 있는 clean skincare/mirror scene |
| `restaurant_bbq` | 좌측 어두운 여백과 우측 고기/불판이 분리된 premium grill table scene |
| `cafe` | 오른쪽 딸기라떼 제품과 왼쪽 넓은 핑크 여백이 있는 minimal strawberry latte product scene |

### v3 Outputs

| Case | v3 이미지 성격 |
|---|---|
| `beauty` | 커튼, 꽃, 살롱/스파 공간감, 인물 모델이 결합된 realistic salon/spa-style scene |
| `restaurant_bbq` | 고기, 집게, 연기, 반찬, 구리 후드가 더 사실적으로 배치된 Korean BBQ close-up scene |
| `cafe` | 딸기 음료, 배경 bokeh, 꽃, 제품 스타일링이 강화된 seasonal cafe campaign photo |

---

## 3. Executive Summary

v3는 전반적으로 **사진적 사실감, 공간감, 업종별 분위기, 상업 사진 느낌**이 개선되었다. v1이 “깨끗한 광고 템플릿”에 가깝다면, v3는 “실제 촬영된 광고 사진”에 가까워졌다.

다만 v3가 모든 기준에서 v1을 이긴 것은 아니다. v1은 더 평평하고 단순한 여백을 제공하기 때문에, `text_safe_area`와 deterministic overlay 관점에서는 더 안전한 경우가 많다. 특히 `beauty`와 `cafe`는 v1이 카피 후합성에는 더 안정적이다.

정확한 결론은 다음과 같다.

- **v1은 template-safe, copy-overlay-friendly baseline이다.**
- **v3는 photographic realism, premium mood, final visual appeal이 개선된 baseline이다.**
- **v3는 최종 광고 품질 면에서 더 유망하지만, CopyVisual validation을 필수로 붙여야 한다.**
- **v1의 큰 여백/단순 구도 제약은 v3에서도 일부 유지해야 한다.**

---

## 4. 왜 v3가 더 사실적으로 보이는가

v3 결과가 더 사실적으로 보이는 이유는 단순히 프롬프트 문장이 길어졌기 때문이 아니다. v3에서는 이미지 생성 프롬프트가 “예쁜 광고 배경” 수준에서 “실제 상업 사진을 찍는 장면 지시서”에 가까워졌다.

### 4.1 ScenePlan 도입

v3는 `ScenePlan`을 통해 다음 정보를 구조적으로 정리한다.

- 업종
- 핵심 피사체
- 피사체 위치
- 텍스트 여백 위치
- 보조 소품
- 조명
- 분위기
- 금지 요소

이로 인해 모델은 추상적인 “카페 광고 배경”이 아니라, “오른쪽에는 딸기 음료가 있고 왼쪽에는 한글 카피를 얹을 깨끗한 여백이 있는 프리미엄 상업 사진”에 가까운 장면을 생성하게 된다.

### 4.2 Business Visual Preset 강화

v3는 업종별 visual preset을 사용한다.

| Preset | 효과 |
|---|---|
| `cafe_dessert_soft_premium` | 파스텔 톤, 딸기, 부드러운 자연광, 우측 제품 히어로, 좌측 여백 |
| `restaurant_bbq_warm_grill` | 어두운 웜톤, 불판, 고기, 집게, 연기, 좌측 dark negative space |
| `beauty_*` subtype presets | skincare / hair / nail / spa 맥락 분리 |

이 구조 때문에 v3는 generic한 이미지보다 업종별 광고 촬영컷에 가까워졌다.

### 4.3 GPT-image-2 전용 Prompt Adapter

v3는 GPT-image-2가 이해하기 쉬운 creative brief형 prompt를 사용한다.

핵심 지시:

```text
text-free advertising background
intended for later Korean copy overlay
clean negative space
premium realistic commercial photography
no text, letters, numbers, signage, logo, watermark, typography
business-specific subject placement
```

이 adapter 때문에 GPT-image-2는 단순 키워드 나열보다 구도와 의도를 더 명확하게 해석한다.

### 4.4 텍스트 후합성 원칙 강화

v3는 이미지 모델이 한글 카피를 직접 그리지 않도록 강하게 제한한다. 이미지 모델은 배경과 피사체만 만들고, 실제 문구는 TextRenderer 또는 CopyVisual overlay 단계에서 후합성한다.

이 역할 분리는 이미지 품질을 안정화한다.

```text
이미지 모델 역할: 텍스트 없는 광고 배경 생성
TextRenderer 역할: headline / subcopy / CTA 후합성
Validation 역할: contrast / safe area / clipping 검증
```

### 4.5 금지 요소 강화

v3는 다음 요소를 더 강하게 억제한다.

- fake text
- fake logo
- signage
- watermark
- menu board
- price tag
- clutter
- cheap flyer mood
- tacky props

이 덕분에 v3는 더 “정돈된 상업 사진”처럼 보인다.

---

## 5. Score Summary

| Case | Version | text_safe_area | copy_overlay_usability | business_fit | fake_text_logo_risk | not_tacky | reference_alignment | copy_visual_fit | mvp_usable |
|---|---|---|---|---|---|---|---|---|---|
| beauty | v1 | Excellent | Excellent | Excellent | Excellent | Excellent | Excellent | Excellent | Excellent |
| beauty | v3 | Good | Good | Good | Excellent | Excellent | Good | Good | Good |
| restaurant_bbq | v1 | Excellent | Excellent | Excellent | Excellent | Excellent | Excellent | Excellent | Excellent |
| restaurant_bbq | v3 | Excellent | Excellent | Excellent | Excellent | Excellent | Excellent | Excellent | Excellent |
| cafe | v1 | Excellent | Excellent | Excellent | Excellent | Excellent | Excellent | Excellent | Excellent |
| cafe | v3 | Good | Good | Excellent | Excellent | Excellent | Excellent | Good | Excellent |

---

## 6. Case-by-Case Review

### 6.1 Beauty

#### v1 Observations

v1 beauty는 skincare/product ad template으로 매우 안정적이다. 좌측에 크고 깨끗한 밝은 여백이 있고, 우측에는 모델, 거울, 화장품 병, 꽃이 배치되어 있다.

장점:

- 좌측 `text_safe_area`가 매우 깨끗함
- skincare/product 광고 맥락이 명확함
- 제품, 모델, 카피 영역의 관계가 안정적임
- fake text/logo 위험이 낮음
- premium하고 clean한 분위기

약점:

- 실제 살롱/스파 공간감은 v3보다 약함
- 조금 더 template-like하게 보임

#### v3 Observations

v3 beauty는 더 사실적이고 분위기가 좋다. 커튼, 꽃, 실내 조명, 살롱/스파 배경이 들어가며 실제 상업 사진 같은 느낌이 강해졌다.

다만 business intent가 v1보다 넓게 읽힌다. v1은 skincare/product beauty로 명확하지만, v3는 beauty salon, spa, bridal beauty, premium care service로 더 넓게 해석된다.

장점:

- 더 사실적인 공간감
- 부드럽고 고급스러운 beauty/spa mood
- 인물과 실내 배경의 자연스러운 결합
- fake text/logo 위험 낮음
- 상업 사진 느낌 강화

약점:

- skincare product 광고로는 v1보다 덜 명확함
- 하단 꽃/커튼 요소 때문에 lower-left overlay는 조심해야 함
- copy placement는 upper-left 또는 mid-left 중심이 적합함

#### Beauty Evaluation

| Criterion | v1 | v3 | Notes |
|---|---|---|---|
| text_safe_area | Excellent | Good | v1은 좌측 여백이 더 평평하고 예측 가능함 |
| copy_overlay_usability | Excellent | Good | v3는 가능하지만 꽃/커튼 요소 때문에 검증 필요 |
| business_fit | Excellent | Good | v1은 skincare/product, v3는 salon/spa broader mood |
| fake_text_logo_risk | Excellent | Excellent | 둘 다 fake typography 위험 낮음 |
| not_tacky | Excellent | Excellent | 둘 다 premium, v3는 더 atmospheric |
| reference_alignment | Excellent | Good | skincare 기준 v1 우세, spa/salon 기준 v3 우세 |
| copy_visual_fit | Excellent | Good | v1이 제품/모델/카피 관계가 더 직접적 |
| mvp_usable | Excellent | Good | v3도 가능하지만 subtype routing 필요 |

**Beauty verdict:** v3는 현실감과 분위기를 개선했지만, skincare/product 광고 MVP 기준에서는 v1이 더 안전하다. v3는 `beauty_spa`, `beauty_salon`, `premium care service`에 더 적합하다.

---

### 6.2 Restaurant BBQ

#### v1 Observations

v1 restaurant BBQ는 이미 강하다. 좌측에 넓은 dark negative space가 있고, 우측에 고기와 불판, 반찬이 배치되어 있어 카피 후합성에 유리하다.

장점:

- 좌측 어두운 카피 여백이 매우 좋음
- 한식 고깃집 맥락이 명확함
- premium하고 non-tacky함
- light-colored text overlay에 적합함
- visual hierarchy가 안정적임

약점:

- v3보다 약간 template-like함
- 깊이감과 현장감은 v3보다 낮음

#### v3 Observations

v3 restaurant BBQ는 v3 중 가장 성공적인 case다. 고기 질감, 집게, 연기, 후드, 반찬, 조명이 더 사실적으로 구성되었고, 좌측 dark copy area도 유지된다.

장점:

- 고기와 연기의 현실감 개선
- 프리미엄 고깃집 분위기 강화
- 좌측 copy safe area 유지
- food appetite appeal 강화
- fake text/logo 위험 낮음
- v1보다 완성된 commercial photo 느낌

약점:

- grill/smoke 근처에는 copy를 두면 안 됨
- 오른쪽 영역은 시각 요소가 많아 좌측 고정 overlay가 필요함

#### Restaurant BBQ Evaluation

| Criterion | v1 | v3 | Notes |
|---|---|---|---|
| text_safe_area | Excellent | Excellent | 둘 다 좌측 dark copy zone 제공 |
| copy_overlay_usability | Excellent | Excellent | v3는 현실감이 올라가도 여백을 유지함 |
| business_fit | Excellent | Excellent | 둘 다 명확한 Korean BBQ |
| fake_text_logo_risk | Excellent | Excellent | fake text/logo 위험 낮음 |
| not_tacky | Excellent | Excellent | v3가 더 premium하고 natural |
| reference_alignment | Excellent | Excellent | v3는 premium BBQ commercial photography에 더 가까움 |
| copy_visual_fit | Excellent | Excellent | copy/image separation이 잘 유지됨 |
| mvp_usable | Excellent | Excellent | v3는 production-leaning MVP quality |

**Restaurant BBQ verdict:** v3가 명확한 업그레이드다. v1의 copy-safe area 장점을 유지하면서 사실감과 식욕 자극을 개선했다.

---

### 6.3 Cafe

#### v1 Observations

v1 cafe는 매우 안전한 광고 배경이다. 오른쪽에 딸기라떼 제품이 있고, 왼쪽은 평평한 핑크 여백으로 남아 있어 카피 overlay가 매우 쉽다.

장점:

- `text_safe_area`가 매우 좋음
- 제품 hero가 명확함
- strawberry cafe/menu promotion 맥락이 분명함
- visual noise가 거의 없음
- 한글 overlay에 매우 안정적

약점:

- 조금 단순하고 template-like함
- 실제 campaign photo보다 생성 mockup처럼 느껴질 수 있음
- 깊이감과 계절감은 v3보다 약함

#### v3 Observations

v3 cafe는 더 자연스럽고 감성적인 seasonal campaign photo에 가깝다. 음료, 딸기, 꽃, bokeh, 배경 심도가 더 풍부하다.

하지만 v3는 v1보다 배경 정보량이 많다. 좌측 여백은 여전히 충분하지만, gradient, bokeh, floral blur 때문에 overlay validation이 필요하다.

장점:

- 더 사실적인 제품 촬영 느낌
- 계절감과 감성 강화
- premium cafe campaign mood
- strawberry beverage business fit 명확
- fake text/logo 위험 낮음

약점:

- v1보다 copy zone이 덜 flat함
- floral/bokeh 영역을 피한 overlay가 필요함
- CopyVisual validation 없이 바로 쓰기에는 v1보다 조심해야 함

#### Cafe Evaluation

| Criterion | v1 | v3 | Notes |
|---|---|---|---|
| text_safe_area | Excellent | Good | v1은 더 평평하고 깨끗한 copy area |
| copy_overlay_usability | Excellent | Good | v3도 가능하지만 배경 디테일이 증가함 |
| business_fit | Excellent | Excellent | 둘 다 strawberry cafe promotion에 적합 |
| fake_text_logo_risk | Excellent | Excellent | 둘 다 fake text/logo 위험 낮음 |
| not_tacky | Excellent | Excellent | v3가 더 premium하고 natural |
| reference_alignment | Excellent | Excellent | v3가 seasonal commercial photography에 더 가까움 |
| copy_visual_fit | Excellent | Good | v1은 안정적, v3는 검증 기반 placement 필요 |
| mvp_usable | Excellent | Excellent | v1은 안전, v3는 더 polished |

**Cafe verdict:** v3는 최종 visual appeal이 좋아졌고 더 실제 광고 사진 같다. 다만 deterministic overlay safety는 v1이 더 높다.

---

## 7. Cross-Case Findings

### 7.1 text_safe_area

v1은 더 강한 `text_safe_area`를 제공한다. v1은 여백이 평평하고 단순해서, 카피를 얹었을 때 실패할 가능성이 낮다.

v3는 여백 자체는 유지하지만, 더 많은 환경 요소와 심도, gradient, 꽃, 커튼, bokeh가 들어가므로 overlay safety가 case별로 달라진다.

결론:

```text
v1 = strict layout safety
v3 = realism + validation-dependent layout safety
```

### 7.2 copy_overlay_usability

v1은 바로 overlay하기 쉽다. v3는 CopyVisual validation과 함께 써야 한다.

v3 권장 overlay 위치:

| Case | 추천 위치 |
|---|---|
| beauty | upper-left 또는 mid-left, lower-left 꽃/커튼 회피 |
| restaurant_bbq | left side 고정, grill/smoke/food 회피 |
| cafe | left 또는 upper-left, product/floral/bokeh 회피 |

### 7.3 business_fit

v3는 업종 분위기를 더 잘 만든다. 특히 restaurant와 cafe는 v3가 더 자연스럽고 상업 사진스럽다.

Beauty는 subtype에 따라 다르다.

```text
beauty_skincare/product ad → v1 우세
beauty_spa/salon/service ad → v3 우세
```

### 7.4 fake_text_logo_risk

v1/v3 모두 우수하다. fake text, logo, signage, watermark, broken typography는 관찰되지 않았다. no-text-in-image 정책은 유지되고 있다.

### 7.5 not_tacky

v3는 더 natural하고 premium하다. v1은 clean하고 controlled하다. v3의 위험은 tacky함이 아니라 composition complexity 증가다.

### 7.6 reference_alignment

v3는 realistic ad photography reference와 더 잘 맞는다. 특히 BBQ와 cafe에서 조명, 피사체, 공간감이 개선되었다.

Beauty는 목표 reference에 따라 달라진다.

### 7.7 copy_visual_fit

v1은 copy/image separation이 매우 강하다. v3는 visual quality가 높지만, overlay placement가 더 중요하다.

즉, v3를 baseline으로 쓰려면 CopyVisual loop가 필수다.

### 7.8 mvp_usable

둘 다 MVP usable이다. 단, 의미가 다르다.

```text
v1 MVP usable:
- 안전하고 단순하며 overlay 실패율이 낮다.

v3 MVP usable:
- 더 사실적이고 매력적이지만 validation 기반 운영이 필요하다.
```

---

## 8. Final Conclusion

v3 mini batch는 실제 이미지 품질을 개선했다. 특히 다음 부분에서 개선이 명확하다.

- photographic realism
- natural commercial mood
- business-specific atmosphere
- depth and lighting
- less rigid template feeling
- final ad visual appeal

하지만 v3의 개선은 “더 안전한 카피 여백”이 아니라 “더 완성도 높은 광고 사진” 쪽이다. strict overlay predictability는 v1이 더 강하다.

### Final verdict by case

#### Beauty

- **v1 wins for skincare/product ad usability.**
- **v3 wins for salon/spa atmosphere and realism.**
- 결정: v3 방향은 유지하되 beauty subtype routing을 더 엄격히 해야 한다.

#### Restaurant BBQ

- **v3 wins overall.**
- v1의 copy-safe area를 유지하면서 realism과 appetite appeal이 좋아졌다.
- 결정: v3를 baseline으로 채택해도 된다.

#### Cafe

- **v3 wins for final visual appeal.**
- **v1 wins for strict template safety.**
- 결정: v3를 baseline으로 쓰되, large clean negative space 제약을 더 강하게 유지해야 한다.

---

## 9. Why v1 Can Still Feel Better

팀원 평가에서 v1이 더 낫다는 의견이 나올 수 있다. 이 의견은 틀린 것이 아니다.

v1이 더 좋게 느껴지는 이유:

```text
1. 여백이 더 평평하고 안전하다.
2. 광고 템플릿으로 바로 쓰기 쉽다.
3. 피사체와 카피 영역이 더 강하게 분리된다.
4. 결과 예측 가능성이 높다.
5. overlay preview에서 실패 가능성이 낮다.
```

v3가 더 좋게 느껴지는 이유:

```text
1. 더 실제 촬영된 광고 사진 같다.
2. 조명과 심도가 자연스럽다.
3. 업종별 분위기가 더 풍부하다.
4. final visual appeal이 좋다.
5. 결과물이 덜 template-like하다.
```

따라서 둘 중 하나를 폐기하기보다, 다음 전략이 더 적절하다.

```text
v3의 realism을 baseline으로 가져간다.
v1의 copy-safe composition constraint를 v3 prompt에 다시 강화한다.
```

---

## 10. Recommendation

### 10.1 v3를 다음 baseline으로 사용

v3는 실제 서비스에서 더 매력적인 결과물을 만들 가능성이 높다. 특히 restaurant와 cafe는 v3 방향이 더 좋다.

### 10.2 v1-style layout safety를 보존

v3 prompt에 아래 제약을 더 강하게 넣어야 한다.

```text
large clean negative space
low-detail copy zone
no foreground objects in copy area
smooth uncluttered background for text overlay
clear separation between product hero and copy area
```

### 10.3 Beauty subtype routing 강화

Beauty는 반드시 subtype별로 다르게 가야 한다.

| Subtype | 권장 방향 |
|---|---|
| `beauty_skincare` | 제품, 거울, 깨끗한 스킨케어 공간, clinical premium |
| `beauty_hair` | 살롱 의자, 거울, 헤어 스타일링 공간, 과한 skincare 소품 금지 |
| `beauty_nail` | 손, 네일 테이블, 디테일 컷, 작은 소품 |
| `beauty_spa` | 커튼, 꽃, 부드러운 조명, 웰니스/휴식 분위기 |

### 10.4 CopyVisual validation 필수화

v3에서는 이미지가 더 풍부해졌기 때문에 overlay validation을 optional로 두면 안 된다.

필수 검증:

```text
contrast
safe_area_background_complexity
text_clipping
min_font_size
plate_required
shadow_required
copy_visual_fit
```

### 10.5 FE result binding 전 확인

FE result binding 재점검 전에 다음을 확인해야 한다.

```text
1. v3 final_0.png가 result_payload에 정확히 들어가는가
2. CopyVisual preview가 runtime artifact로 생성되는가
3. FE가 data/outputs path를 직접 쓰지 않는가
4. final_image_url/download_url이 null일 때 UI가 깨지지 않는가
5. R2/static serving 전까지 preview UX를 어떻게 처리할지 결정하는가
```

---

## 11. Prompt Improvement Candidates for v3.1

다음 v3.1 prompt에는 아래 개선을 반영한다.

### Global

```text
Use realistic commercial photography, but preserve a large flat low-detail copy zone.
Keep all foreground objects outside the reserved copy area.
Maintain clear separation between product/service hero and copy space.
Avoid visual clutter in the copy area.
No text, no letters, no signage, no logo, no watermark, no labels, no typography.
```

### Cafe

```text
Subject on the right or lower-right.
Left side should remain smooth pastel negative space.
Avoid flowers, cups, fruit, shadows, or bokeh inside the left copy zone.
Keep background detail concentrated around the product hero.
```

### Restaurant BBQ

```text
Keep dark warm left-side negative space.
Place grill, meat, tongs, smoke, and side dishes on the right.
Avoid smoke drifting into the left copy zone.
Maintain premium Korean BBQ mood, not cheap flyer mood.
```

### Beauty

```text
Use subtype-specific scene selection.
For skincare, keep product/mirror/clean counter visible.
For spa, curtain and floral elements are acceptable but not inside copy zone.
For hair salon, include salon chair/mirror/hair styling context.
Keep the reserved copy area bright, smooth, and uncluttered.
```

---

## 12. Next Steps

Recommended next steps:

```text
1. Commit this review document if needed:
   docs/gpt-image2-v3-mini-batch-review.md

2. Update ImagePrompt v3.1 constraints:
   - stronger copy-safe zone
   - no foreground overlap in copy area
   - beauty subtype routing refinement

3. Run CopyVisual overlay review on v3 outputs.

4. Compare overlay previews:
   - v1 final image + overlay
   - v3 final image + overlay

5. FE result binding 재점검:
   - actual result_payload
   - final_image_url/download_url null handling
   - copy button
   - mobile QA

6. Prepare DB/R2/static serving plan:
   - local data/outputs path를 FE에 노출하지 않기
   - R2 object key + public/signed URL로 전환
```

---

## 13. Commit Note

이 문서는 정성 평가 문서다.

커밋 가능:

```text
docs/gpt-image2-v3-mini-batch-review.md
```

커밋 금지:

```text
data/logs/
data/outputs/
*.png
*.jpg
*.webp
docs/api_key.env
.env
```
