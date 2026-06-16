# Backend Format Approved Plan Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the existing web generation inputs to the format-specific native typography approved plans without changing the frontend.

**Architecture:** Keep the existing `userInput`, selected format/model, and optional custom headline/subcopy request contract. Extend the backend native-copy stage with one format-aware approved-plan builder that preserves exact user copy, extracts only user-grounded extended fields, and writes the existing flyer/product-detail plan objects into graph state before typography planning and preflight.

**Tech Stack:** Python, Pydantic, LangGraph state, pytest, existing GPT-5.4 structured-copy adapter, existing GPT Image 2 native typography pipeline.

---

## Scope And Data Flow

No files under `apps/web` or `apps/bff` should change. The existing request already supplies:

```text
userInput
selected_ad_format
selected_engine / requested_engine / t2i_engine
user_custom_headline
user_custom_subcopy
```

The backend flow becomes:

```text
existing generation request
-> input evidence / product understanding
-> ApprovedNativeCopyBrief
-> format-aware approved-plan builder
-> TypographyExpressionPlan
-> NativeCreativePromptPackage
-> preflight
-> GPT Image 2 native single-shot
-> post-review
```

Format behavior:

```text
banner         -> ApprovedNativeCopyBrief only
poster         -> ApprovedNativeCopyBrief only
product_detail -> ApprovedNativeCopyBrief + ProductDetailApprovedFeaturePlan
flyer          -> ApprovedNativeCopyBrief + either FlyerApprovedCopyPlan
                  or FlyerPromotionalApprovedCopyPlan
```

The builder must not invent operational facts. Prices, discount rates, dates, phone numbers, addresses, locations, schedules, and CTA text may only enter a plan when they are present in grounded user evidence or exact custom copy.

### Task 1: Lock The Frontend-Neutral Request Contract

**Files:**
- Test: `orchestrator/tests/test_generation_jobs.py`
- Test: `orchestrator/tests/test_marketing_graph.py`

- [ ] **Step 1: Add a generation-job contract test**

Add a test that submits the existing camelCase request fields and asserts graph state receives the canonical values:

```python
assert received_payload["user_input"] == "시카 세럼 상세페이지를 만들어줘. 피부 진정과 수분 충전을 강조해줘."
assert received_payload["selected_ad_format"] == "product_detail"
assert received_payload["user_custom_headline"] == "시카 진정 세럼"
assert received_payload["user_custom_subcopy"] == "민감한 피부를 편안하게 감싸는 진정 케어"
```

Also assert the selected engine remains `gpt_image_2` in the execution metadata.

- [ ] **Step 2: Run the request-contract tests and confirm the existing wiring passes**

Run:

```bash
pytest -q orchestrator/tests/test_generation_jobs.py orchestrator/tests/test_marketing_graph.py -k "custom_copy or selected_ad_format or engine"
```

Expected: PASS without modifying frontend or BFF files.

### Task 2: Add A Format-Aware Approved Plan Builder Service

**Files:**
- Create: `orchestrator/app/llm/format_approved_plan_service.py`
- Modify: `orchestrator/app/schemas/native_creative.py`
- Test: `orchestrator/tests/test_format_approved_plan_service.py`

- [ ] **Step 1: Add failing tests for the public builder contract**

Define the service result as a small Pydantic model containing optional format-specific plans:

```python
class FormatApprovedPlanBundle(BaseModel):
    flyer_approved_copy_plan: FlyerApprovedCopyPlan | None = None
    flyer_promotional_approved_copy_plan: FlyerPromotionalApprovedCopyPlan | None = None
    product_detail_approved_feature_plan: ProductDetailApprovedFeaturePlan | None = None
    decision: Literal["approved", "not_required", "manual_review", "rejected"]
    reason_codes: list[str] = Field(default_factory=list)
    provider_metadata: dict = Field(default_factory=dict)
```

Tests must cover:

```text
banner and poster return not_required with no extended plan
product_detail returns only ProductDetailApprovedFeaturePlan
editorial flyer returns only FlyerApprovedCopyPlan
promotional flyer returns only FlyerPromotionalApprovedCopyPlan
no request can populate more than one extended plan
```

- [ ] **Step 2: Run the new service test and verify it fails**

Run:

```bash
pytest -q orchestrator/tests/test_format_approved_plan_service.py
```

Expected: FAIL because the service and bundle do not exist.

- [ ] **Step 3: Implement the deterministic service boundary**

Expose one function:

```python
def build_format_approved_plan_bundle(
    *,
    ad_format: str,
    input_evidence: InputEvidenceBundle,
    product_understanding: ProductUnderstanding,
    approved_copy: ApprovedNativeCopyBrief,
    state: dict[str, Any],
) -> FormatApprovedPlanBundle:
    ...
```

Rules:

```text
banner/poster: return not_required without calling an adapter
product_detail: use product-detail planning only
flyer: classify editorial versus promotional, then invoke only that planner
unsupported/missing format: return manual_review
adapter/schema/validation failure: return rejected with explicit reason codes
```

Use a `format_approved_plan_adapter` from state for tests and provider abstraction. The default provider implementation should be added in Task 4.

- [ ] **Step 4: Run the service tests**

Run:

```bash
pytest -q orchestrator/tests/test_format_approved_plan_service.py
```

Expected: PASS.

### Task 3: Preserve Exact Custom Headline And Subcopy

**Files:**
- Modify: `orchestrator/app/llm/format_approved_plan_service.py`
- Modify: `orchestrator/app/llm/native_copy_brief_service.py`
- Test: `orchestrator/tests/test_format_approved_plan_service.py`
- Test: `orchestrator/tests/test_native_copy_brief_service.py`

- [ ] **Step 1: Add failing exact-copy precedence tests**

Cover both direct custom fields and generated-copy mode:

```python
state = {
    "user_custom_headline": "시카 진정 세럼",
    "user_custom_subcopy": "민감한 피부를 편안하게 감싸는 진정 케어",
}
```

Expected behavior:

```text
headline is preserved byte-for-byte
supporting copy is preserved byte-for-byte
copy_source_mode is user_exact
both strings appear first in allowed_texts
the format planner cannot rewrite, shorten, or normalize them
```

When custom fields are absent, the existing generated `ApprovedNativeCopyBrief` remains authoritative for headline and supporting copy.

- [ ] **Step 2: Run the tests and verify failure**

Run:

```bash
pytest -q orchestrator/tests/test_native_copy_brief_service.py orchestrator/tests/test_format_approved_plan_service.py -k "exact or custom"
```

- [ ] **Step 3: Implement copy precedence**

Create one helper used by both brief construction and the format-plan builder:

```python
def resolve_approved_primary_copy(
    *, state: dict[str, Any], approved_copy: ApprovedNativeCopyBrief
) -> tuple[str | None, str | None, str]:
    ...
```

Priority:

```text
user_custom_headline > approved_copy.headline
user_custom_subcopy > approved_copy.supporting_copy
```

Do not reinterpret arbitrary `userInput` as exact display copy.

- [ ] **Step 4: Run exact-copy tests**

Expected: PASS.

### Task 4: Generate Product Detail Feature Plans From Grounded User Input

**Files:**
- Modify: `orchestrator/app/llm/format_approved_plan_service.py`
- Test: `orchestrator/tests/test_format_approved_plan_service.py`

- [ ] **Step 1: Add failing product-detail extraction tests**

Use a request such as:

```text
시카 세럼 상세페이지를 만들어줘. 피부 진정, 수분 충전, 산뜻한 흡수, 데일리 케어를 강조해줘.
```

Assert the plan contains exactly:

```python
feature_labels == ["피부 진정", "수분 충전", "산뜻한 흡수", "데일리 케어"]
allowed_texts == [headline, supporting_copy, *feature_labels]
```

Add rejection/manual-review cases for:

```text
fewer than two grounded feature labels
more than four labels without a deterministic truncation decision
feature labels containing invented efficacy claims
price/date/phone/address/CTA in a feature label
adapter output not found in input evidence
```

- [ ] **Step 2: Implement the structured provider prompt and grounding check**

The provider prompt must return JSON only and must treat `headline` and `supporting_copy` as immutable inputs. It may select two to four short feature labels only from explicit user facts, user-request phrases, and verified product evidence.

After provider output, perform deterministic validation:

```text
2-4 labels
each label <= 16 characters
no duplicate labels
no sensitive operational text
every label has a source evidence match
visible texts exactly equal headline + supporting copy + labels
```

Do not silently fall back to generic labels. Insufficient grounded features produce `manual_review` and no feature plan.

- [ ] **Step 3: Run product-detail tests**

Run:

```bash
pytest -q orchestrator/tests/test_format_approved_plan_service.py -k product_detail
```

Expected: PASS.

### Task 5: Generate Editorial Or Promotional Flyer Plans

**Files:**
- Modify: `orchestrator/app/llm/format_approved_plan_service.py`
- Test: `orchestrator/tests/test_format_approved_plan_service.py`

- [ ] **Step 1: Add failing flyer mode-selection tests**

Promotional indicators must come from structured or explicit user evidence, including offers, recruitment, benefits, contact, location, operation notice, opening, or sale intent. A generic informational request without these signals remains editorial.

Test:

```text
editorial request -> FlyerApprovedCopyPlan only
business promotion request -> FlyerPromotionalApprovedCopyPlan only
ambiguous request -> manual_review, not an arbitrary promotional plan
```

- [ ] **Step 2: Add failing promotional grounding tests**

For a full gym request, assert approved fields map exactly from user evidence:

```python
promo_badge == "GRAND OPEN"
headline == "프리미엄 헬스장 오픈"
info_items == ["1:1 PT 상담 가능", "유산소·웨이트존 운영", "초보자 맞춤 지도"]
contact_line == "문의 000-0000-0000"
location_line == "OO역 3번 출구 앞"
notice_line == "상담은 예약제로 운영됩니다"
```

Also assert omitted contact/location/notice fields stay `None`; the model must not fill them.

- [ ] **Step 3: Implement flyer planning and operational evidence gating**

Build `approved_operational_texts` only from exact evidence-backed values. Enforce:

```text
phone/address/location/date/price/discount/CTA must have exact source evidence
optional operational fields remain absent when not supplied
allowed_texts must exactly match visible structured fields in display order
promotional plans contain 7-10 blocks
editorial plans contain 4-6 blocks
```

Provider-created marketing prose may be allowed only for non-operational fields under the existing generated-copy policy and must still pass copy validation. It may never fabricate factual benefits or business details.

- [ ] **Step 4: Run flyer service tests**

Run:

```bash
pytest -q orchestrator/tests/test_format_approved_plan_service.py -k flyer
```

Expected: PASS.

### Task 6: Wire The Bundle Into Graph State Before Typography Planning

**Files:**
- Modify: `orchestrator/app/llm/nodes/native_copy_brief.py`
- Modify: `orchestrator/app/graph/state.py`
- Test: `orchestrator/tests/test_marketing_state_shape.py`
- Test: `orchestrator/tests/test_typography_expression_planner.py`
- Test: `orchestrator/tests/test_marketing_graph.py`

- [ ] **Step 1: Add failing graph-state tests**

Add state fields:

```python
format_approved_plan_bundle: dict[str, Any] | None
flyer_approved_copy_plan: dict[str, Any] | None
flyer_promotional_approved_copy_plan: dict[str, Any] | None
product_detail_approved_feature_plan: dict[str, Any] | None
```

Tests must assert the fields initialize to `None`, survive snapshots/resume where appropriate, and remain format-isolated.

- [ ] **Step 2: Extend `native_copy_brief_node`**

After producing an approved base brief, call `build_format_approved_plan_bundle(...)`. Return only the plan field matching `selected_ad_format`:

```python
return {
    "approved_native_copy_brief": brief.model_dump(),
    "format_approved_plan_bundle": bundle.model_dump(),
    "flyer_approved_copy_plan": optional_editorial_flyer,
    "flyer_promotional_approved_copy_plan": optional_promotional_flyer,
    "product_detail_approved_feature_plan": optional_product_detail,
    "native_generation_status": status,
}
```

If an extended plan is required but the bundle is not approved, set `native_generation_status` to `manual_review` or `rejected`; do not continue as if the two-block brief were sufficient.

- [ ] **Step 3: Verify the existing graph edge remains unchanged**

Keep:

```text
native_copy_brief -> typography_expression_planner -> native_creative_preflight
```

No new graph node is required.

- [ ] **Step 4: Run graph and state tests**

Run:

```bash
pytest -q orchestrator/tests/test_marketing_state_shape.py orchestrator/tests/test_typography_expression_planner.py orchestrator/tests/test_marketing_graph.py
```

Expected: PASS.

### Task 7: Enforce Plan Isolation In Typography Planning And Preflight

**Files:**
- Modify: `orchestrator/app/llm/typography_expression_service.py`
- Modify: `orchestrator/app/llm/nodes/native_creative_preflight.py`
- Modify: `orchestrator/app/llm/native_copy_policy.py`
- Test: `orchestrator/tests/test_typography_expression_planner.py`
- Test: `orchestrator/tests/test_native_creative_preflight.py`

- [ ] **Step 1: Add failing cross-format contamination tests**

Assert:

```text
banner/poster reject or ignore all extended plan payloads
product_detail rejects flyer plans
flyer rejects product-detail plans
flyer rejects simultaneous editorial and promotional plans
required extended plans cannot be absent while extended mode is selected
```

- [ ] **Step 2: Centralize plan selection**

Add a helper in `typography_expression_service.py` that resolves exactly one visible-text source by format. It should return explicit failure codes for conflicting plans rather than choosing one by precedence.

- [ ] **Step 3: Keep existing validators authoritative**

Reuse:

```python
validate_flyer_approved_copy_plan
validate_flyer_promotional_approved_copy_plan
validate_product_detail_approved_feature_plan
```

Do not weaken the common `ApprovedNativeCopyBrief.max_text_blocks <= 2` contract. Extended visible text is authorized only through the matching isolated plan.

- [ ] **Step 4: Run planner and preflight tests**

Run:

```bash
pytest -q orchestrator/tests/test_typography_expression_planner.py orchestrator/tests/test_native_creative_preflight.py
```

Expected: PASS.

### Task 8: Verify Prompt Package Output For All Four Formats

**Files:**
- Test: `orchestrator/tests/test_typography_expression_planner.py`
- Test: `orchestrator/tests/test_native_copy_policy.py`

- [ ] **Step 1: Add prompt-package integration tests**

For each format, begin with a web-shaped state payload and assert the final prompt package contains the intended visible text and only the matching profile grammar:

```text
banner: headline + support only; no flyer/product-detail plan text
poster: headline + support only; no flyer/product-detail plan text
product_detail: headline + support + 2-4 approved feature labels
editorial flyer: only its 4-6 approved blocks
promotional flyer: only its 7-10 approved blocks and approved operational text
```

Also assert custom headline/subcopy remain exact in every format.

- [ ] **Step 2: Run prompt-package integration tests**

Run:

```bash
pytest -q orchestrator/tests/test_typography_expression_planner.py orchestrator/tests/test_native_copy_policy.py
```

Expected: PASS.

### Task 9: Add Web-To-Native Pipeline Regression Coverage

**Files:**
- Test: `orchestrator/tests/test_generation_jobs.py`
- Test: `orchestrator/tests/test_marketing_graph.py`
- Test: `orchestrator/tests/test_gpt_image2_native_single_shot.py`

- [ ] **Step 1: Add backend end-to-end tests with provider adapters**

Exercise existing generation-job input through graph planning without making paid API calls. Stub the copy and format-plan adapters, then assert:

```text
selected gpt_image_2 reaches gpt_native_single_shot
selected format determines the format profile
format plan reaches NativeCreativePromptPackage
preflight accepts valid grounded plans
preflight fails closed for invented operational text
image call limit remains 1
edit/retry/external renderer remain disabled
```

- [ ] **Step 2: Add no-frontend-change guard**

Record the frontend/BFF request field names in the backend regression test description and verify no new required API field is introduced. Do not add format-plan fields to the web request schema.

- [ ] **Step 3: Run pipeline regression tests**

Run:

```bash
pytest -q orchestrator/tests/test_generation_jobs.py orchestrator/tests/test_marketing_graph.py orchestrator/tests/test_gpt_image2_native_single_shot.py
```

Expected: PASS with all external providers stubbed.

### Task 10: Final Focused And Expanded Verification

**Files:**
- Verify only; no production file changes expected.

- [ ] **Step 1: Run focused native typography tests**

```bash
pytest -q \
  orchestrator/tests/test_format_approved_plan_service.py \
  orchestrator/tests/test_native_copy_brief_service.py \
  orchestrator/tests/test_typography_expression_planner.py \
  orchestrator/tests/test_native_creative_preflight.py \
  orchestrator/tests/test_native_copy_policy.py
```

Expected: PASS.

- [ ] **Step 2: Run graph and generation-job regressions**

```bash
pytest -q \
  orchestrator/tests/test_generation_jobs.py \
  orchestrator/tests/test_marketing_graph.py \
  orchestrator/tests/test_marketing_state_shape.py \
  orchestrator/tests/test_gpt_image2_native_single_shot.py
```

Expected: PASS.

- [ ] **Step 3: Confirm frontend and BFF remain untouched**

```bash
git diff --name-only -- apps/web apps/bff
```

Expected: no output from this implementation.

- [ ] **Step 4: Check patch hygiene**

```bash
git diff --check
```

Expected: no output and exit code 0.

- [ ] **Step 5: Review the final diff without committing**

```bash
git diff --stat
git diff -- orchestrator/app orchestrator/tests
```

Confirm the implementation is limited to backend planning, graph state, preflight/prompt integration, and tests. Do not create a commit until explicitly requested.

## Acceptance Criteria

```text
1. No frontend or BFF source changes are required.
2. Existing free input, selected format/model, and custom copy fields drive the backend plans.
3. Exact custom headline/subcopy are never rewritten.
4. Product-detail feature labels are grounded, limited to 2-4, and format-isolated.
5. Flyer editorial/promotional plans are explicitly separated.
6. Operational text is allowed only when exactly grounded in user evidence.
7. Banner and poster retain the common two-block plan only.
8. Conflicting, missing, or ungrounded plans fail closed before image generation.
9. Existing GPT Image 2 single-shot and 1/0/0/0 call policy remains unchanged.
10. Focused tests, graph regressions, and `git diff --check` pass.
```
