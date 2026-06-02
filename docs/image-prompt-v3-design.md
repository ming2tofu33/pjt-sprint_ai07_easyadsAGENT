# ImagePrompt v3: ScenePlan + Engine Prompt Adapter + Business Visual Preset 설계서

## 1. 개요 및 목적
ImagePrompt v3의 주요 목적은 실제 T2I 이미지 생성 API를 추가로 호출하지 않고, 기존에 생성 완료된 GPT-image-2 actual quality batch v1 및 `docs/gpt-image2-quality-review-v1.md` 평가 결과를 기반으로 이미지 프롬프트 생성 파이프라인의 구조적 완성도를 높이는 것입니다. 

텍스트 제거 정책(no-text policy) 및 여백(copy-space) 확보의 일관성을 극대화하기 위해 결정론적 장면 설계안(`ScenePlan`)과 품질 제약 방침(`PromptQualityPolicy`), 그리고 타겟 엔진 맞춤형 프롬프트 생성기(`Engine Prompt Adapter`) 구조를 도입했습니다.

---

## 2. GPT-image-2 v1 Quality Review 반영 및 교훈
v1 actual lane 실행 결과로부터 획득한 세부 업종별 개선안을 이미지 프롬프트 v3에 적극 반영하였습니다.

- **Cafe (카페/디저트)**
  - **v1 평가**: 우측 피사체(딸기라떼 등) 배치와 좌측의 깨끗한 텍스트 여백 구성이 매우 안정적으로 나와 최우수 demo-safe 케이스로 선정되었습니다.
  - **v3 반영**: pastel pink / cream palette 기반의 부드러운 무드를 유지하고, 좌측/상단 여백을 명시하는 지침을 프리셋(`cafe_dessert_soft_premium`) 수준에서 더욱 공고히 하였습니다. 가짜 메뉴판, 텍스트 로고 및 가격표, 카페 간판 생성 방지 방침을 추가로 명시했습니다.
- **Restaurant BBQ (고깃집)**
  - **v1 평가**: 우측에 구워지는 고기 등의 음식 피사체를 배치하고 좌측 어두운 공간에 넓은 여백을 주어 한글 광고 카피 가독성이 가장 훌륭했습니다.
  - **v3 반영**: dark warm left-side negative space와 right-side grill hero 구조를 유지하도록 프리셋(`restaurant_bbq_warm_grill`)에 반영하였으며, 저가 전단지 느낌의 혼잡한 식탁 배열이나 임의의 가짜 텍스트 라벨 생성을 강력히 방어하도록 금지 규정을 고도화했습니다.
- **Beauty (뷰티/살롱)**
  - **v1 평가**: 높은 품질의 인물이 생성되었으나, 미용실(헤어살롱) 광고라기보다는 스킨케어/에스테틱 제품 광고에 치우친 점과 지나치게 강한 모델 중심 구도가 광고 범용 템플릿으로서 한계를 가졌습니다.
  - **v3 반영**: `beauty_salon` 단일 프리셋 구조를 탈피하고 하위 타입을 4가지(`beauty_skincare`, `beauty_hair`, `beauty_nail`, `beauty_spa`)로 완전히 분리하였습니다.
    - `beauty_hair`: 인물의 강한 클로즈업보다 살롱 인테리어, 경판(거울) 공간, 미용 의자 및 가위/빗 등 헤어 도구 위주로 묘사하여 미용실 적합성을 높였습니다.
    - `beauty_skincare` / `beauty_spa`: 부드러운 분위기와 스킨케어 제품 용기, 웰니스 소품을 묘사하고 인물 얼굴 사용 시 부드러운 광원 및 피부 텍스처 중심의 옵션을 부여합니다.

---

## 3. 핵심 스펙 명세

### A. ScenePlan 스키마
`ScenePlan`은 생성할 광고 배경 이미지의 레이아웃, 주요 피사체, 여백 위치, 분위기 및 금지 요소를 사전 정의하는 결정론적 빌더의 핵심 구조체입니다.

- `business_type`: 업종 유형 (cafe, restaurant_bbq, beauty_hair 등)
- `ad_format`: 광고 규격 (instagram_feed, instagram_story, poster 등)
- `primary_subject`: 주 피사체에 대한 정밀 묘사 템플릿
- `reserved_copy_area`: 카피 오버레이를 위해 비워둘 여백 영역 (left, right 등)
- `desired_mood`: 분위기 및 색감 지침 리스트
- `forbidden_visual_elements`: 생성 금지할 비주얼 요소 리스트

### B. PromptQualityPolicy 스키마
`PromptQualityPolicy`는 이미지 내에 무단으로 텍스트나 조잡한 로고가 삽입되는 것을 방지하기 위한 안전 대책 스펙입니다.

- `no_text_policy`: 텍스트 절대 금지 방침 문구
- `safe_area_policy`: 카피 영역 보존 지침 문구
- `fake_text_negative_terms`: negative prompt에 들어갈 텍스트 관련 거부어 리스트
- `positive_safe_area_terms`: positive prompt에 넣을 안전 여백 지시 표현 리스트

### C. Engine Prompt Adapter 전략
각 T2I 생성 엔진의 프롬프트 반응 특성에 맞춰 입력 프롬프트를 번역 및 최적화합니다.

1. **GPT-image-2 Adapter**
   - 크리에이티브 브리프(Creative Brief) 형식의 서술형 문장 구조로 렌더링합니다.
   - `Create a text-free advertising background.`, `intended for later Korean copy overlay.`, `Do not include any text...` 등 텍스트 금지 및 여백 보존 지시문을 서두와 말미에 고정 배치합니다.
2. **SD 3.5 Adapter (Skeleton)**
   - 쉼표로 구분된 짧고 명확한 상업 사진 태그(compact commercial photography tags) 조합으로 positive 프롬프트를 구성합니다.
   - negative prompt 필드에 텍스트, 워터마크, 간판, 찌그러진 디테일 등의 거부어를 완전하게 분리하여 전달합니다.
3. **Flux Adapter (Skeleton)**
   - Flux의 뛰어난 자연어 이해력과 negative prompt 부재 특성을 고려하여, 부정적인 지침보다는 긍정형 대체 표현("clean unmarked surfaces", "blank negative space", "no visible writing") 중심으로 자연스러운 영문 설명을 묘사합니다.

---

## 4. 다음 단계: Copy + Visual Overlay Loop
v3 프롬프트 어댑터와 씬 플랜이 정비되었으므로, 다음 고도화 단계는 다음과 같습니다.
1. **Copy + Visual 산출물 개선 루프**: 생성된 배경 이미지에 실제 카피 오버레이를 적용하고 텍스트 레이아웃과의 대조(Contrast), 크롭 안전 영역(Safe Area) 및 텍스트 시인성(Clipping)을 사후 검증하는 피드백 루프 구축.
2. **Mini Batch**: v3 프롬프트를 활용해 3개 주요 업종 케이스의 소규모 batch 실행 및 v1 결과물과의 수동 평가 비교.
3. **SD3.5 및 FLUX 로컬 엔진 비교**: 스켈레톤 어댑터를 실제 로컬 엔진 파이프라인에 연결하여 최종 아웃풋 정성적/정량적 비교 분석.
