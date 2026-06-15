# MarketingState Sub-State Split (Organizational) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the flat 161-field `MarketingState` TypedDict into 10 pipeline-aligned group TypedDicts combined via multiple inheritance, with ZERO runtime/behavior change (the merged `__annotations__` stays byte-identical), so the schema becomes navigable (review priority ④, "필드 그룹별 sub-state 분리" — organizational interpretation chosen by the user).

**Architecture:** `MarketingState` is the LangGraph `StateGraph(MarketingState)` schema; nodes return partial flat dicts that LangGraph merges by top-level key, and ~557 call sites read/write flat keys. We therefore keep the runtime shape FLAT. TypedDict multiple inheritance (`class MarketingState(GroupA, GroupB, ...)`) yields a class whose `__annotations__` is the union of all parents' annotations — identical to the current flat class — so LangGraph, every node, and every access site are completely unaffected. Only the source organization changes.

**Tech Stack:** Python 3.12 `typing.TypedDict` (multiple inheritance), pytest via `EASYADS_DB_BACKEND=memory uv run python -m pytest <path> -q` from repo root.

**Correctness contract (non-negotiable):** after the split, `MarketingState.__annotations__` must contain EXACTLY the same 161 field names with the same annotation strings as before. The partition is exhaustive (every field in exactly one group) and disjoint (no field in two groups). `from __future__ import annotations` is active in state.py, so annotation values are strings — easy to compare.

**Conventions:**
- Branch: create `refactor/marketing-state-substate-split` off latest `origin/develop` (after PR #180 merges) OR stacked on `refactor/marketing-state-union-cleanup` if #180 is not yet merged. Confirm base before starting.
- Line numbers reference state.py as of 2026-06-14 (post-union-cleanup). Match the shown field blocks, not line numbers.
- Do NOT modify the untracked `docs/superpowers/plans/2026-06-13-generation-job-background-resume-reliability.md`.
- Conventional commits + Co-Authored-By trailer shown per step.

---

### Task 1: Characterization test — lock the exact 161-field surface

**Files:**
- Create: `orchestrator/tests/test_marketing_state_shape.py`

- [ ] **Step 1: Write the test (passes against the CURRENT flat class)**

Create `orchestrator/tests/test_marketing_state_shape.py`:

```python
"""Characterization guard for the MarketingState field surface.

Locks the exact set of 161 fields so the sub-state reorganization cannot
silently drop, rename, duplicate, or re-type a field.
"""

from orchestrator.app.graph.state import MarketingState

EXPECTED_FIELDS = frozenset({
    # job meta / routing / accounting
    "schema_version", "job_id", "thread_id", "usage_job_db_id", "usage_thread_db_id",
    "workspace_id", "project_id", "user_id", "organization_id", "user_plan",
    "plan_policy", "model_selections", "llm_call_results", "revision", "status",
    "entry_mode", "generation_route", "engine", "render_profile", "progress_state",
    # intake / brief / product understanding
    "user_input", "prompt_json", "messages", "conversation_summary", "current_brief",
    "dirty_fields", "user_selection", "image_input", "reference_input", "source_asset_id",
    "reference_asset_id", "source_image_path", "reference_image_path", "input_evidence_bundle",
    "input_normalization_status", "input_conflicts", "unresolved_questions", "product_understanding",
    "product_understanding_status", "product_understanding_confidence",
    "product_understanding_provider_metadata", "vision_preprocess_mode",
    # reference templates / vision preprocess
    "selected_reference_template_id", "selected_reference_template", "reference_template_selection",
    "vision_pipeline_results", "image_preprocess_result", "image_features",
    "reference_style_profile", "product_preserve_spec", "reference_style",
    # context / validation / options
    "context", "validator_output", "missing_fields", "option_question",
    # copy
    "ad_format_spec", "layout_spec", "marketing_copy", "copywriting_output", "copy_generation_mode",
    "copy_candidates", "copy_candidate_origin", "selected_copy_id", "selected_channel_id",
    "selected_ad_format", "selected_tone", "custom_direction", "user_custom_headline",
    "user_custom_subcopy", "copy_required", "text_overlay_pending", "tone_binding_output",
    "copy_mode_inference_output", "copy_selection", "input_compliance_risk", "copy_compliance",
    "copy_compliance_status", "copy_compliance_publication_ready", "copy_compliance_gate",
    "copy_compliance_resolution", "custom_copy_input", "copy_spec", "text_layout_spec",
    "text_style_spec", "copy_visual_intent", "product_copy_context", "copy_presence_plan",
    "language_policy", "interaction_copy_plan", "minimal_copy_candidates",
    "selected_minimal_copy_candidate_id",
    # native creative
    "creative_execution_plan", "native_typography_eligibility", "approved_native_copy_brief",
    "native_source_visual_analysis", "native_creative_prompt_package",
    "native_creative_preflight_review", "native_generation_budget", "native_generation_result",
    "native_generation_review", "native_generation_status",
    # typography / layout refinement
    "typography_art_direction", "font_catalog_summary", "adaptive_typography_report",
    "image_layout_analysis", "layout_candidate_scores", "layout_refinement_result",
    "layout_copy_fit_report", "layout_revision_attempts",
    # image prompt / t2i
    "image_prompt_spec", "image_prompt", "prompt_optimization_output", "user_readable_image_guide",
    "prompt_render_output", "t2i_request", "t2i_result",
    # quality / ocr gates / candidates
    "background_quality_gate", "final_quality_gate", "quality_gate_attempts",
    "quality_gate_decision", "quality_gate_status", "quality_gate_retry_feedback",
    "background_ocr_gate", "final_ocr_gate", "ocr_gate_decision", "ocr_gate_status",
    "ocr_gate_retry_feedback", "ocr_revision_action", "ocr_revision_attempts",
    "regeneration_patch", "candidates", "selected_candidate_id",
    # render / validation / finalize
    "background_validation_report", "safe_area_report", "readability_report", "render_result",
    "text_overlay_config", "final_image_path", "final_validation_report",
    "final_composite_quality_report", "final_composite_revision_plan", "final_composite_revision_patch",
    "final_composite_retry_feedback", "final_composite_partial_rerun", "final_composite_rerun_action",
    "reuse_existing_background", "final_copy_revision_result", "final_composite_attempts",
    "final_copy_revision_attempts", "final_layout_revision_attempts", "final_style_revision_attempts",
    "final_background_regeneration_attempts", "validation_report", "result_payload", "artifact_refs",
    "error_message", "error_info", "created_at", "updated_at", "latency_ms", "route",
})


def test_marketing_state_has_exactly_expected_fields():
    actual = set(MarketingState.__annotations__.keys())
    assert actual == EXPECTED_FIELDS, {
        "missing": EXPECTED_FIELDS - actual,
        "unexpected": actual - EXPECTED_FIELDS,
    }


def test_marketing_state_field_count_is_161():
    assert len(MarketingState.__annotations__) == 161


def test_marketing_state_all_keys_optional_under_total_false():
    # total=False semantics must survive the inheritance reassembly.
    assert MarketingState.__optional_keys__ == frozenset(MarketingState.__annotations__)
    assert MarketingState.__required_keys__ == frozenset()
```

- [ ] **Step 2: Run — must PASS against current flat class**

Run: `EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests/test_marketing_state_shape.py -q`
Expected: 3 passed. If `test_marketing_state_has_exactly_expected_fields` fails, the EXPECTED_FIELDS set here is wrong for the current code — fix EXPECTED_FIELDS to match `MarketingState.__annotations__` (print the diff), since current code is the source of truth, before proceeding.

- [ ] **Step 3: Commit**

```bash
git add orchestrator/tests/test_marketing_state_shape.py
git commit -m "test(graph): lock MarketingState 161-field surface before sub-state split

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Split into 10 group TypedDicts + reassemble via inheritance

**Files:**
- Modify: `orchestrator/app/graph/state.py` (replace the flat `class MarketingState` body, ~lines 34-195)

- [ ] **Step 1: Snapshot the current merged annotations (pre-change safety net)**

Run:
```bash
EASYADS_DB_BACKEND=memory uv run python -c "
from orchestrator.app.graph.state import MarketingState
import json
print(json.dumps(dict(MarketingState.__annotations__), ensure_ascii=False))
" > /tmp/ms_annotations_before.json
wc -c /tmp/ms_annotations_before.json
```
Expected: a non-empty JSON file. Keep it for Step 4's comparison.

- [ ] **Step 2: Replace the flat class with grouped TypedDicts**

In `orchestrator/app/graph/state.py`, replace the entire `class MarketingState(TypedDict, total=False):` block (from `class MarketingState` through the last field `route: NotRequired[GenerationRoute]`, ~lines 34-195) with the following. Each field annotation is copied VERBATIM from the current class — only the grouping/class headers are new:

```python
class JobMetaState(TypedDict, total=False):
    """Identity, tenancy, routing, plan policy, and run accounting."""
    schema_version: str
    job_id: str
    thread_id: str
    usage_job_db_id: str | None
    usage_thread_db_id: str | None
    workspace_id: str | None
    project_id: str | None
    user_id: str | None
    organization_id: str | None
    user_plan: UserPlan | str
    plan_policy: dict[str, Any] | PlanPolicy
    model_selections: list[dict[str, Any] | ModelSelection]
    llm_call_results: list[dict[str, Any] | LLMCallResult]
    revision: int
    status: JobStatus
    entry_mode: EntryMode
    generation_route: GenerationRoute
    engine: GenerationEngine
    render_profile: RenderProfile
    progress_state: dict[str, Any] | None


class IntakeState(TypedDict, total=False):
    """User input, conversation/brief, asset inputs, and product understanding."""
    user_input: str
    prompt_json: dict[str, Any] | None
    messages: list[dict[str, Any] | ConversationMessage]
    conversation_summary: str | None
    current_brief: dict[str, Any]
    dirty_fields: list[str]
    user_selection: dict[str, Any] | None
    image_input: dict[str, Any] | None
    reference_input: dict[str, Any] | None
    source_asset_id: str | None
    reference_asset_id: str | None
    source_image_path: str | None
    reference_image_path: str | None
    input_evidence_bundle: dict[str, Any] | None
    input_normalization_status: str | None
    input_conflicts: list[dict[str, Any]]
    unresolved_questions: list[str]
    product_understanding: dict[str, Any] | None
    product_understanding_status: str | None
    product_understanding_confidence: float | None
    product_understanding_provider_metadata: dict[str, Any] | None
    vision_preprocess_mode: str | None


class ReferenceVisionState(TypedDict, total=False):
    """Reference template selection and vision preprocessing artifacts."""
    selected_reference_template_id: str | None
    selected_reference_template: dict[str, Any] | None
    reference_template_selection: dict[str, Any] | None
    vision_pipeline_results: list[dict[str, Any]]
    image_preprocess_result: dict[str, Any] | None
    image_features: dict[str, Any] | None
    reference_style_profile: dict[str, Any] | None
    product_preserve_spec: dict[str, Any] | None
    reference_style: dict[str, Any] | None


class ContextValidationState(TypedDict, total=False):
    """Resolved marketing context, validator output, and option questions."""
    context: dict[str, Any] | MarketingContext
    validator_output: dict[str, Any] | None
    missing_fields: list[MissingField]
    option_question: dict[str, Any] | None


class CopyState(TypedDict, total=False):
    """Ad format, copy generation, compliance, and copy/text specs."""
    ad_format_spec: dict[str, Any] | None
    layout_spec: dict[str, Any] | None
    marketing_copy: dict[str, Any] | None
    copywriting_output: dict[str, Any] | None
    copy_generation_mode: CopyGenerationMode | None
    copy_candidates: list[dict[str, Any] | CopyCandidate]
    copy_candidate_origin: str | None
    selected_copy_id: str | None
    selected_channel_id: str | None
    selected_ad_format: str | None
    selected_tone: str | None
    custom_direction: str | None
    user_custom_headline: str | None
    user_custom_subcopy: str | None
    copy_required: bool
    text_overlay_pending: bool
    tone_binding_output: dict[str, Any] | None
    copy_mode_inference_output: dict[str, Any] | None
    copy_selection: dict[str, Any] | None
    input_compliance_risk: dict[str, Any] | None
    copy_compliance: list[dict[str, Any]]
    copy_compliance_status: str | None
    copy_compliance_publication_ready: bool
    copy_compliance_gate: dict[str, Any] | None
    copy_compliance_resolution: dict[str, Any] | None
    custom_copy_input: dict[str, Any] | None
    copy_spec: dict[str, Any] | None
    text_layout_spec: dict[str, Any] | None
    text_style_spec: dict[str, Any] | None
    copy_visual_intent: dict[str, Any] | None
    product_copy_context: dict[str, Any] | None
    copy_presence_plan: dict[str, Any] | None
    language_policy: dict[str, Any] | None
    interaction_copy_plan: dict[str, Any] | None
    minimal_copy_candidates: list[dict[str, Any]]
    selected_minimal_copy_candidate_id: str | None


class NativeCreativeState(TypedDict, total=False):
    """GPT-Image native typography single-shot pipeline."""
    creative_execution_plan: dict[str, Any] | None
    native_typography_eligibility: dict[str, Any] | None
    approved_native_copy_brief: dict[str, Any] | None
    native_source_visual_analysis: dict[str, Any] | None
    native_creative_prompt_package: dict[str, Any] | None
    native_creative_preflight_review: dict[str, Any] | None
    native_generation_budget: dict[str, Any] | None
    native_generation_result: dict[str, Any] | None
    native_generation_review: dict[str, Any] | None
    native_generation_status: str | None


class TypographyLayoutState(TypedDict, total=False):
    """Typography art direction and layout-fit refinement."""
    typography_art_direction: dict[str, Any] | None
    font_catalog_summary: list[dict[str, Any]]
    adaptive_typography_report: dict[str, Any] | None
    image_layout_analysis: dict[str, Any] | None
    layout_candidate_scores: list[dict[str, Any]]
    layout_refinement_result: dict[str, Any] | None
    layout_copy_fit_report: dict[str, Any] | None
    layout_revision_attempts: int


class ImagePromptT2IState(TypedDict, total=False):
    """Image prompt construction and text-to-image request/result."""
    image_prompt_spec: dict[str, Any] | None
    image_prompt: dict[str, Any] | None
    prompt_optimization_output: dict[str, Any] | None
    user_readable_image_guide: dict[str, Any] | None
    prompt_render_output: dict[str, Any] | None
    t2i_request: dict[str, Any] | None
    t2i_result: dict[str, Any] | None


class QualityGateState(TypedDict, total=False):
    """Quality + OCR gates, regeneration, and image candidates."""
    background_quality_gate: dict[str, Any] | None
    final_quality_gate: dict[str, Any] | None
    quality_gate_attempts: int
    quality_gate_decision: str | None
    quality_gate_status: str | None
    quality_gate_retry_feedback: list[str]
    background_ocr_gate: dict[str, Any] | None
    final_ocr_gate: dict[str, Any] | None
    ocr_gate_decision: str | None
    ocr_gate_status: str | None
    ocr_gate_retry_feedback: list[str]
    ocr_revision_action: str | None
    ocr_revision_attempts: int
    regeneration_patch: dict[str, Any] | None
    candidates: list[dict[str, Any] | GeneratedImageCandidate]
    selected_candidate_id: str | None


class RenderFinalizeState(TypedDict, total=False):
    """Rendering, validation reports, final composite revision, and result."""
    background_validation_report: dict[str, Any] | None
    safe_area_report: dict[str, Any] | None
    readability_report: dict[str, Any] | None
    render_result: dict[str, Any] | None
    text_overlay_config: dict[str, Any] | None
    final_image_path: str | None
    final_validation_report: dict[str, Any] | None
    final_composite_quality_report: dict[str, Any] | None
    final_composite_revision_plan: dict[str, Any] | None
    final_composite_revision_patch: dict[str, Any] | None
    final_composite_retry_feedback: list[str]
    final_composite_partial_rerun: bool
    final_composite_rerun_action: str | None
    reuse_existing_background: bool
    final_copy_revision_result: dict[str, Any] | None
    final_composite_attempts: int
    final_copy_revision_attempts: int
    final_layout_revision_attempts: int
    final_style_revision_attempts: int
    final_background_regeneration_attempts: int
    validation_report: dict[str, Any] | None
    result_payload: dict[str, Any] | None
    artifact_refs: list[dict[str, Any] | ArtifactRef]
    error_message: str | None
    error_info: dict[str, Any] | None
    created_at: str
    updated_at: str
    latency_ms: int | None
    route: NotRequired[GenerationRoute]


class MarketingState(
    JobMetaState,
    IntakeState,
    ReferenceVisionState,
    ContextValidationState,
    CopyState,
    NativeCreativeState,
    TypographyLayoutState,
    ImagePromptT2IState,
    QualityGateState,
    RenderFinalizeState,
    total=False,
):
    """Full LangGraph state — flat at runtime; organized into the sub-state
    groups above for navigability. Composition is by multiple inheritance, so
    `__annotations__` is the union of all groups and the runtime shape is the
    same flat dict every node already reads/writes. See docs/state-source-of-truth.md.
    """
```

- [ ] **Step 3: Run the characterization guard (must stay green)**

Run: `EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests/test_marketing_state_shape.py -q`
Expected: 3 passed. A failure here means a field was dropped/duplicated/miscategorized between groups — diff the reported missing/unexpected sets and fix the grouping.

- [ ] **Step 4: Byte-compare merged annotations against the pre-change snapshot**

Run:
```bash
EASYADS_DB_BACKEND=memory uv run python -c "
from orchestrator.app.graph.state import MarketingState
import json
print(json.dumps(dict(MarketingState.__annotations__), ensure_ascii=False))
" > /tmp/ms_annotations_after.json
diff <(python -c "import json;print(json.dumps(json.load(open('/tmp/ms_annotations_before.json')),sort_keys=True,ensure_ascii=False,indent=1))") \
     <(python -c "import json;print(json.dumps(json.load(open('/tmp/ms_annotations_after.json')),sort_keys=True,ensure_ascii=False,indent=1))") \
  && echo "ANNOTATIONS IDENTICAL"
```
Expected: `ANNOTATIONS IDENTICAL` (the merged annotation mapping is unchanged — name AND type string for all 161 fields). If diff shows anything, a field's annotation was altered during the move — fix it to match the original verbatim.

- [ ] **Step 5: Import sanity + full suite**

Run: `EASYADS_DB_BACKEND=memory uv run python -c "import orchestrator.app.graph.builder; from orchestrator.app.api.app import create_app; create_app(); print('graph + app ok')"`
Expected: `graph + app ok`.

Run: `EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests -q`
Expected: same pass count as the branch base (1431 passed / 2 skipped at time of writing) plus the 3 new shape tests; zero new failures.

- [ ] **Step 6: Commit**

```bash
git add orchestrator/app/graph/state.py
git commit -m "refactor(graph): organize MarketingState into 10 sub-state TypedDicts

Flat runtime shape unchanged (composition via multiple inheritance);
__annotations__ is byte-identical to the previous flat class. Pure
organizational change — no node or LangGraph behavior is affected.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Document the grouping

**Files:**
- Modify: `docs/state-source-of-truth.md` (append a section)

- [ ] **Step 1: Append the section**

Append to `docs/state-source-of-truth.md`:

```markdown
## MarketingState 그룹 구조 (sub-state, 조직화)

리뷰 지적 ④의 "필드 그룹별 sub-state 분리"를 **조직화 방식**으로 적용한 결과.
(2026-06-14)

`MarketingState`는 런타임에서는 여전히 **flat dict**다 (LangGraph가 top-level
키로 병합하고 노드들이 flat 키를 읽고 씀 — 변경 없음). 다만 소스에서는 161개
필드를 파이프라인 단계별 10개 TypedDict로 나누고 **다중 상속**으로 합친다:

| 그룹 TypedDict | 책임 |
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

규칙:
- 새 필드는 의미가 맞는 그룹 TypedDict에 추가한다 (flat 클래스에 직접 추가 금지).
- 런타임 형태는 dict이므로 [read_model 컨벤션](#dict--pydantic-모델-경계-read_model-컨벤션)이 그대로 적용된다.
- `MarketingState.__annotations__`는 10개 그룹의 합집합이며, 분리 전 flat
  클래스와 byte-identical (테스트 `test_marketing_state_shape.py`가 161필드 surface를 고정).
- 더 깊은 변경(런타임 중첩 `state["copy"][...]`)은 의도적으로 하지 않았다 —
  557개 접근 지점 재작성 + LangGraph reducer 커스텀이 필요해 리스크 대비 효용이 낮다.
```

- [ ] **Step 2: Commit**

```bash
git add docs/state-source-of-truth.md
git commit -m "docs: document MarketingState sub-state group structure

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Full suite**

Run: `EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests -q`
Expected: branch-base count + 3 shape tests; zero new failures.

- [ ] **Step 2: Confirm the flat surface and group disjointness one more time**

Run:
```bash
EASYADS_DB_BACKEND=memory uv run python -c "
from orchestrator.app.graph import state as s
groups = [s.JobMetaState, s.IntakeState, s.ReferenceVisionState, s.ContextValidationState,
          s.CopyState, s.NativeCreativeState, s.TypographyLayoutState, s.ImagePromptT2IState,
          s.QualityGateState, s.RenderFinalizeState]
total = sum(len(g.__annotations__) for g in groups)
union = set().union(*(g.__annotations__ for g in groups))
assert total == len(union), 'overlap: a field is in two groups'
assert union == set(s.MarketingState.__annotations__), 'MarketingState != union of groups'
assert len(union) == 161, f'expected 161, got {len(union)}'
print('disjoint + exhaustive + 161 fields ok')
"
```
Expected: `disjoint + exhaustive + 161 fields ok`.

- [ ] **Step 3: Confirm clean tree**

Run: `git status --short`
Expected: only the untracked `docs/superpowers/plans/2026-06-13-generation-job-background-resume-reliability.md`.
