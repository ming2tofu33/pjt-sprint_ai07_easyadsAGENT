# Domain Routing A4 Exact Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove selector-level substring and keyword classification so visual selectors only consume exact resolved keys and otherwise fall back explicitly to generic.

**Architecture:** A-4 does not introduce the final A-5 single resolved-key adapter. Instead, it makes the existing legacy selectors fail closed: `select_visual_preset()`, `select_visual_template()`, and `scene_planner.resolve_business_type()` must not inspect raw user text or style keywords to infer domains. Exact legacy route keys such as `restaurant_bbq`, `beauty_hair`, and `beauty_skincare` continue to work; ambiguous or raw values such as `beauty`, `beauty_salon`, `숯불 삼겹살 맛집`, and `korean cafe restaurant` route to `generic`.

**Tech Stack:** Python 3.12, Pydantic v2, pytest via `PYTHONPATH=. uv run pytest`.

---

## File Structure

- Modify: `orchestrator/app/llm/visual_presets.py`
  - Remove `_PRESET_KEYWORD_FALLBACKS`.
  - Keep `PRESET_ID_BY_BUSINESS_TYPE` as the exact visual route key registry.
  - Remove ambiguous `beauty` and `beauty_salon` exact routes.

- Modify: `orchestrator/app/llm/visual_templates.py`
  - Replace haystack substring matching with exact `business_type` lookup.
  - Ignore `style_keywords` for domain/template selection in A-4.
  - Add exact route keys for beauty subtypes.

- Modify: `orchestrator/app/llm/scene_planner.py`
  - Replace raw `user_input` keyword heuristics and beauty subtype inference with exact route-key validation.
  - Return `generic` for unsupported, ambiguous, or raw free-text values.

- Modify: `orchestrator/tests/test_domain_routing_contract.py`
  - Update legacy contract tests so raw Korean BBQ input no longer reaches the BBQ preset.
  - Update ambiguous beauty selector expectations to generic.

- Modify: `orchestrator/tests/test_visual_templates.py`
  - Update template tests for exact mapping and reference keyword fail-closed behavior.

- Modify: `orchestrator/tests/test_image_prompt_planner.py`
  - Update image prompt planner expectations for ambiguous beauty and exact beauty subtype route keys.

- Create/Modify: `docs/superpowers/plans/2026-06-16-domain-routing-a4-exact-mapping.md`
  - Documents this plan and execution status.

---

### Task 1: Pin Visual Preset Exact Mapping

**Files:**
- Modify: `orchestrator/tests/test_domain_routing_contract.py`
- Modify: `orchestrator/app/llm/visual_presets.py`

- [x] **Step 1: Write failing preset tests**

In `orchestrator/tests/test_domain_routing_contract.py`, replace the ambiguous beauty and keyword fallback tests with:

```python
def test_beauty_salon_routes_to_generic_until_subtype_evidence_exists():
    preset = select_visual_preset("beauty_salon")
    assert preset["business_type"] == "generic"
    assert preset["preset_id"] == "generic_clean_ad_background"


def test_ambiguous_beauty_routes_to_generic():
    preset = select_visual_preset("beauty")
    assert preset["business_type"] == "generic"
    assert preset["preset_id"] == "generic_clean_ad_background"


def test_raw_korean_bbq_input_no_longer_routes_by_keyword_to_bbq():
    preset = select_visual_preset("숯불 삼겹살 맛집")
    assert preset["business_type"] == "generic"
    assert preset["preset_id"] == "generic_clean_ad_background"
```

Keep `test_explicit_beauty_subtypes_still_route_correctly()` unchanged.

- [x] **Step 2: Run tests to verify RED**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing_contract.py::test_beauty_salon_routes_to_generic_until_subtype_evidence_exists orchestrator/tests/test_domain_routing_contract.py::test_ambiguous_beauty_routes_to_generic orchestrator/tests/test_domain_routing_contract.py::test_raw_korean_bbq_input_no_longer_routes_by_keyword_to_bbq -q
```

Expected: FAIL because current `select_visual_preset()` maps `beauty_salon` and `beauty` to skincare and raw Korean BBQ text to `restaurant_bbq`.

- [x] **Step 3: Implement exact preset lookup**

In `orchestrator/app/llm/visual_presets.py`, update `PRESET_ID_BY_BUSINESS_TYPE` and `select_visual_preset()`:

```python
PRESET_ID_BY_BUSINESS_TYPE: dict[str, str] = {
    "cafe": "cafe_dessert_soft_premium",
    "restaurant_bbq": "restaurant_bbq_warm_grill",
    "restaurant": "restaurant_generic_clean",
    "beauty_skincare": "beauty_skincare_clean_premium",
    "beauty_hair": "beauty_hair_salon_clean",
    "beauty_nail": "beauty_nail_clean_detail",
    "beauty_spa": "beauty_spa_soft_wellness",
    "generic": "generic_clean_ad_background",
}
```

Delete `_PRESET_KEYWORD_FALLBACKS`.

Replace the fallback loop in `select_visual_preset()` with:

```python
    exact = PRESET_ID_BY_BUSINESS_TYPE.get(bt)
    if exact:
        return VISUAL_PRESETS[exact]

    return VISUAL_PRESETS["generic_clean_ad_background"]
```

- [x] **Step 4: Run tests to verify GREEN**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing_contract.py::test_beauty_salon_routes_to_generic_until_subtype_evidence_exists orchestrator/tests/test_domain_routing_contract.py::test_ambiguous_beauty_routes_to_generic orchestrator/tests/test_domain_routing_contract.py::test_raw_korean_bbq_input_no_longer_routes_by_keyword_to_bbq orchestrator/tests/test_domain_routing_contract.py::test_explicit_beauty_subtypes_still_route_correctly -q
```

Expected: PASS.

### Task 2: Pin Visual Template Exact Mapping

**Files:**
- Modify: `orchestrator/tests/test_visual_templates.py`
- Modify: `orchestrator/app/llm/visual_templates.py`

- [x] **Step 1: Write failing template tests**

Replace `orchestrator/tests/test_visual_templates.py` with:

```python
from orchestrator.app.llm.visual_templates import select_visual_template


def test_visual_template_exact_business_type_selection():
    assert select_visual_template("cafe", "instagram_feed", "premium").template_id == "cafe_dessert_soft_premium"
    assert select_visual_template("restaurant_bbq", "banner", "bold").template_id == "restaurant_bbq_warm_grill"
    assert select_visual_template("restaurant", "instagram_feed", "clean").template_id == "restaurant_generic_clean"
    assert select_visual_template("beauty_skincare", "instagram_story", "clean").template_id == "beauty_salon_clean_pastel"
    assert select_visual_template("beauty_hair", "instagram_story", "clean").template_id == "beauty_salon_clean_pastel"
    assert select_visual_template("beauty_nail", "instagram_story", "clean").template_id == "beauty_salon_clean_pastel"
    assert select_visual_template("beauty_spa", "instagram_story", "clean").template_id == "beauty_salon_clean_pastel"


def test_visual_template_fails_closed_for_raw_or_ambiguous_values():
    assert select_visual_template("bbq", "banner", "bold").template_id == "generic_clean_ad_background"
    assert select_visual_template("beauty_salon", "instagram_story", "clean").template_id == "generic_clean_ad_background"
    assert select_visual_template("korean cafe restaurant", "instagram_feed", "premium").template_id == "generic_clean_ad_background"
    assert select_visual_template("unknown", "unknown", None).template_id == "generic_clean_ad_background"


def test_visual_template_does_not_infer_domain_from_reference_keywords():
    template = select_visual_template(None, None, None, {"style_keywords": ["skincare", "pastel"]})
    assert template.template_id == "generic_clean_ad_background"
```

- [x] **Step 2: Run tests to verify RED**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_visual_templates.py -q
```

Expected: FAIL because current template selector uses haystack substring matching and reference keywords.

- [x] **Step 3: Implement exact template lookup**

In `orchestrator/app/llm/visual_templates.py`, update template `business_types` to exact route keys:

```python
business_types=["cafe"]
business_types=["restaurant_bbq"]
business_types=["beauty_skincare", "beauty_hair", "beauty_nail", "beauty_spa"]
business_types=["restaurant"]
business_types=["generic"]
```

Replace `select_visual_template()` with:

```python
def select_visual_template(
    business_type: str | None,
    ad_format: str | None,
    style_profile: str | None,
    selected_reference_template: dict[str, Any] | None = None,
) -> VisualTemplate:
    key = str(business_type or "").strip().lower()
    templates = get_visual_templates()
    for template in templates:
        if key in {token.lower() for token in template.business_types if token != "*"}:
            return template
    return templates[-1]
```

- [x] **Step 4: Run tests to verify GREEN**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_visual_templates.py -q
```

Expected: PASS.

### Task 3: Pin Scene Planner Exact Mapping

**Files:**
- Modify: `orchestrator/tests/test_image_prompt_planner.py`
- Modify: `orchestrator/tests/test_image_prompt_v3_sceneplan.py`
- Modify: `orchestrator/app/llm/scene_planner.py`

- [x] **Step 1: Add failing image prompt planner tests**

Update `test_image_prompt_template_selection_variants()` in `orchestrator/tests/test_image_prompt_planner.py`:

```python
def test_image_prompt_template_selection_variants():
    assert build_image_prompt_spec_with_critic(_state("restaurant")).metadata["visual_template_id"] == "restaurant_generic_clean"
    assert build_image_prompt_spec_with_critic(_state("restaurant_bbq")).metadata["visual_template_id"] == "restaurant_bbq_warm_grill"
    assert build_image_prompt_spec_with_critic(_state("beauty")).metadata["visual_template_id"] == "generic_clean_ad_background"
    assert build_image_prompt_spec_with_critic(_state("beauty_skincare")).metadata["visual_template_id"] == "beauty_salon_clean_pastel"
    assert build_image_prompt_spec_with_critic(_state("unknown")).metadata["visual_template_id"] == "generic_clean_ad_background"
```

Add this test:

```python
def test_image_prompt_scene_planner_does_not_infer_bbq_from_raw_user_input():
    state = _state("restaurant")
    state["user_input"] = "숯불 삼겹살 맛집 포스터 만들어줘"

    spec = build_image_prompt_spec_with_critic(state)

    assert spec.metadata["business_visual_preset_id"] == "restaurant_generic_clean"
    assert spec.metadata["scene_plan"]["business_type"] == "restaurant"
```

Update `orchestrator/tests/test_image_prompt_v3_sceneplan.py` so scene planner behavior is pinned directly:

```python
def test_restaurant_bbq_scene_plan():
    scene_plan = build_scene_plan(
        user_input="참숯에 구운 프리미엄 한우 삼겹살 갈비",
        business_type="restaurant_bbq",
        ad_format="instagram_feed"
    )
    assert scene_plan.business_type == "restaurant_bbq"


def test_beauty_subtypes_require_exact_route_keys():
    assert resolve_business_type(user_input="홍대 미용실 헤어 컷트 셋팅펌 스타일링", business_type="beauty_hair") == "beauty_hair"
    assert resolve_business_type(user_input="피부과 에스테틱 스킨케어 앰플 수분 크림", business_type="beauty_skincare") == "beauty_skincare"
    assert resolve_business_type(user_input="여름 젤네일 아트 추천", business_type="beauty_nail") == "beauty_nail"
    assert resolve_business_type(user_input="태국 아로마 스파 마사지 힐링 웰니스", business_type="beauty_spa") == "beauty_spa"


def test_scene_planner_fails_closed_for_ambiguous_or_raw_values():
    assert resolve_business_type(user_input="강남 뷰티샵 헤어 스타일링", business_type="beauty") == "generic"
    assert resolve_business_type(user_input="강남 뷰티샵 헤어 스타일링", business_type="beauty_salon") == "generic"
    assert resolve_business_type(user_input="숯불 삼겹살 맛집 포스터 만들어줘", business_type=None) == "generic"
    assert resolve_business_type(user_input="korean cafe restaurant", business_type=None) == "generic"
    assert resolve_business_type(user_input="", business_type="bbq") == "generic"


def test_scene_planner_accepts_exact_reference_route_keys_only():
    assert resolve_business_type(user_input="", business_type=None, selected_reference_template={"business_type": "restaurant_bbq"}) == "restaurant_bbq"
    assert resolve_business_type(user_input="헤어 스타일링", business_type=None, selected_reference_template={"category": "beauty_salon"}) == "generic"
```

- [x] **Step 2: Run tests to verify RED**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_image_prompt_planner.py::test_image_prompt_template_selection_variants orchestrator/tests/test_image_prompt_planner.py::test_image_prompt_scene_planner_does_not_infer_bbq_from_raw_user_input -q
PYTHONPATH=. uv run pytest orchestrator/tests/test_image_prompt_v3_sceneplan.py::test_beauty_subtypes_require_exact_route_keys orchestrator/tests/test_image_prompt_v3_sceneplan.py::test_scene_planner_fails_closed_for_ambiguous_or_raw_values orchestrator/tests/test_image_prompt_v3_sceneplan.py::test_scene_planner_accepts_exact_reference_route_keys_only -q
```

Expected: FAIL because `scene_planner.resolve_business_type()` currently infers BBQ/beauty subtypes from raw `user_input`, and ambiguous `beauty` / `beauty_salon` routes to skincare.

- [x] **Step 3: Implement exact scene planner route validation**

In `orchestrator/app/llm/scene_planner.py`, import the preset route map:

```python
from orchestrator.app.llm.visual_presets import PRESET_ID_BY_BUSINESS_TYPE, select_visual_preset, VISUAL_PRESETS
```

Replace `resolve_beauty_subtype()` with a compatibility stub:

```python
def resolve_beauty_subtype(bt_str: str, user_input: str) -> str | None:
    return _exact_visual_route_key(bt_str)
```

Add:

```python
def _exact_visual_route_key(value: str | None) -> str | None:
    key = str(value or "").strip().lower()
    if key in PRESET_ID_BY_BUSINESS_TYPE and key not in {"beauty", "beauty_salon"}:
        return key
    return None
```

Replace `resolve_business_type()` with:

```python
def resolve_business_type(
    user_input: str,
    business_type: str | None,
    selected_reference_template: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    candidates: list[str | None] = [
        str((metadata or {}).get("business_type")) if (metadata or {}).get("business_type") else None,
        str((selected_reference_template or {}).get("business_type")) if (selected_reference_template or {}).get("business_type") else None,
        str((selected_reference_template or {}).get("category")) if (selected_reference_template or {}).get("category") else None,
        business_type,
    ]
    for candidate in candidates:
        route_key = _exact_visual_route_key(candidate)
        if route_key:
            return route_key
    return "generic"
```

- [x] **Step 4: Run tests to verify GREEN**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_image_prompt_planner.py::test_image_prompt_template_selection_variants orchestrator/tests/test_image_prompt_planner.py::test_image_prompt_scene_planner_does_not_infer_bbq_from_raw_user_input -q
PYTHONPATH=. uv run pytest orchestrator/tests/test_image_prompt_v3_sceneplan.py -q
```

Expected: PASS.

### Task 4: Update Cross-Module Contracts

**Files:**
- Modify: `orchestrator/tests/test_domain_routing_contract.py`
- Inspect: `orchestrator/tests/test_image_prompt_v3_sceneplan.py`
- Inspect: `orchestrator/tests/test_image_prompt_v3_integration.py`

- [x] **Step 1: Update preset/template family contract for ambiguous beauty**

Keep `test_preset_and_template_share_domain_family()` but ensure the parameter list remains:

```python
@pytest.mark.parametrize("business_type", ["cafe", "restaurant_bbq", "restaurant", "beauty_salon"])
```

After A-4, `beauty_salon` should pass because both preset and template return generic/OTHER.

- [x] **Step 2: Run broader visual routing tests**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing_contract.py orchestrator/tests/test_visual_templates.py orchestrator/tests/test_image_prompt_planner.py orchestrator/tests/test_image_prompt_v3_sceneplan.py orchestrator/tests/test_image_prompt_v3_integration.py -q
```

Expected: PASS after Tasks 1-3.

### Task 5: Final Verification

**Files:**
- Inspect: `orchestrator/app/llm/visual_presets.py`
- Inspect: `orchestrator/app/llm/visual_templates.py`
- Inspect: `orchestrator/app/llm/scene_planner.py`
- Inspect: `orchestrator/tests/test_domain_routing_contract.py`
- Inspect: `orchestrator/tests/test_visual_templates.py`
- Inspect: `orchestrator/tests/test_image_prompt_planner.py`

- [x] **Step 1: Run focused A-4 suite**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing.py orchestrator/tests/test_domain_routing_contract.py orchestrator/tests/test_visual_templates.py orchestrator/tests/test_image_prompt_planner.py orchestrator/tests/test_brief_interpreter_llm_v1.py orchestrator/tests/test_business_context.py -q
```

Expected: PASS.

- [x] **Step 2: Run selector smoke script**

Run:

```bash
PYTHONPATH=. uv run python - <<'PY'
from orchestrator.app.llm.visual_presets import select_visual_preset
from orchestrator.app.llm.visual_templates import select_visual_template
from orchestrator.app.llm.scene_planner import resolve_business_type

for value in ["restaurant_bbq", "숯불 삼겹살 맛집", "beauty", "beauty_salon", "beauty_hair", "korean cafe restaurant"]:
    print(value, select_visual_preset(value)["business_type"], select_visual_template(value, "instagram_feed", "premium").template_id, resolve_business_type(value, value))
PY
```

Expected output includes:

```text
restaurant_bbq restaurant_bbq restaurant_bbq_warm_grill restaurant_bbq
숯불 삼겹살 맛집 generic generic_clean_ad_background generic
beauty generic generic_clean_ad_background generic
beauty_salon generic generic_clean_ad_background generic
beauty_hair beauty_hair beauty_salon_clean_pastel beauty_hair
korean cafe restaurant generic generic_clean_ad_background generic
```

- [x] **Step 3: Run whitespace diff check**

Run:

```bash
git diff --check
```

Expected: no output.

- [x] **Step 4: Confirm changed files**

Run:

```bash
git diff --name-only
```

Expected changed files include:

```text
docs/superpowers/plans/2026-06-16-domain-routing-a4-exact-mapping.md
orchestrator/app/llm/scene_planner.py
orchestrator/app/llm/visual_presets.py
orchestrator/app/llm/visual_templates.py
orchestrator/tests/test_domain_routing_contract.py
orchestrator/tests/test_image_prompt_planner.py
orchestrator/tests/test_image_prompt_v3_integration.py
orchestrator/tests/test_image_prompt_v3_sceneplan.py
orchestrator/tests/test_visual_templates.py
```

### Self-Review

- Spec coverage: The plan removes substring/keyword routing from preset, template, and scene planner selectors while preserving exact legacy keys.
- Placeholder scan: The plan contains no `TBD`, `TODO`, or unspecified implementation steps.
- Type consistency: All referenced names exist in the current codebase or are defined in this plan: `PRESET_ID_BY_BUSINESS_TYPE`, `select_visual_preset()`, `select_visual_template()`, `resolve_business_type()`, and `_exact_visual_route_key()`.
