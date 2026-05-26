좋아. 아래는 **LLM/LangGraph 구현 기준 스키마 확정본**이야. 네가 동의한 수정사항을 전부 반영했다.

기준은 네가 첨부한 최신 MarketingState/스키마 문서이며, 여기에 `snake_case 통일`, `Option JSON 오류 수정`, `GenerationEngine 사용자 질문 제거`, `RenderProfile 도입`, `Refactoring Node 분리`, `PromptRenderer 추가`, `checkpointer + thread_id + interrupt/resume` 규칙을 반영했다.  LangGraph 쪽은 공식 문서 기준으로, `interrupt()`는 JSON-serializable payload를 외부로 노출하고 checkpointer/state 저장 후 `Command(resume=...)`로 같은 `thread_id`에서 재개하는 구조를 전제로 잡았다. ([LangChain 문서][1])

---

# EasyAds LLM/LangGraph 구현 기준 스키마 확정본

## 0. 문서 목적

이 문서는 EasyAds / 사장님 배너공장의 **LLM + LangGraph 구현 기준 스키마 확정본**이다.

이번 문서의 목적은 다음이다.

```text
1. LLM/LangGraph 팀이 구현할 기준 스키마를 확정한다.
2. FE, Backend, Image Serving, Validation 파트와 충돌하지 않도록 Literal 값을 통일한다.
3. Validator / Options / FormatPlanner / Copywriting / PromptOptimization / PromptRenderer의 책임 범위를 분리한다.
4. Human-in-the-loop interrupt/resume 구조를 명확히 한다.
5. 멀티턴 수정 시 어떤 노드부터 재실행해야 하는지 dirty_fields 기준을 정의한다.
```

이번 확정본에서 반영한 핵심 수정사항은 다음이다.

```text
- field naming은 전부 snake_case로 통일
- Option JSON의 잘못된 value/id 오류 수정
- GenerationEngine은 일반 사용자 질문에서 제거
- 사용자는 RenderProfile만 선택 가능
- Refactoring Node는 Copywriting Node와 PromptOptimization Node로 분리
- PromptRenderer Node 추가
- checkpointer + thread_id + interrupt/resume 규칙 명시
- 최신 MarketingState / Literal / Schema 기준으로 통일
```

---

# 1. 전체 Workflow 확정안

## 1.1 최종 LangGraph 흐름

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

## 1.2 핵심 설계 원칙

이 프로젝트는 완전 자율 agent보다 **결정적 workflow + 제한적 LLM node** 구조가 맞다. LangGraph 공식 문서도 workflow와 agent를 구분하며, workflow는 미리 정의된 코드 경로를 따라가는 구조이고 agent는 모델이 동적으로 자신의 흐름과 tool 사용을 정하는 구조로 설명한다. 이 프로젝트는 광고 생성 절차가 정해져 있으므로 StateGraph workflow가 더 적합하다. ([LangChain 문서][2])

적용 원칙은 다음이다.

```text
1. Graph는 순서와 상태를 관리한다.
2. LLM은 구조화 출력이 필요한 node에서만 사용한다.
3. 이미지 생성은 LangGraph 내부에서 직접 무거운 모델을 들고 있지 않고 T2I service layer를 호출한다.
4. 사용자 선택이 필요한 순간에는 interrupt()로 멈춘다.
5. resume은 반드시 같은 thread_id로 진행한다.
6. 멀티턴 수정은 dirty_fields 기준으로 필요한 node부터 재실행한다.
```

---

# 2. Literal 값 확정

## 2.1 EntryMode

```python
EntryMode = Literal[
    "chat_start",
    "photo_start",
    "reference_start",
]
```

| 값                 | 의미          |
| ----------------- | ----------- |
| `chat_start`      | 대화로 시작하기    |
| `photo_start`     | 내 사진으로 만들기  |
| `reference_start` | 레퍼런스 보고 만들기 |

기존의 `chat`, `upload`, `reference`는 사용하지 않는다.

---

## 2.2 GenerationRoute

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

| 값                      | 의미                    |
| ---------------------- | --------------------- |
| `text_to_image`        | 텍스트만으로 광고 배경/포스터 생성   |
| `reference_guided_t2i` | 레퍼런스 스타일 DNA를 반영한 T2I |
| `product_composite`    | 제품 배경 제거 후 광고 배경에 합성  |
| `product_inpainting`   | 제품 보존형 배경 변경          |
| `interior_integration` | 매장/공간 이미지에 포스터 삽입     |
| `typography_only`      | 이미지 생성 없이 텍스트 합성만 수행  |

---

## 2.3 GenerationEngine

```python
GenerationEngine = Literal[
    "mock",
    "sd35_large",
    "flux",
    "gpt_image_2",
]
```

| 값             | 의미                                |
| ------------- | --------------------------------- |
| `mock`        | 개발/테스트용 placeholder               |
| `sd35_large`  | 기본 로컬 T2I 엔진                      |
| `flux`        | 고품질 로컬 프리미엄 엔진                    |
| `gpt_image_2` | OpenAI API 기반 fallback/premium 엔진 |

중요 규칙:

```text
GenerationEngine은 일반 사용자에게 직접 묻지 않는다.
내부 라우팅/개발자 설정/benchmark용 값으로만 사용한다.
```

---

## 2.4 RenderProfile

```python
RenderProfile = Literal[
    "fast",
    "balanced",
    "premium_local",
    "premium_api",
    "benchmark",
]
```

| 값               | 사용자 노출 라벨 | 내부 기본 엔진               | 용도              |
| --------------- | --------- | ---------------------- | --------------- |
| `fast`          | 빠르게 미리보기  | `sd35_large` 또는 `mock` | 빠른 preview      |
| `balanced`      | 기본 품질     | `sd35_large`           | 일반 생성           |
| `premium_local` | 고급 품질     | `flux`                 | 고품질 로컬 생성       |
| `premium_api`   | API 고급 품질 | `gpt_image_2`          | API 기반 fallback |
| `benchmark`     | 비교 실험     | 복수 엔진                  | 내부 평가           |

사용자에게는 `GenerationEngine` 대신 `RenderProfile`만 노출한다.

---

## 2.5 JobStatus

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

기존 `refactoring`은 더 이상 단일 상태로 쓰지 않는다.
대신 아래처럼 분리한다.

```text
refactoring
→ copywriting
→ optimizing_prompt
→ rendering_prompt
```

---

## 2.6 CopySpace

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

## 2.7 MissingField

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

질문 우선순위는 다음과 같이 둔다.

```text
P0: business_type, item_or_service, promotion_goal, ad_format
P1: target_persona, region_type, brand_tone
P2: usp, time_context, price_or_discount, brand_name, contact_or_order_method
P3: copy_space, render_profile, 세부 시각 취향
```

MVP에서는 P0/P1 중심으로 질문하고, P2/P3는 가능하면 추론하거나 optional로 둔다.

---

# 3. MarketingState 확정본

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
    progress_state: ProgressState | None

    # Input / Memory
    user_input: str
    prompt_json: dict[str, Any] | None
    messages: list[ConversationMessage]
    conversation_summary: str | None
    current_brief: dict[str, Any]
    dirty_fields: list[str]
    user_selection: UserSelectionRequest | None

    # Image / Reference Input
    image_input: ImageInput | None
    reference_input: ReferenceInput | None
    image_features: ImageFeatures | None
    reference_style: ReferenceStyleSpec | None

    # Validation / HITL
    context: MarketingContext
    validator_output: ValidatorOutput | None
    missing_fields: list[MissingField]
    option_question: OptionQuestion | None

    # Planning / Design
    ad_format_spec: AdFormatSpec | None
    layout_spec: LayoutSpec | None

    # Copy / Prompt
    marketing_copy: MarketingCopy | None
    copywriting_output: CopywritingOutput | None
    image_prompt: ImagePrompt | None
    prompt_optimization_output: PromptOptimizationOutput | None
    user_readable_image_guide: UserReadableImageGuide | None
    prompt_render_output: PromptRenderOutput | None

    # T2I / Image Generation
    t2i_request: T2IRequest | None
    t2i_result: T2IResult | None
    candidates: list[GeneratedImageCandidate]
    selected_candidate_id: str | None

    # Overlay / Validation / Output
    background_validation_report: BackgroundValidationReport | None
    text_overlay_config: TextOverlayConfig | None
    final_image_path: str | None
    final_validation_report: FinalValidationReport | None
    validation_report: ValidationReport | None

    # Artifacts / Error / Metadata
    artifact_refs: list[ArtifactRef]
    error_message: str | None
    error_info: ErrorInfo | None
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
- prompt_render_output 유지
- selected_candidate_id 명시
- thread_id는 checkpointer resume의 핵심 key
```

---

# 4. 요청 스키마

## 4.1 InitialMarketingRequest

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

# 5. Context / Validator 스키마

## 5.1 MarketingContext

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

v1에서는 `BusinessType`, `RegionType`, `PromotionGoal` 등을 엄격한 Literal로 고정하지 않고 `str`로 둬도 된다. 이유는 소상공인 업종이 너무 다양하고, `custom` 입력이 많을 수 있기 때문이다. 다만 옵션 value는 표준값을 사용한다.

---

## 5.2 ValidatorOutput

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

# 6. Options / HITL 스키마

## 6.1 OptionItem

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

## 6.2 OptionQuestion

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

Options Node는 **한 번에 하나의 missing field에 대한 질문만 생성**하는 것을 v1 기본값으로 한다.

```text
좋은 구조:
missing_fields = ["brand_tone", "ad_format"]
→ OptionsNode는 우선순위가 가장 높은 field 하나만 질문
→ user_selection 수신
→ StateUpdate
→ Validator 재진입
```

---

## 6.3 UserSelectionRequest

```python
class UserSelectionRequest(BaseModel):
    job_id: str
    thread_id: str

    field: MissingField
    value: str | list[str]

    custom_text: str | None = None
```

---

## 6.4 Corrected Option Question Registry

아래는 기존 옵션 JSON을 수정한 확정 버전이다.

```python
OPTION_QUESTION_REGISTRY: dict[MissingField, OptionQuestion] = {
    "business_type": OptionQuestion(
        field="business_type",
        question="어떤 가게의 광고인가요?",
        options=[
            OptionItem(id=1, label="식당/레스토랑", value="restaurant"),
            OptionItem(id=2, label="카페/디저트", value="cafe"),
            OptionItem(id=3, label="뷰티/미용실", value="beauty_salon"),
            OptionItem(id=4, label="주점/바", value="bar"),
            OptionItem(id=5, label="피트니스/헬스", value="fitness"),
            OptionItem(id=6, label="학원/교육", value="academy"),
            OptionItem(id=7, label="꽃집", value="flower_shop"),
            OptionItem(id=8, label="일반 매장/소매점", value="store"),
            OptionItem(id=9, label="직접 입력", value="custom"),
        ],
        required=True,
    ),

    "promotion_goal": OptionQuestion(
        field="promotion_goal",
        question="어떤 광고를 만들까요?",
        options=[
            OptionItem(id=1, label="신메뉴/신상품 출시", value="new_launch"),
            OptionItem(id=2, label="시즌 한정 홍보", value="seasonal_limited"),
            OptionItem(id=3, label="할인 이벤트", value="discount_event"),
            OptionItem(id=4, label="예약/방문 유도", value="reservation_cta"),
            OptionItem(id=5, label="브랜드 감성 홍보", value="brand_awareness"),
            OptionItem(id=6, label="리뷰 이벤트", value="review_event"),
            OptionItem(id=7, label="단골/재방문 유도", value="retention"),
            OptionItem(id=8, label="직접 입력", value="custom"),
        ],
        required=True,
    ),

    "brand_tone": OptionQuestion(
        field="brand_tone",
        question="분위기는 어떤 느낌이 좋나요?",
        options=[
            OptionItem(id=1, label="감성적인", value="emotional_mood"),
            OptionItem(id=2, label="상큼한", value="fresh_refreshing"),
            OptionItem(id=3, label="고급스러운", value="premium_luxurious"),
            OptionItem(id=4, label="귀여운", value="cute_adorable"),
            OptionItem(id=5, label="깔끔한", value="clean_minimal"),
            OptionItem(id=6, label="따뜻한", value="warm_cozy"),
            OptionItem(id=7, label="힙하고 트렌디한", value="hip_trendy"),
            OptionItem(id=8, label="강렬한", value="bold_urgent"),
            OptionItem(id=9, label="직접 입력", value="custom"),
        ],
        required=True,
    ),

    "ad_format": OptionQuestion(
        field="ad_format",
        question="어디에 사용할 광고인가요?",
        options=[
            OptionItem(id=1, label="인스타그램 피드 1:1", value="instagram_feed"),
            OptionItem(id=2, label="인스타그램 스토리 9:16", value="instagram_story"),
            OptionItem(id=3, label="포스터 4:5", value="poster"),
            OptionItem(id=4, label="전단지 A4", value="flyer"),
            OptionItem(id=5, label="웹 배너 16:9", value="banner"),
            OptionItem(id=6, label="스마트스토어/상세페이지", value="product_detail"),
            OptionItem(id=7, label="기타 사이즈", value="custom"),
        ],
        required=True,
    ),

    "target_persona": OptionQuestion(
        field="target_persona",
        question="주요 타겟 고객을 선택해주세요.",
        options=[
            OptionItem(id=1, label="20대 대학생", value="college_student"),
            OptionItem(id=2, label="30~40대 직장인", value="office_worker"),
            OptionItem(id=3, label="20~30대 커플/친구", value="young_social"),
            OptionItem(id=4, label="관광객", value="tourist"),
            OptionItem(id=5, label="가족/동네 단골", value="family_local"),
            OptionItem(id=6, label="직접 입력", value="custom"),
        ],
        required=False,
    ),

    "region_type": OptionQuestion(
        field="region_type",
        question="가게가 위치한 상권 유형을 선택해주세요.",
        options=[
            OptionItem(id=1, label="오피스/직장인 상권", value="office_district"),
            OptionItem(id=2, label="대학가", value="university_area"),
            OptionItem(id=3, label="감성/힙 상권", value="trendy_district"),
            OptionItem(id=4, label="관광지/명소 상권", value="tourist_spot"),
            OptionItem(id=5, label="주거지/동네 상권", value="residential_area"),
            OptionItem(id=6, label="직접 입력", value="custom"),
        ],
        required=False,
    ),

    "usp": OptionQuestion(
        field="usp",
        question="우리 가게만의 차별점을 선택해주세요. 복수 선택도 가능해요.",
        options=[
            OptionItem(id=1, label="단체석/룸 예약 가능", value="group_reservation"),
            OptionItem(id=2, label="뷰맛집/포토존", value="view_spot"),
            OptionItem(id=3, label="가성비가 좋음", value="value_for_money"),
            OptionItem(id=4, label="늦은 시간까지 영업", value="late_hours"),
            OptionItem(id=5, label="신선한 재료", value="fresh_ingredients"),
            OptionItem(id=6, label="직접 입력", value="custom"),
        ],
        required=False,
        multi_select=True,
    ),

    "time_context": OptionQuestion(
        field="time_context",
        question="주로 어떤 시간대나 상황에 노출할 광고인가요?",
        options=[
            OptionItem(id=1, label="평일 점심", value="weekday_lunch"),
            OptionItem(id=2, label="평일 저녁/회식", value="weekday_dinner"),
            OptionItem(id=3, label="금요일 밤/불금", value="friday_night"),
            OptionItem(id=4, label="주말 브런치", value="weekend_brunch"),
            OptionItem(id=5, label="주말 저녁", value="weekend_dinner"),
            OptionItem(id=6, label="직접 입력", value="custom"),
        ],
        required=False,
    ),
}
```

제거된 질문:

```text
GenerationEngine 질문
CopySpace 필수 질문
```

이 두 개는 사용자가 아니라 시스템이 기본 결정한다.

---

# 7. ProgressState

```python
class ProgressState(BaseModel):
    current_step: int
    total_steps: int
    current_label: str

    skipped_steps: list[str] = Field(default_factory=list)
    remaining_fields: list[MissingField] = Field(default_factory=list)

    can_skip_question_screen: bool = False
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

# 8. 광고 형식 / 레이아웃 스키마

## 8.1 AdFormatSpec

```python
class AdFormatSpec(BaseModel):
    ad_format: Literal[
        "instagram_feed",
        "instagram_story",
        "poster",
        "flyer",
        "product_detail",
        "banner",
    ]

    platform: Literal[
        "instagram",
        "offline",
        "web",
        "naver_smartstore",
        "naver_place",
        "danggeun",
        "etc",
    ]

    aspect_ratio: Literal[
        "1:1",
        "4:5",
        "9:16",
        "16:9",
        "A4_vertical",
        "custom",
    ]

    width: int | None = None
    height: int | None = None

    information_density: Literal[
        "low",
        "medium",
        "high",
    ]

    visual_priority: Literal[
        "product_hero",
        "mood_first",
        "information_first",
        "detail_explanation",
        "click_conversion",
    ]

    output_strategy: Literal[
        "generate_text_free_background_then_overlay",
        "template_composite",
        "multi_section_layout",
        "product_preserving_edit",
        "typography_only",
    ]
```

## 8.2 Format Mapping

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

## 8.3 LayoutSpec

```python
class Zone(BaseModel):
    x: float
    y: float
    w: float
    h: float


class TextZone(BaseModel):
    role: Literal[
        "headline",
        "subcopy",
        "cta",
        "disclaimer",
        "price",
        "hashtag",
    ]
    zone: Zone
    max_chars: int | None = None


class LayoutSpec(BaseModel):
    layout_type: Literal[
        "single_hero",
        "split_text_image",
        "top_headline_bottom_product",
        "multi_section",
        "story_vertical",
        "flyer_information",
    ]

    copy_space: CopySpace

    safe_area: dict[str, int] = Field(
        default_factory=lambda: {
            "top": 80,
            "right": 80,
            "bottom": 80,
            "left": 80,
        }
    )

    text_zones: list[TextZone] = Field(default_factory=list)
    product_zone: Zone | None = None
    cta_zone: Zone | None = None

    overlay_style: Literal[
        "none",
        "gradient",
        "solid_box",
        "glassmorphism",
        "stroke_shadow",
    ] = "gradient"

    text_align: Literal[
        "left",
        "center",
        "right",
    ] = "center"

    max_text_density: Literal[
        "low",
        "medium",
        "high",
    ] = "medium"
```

---

# 9. Copywriting Node 스키마

## 9.1 MarketingCopy

```python
class MarketingCopy(BaseModel):
    headline: str
    subcopy: str
    cta: str

    price_line: str | None = None
    period_line: str | None = None
    disclaimer: str | None = None
    hashtags: list[str] = Field(default_factory=list)

    tone_notes: str | None = None
```

## 9.2 CopywritingOutput

```python
class CopywritingOutput(BaseModel):
    marketing_copy: MarketingCopy
    context: MarketingContext
    ad_format_spec: AdFormatSpec

    applied_tone_profile: str | None = None
    rationale: str | None = None
```

## 9.3 Copy Tone Mapping Table

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
    "beauty_salon": {
        "default": {
            "style": "부담을 낮추고 변화를 기대하게 하는 문장",
            "keywords": ["분위기 전환", "나에게 맞는", "트렌디한", "예약"],
        },
    },
    "fitness": {
        "default": {
            "style": "동기부여와 실천을 유도하는 문장",
            "keywords": ["오늘부터", "변화", "루틴", "건강"],
        },
    },
    "store": {
        "default": {
            "style": "상품 혜택과 구매 이유가 명확한 문장",
            "keywords": ["특가", "신상품", "한정", "지금"],
        },
    },
}
```

---

# 10. PromptOptimization Node 스키마

## 10.1 ImagePrompt

```python
class ImagePrompt(BaseModel):
    subject: str
    style: str
    lighting: str
    composition: str
    copy_space: CopySpace
    negative_prompt: str

    aspect_ratio_hint: str | None = None
    style_reference_hint: str | None = None
    must_avoid: list[str] = Field(default_factory=list)
```

## 10.2 UserReadableImageGuide

```python
class UserReadableImageGuide(BaseModel):
    subject_ko: str
    mood_ko: str
    composition_ko: str
    copy_space_ko: str
    summary: str
```

## 10.3 PromptOptimizationOutput

```python
class PromptOptimizationOutput(BaseModel):
    image_prompt: ImagePrompt
    user_readable_image_guide: UserReadableImageGuide

    ad_format_spec: AdFormatSpec
    layout_spec: LayoutSpec
    context: MarketingContext

    rationale: str | None = None
```

---

# 11. PromptRenderer Node 스키마

## 11.1 PromptRenderOutput

```python
class PromptRenderOutput(BaseModel):
    engine: GenerationEngine
    render_profile: RenderProfile

    positive_prompt: str
    negative_prompt: str | None = None

    width: int
    height: int

    render_notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
```

## 11.2 Engine별 렌더링 규칙

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

# 12. RefactoringOutput 처리 방침

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

# 13. Image / Reference 스키마

## 13.1 ImageInput

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

## 13.2 ImageFeatures

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

## 13.3 ReferenceInput / ReferenceStyleSpec

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

# 14. T2I 연동 스키마

## 14.1 T2IRequest

현재 이미지 serving 쪽 구현과 맞춘다.

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

## 14.2 T2IRequest metadata 기준

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

    "effective_negative_prompt": "...",
    "negative_prompt_sources": [...],
}
```

## 14.3 T2IResult

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

# 15. 후보 / 오버레이 / 검증 스키마

## 15.1 GeneratedImageCandidate

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

## 15.2 TextOverlayConfig

```python
class TextOverlayConfig(BaseModel):
    marketing_copy: MarketingCopy
    ad_format_spec: AdFormatSpec
    layout_spec: LayoutSpec

    copy_space: CopySpace
    font_path: str | None = None

    brand_color: str = "#E85D75"
    text_color: str = "#FFFFFF"

    overlay_style: Literal[
        "none",
        "gradient",
        "solid_box",
        "glassmorphism",
        "stroke_shadow",
    ] = "gradient"

    output_channel: Literal[
        "instagram_feed",
        "instagram_story",
        "naver_place",
        "smartstore_thumbnail",
        "flyer",
        "banner",
    ] = "instagram_feed"
```

## 15.3 BackgroundValidationReport

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

## 15.4 FinalValidationReport

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

## 15.5 ValidationReport

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

# 16. JobStatusResponse

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

# 17. LangGraph Interrupt / Resume 규칙

## 17.1 기본 규칙

LangGraph의 interrupt는 graph 실행을 멈추고 외부 입력을 기다리며, checkpointer가 저장한 graph state를 기준으로 같은 `thread_id`에서 재개된다. 따라서 HITL 구조에서는 checkpointer와 thread_id가 필수다. ([LangChain 문서][1])

필수 규칙:

```text
1. 모든 graph invoke에는 thread_id를 config로 넣는다.
2. OptionsNode는 interrupt(option_question_json)을 호출한다.
3. FE/BFF는 interrupt payload를 사용자에게 렌더링한다.
4. 사용자가 선택하면 Command(resume=user_selection_payload)를 보낸다.
5. resume은 반드시 같은 thread_id로 호출한다.
6. OptionsNode 내부에서 interrupt 이전에 비멱등 side effect를 만들지 않는다.
```

## 17.2 invoke 예시

```python
config = {
    "configurable": {
        "thread_id": thread_id,
    }
}

result = graph.invoke(initial_input, config=config, version="v2")
```

## 17.3 interrupt payload 예시

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

## 17.4 resume payload 예시

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
    version="v2",
)
```

공식 문서 기준으로 `Command(resume=...)`에 들어간 값은 interrupt 호출 지점의 반환값이 되며, 같은 thread ID를 써야 기존 checkpoint에서 재개된다. ([LangChain 문서][1])

---

# 18. Node 책임 범위 확정

## 18.1 InputNode

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

## 18.2 EntryRouterNode

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

## 18.3 ValidatorNode

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

---

## 18.4 OptionsNode

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

## 18.5 StateUpdateNode

역할:

```text
- Command(resume=...)로 들어온 UserSelectionRequest 처리
- selected value를 MarketingContext 또는 request field에 반영
- messages append
- current_brief 업데이트
- dirty_fields 재계산
- status = updating_state
```

---

## 18.6 FormatPlannerNode

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

## 18.7 CopywritingNode

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

## 18.8 PromptOptimizationNode

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

## 18.9 PromptRendererNode

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

## 18.10 T2IRequestBuilderNode

역할:

```text
- PromptRenderOutput을 T2IRequest로 변환
- metadata 구성
- render_text_in_image = false 정책 유지
```

---

## 18.11 T2IGenerationNode

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

## 18.12 BackgroundValidationNode

역할:

```text
- 텍스트 artifact 검사
- watermark/logo 검사
- copy_space 검사
- 광고 배경 품질 검사
- retry 여부 결정
```

---

## 18.13 TextOverlayNode

역할:

```text
- MarketingCopy를 이미지 위에 후합성
- LayoutSpec safe_area 반영
- 한글 텍스트 정확도 보장
```

---

## 18.14 FinalValidationNode

역할:

```text
- OCR 검증
- rule 기반 검증
- 가독성 검증
- layout 검증
- 최종 광고 품질 검사
```

---

# 19. dirty_fields 기반 멀티턴 수정 규칙

## 19.1 문구만 수정

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

## 19.2 분위기 수정

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

## 19.3 포맷 변경

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

## 19.4 후보 선택

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

# 20. Graph Conditional Routing 규칙

## 20.1 EntryRouter

```python
def route_by_entry_mode(state: MarketingState) -> str:
    if state["entry_mode"] == "photo_start":
        return "image_feature_extraction"
    if state["entry_mode"] == "reference_start":
        return "reference_style_extraction"
    return "validator"
```

## 20.2 ContextCompletenessRouter

```python
def route_after_validator(state: MarketingState) -> str:
    if state.get("missing_fields"):
        return "options"
    return "format_planner"
```

## 20.3 RetryRouter

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

# 21. 최종 확정된 구현 우선순위

LLM/LangGraph 파트는 이 순서로 구현하는 게 맞다.

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
10. Graph skeleton 연결
11. T2I service와 연결
12. 멀티턴 dirty_fields partial rerun
```

---

# 22. 최종 요약

이번 확정본의 핵심은 다음이다.

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

따라서 LLM/LangGraph 구현 기준은 이렇게 확정하면 된다.

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

이 구조가 현재 프로젝트 기준으로 가장 안정적이다.
