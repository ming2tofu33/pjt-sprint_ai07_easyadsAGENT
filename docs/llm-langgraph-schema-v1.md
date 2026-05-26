# EasyAds LLM/LangGraph 구현 기준 스키마 확정본 v1

> 목적: 이 문서는 EasyAds / 사장님 배너공장의 LLM + LangGraph 구현 기준 스키마와 워크플로우를 팀 공통 기준으로 정리한 문서다.  
> 기준: `feat/llm/langgraph-core-v1` 브랜치의 1차/2차 구현 결과와 기존 확정 스키마를 반영했다.  
> 적용 범위: LLM/LangGraph, Backend Orchestrator, FE/BFF API 계약, Image Serving 연동 기준.

---

## 0. 문서 목적

이 문서는 EasyAds 프로젝트에서 LLM/LangGraph 파트가 따라야 할 구현 기준을 정의한다.

핵심 목적은 다음과 같다.

```text
1. LLM/LangGraph 구현 기준 스키마를 확정한다.
2. FE, Backend, Image Serving, Validation 파트와 충돌하지 않도록 Literal 값을 통일한다.
3. Validator / Options / FormatPlanner / Copywriting / PromptOptimization / PromptRenderer의 책임 범위를 분리한다.
4. Human-in-the-loop interrupt/resume 구조를 명확히 한다.
5. 멀티턴 수정 시 dirty_fields 기준으로 어떤 노드부터 재실행해야 하는지 정의한다.
```

이번 확정본에서 반영한 핵심 수정사항은 다음과 같다.

```text
- field naming은 전부 snake_case로 통일한다.
- Option JSON의 잘못된 value/id 오류를 수정한다.
- GenerationEngine은 일반 사용자 질문에서 제거한다.
- 사용자는 GenerationEngine 대신 RenderProfile만 선택할 수 있다.
- Refactoring Node는 Copywriting Node와 PromptOptimization Node로 분리한다.
- PromptRenderer Node를 추가한다.
- checkpointer + thread_id + interrupt/resume 규칙을 명시한다.
- 최신 MarketingState / Literal / Schema 기준으로 통일한다.
- 2차 구현 기준으로 Validator → Options → StateUpdate → Validator 재진입 HITL mini graph를 반영한다.
```

---

## 1. 전체 Workflow 확정안

### 1.1 최종 LangGraph 흐름

```text
START
↓
InputNode
↓
EntryRouterNode
↓
[조건부 분기]
  chat_start
    → ValidatorNode

  photo_start
    → ImageFeatureExtractionNode
    → ValidatorNode

  reference_start
    → ReferenceStyleExtractionNode
    → ValidatorNode
↓
ContextCompletenessRouter
  missing_fields 있음
    → OptionsNode
    → interrupt(option_question)
    → StateUpdateNode
    → ValidatorNode 재진입

  missing_fields 없음
    → FormatPlannerNode
↓
FormatPlannerNode
↓
CopywritingNode
↓
PromptOptimizationNode
↓
PromptRendererNode
↓
T2IRequestBuilderNode
↓
T2IGenerationNode
↓
BackgroundValidationNode
  pass
    → CandidateSelectionNode 또는 TextOverlayNode

  fail
    → RetryRouter(max_retry=3)
    → PromptOptimizationNode 또는 T2IGenerationNode 재진입
↓
TextOverlayNode
↓
FinalValidationNode
↓
ResultNode
↓
END
```

### 1.2 핵심 설계 원칙

이 프로젝트는 완전 자율 agent보다 **결정적 workflow + 제한적 LLM node** 구조가 적합하다. 광고 생성 절차가 다음처럼 비교적 명확하기 때문이다.

```text
사용자 입력
→ 맥락 추출
→ 부족 정보 질문
→ 광고 형식 결정
→ 카피 생성
→ 이미지 프롬프트 최적화
→ 이미지 생성
→ 검증
→ 텍스트 후합성
→ 최종 검증
```

적용 원칙은 다음과 같다.

```text
1. Graph는 순서와 상태를 관리한다.
2. LLM은 구조화 출력이 필요한 node에서만 사용한다.
3. 이미지 생성은 LangGraph 내부에서 직접 무거운 모델을 들고 있지 않고 T2I service layer를 호출한다.
4. 사용자 선택이 필요한 순간에는 interrupt()로 멈춘다.
5. resume은 반드시 같은 thread_id로 진행한다.
6. 멀티턴 수정은 dirty_fields 기준으로 필요한 node부터 재실행한다.
```

---

## 2. Literal 값 확정

### 2.1 EntryMode

```python
EntryMode = Literal[
    "chat_start",
    "photo_start",
    "reference_start",
]
```

| 값 | 의미 |
|---|---|
| `chat_start` | 대화로 시작하기 |
| `photo_start` | 내 사진으로 만들기 |
| `reference_start` | 레퍼런스 보고 만들기 |

기존의 `chat`, `upload`, `reference` 값은 사용하지 않는다.

---

### 2.2 GenerationRoute

```python
GenerationRoute = Literal[
    "text_to_image",
    "reference_guided_t2i",
    "product_composite",
    "product_inpainting",
    "interior_integration",
    "typography_only",
]
```

| 값 | 의미 |
|---|---|
| `text_to_image` | 텍스트만으로 광고 배경/포스터 생성 |
| `reference_guided_t2i` | 레퍼런스 스타일 DNA를 반영한 T2I |
| `product_composite` | 제품 배경 제거 후 광고 배경에 합성 |
| `product_inpainting` | 제품 보존형 배경 변경 |
| `interior_integration` | 매장/공간 이미지에 포스터 삽입 |
| `typography_only` | 이미지 생성 없이 텍스트 합성만 수행 |

---

### 2.3 GenerationEngine

```python
GenerationEngine = Literal[
    "mock",
    "sd35_large",
    "flux",
    "gpt_image_2",
]
```

| 값 | 의미 |
|---|---|
| `mock` | 개발/테스트용 placeholder |
| `sd35_large` | 기본 로컬 T2I 엔진 |
| `flux` | 고품질 로컬 프리미엄 엔진 |
| `gpt_image_2` | OpenAI API 기반 fallback/premium 엔진 |

중요 규칙:

```text
GenerationEngine은 일반 사용자에게 직접 묻지 않는다.
내부 라우팅, 개발자 설정, benchmark 용도로만 사용한다.
```

---

### 2.4 RenderProfile

```python
RenderProfile = Literal[
    "fast",
    "balanced",
    "premium_local",
    "premium_api",
    "benchmark",
]
```

| 값 | 사용자 노출 라벨 | 내부 기본 엔진 | 용도 |
|---|---|---|---|
| `fast` | 빠르게 미리보기 | `mock` 또는 `sd35_large` | 빠른 preview |
| `balanced` | 기본 품질 | `sd35_large` | 일반 생성 |
| `premium_local` | 고급 품질 | `flux` | 고품질 로컬 생성 |
| `premium_api` | API 고급 품질 | `gpt_image_2` | API 기반 fallback |
| `benchmark` | 비교 실험 | 복수 엔진 | 내부 평가 |

사용자에게는 `GenerationEngine` 대신 `RenderProfile`만 노출한다.

---

### 2.5 JobStatus

```python
JobStatus = Literal[
    "created",
    "input_received",
    "analyzing_image",
    "extracting_reference_style",
    "validating_context",
    "waiting_user_selection",
    "updating_state",
    "planning_format",
    "copywriting",
    "optimizing_prompt",
    "rendering_prompt",
    "t2i_queued",
    "t2i_running",
    "background_validating",
    "waiting_candidate_selection",
    "overlaying_text",
    "final_validating",
    "waiting_revision",
    "done",
    "failed",
]
```

기존 `refactoring`은 더 이상 단일 상태로 쓰지 않는다. 아래처럼 분리한다.

```text
refactoring
→ copywriting
→ optimizing_prompt
→ rendering_prompt
```

---

### 2.6 CopySpace

```python
CopySpace = Literal[
    "top",
    "top_left",
    "top_right",
    "center",
    "bottom",
    "bottom_left",
    "bottom_right",
    "left",
    "right",
    "none",
]
```

`copy_space`는 기본적으로 `LayoutSpec`이 자동 결정한다. 사용자에게 매번 묻지 않는다.

---

### 2.7 MissingField

```python
MissingField = Literal[
    "business_type",
    "item_or_service",
    "region_type",
    "target_persona",
    "promotion_goal",
    "brand_tone",
    "usp",
    "ad_format",
    "platform",
    "aspect_ratio",
    "time_context",
    "price_or_discount",
    "brand_name",
    "location_text",
    "contact_or_order_method",
    "custom_request",
]
```

질문 우선순위는 다음과 같다.

```text
P0: business_type, item_or_service, promotion_goal, ad_format
P1: target_persona, region_type, brand_tone
P2: usp, time_context, price_or_discount, brand_name, contact_or_order_method
P3: custom_request
```

MVP에서는 P0/P1 중심으로 질문하고, P2/P3는 가능하면 추론하거나 optional로 둔다.

`platform`, `aspect_ratio`, `location_text`는 `MissingField`에는 포함하되, MVP 기본 OptionQuestion Registry에서는 제외한다.  
이 값들은 FormatPlanner, 자유 텍스트 parsing, 또는 후속 단계에서 보완한다.

---

## 3. MarketingState 확정본

LangGraph state는 `TypedDict` 기반으로 운용한다. Pydantic 모델은 state 내부 값 검증과 API response 모델에 사용한다.

```python
class MarketingState(TypedDict, total=False):
    # Identity / Tracking
    schema_version: str
    job_id: str
    thread_id: str
    project_id: str | None
    user_id: str | None
    organization_id: str | None
    revision: int

    # Status / Routing
    status: JobStatus
    entry_mode: EntryMode
    generation_route: GenerationRoute
    engine: GenerationEngine
    render_profile: RenderProfile
    progress_state: ProgressState | dict[str, Any] | None

    # Input / Memory
    user_input: str
    prompt_json: dict[str, Any] | None
    messages: list[ConversationMessage | dict[str, Any]]
    conversation_summary: str | None
    current_brief: dict[str, Any]
    dirty_fields: list[str]
    user_selection: UserSelectionRequest | dict[str, Any] | None

    # Image / Reference Input
    image_input: ImageInput | dict[str, Any] | None
    reference_input: ReferenceInput | dict[str, Any] | None
    image_features: ImageFeatures | dict[str, Any] | None
    reference_style: ReferenceStyleSpec | dict[str, Any] | None

    # Validation / HITL
    context: MarketingContext | dict[str, Any]
    validator_output: ValidatorOutput | dict[str, Any] | None
    missing_fields: list[MissingField]
    option_question: OptionQuestion | dict[str, Any] | None

    # Planning / Design
    ad_format_spec: AdFormatSpec | dict[str, Any] | None
    layout_spec: LayoutSpec | dict[str, Any] | None

    # Copy / Prompt
    marketing_copy: MarketingCopy | dict[str, Any] | None
    copywriting_output: CopywritingOutput | dict[str, Any] | None
    image_prompt: ImagePrompt | dict[str, Any] | None
    prompt_optimization_output: PromptOptimizationOutput | dict[str, Any] | None
    user_readable_image_guide: UserReadableImageGuide | dict[str, Any] | None
    prompt_render_output: PromptRenderOutput | dict[str, Any] | None

    # T2I / Image Generation
    t2i_request: T2IRequest | dict[str, Any] | None
    t2i_result: T2IResult | dict[str, Any] | None
    candidates: list[GeneratedImageCandidate | dict[str, Any]]
    selected_candidate_id: str | None

    # Overlay / Validation / Output
    background_validation_report: BackgroundValidationReport | dict[str, Any] | None
    text_overlay_config: TextOverlayConfig | dict[str, Any] | None
    final_image_path: str | None
    final_validation_report: FinalValidationReport | dict[str, Any] | None
    validation_report: ValidationReport | dict[str, Any] | None

    # Artifacts / Error / Metadata
    artifact_refs: list[ArtifactRef | dict[str, Any]]
    error_message: str | None
    error_info: ErrorInfo | dict[str, Any] | None
    created_at: str
    updated_at: str
    latency_ms: int | None
```

핵심 변경점:

```text
- route → generation_route로 통일
- progress_state 명칭 사용
- refactoring_output 중심 구조를 분해
- copywriting_output 추가
- prompt_optimization_output 추가
- prompt_render_output 추가
- selected_candidate_id 명시
- thread_id는 checkpointer resume의 핵심 key
```

---

## 4. 요청 스키마

### 4.1 InitialMarketingRequest

```python
class InitialMarketingRequest(BaseModel):
    entry_mode: EntryMode = "chat_start"
    user_input: str = Field(..., min_length=1)

    prompt_json: dict[str, Any] | None = None
    context: MarketingContext | None = None

    image_input: ImageInput | None = None
    reference_input: ReferenceInput | None = None

    render_profile: RenderProfile = "balanced"

    requested_ad_format: str | None = None
    requested_platform: str | None = None

    project_id: str | None = None
    user_id: str | None = None
    organization_id: str | None = None
    job_id: str | None = None
    thread_id: str | None = None
```

규칙:

```text
- job_id/thread_id가 없으면 InputNode 또는 create_initial_marketing_state()에서 uuid로 생성한다.
- 이미 진행 중인 세션을 이어받는 경우 외부에서 thread_id를 전달할 수 있다.
- LangGraph checkpointer resume은 thread_id를 기준으로 동작하므로 thread_id는 HITL에서 핵심 식별자다.
```

제거할 필드:

```text
preferred_engine
```

이유:

```text
일반 사용자는 engine을 선택하지 않는다.
engine은 render_profile과 backend policy로 결정한다.
```

---

## 5. Context / Validator 스키마

### 5.1 MarketingContext

```python
class MarketingContext(BaseModel):
    business_type: str | None = None
    item_or_service: str | None = None

    region_type: str | None = None
    target_persona: str | None = None
    promotion_goal: str | None = None
    brand_tone: str | None = None
    usp: str | list[str] | None = None

    time_context: str | None = None
    price_or_discount: str | None = None
    brand_name: str | None = None
    location_text: str | None = None
    contact_or_order_method: str | None = None

    extra: dict[str, Any] = Field(default_factory=dict)
```

v1에서는 `BusinessType`, `RegionType`, `PromotionGoal` 등을 엄격한 Literal로 고정하지 않고 `str`로 둔다. 소상공인 업종이 다양하고 `custom` 입력이 많을 수 있기 때문이다. 다만 Option value는 표준값을 사용한다.

---

### 5.2 ValidatorOutput

```python
class ValidatorOutput(BaseModel):
    context: MarketingContext
    missing_fields: list[MissingField]

    confidence: float = Field(..., ge=0.0, le=1.0)
    needs_user_selection: bool

    inferred_entry_mode: EntryMode | None = None
    inferred_generation_route: GenerationRoute | None = None
    inferred_ad_format: AdFormatSpec | None = None

    progress_state: ProgressState | None = None
    reasoning_summary: str | None = None
```

주의:

```text
reasoning_summary는 사용자에게 노출 가능한 짧은 요약만 담는다.
LLM의 chain-of-thought를 저장하지 않는다.
```

---

## 6. Options / HITL 스키마

### 6.1 OptionItem

```python
class OptionItem(BaseModel):
    id: int
    label: str
    value: str
    description: str | None = None
    icon: str | None = None
    recommended: bool = False
```

---

### 6.2 OptionQuestion

```python
class OptionQuestion(BaseModel):
    field: MissingField
    question: str
    options: list[OptionItem]

    required: bool = True
    multi_select: bool = False

    allow_custom: bool = True
    progress_state: ProgressState | None = None
```

OptionsNode는 **한 번에 하나의 missing field에 대한 질문만 생성**하는 것을 v1 기본값으로 한다.

```text
예:
missing_fields = ["brand_tone", "ad_format"]
→ OptionsNode는 우선순위가 가장 높은 field 하나만 질문
→ user_selection 수신
→ StateUpdate
→ Validator 재진입
```

---

### 6.3 UserSelectionRequest

```python
class UserSelectionRequest(BaseModel):
    job_id: str
    thread_id: str

    field: MissingField
    value: str | list[str]

    custom_text: str | None = None
```

---

## 7. Option Question Registry

기존 Option JSON에서 수정한 사항:

```text
- field name은 모두 snake_case로 통일한다.
- "디저트"를 beauty_salon으로 매핑하지 않는다.
- ad_format id 중복을 제거한다.
- A4는 ad_format value가 아니라 flyer의 aspect_ratio/size 성격으로 처리한다.
- GenerationEngine 질문은 사용자 질문에서 제거한다.
- CopySpace는 기본 필수 질문에서 제거한다.
- usp는 multi_select=True로 둔다.
```

### 7.1 기본 질문 목록

| field | required | multi_select | 비고 |
|---|---:|---:|---|
| `business_type` | true | false | 업종 |
| `promotion_goal` | true | false | 광고 목적 |
| `brand_tone` | false 또는 상황별 true | false | 분위기 |
| `ad_format` | true | false | 사용 채널/형식 |
| `target_persona` | false | false | 타겟 고객 |
| `region_type` | false | false | 상권 |
| `usp` | false | true | 차별점 |
| `time_context` | false | false | 노출 시간대/상황 |

### 7.2 business_type 옵션

```python
[
    {"id": 1, "label": "식당/레스토랑", "value": "restaurant"},
    {"id": 2, "label": "카페/디저트", "value": "cafe"},
    {"id": 3, "label": "뷰티/미용실", "value": "beauty_salon"},
    {"id": 4, "label": "주점/바", "value": "bar"},
    {"id": 5, "label": "피트니스/헬스", "value": "fitness"},
    {"id": 6, "label": "학원/교육", "value": "academy"},
    {"id": 7, "label": "꽃집", "value": "flower_shop"},
    {"id": 8, "label": "일반 매장/소매점", "value": "store"},
    {"id": 9, "label": "직접 입력", "value": "custom"},
]
```

### 7.3 promotion_goal 옵션

```python
[
    {"id": 1, "label": "신메뉴/신상품 출시", "value": "new_launch"},
    {"id": 2, "label": "시즌 한정 홍보", "value": "seasonal_limited"},
    {"id": 3, "label": "할인 이벤트", "value": "discount_event"},
    {"id": 4, "label": "예약/방문 유도", "value": "reservation_cta"},
    {"id": 5, "label": "브랜드 감성 홍보", "value": "brand_awareness"},
    {"id": 6, "label": "리뷰 이벤트", "value": "review_event"},
    {"id": 7, "label": "단골/재방문 유도", "value": "retention"},
    {"id": 8, "label": "직접 입력", "value": "custom"},
]
```

### 7.4 brand_tone 옵션

```python
[
    {"id": 1, "label": "감성적인", "value": "emotional_mood"},
    {"id": 2, "label": "상큼한", "value": "fresh_refreshing"},
    {"id": 3, "label": "고급스러운", "value": "premium_luxurious"},
    {"id": 4, "label": "귀여운", "value": "cute_adorable"},
    {"id": 5, "label": "깔끔한", "value": "clean_minimal"},
    {"id": 6, "label": "따뜻한", "value": "warm_cozy"},
    {"id": 7, "label": "힙하고 트렌디한", "value": "hip_trendy"},
    {"id": 8, "label": "강렬한", "value": "bold_urgent"},
    {"id": 9, "label": "직접 입력", "value": "custom"},
]
```

### 7.5 ad_format 옵션

```python
[
    {"id": 1, "label": "인스타그램 피드 1:1", "value": "instagram_feed"},
    {"id": 2, "label": "인스타그램 스토리 9:16", "value": "instagram_story"},
    {"id": 3, "label": "포스터 4:5", "value": "poster"},
    {"id": 4, "label": "전단지 A4", "value": "flyer"},
    {"id": 5, "label": "웹 배너 16:9", "value": "banner"},
    {"id": 6, "label": "스마트스토어/상세페이지", "value": "product_detail"},
    {"id": 7, "label": "기타 사이즈", "value": "custom"},
]
```

---

## 8. ProgressState

```python
class ProgressState(BaseModel):
    current_step: int
    total_steps: int
    current_label: str

    skipped_steps: list[str] = Field(default_factory=list)
    remaining_fields: list[MissingField] = Field(default_factory=list)

    can_skip_question_screen: bool = False
    status: JobStatus | None = None
    message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

동적 처리 규칙:

```text
missing_fields 있음:
  total_steps = min(질문할 missing_fields 수, MVP 질문 제한) + 2
  질문 단계 + 카피/채널 확인 + 최종 브리프 확인

missing_fields 없음:
  질문 화면 스킵
  total_steps = 2
  카피/채널 확인 + 최종 브리프 확인
```

---

## 9. 광고 형식 / 레이아웃 스키마

### 9.1 AdFormatSpec

```python
AdFormat = Literal[
    "instagram_feed",
    "instagram_story",
    "poster",
    "flyer",
    "product_detail",
    "banner",
]

Platform = Literal[
    "instagram",
    "offline",
    "web",
    "naver_smartstore",
    "naver_place",
    "danggeun",
    "etc",
]

AspectRatio = Literal[
    "1:1",
    "4:5",
    "9:16",
    "16:9",
    "A4_vertical",
    "custom",
]

class AdFormatSpec(BaseModel):
    ad_format: AdFormat
    platform: Platform
    aspect_ratio: AspectRatio
    width: int = Field(..., ge=1)
    height: int = Field(..., ge=1)

    information_density: Literal[
        "low",
        "medium",
        "high",
    ] = "medium"

    visual_priority: Literal[
        "product_hero",
        "mood_first",
        "information_first",
        "detail_explanation",
        "click_conversion",
    ] = "mood_first"

    output_strategy: Literal[
        "generate_text_free_background_then_overlay",
        "template_composite",
        "multi_section_layout",
        "product_preserving_edit",
        "typography_only",
    ]

    metadata: dict[str, Any] = Field(default_factory=dict)
```

---

### 9.2 Format Mapping

```python
AD_FORMAT_PRESETS = {
    "instagram_feed": {
        "platform": "instagram",
        "aspect_ratio": "1:1",
        "width": 1080,
        "height": 1080,
        "information_density": "low",
        "visual_priority": "product_hero",
        "output_strategy": "generate_text_free_background_then_overlay",
    },
    "instagram_story": {
        "platform": "instagram",
        "aspect_ratio": "9:16",
        "width": 1080,
        "height": 1920,
        "information_density": "low",
        "visual_priority": "mood_first",
        "output_strategy": "generate_text_free_background_then_overlay",
    },
    "poster": {
        "platform": "offline",
        "aspect_ratio": "4:5",
        "width": 1080,
        "height": 1350,
        "information_density": "medium",
        "visual_priority": "product_hero",
        "output_strategy": "generate_text_free_background_then_overlay",
    },
    "flyer": {
        "platform": "offline",
        "aspect_ratio": "A4_vertical",
        "width": 1240,
        "height": 1754,
        "information_density": "high",
        "visual_priority": "information_first",
        "output_strategy": "multi_section_layout",
    },
    "banner": {
        "platform": "web",
        "aspect_ratio": "16:9",
        "width": 1280,
        "height": 720,
        "information_density": "medium",
        "visual_priority": "click_conversion",
        "output_strategy": "generate_text_free_background_then_overlay",
    },
    "product_detail": {
        "platform": "naver_smartstore",
        "aspect_ratio": "custom",
        "width": 1000,
        "height": 1500,
        "information_density": "high",
        "visual_priority": "detail_explanation",
        "output_strategy": "multi_section_layout",
    },
}
```

---

### 9.3 LayoutSpec

현재 구현 기준은 `Zone`을 상속하는 `TextZone` 구조를 사용한다.

```python
class Zone(BaseModel):
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)
    width: float = Field(..., gt=0.0, le=1.0)
    height: float = Field(..., gt=0.0, le=1.0)


class TextZone(Zone):
    role: Literal[
        "headline",
        "subcopy",
        "cta",
        "price",
        "disclaimer",
        "free",
    ] = "free"

    max_chars: int | None = Field(default=None, ge=1)
    align: Literal["left", "center", "right"] = "center"


class LayoutSpec(BaseModel):
    layout_type: Literal[
        "single_panel",
        "story",
        "poster",
        "flyer",
        "banner",
        "product_detail",
    ] = "single_panel"

    copy_space: CopySpace = "bottom"
    safe_area: Zone | None = None

    text_zones: list[TextZone] = Field(default_factory=list)
    product_zone: Zone | None = None
    cta_zone: Zone | None = None
    background_zone: Zone | None = None

    overlay_style: OverlayStyle = "gradient"
    text_align: Literal["left", "center", "right"] = "center"
    max_text_density: Literal["low", "medium", "high"] = "medium"

    metadata: dict[str, Any] = Field(default_factory=dict)
```

---

## 10. Copywriting Node 스키마

### 10.1 MarketingCopy

```python
class MarketingCopy(BaseModel):
    headline: str
    subcopy: str | None = None
    cta: str | None = None
    price_line: str | None = None
    period_line: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    disclaimer: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

주의:

```text
가격, 전화번호, 주소, 기간 등은 사용자가 제공하지 않았다면 임의로 생성하지 않는다.
```

---

### 10.2 CopywritingOutput

```python
class CopywritingOutput(BaseModel):
    marketing_copy: MarketingCopy
    tone_profile: dict[str, Any] = Field(default_factory=dict)
    alternatives: list[MarketingCopy] = Field(default_factory=list)
    progress_state: ProgressState | None = None
    rationale: str | None = None
```

---

### 10.3 Copy Tone Mapping Table

지원 업종:

```text
restaurant
cafe
beauty_salon
bar
fitness
academy
flower_shop
store
```

예시:

```python
COPY_TONE_MAPPING = {
    "restaurant": {
        "default": {
            "style": "직관적이고 식욕을 자극하는 문장",
            "avoid": ["과도한 허세", "너무 추상적인 감성어"],
        },
        "office_worker": {
            "style": "회식/점심/단체예약 중심의 실용적 문장",
            "keywords": ["회식", "단체석", "예약", "든든한 한 끼"],
        },
        "family_local": {
            "style": "신뢰감 있고 편안한 동네 단골 문장",
            "keywords": ["우리 동네", "가족", "정직한", "푸짐한"],
        },
    },
    "cafe": {
        "default": {
            "style": "감성적이고 가볍게 공유하고 싶은 문장",
            "keywords": ["오늘의 여유", "달콤한", "시즌", "한 잔"],
        },
    },
}
```

---

## 11. PromptOptimization Node 스키마

### 11.1 ImagePrompt

```python
class ImagePrompt(BaseModel):
    subject: str
    style: str
    lighting: str
    composition: str
    copy_space: CopySpace
    negative_prompt: str

    scene: str | None = None
    color_palette: list[str] = Field(default_factory=list)
    avoid_text: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
```

핵심 6-field:

```text
subject
style
lighting
composition
copy_space
negative_prompt
```

---

### 11.2 UserReadableImageGuide

```python
class UserReadableImageGuide(BaseModel):
    summary: str
    style_keywords: list[str] = Field(default_factory=list)
    copy_space: CopySpace | None = None
    warnings: list[str] = Field(default_factory=list)
```

---

### 11.3 PromptOptimizationOutput

```python
class PromptOptimizationOutput(BaseModel):
    image_prompt: ImagePrompt
    user_readable_image_guide: UserReadableImageGuide | None = None
    negative_prompt: str | None = None
    progress_state: ProgressState | None = None
    rationale: str | None = None
```

---

## 12. PromptRenderer Node 스키마

### 12.1 PromptRenderOutput

```python
class PromptRenderOutput(BaseModel):
    engine: GenerationEngine
    positive_prompt: str
    negative_prompt: str | None = None
    render_profile: RenderProfile = "balanced"
    render_notes: list[str] = Field(default_factory=list)
    width: int = Field(..., ge=1)
    height: int = Field(..., ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
```

---

### 12.2 엔진별 렌더링 규칙

```text
mock:
  - positive_prompt 일부만 placeholder 이미지에 표시
  - 테스트용

sd35_large:
  - positive_prompt와 negative_prompt 분리
  - negative_prompt는 기존 T2I negative policy와 병합

flux:
  - negative_prompt 영향이 약할 수 있으므로
    positive_prompt 내부에도 "no text, no watermark, no logo" 조건을 포함

gpt_image_2:
  - 단순 키워드 prompt보다 광고 creative brief 형태로 구성
  - "text-free background for later Korean copy overlay"를 명확히 포함
```

---

## 13. RefactoringOutput 처리 방침

기존 `RefactoringOutput`은 유지하되, v1 구현에서는 단일 LLM node 결과물이 아니라 **CopywritingOutput + PromptOptimizationOutput을 묶는 통합 객체**로 사용한다.

```python
class RefactoringOutput(BaseModel):
    marketing_copy: MarketingCopy
    ad_format_spec: AdFormatSpec
    layout_spec: LayoutSpec
    image_prompt: ImagePrompt
    context: MarketingContext

    user_readable_image_guide: UserReadableImageGuide | None = None
    rationale: str | None = None
```

권장 사용 방식:

```text
CopywritingNode
→ CopywritingOutput 생성

PromptOptimizationNode
→ PromptOptimizationOutput 생성

State 병합 시
→ RefactoringOutput 호환 객체 생성 가능
```

즉, `RefactoringOutput`은 API/FE 호환용 통합 뷰로 유지하고, LangGraph 내부 node는 분리한다.

---

## 14. Image / Reference 스키마

### 14.1 ImageInput

```python
class ImageInput(BaseModel):
    image_id: str
    original_path: str
    preprocessed_path: str | None = None

    filename: str | None = None
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    file_size_bytes: int | None = None

    image_role: Literal[
        "product_photo",
        "food_photo",
        "interior_photo",
        "flat_background",
        "unknown",
    ] = "unknown"

    metadata: dict[str, Any] = Field(default_factory=dict)
```

---

### 14.2 ImageFeatures

```python
class ImageFeatures(BaseModel):
    category: Literal[
        "food",
        "product",
        "interior",
        "flat",
        "person",
        "unknown",
    ]

    subject_summary: str | None = None
    detected_objects: list[str] = Field(default_factory=list)

    color_palette: list[str] = Field(default_factory=list)
    mood: list[str] = Field(default_factory=list)
    lighting: str | None = None
    composition: str | None = None
    background_style: str | None = None

    copy_space_available: bool | None = None
    recommended_copy_space: CopySpace | None = None

    product_mask_path: str | None = None
    product_cutout_path: str | None = None
    depth_map_path: str | None = None

    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    raw_vlm_output: dict[str, Any] = Field(default_factory=dict)
```

---

### 14.3 ReferenceInput / ReferenceStyleSpec

```python
class ReferenceInput(BaseModel):
    reference_id: str
    reference_path: str
    category: str | None = None
    source: Literal["gallery", "user_upload", "system"] = "gallery"
    metadata: dict[str, Any] = Field(default_factory=dict)
```

```python
class ReferenceStyleSpec(BaseModel):
    color_palette: list[str] = Field(default_factory=list)
    mood: list[str] = Field(default_factory=list)
    layout: str | None = None
    lighting: str | None = None
    typography_hint: str | None = None
    background_style: str | None = None
    ad_style_prompt: str | None = None
```

---

## 15. T2I 연동 스키마

### 15.1 T2IRequest

현재 이미지 serving 쪽 구현과 맞춘다. 별도 중복 정의하지 않고 기존 `orchestrator.app.t2i.schemas`의 `T2IRequest`를 재사용한다.

```python
class T2IRequest(BaseModel):
    prompt: str
    negative_prompt: str | None = None

    width: int = 1024
    height: int = 1024

    seed: int | None = None
    num_images: int = 1
    steps: int | None = None
    guidance_scale: float | None = None
    quality: str | None = None

    output_dir: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

### 15.2 T2IRequest metadata 기준

```python
metadata = {
    "job_id": "...",
    "thread_id": "...",
    "entry_mode": "chat_start",
    "generation_route": "text_to_image",

    "ad_format_spec": {...},
    "layout_spec": {...},

    "business_type": "restaurant",
    "item_or_service": "삼겹살",

    "engine": "sd35_large",
    "render_profile": "balanced",

    "render_text_in_image": False,
    "effective_negative_prompt": "...",
    "negative_prompt_sources": [...],
}
```

---

### 15.3 T2IResult

```python
class T2IResult(BaseModel):
    engine: GenerationEngine
    image_paths: list[str]

    seed: int | None = None
    latency_ms: int

    width: int
    height: int

    prompt: str
    negative_prompt: str | None = None

    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
```

---

## 16. 후보 / 오버레이 / 검증 스키마

### 16.1 GeneratedImageCandidate

```python
class GeneratedImageCandidate(BaseModel):
    image_id: str
    image_path: str
    width: int
    height: int

    engine: GenerationEngine
    seed: int | None = None
    latency_ms: int | None = None

    background_validation: BackgroundValidationReport | None = None
    final_validation: FinalValidationReport | None = None

    quality_score: float | None = None
    selected: bool = False

    metadata: dict[str, Any] = Field(default_factory=dict)
```

---

### 16.2 TextOverlayConfig

```python
class TextOverlayConfig(BaseModel):
    marketing_copy: MarketingCopy
    ad_format_spec: AdFormatSpec
    layout_spec: LayoutSpec

    copy_space: CopySpace
    font_path: str | None = None

    brand_color: str = "#E85D75"
    text_color: str = "#FFFFFF"

    overlay_style: OverlayStyle = "gradient"
    output_channel: OutputChannel = "instagram_feed"
```

---

### 16.3 BackgroundValidationReport

```python
class BackgroundValidationReport(BaseModel):
    overall_pass: bool

    text_artifact_pass: bool
    watermark_pass: bool
    copy_space_pass: bool
    visual_quality_pass: bool
    brand_safety_pass: bool

    detected_text_artifacts: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)

    retry_recommended: bool = False
    retry_reason: str | None = None

    metadata: dict[str, Any] = Field(default_factory=dict)
```

---

### 16.4 FinalValidationReport

```python
class FinalValidationReport(BaseModel):
    overall_pass: bool

    ocr_pass: bool
    rule_pass: bool
    readability_pass: bool
    layout_pass: bool
    visual_pass: bool

    expected_text: list[str] = Field(default_factory=list)
    detected_text: list[str] = Field(default_factory=list)

    warnings: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)

    metadata: dict[str, Any] = Field(default_factory=dict)
```

---

### 16.5 ValidationReport

```python
class ValidationReport(BaseModel):
    overall_pass: bool

    background: BackgroundValidationReport | None = None
    final: FinalValidationReport | None = None

    product_preservation_pass: bool | None = None
    product_similarity_score: float | None = None

    warnings: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)

    metadata: dict[str, Any] = Field(default_factory=dict)
```

---

## 17. JobStatusResponse

```python
class JobStatusResponse(BaseModel):
    job_id: str
    thread_id: str
    status: JobStatus
    entry_mode: EntryMode

    progress_state: ProgressState | None = None

    context: MarketingContext | None = None
    ad_format_spec: AdFormatSpec | None = None
    layout_spec: LayoutSpec | None = None

    image_features: ImageFeatures | None = None
    reference_style: ReferenceStyleSpec | None = None

    option_question: OptionQuestion | None = None

    marketing_copy: MarketingCopy | None = None
    user_readable_image_guide: UserReadableImageGuide | None = None

    prompt_render_output: PromptRenderOutput | None = None

    t2i_result: T2IResult | None = None
    candidates: list[GeneratedImageCandidate] = Field(default_factory=list)

    selected_candidate_id: str | None = None
    final_image_path: str | None = None
    validation_report: ValidationReport | None = None

    error_message: str | None = None
```

---

## 18. LangGraph Interrupt / Resume 규칙

### 18.1 기본 규칙

LangGraph의 interrupt는 graph 실행을 멈추고 외부 입력을 기다리며, checkpointer가 저장한 graph state를 기준으로 같은 `thread_id`에서 재개된다.

필수 규칙:

```text
1. 모든 graph invoke에는 thread_id를 config로 넣는다.
2. OptionsNode는 interrupt(option_question_json)을 호출한다.
3. FE/BFF는 interrupt payload를 사용자에게 렌더링한다.
4. 사용자가 선택하면 Command(resume=user_selection_payload)를 보낸다.
5. resume은 반드시 같은 thread_id로 호출한다.
6. OptionsNode 내부에서 interrupt 이전에 비멱등 side effect를 만들지 않는다.
```

### 18.2 invoke 예시

```python
config = {
    "configurable": {
        "thread_id": thread_id,
    }
}

result = graph.invoke(initial_input, config=config)
```

### 18.3 interrupt payload 예시

```json
{
  "type": "option_question",
  "job_id": "job_123",
  "thread_id": "thread_123",
  "option_question": {
    "field": "ad_format",
    "question": "어디에 사용할 광고인가요?",
    "options": [
      {"id": 1, "label": "인스타그램 피드 1:1", "value": "instagram_feed"},
      {"id": 2, "label": "인스타그램 스토리 9:16", "value": "instagram_story"},
      {"id": 3, "label": "포스터 4:5", "value": "poster"},
      {"id": 4, "label": "전단지 A4", "value": "flyer"}
    ],
    "required": true,
    "multi_select": false
  }
}
```

주의:

```text
- option_question에는 question 필드를 사용한다.
- title 필드는 사용하지 않는다.
```

### 18.4 resume payload 예시

```json
{
  "job_id": "job_123",
  "thread_id": "thread_123",
  "field": "ad_format",
  "value": "instagram_feed"
}
```

```python
graph.invoke(
    Command(resume=resume_payload),
    config=config,
)
```

### 18.5 OptionsNode 구현 세부 규칙

OptionsNode는 interrupt payload를 생성한 뒤 `interrupt(payload)`를 호출한다.  
이때 `interrupt()`의 반환값은 사용자가 선택한 resume payload가 된다.

구현 규칙:

```python
resume_payload = interrupt(payload)
return {
    "user_selection": resume_payload,
    "status": "updating_state",
}
```

주의:

```text
- OptionsNode는 사용자 선택값을 직접 context에 반영하지 않는다.
- OptionsNode는 resume_payload를 state["user_selection"]에 저장하는 역할까지만 한다.
- 실제 MarketingContext 업데이트는 StateUpdateNode에서 수행한다.
- interrupt payload는 반드시 JSON-serializable dict여야 한다.
- Pydantic 객체는 model_dump() 후 전달한다.
- OptionsNode 내부에서 interrupt 이전에 파일 저장, DB 저장, API 호출 같은 비멱등 side effect를 만들지 않는다.
```

---

## 19. Node 책임 범위 확정

### 19.1 InputNode

역할:

```text
- user_input 저장
- thread_id / job_id 확인 또는 생성
- messages append
- current_brief 업데이트
- revision 증가
- dirty_fields 초기 계산
- status = input_received
```

생성/수정:

```text
MarketingState
ConversationMessage
dirty_fields
```

---

### 19.2 EntryRouterNode

역할:

```text
- entry_mode 결정
- generation_route 초기 결정
- render_profile 기본값 결정
```

라우팅:

```text
chat_start → text_to_image
photo_start → product_composite 또는 product_inpainting 후보
reference_start → reference_guided_t2i
```

---

### 19.3 ValidatorNode

역할:

```text
- user_input/current_brief에서 MarketingContext 추출
- inferred_ad_format 추론
- missing_fields 계산
- needs_user_selection 결정
- progress_state 계산
```

출력:

```text
ValidatorOutput
MarketingContext
missing_fields
progress_state
```

#### ValidatorNode v1 휴리스틱 정책

v1에서는 실제 LLM API를 호출하지 않고 규칙 기반/휴리스틱 기반으로 구현한다.

기본 추출 규칙:

```text
business_type:
- "카페", "라떼", "디저트", "커피" → cafe
- "삼겹살", "고기", "한우", "식당", "레스토랑" → restaurant
- "미용실", "헤어", "염색", "펌" → beauty_salon
- "헬스", "PT", "운동", "피트니스" → fitness
- "꽃", "꽃집", "플라워" → flower_shop

promotion_goal:
- "할인", "%", "세일", "특가" → discount_event
- "신메뉴", "신상품", "출시", "오픈" → new_launch
- "예약", "방문", "문의" → reservation_cta
- "리뷰" → review_event

ad_format:
- "인스타", "피드" → instagram_feed
- "스토리" → instagram_story
- "전단지", "A4", "당근" → flyer
- "배너", "웹" → banner
- "상세페이지", "스마트스토어" → product_detail
```

item_or_service 추출 규칙:

```text
- "삼겹살집" → item_or_service = "삼겹살"
- "삼겹살" → item_or_service = "삼겹살"
- "한우 선물세트" → item_or_service = "한우 선물세트"
- "한우" → item_or_service = "한우"
- "딸기라떼" → item_or_service = "딸기라떼"
- "라떼" → item_or_service = "라떼"
- "염색" → item_or_service = "염색"
- "PT" → item_or_service = "PT"
```

missing field 정책:

```text
필수:
- business_type
- item_or_service
- promotion_goal
- ad_format

선택:
- brand_tone
- target_persona
- region_type
- usp
- time_context
```

예시:

```text
"우리 삼겹살집 인스타 광고"
→ business_type = restaurant
→ item_or_service = 삼겹살
→ ad_format = instagram_feed
→ promotion_goal은 추론 불충분하므로 missing_fields에 유지
```

---

### 19.4 OptionsNode

역할:

```text
- missing_fields 중 우선순위가 가장 높은 field 하나 선택
- OptionQuestion 생성
- interrupt(option_question) 호출
```

하지 말 것:

```text
- 여러 질문을 한 번에 모두 던지지 않음
- 사용자 선택값을 직접 context에 반영하지 않음
- interrupt 이전에 파일/DB 쓰기 같은 side effect를 만들지 않음
```

---

### 19.5 StateUpdateNode

역할:

```text
- Command(resume=...)로 들어온 UserSelectionRequest 처리
- selected value를 MarketingContext 또는 current_brief에 반영
- messages append
- current_brief 업데이트
- dirty_fields 재계산
- status = updating_state
```

#### StateUpdateNode 세부 처리 규칙

```text
1. value != "custom"
   → context[field] = value

2. value == "custom" and custom_text exists
   → context[field] = custom_text

3. value == "custom" and custom_text is empty
   → context를 업데이트하지 않고 해당 field를 missing_fields에 유지

4. multi_select field
   → list[str]를 허용한다.
   → 예: field="usp", value=["fresh_ingredients", "value_for_money"]

5. field == "ad_format"
   → context.extra["ad_format"] 또는 current_brief["requested_ad_format"]에 저장한다.
   → 다음 FormatPlannerNode에서 AdFormatSpec으로 변환한다.

6. 업데이트된 field
   → missing_fields에서 제거한다.

7. 업데이트 후
   → messages append
   → current_brief 업데이트
   → dirty_fields 재계산
   → revision += 1
   → status = "updating_state"
```

---

### 19.6 FormatPlannerNode

역할:

```text
- ad_format_spec 생성
- layout_spec 생성
- width/height 결정
- information_density 결정
- output_strategy 결정
```

입력:

```text
MarketingContext
ValidatorOutput.inferred_ad_format
ImageFeatures
ReferenceStyleSpec
```

출력:

```text
AdFormatSpec
LayoutSpec
```

---

### 19.7 CopywritingNode

역할:

```text
- 광고 카피 생성
- headline/subcopy/cta 생성
- price_line, period_line, hashtags 생성
- 업종별/타겟별 카피 톤 적용
```

출력:

```text
CopywritingOutput
MarketingCopy
```

---

### 19.8 PromptOptimizationNode

역할:

```text
- ImagePrompt 생성
- UserReadableImageGuide 생성
- copy_space 반영
- negative prompt 방향 반영
- 레퍼런스 스타일/이미지 특징 반영
```

출력:

```text
PromptOptimizationOutput
ImagePrompt
UserReadableImageGuide
```

---

### 19.9 PromptRendererNode

역할:

```text
- ImagePrompt를 엔진별 최종 prompt string으로 변환
- SD3.5 / FLUX / GPT-image-2 형식 차이 흡수
- width/height 반영
- negative_prompt 정리
```

출력:

```text
PromptRenderOutput
```

---

### 19.10 T2IRequestBuilderNode

역할:

```text
- PromptRenderOutput을 T2IRequest로 변환
- metadata 구성
- render_text_in_image = false 정책 유지
```

---

### 19.11 T2IGenerationNode

역할:

```text
- 현재 image serving layer 호출
- generate_image_v1 또는 T2I service 호출
- 후보 이미지 생성
```

출력:

```text
T2IResult
GeneratedImageCandidate[]
ArtifactRef[]
```

---

### 19.12 BackgroundValidationNode

역할:

```text
- 텍스트 artifact 검사
- watermark/logo 검사
- copy_space 검사
- 광고 배경 품질 검사
- retry 여부 결정
```

---

### 19.13 TextOverlayNode

역할:

```text
- MarketingCopy를 이미지 위에 후합성
- LayoutSpec safe_area 반영
- 한글 텍스트 정확도 보장
```

---

### 19.14 FinalValidationNode

역할:

```text
- OCR 검증
- rule 기반 검증
- 가독성 검증
- layout 검증
- 최종 광고 품질 검사
```

---

## 20. Graph Conditional Routing 규칙

### 20.1 EntryRouter

```python
def route_by_entry_mode(state: MarketingState) -> str:
    if state["entry_mode"] == "photo_start":
        return "image_feature_extraction"
    if state["entry_mode"] == "reference_start":
        return "reference_style_extraction"
    return "validator"
```

2차 intake mini graph에서는 이미지/레퍼런스 분석 노드를 아직 구현하지 않기 때문에 `photo_start`, `reference_start`도 임시로 `validator`로 보낸다.

---

### 20.2 ContextCompletenessRouter

전체 graph 기준:

```python
def route_after_validator(state: MarketingState) -> str:
    if state.get("missing_fields"):
        return "options"
    return "format_planner"
```

2차 intake mini graph 기준:

```python
def route_after_validator(state: MarketingState) -> str:
    if state.get("missing_fields"):
        return "options"
    return "__end__"
```

주의:

```text
- 전체 graph에서는 missing_fields가 없으면 FormatPlannerNode로 간다.
- 2차 mini graph에서는 FormatPlannerNode가 없으므로 END로 종료한다.
- ready_for_planning=True는 router가 직접 state mutation하지 않고 ValidatorNode에서 처리한다.
```

---

### 20.3 Intake Mini Graph v1 Routing

2차 구현 범위에서는 FormatPlannerNode를 아직 구현하지 않는다. 따라서 intake mini graph에서는 `missing_fields`가 없으면 `END`로 종료한다.

필수 edge:

```text
input → validator
validator → options 또는 END
options → state_update
state_update → validator
```

---

### 20.4 RetryRouter

```python
def route_after_background_validation(state: MarketingState) -> str:
    report = state.get("background_validation_report")

    if report and report.overall_pass:
        return "text_overlay"

    retry_count = state.get("current_brief", {}).get("retry_count", 0)

    if retry_count >= 3:
        return "waiting_revision"

    return "prompt_optimization"
```

---

## 21. dirty_fields 기반 멀티턴 수정 규칙

### 21.1 문구만 수정

예:

```text
"문구만 짧게 해줘"
```

dirty_fields:

```text
marketing_copy
text_overlay_config
final_validation_report
```

재실행:

```text
CopywritingNode
→ TextOverlayNode
→ FinalValidationNode
```

재사용:

```text
AdFormatSpec
LayoutSpec
ImagePrompt
T2IResult
GeneratedImageCandidate
```

---

### 21.2 분위기 수정

예:

```text
"좀 더 고급스럽게 해줘"
```

dirty_fields:

```text
brand_tone
marketing_copy
image_prompt
prompt_render_output
t2i_request
t2i_result
background_validation_report
text_overlay_config
final_validation_report
```

재실행:

```text
CopywritingNode
→ PromptOptimizationNode
→ PromptRendererNode
→ T2IRequestBuilderNode
→ T2IGenerationNode
→ BackgroundValidationNode
→ TextOverlayNode
→ FinalValidationNode
```

---

### 21.3 포맷 변경

예:

```text
"스토리용으로 바꿔줘"
```

dirty_fields:

```text
ad_format_spec
layout_spec
image_prompt
prompt_render_output
t2i_request
t2i_result
text_overlay_config
validation_report
```

재실행:

```text
FormatPlannerNode
→ CopywritingNode
→ PromptOptimizationNode
→ PromptRendererNode
→ T2IRequestBuilderNode
→ T2IGenerationNode
→ BackgroundValidationNode
→ TextOverlayNode
→ FinalValidationNode
```

---

### 21.4 후보 선택

예:

```text
"2번으로 해줘"
```

dirty_fields:

```text
selected_candidate_id
text_overlay_config
final_validation_report
```

재실행:

```text
TextOverlayNode
→ FinalValidationNode
```

---

## 22. 현재 구현 상태

`feat/llm/langgraph-core-v1` 기준 2차까지 구현된 범위:

```text
완료:
- LLM/LangGraph schema v1
- OptionQuestion registry
- AdFormat preset
- Copy tone mapping
- MarketingState TypedDict
- InitialMarketingRequest
- create_initial_marketing_state()
- ValidatorNode v1
- OptionsNode v1
- StateUpdateNode v1
- build_intake_graph()
- checkpointer + thread_id 기반 interrupt/resume test

아직 미구현:
- FormatPlannerNode
- CopywritingNode
- PromptOptimizationNode
- PromptRendererNode
- T2IRequestBuilderNode
- T2IGenerationNode graph 연결
- BackgroundValidationNode
- TextOverlayNode
- FinalValidationNode
- FastAPI endpoint
- FE/BFF 연동
```

테스트 기준:

```text
1차 완료: 41 passed, 2 warnings
2차 완료: 58 passed, 2 warnings
```

---

## 23. 최종 구현 우선순위

LLM/LangGraph 파트는 다음 순서로 구현한다.

```text
1. Literal / Schema 통일
2. OptionQuestion registry 정리
3. ValidatorNode v1
4. OptionsNode v1
5. StateUpdateNode + interrupt/resume
6. FormatPlannerNode v1
7. CopywritingNode v1
8. PromptOptimizationNode v1
9. PromptRendererNode v1
10. T2IRequestBuilderNode
11. T2IGenerationNode mock 연결
12. BackgroundValidationNode
13. TextOverlayNode
14. FinalValidationNode
15. 멀티턴 dirty_fields partial rerun
```

---

## 24. 팀 공통 주의사항

```text
- schema field naming은 snake_case로 통일한다.
- GenerationEngine을 사용자에게 직접 묻지 않는다.
- 사용자는 RenderProfile만 선택한다.
- 이미지 모델이 텍스트를 직접 그리게 하지 않는다.
- render_text_in_image = false 정책을 유지한다.
- 한국어 광고 문구는 TextOverlayNode에서 후합성한다.
- 사용자가 제공하지 않은 가격, 전화번호, 주소, 기간은 생성하지 않는다.
- interrupt payload는 반드시 JSON-serializable dict로 보낸다.
- resume은 반드시 같은 thread_id로 실행한다.
- Router는 가능하면 state mutation을 하지 않는다.
- router에서 필요한 상태 업데이트는 이전 node에서 처리한다.
```

---

## 25. 최종 요약

이 문서의 기준 구조는 다음과 같다.

```text
소상공인 입력
→ MarketingContext 추출
→ missing_fields HITL 보완
→ AdFormatSpec / LayoutSpec 확정
→ Copywriting
→ PromptOptimization
→ PromptRenderer
→ T2I Service 호출
→ BackgroundValidation
→ TextOverlay
→ FinalValidation
→ 후보 선택 / 수정 루프
```

핵심 노드 책임은 다음과 같다.

```text
MarketingState
= 광고 생성 세션 전체를 들고 다니는 LangGraph 상태

ValidatorNode
= 사용자 입력에서 MarketingContext를 추출하고 missing_fields를 계산하는 노드

OptionsNode
= 부족한 필드 하나에 대해 OptionQuestion을 만들고 interrupt하는 노드

StateUpdateNode
= resume된 사용자 선택값을 MarketingState에 반영하는 노드

FormatPlannerNode
= AdFormatSpec과 LayoutSpec을 먼저 확정하는 노드

CopywritingNode
= 광고 문구만 생성하는 노드

PromptOptimizationNode
= 이미지 방향과 구조화 ImagePrompt를 생성하는 노드

PromptRendererNode
= ImagePrompt를 SD3.5 / FLUX / GPT-image-2용 실제 prompt string으로 변환하는 노드

T2IGenerationNode
= 현재 image serving layer를 호출하는 노드

BackgroundValidationNode
= 텍스트 없는 배경 이미지 품질을 검증하는 노드

TextOverlayNode
= 정확한 한글 광고 문구를 후합성하는 노드

FinalValidationNode
= 최종 광고 이미지 OCR/가독성/룰 검증을 수행하는 노드
```
