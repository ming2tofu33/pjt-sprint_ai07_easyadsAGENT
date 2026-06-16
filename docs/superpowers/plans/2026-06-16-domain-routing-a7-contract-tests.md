# Domain Routing A-7 Contract Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lock the Track A domain-routing contract with regression tests so raw business inputs cannot bypass the SSOT, legacy route inventory stays valid, and copy/visual paths keep using explicit resolved keys.

**Architecture:** A-7 is a contract-test phase, not a new resolver phase. The tests should cover every input surface that can introduce business routing values, then verify the canonical `DomainRoutingResult` and deprecated `LegacyRoutingProjection` boundary before downstream preset/template/ScenePlan/copy-tone consumers. Minimal implementation changes are allowed only where tests reveal existing bypasses, especially option-registry aliases, ScenePlan ambiguous values, and tone-binding fallback behavior.

**Tech Stack:** Python 3.12, pytest, Pydantic models, LangGraph orchestrator modules, existing `uv run pytest` workflow.

---

## Current Baseline

A-1 through A-6 created these important boundaries:

- `orchestrator/app/llm/domain_routing.py` owns `CanonicalBusinessDomain`, `DomainRoutingResult`, and `project_to_legacy_visual_route()`.
- `orchestrator/app/llm/nodes/image_prompt_planner.py` now computes `resolved_visual_route_key` and passes that same key into visual template selection, ScenePlan, visual preset, and metadata.
- `orchestrator/app/llm/copy_tone_policy.py`, `copy_fallbacks.py`, and `copy_prompts.py` route raw restaurant/BBQ and ambiguous beauty copy inputs through neutral `generic`.

A-7 must turn those into hard regression contracts. It must also cover input surfaces and legacy helper paths that were not covered enough by A-1 through A-6.

## File Structure

Modify these files:

- `orchestrator/tests/test_domain_routing_contract.py`
  - Main A-7 contract matrix.
  - Add tests for option-registry business values, legacy route inventory, ScenePlan allowed values, single resolved key assumptions, and silent generic breadcrumbs.

- `orchestrator/tests/test_domain_routing.py`
  - Clarify `is_supported_domain()` semantics so nobody uses it as route-readiness.

- `orchestrator/tests/test_image_prompt_planner.py`
  - Add production-path assertions that `resolved_visual_route_key` controls template, preset, ScenePlan, and metadata for ambiguous/fallback cases.

- `orchestrator/tests/test_image_prompt_v3_sceneplan.py`
  - Add a direct `build_scene_plan()` fail-closed check for `beauty_salon` after removing it from the schema literal.

- `orchestrator/tests/test_tone_binding_node.py`
  - Add A-7/A-6 bridge tests proving graph tone binding also uses neutral fallback for raw restaurant/BBQ and ambiguous beauty values.

- `orchestrator/app/llm/domain_routing.py`
  - Add explicit routing for option-registry values `bar`, `academy`, and `flower_shop` so they are not unresolved accidental gaps.

- `orchestrator/app/llm/schemas/image_prompt_v3.py`
  - Remove `beauty_salon` from `BusinessType`; it is an ambiguous input, not a valid resolved ScenePlan route.

- `orchestrator/app/llm/copy_tone.py`
  - Route graph tone binding through `resolve_copy_route_key()` so old tone binding cannot bypass A-6 neutral fallback.

No changes are planned for reference-template migrations. That remains a separate owner/PR because it touches catalog/admin/service seed paths beyond A-7 contract tests.

---

### Task 1: Add Option Registry Input Contract

**Files:**
- Modify: `orchestrator/tests/test_domain_routing_contract.py`
- Modify: `orchestrator/app/llm/domain_routing.py`

- [ ] **Step 1: Write the failing option-registry contract test**

Add this import to `orchestrator/tests/test_domain_routing_contract.py` with the other imports:

```python
from orchestrator.app.llm.option_registry import OPTION_QUESTION_REGISTRY
```

Add this test near the `P4: BriefBusinessType routing table` section:

```python
def test_a7_business_type_option_registry_values_have_explicit_routing_contract():
    question = OPTION_QUESTION_REGISTRY["business_type"]
    actual = {}

    for option in question.options:
        result = normalize_business_type(option.value)
        actual[option.value] = (
            result.canonical_domain.value,
            result.support_status.value,
            result.unsupported_domain_hint,
            result.fallback_reason.value if result.fallback_reason else None,
            result.business_type,
        )

    assert actual == {
        "restaurant": ("food_and_beverage", "specialized", None, None, "restaurant"),
        "cafe": ("food_and_beverage", "specialized", None, None, "cafe"),
        "beauty_salon": ("beauty", "needs_evidence", None, "ambiguous_beauty_subdomain", None),
        "bar": ("other", "generic_fallback", "bar", "unsupported_domain_in_mvp", "bar"),
        "fitness": ("other", "generic_fallback", "fitness", "unsupported_domain_in_mvp", "fitness"),
        "academy": ("other", "generic_fallback", "education", "unsupported_domain_in_mvp", "education"),
        "flower_shop": ("retail", "specialized", None, None, "retail"),
        "store": ("retail", "specialized", None, None, "retail"),
        "custom": ("other", "unresolved", None, "unrecognized_business_type", None),
    }
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing_contract.py::test_a7_business_type_option_registry_values_have_explicit_routing_contract -q
```

Expected before implementation: FAIL because `bar`, `academy`, and `flower_shop` are unresolved or not aligned with the expected canonical route.

- [ ] **Step 3: Add exact option-registry aliases to the SSOT**

In `orchestrator/app/llm/domain_routing.py`, add these entries to `_DOMAIN_ALIASES`:

```python
    "bar": CanonicalBusinessDomain.OTHER,
    "academy": CanonicalBusinessDomain.OTHER,
    "flower_shop": CanonicalBusinessDomain.RETAIL,
```

Add these entries to `_BUSINESS_TAGS_BY_ALIAS`:

```python
    "bar": ("bar",),
    "academy": ("education", "academy"),
    "flower_shop": ("retail", "flower_shop"),
```

Add these entries to `_UNSUPPORTED_DOMAIN_HINTS`:

```python
    "bar": "bar",
    "academy": "education",
```

The intended behavior is:

- `bar`: unsupported in MVP, explicit generic fallback, preserve `bar` as the hint.
- `academy`: unsupported in MVP, explicit generic fallback, normalize the user-facing category to the existing `education` hint.
- `flower_shop`: retail domain, specialized canonical result, visual fallback remains handled later by `project_to_legacy_visual_route()`.
- `custom`: not a real business type; keep unresolved with clarification.

- [ ] **Step 4: Run the option-registry contract test again**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing_contract.py::test_a7_business_type_option_registry_values_have_explicit_routing_contract -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add orchestrator/tests/test_domain_routing_contract.py orchestrator/app/llm/domain_routing.py
git commit -m "test(srv): cover business option routing contract"
```

---

### Task 2: Clarify Supported Domain Versus Route Readiness

**Files:**
- Modify: `orchestrator/tests/test_domain_routing.py`

- [ ] **Step 1: Write the route-readiness clarification test**

Add this test near `test_is_supported_domain()` in `orchestrator/tests/test_domain_routing.py`:

```python
def test_is_supported_domain_is_not_route_readiness():
    beauty_salon = normalize_business_type("beauty_salon")
    restaurant_bbq = normalize_business_type("restaurant_bbq")
    retail = normalize_business_type("retail")

    assert is_supported_domain("beauty_salon") is True
    assert beauty_salon.support_status == DomainSupportStatus.NEEDS_EVIDENCE
    assert beauty_salon.business_type is None

    assert is_supported_domain("restaurant_bbq") is True
    assert restaurant_bbq.support_status == DomainSupportStatus.SPECIALIZED
    assert restaurant_bbq.business_type == "restaurant"

    assert is_supported_domain("retail") is True
    assert retail.support_status == DomainSupportStatus.SPECIALIZED
    assert retail.business_type == "retail"
```

- [ ] **Step 2: Run the clarification test**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing.py::test_is_supported_domain_is_not_route_readiness -q
```

Expected: PASS if `is_supported_domain()` still means "canonical family is supported"; FAIL if someone changed it into a route-ready helper.

- [ ] **Step 3: Restore helper semantics if the test fails**

If the test fails because `is_supported_domain()` was changed, restore this implementation in `orchestrator/app/llm/domain_routing.py`:

```python
def is_supported_domain(value: str | CanonicalBusinessDomain | None) -> bool:
    """True when the canonical domain is in the MVP specialized set."""
    return to_canonical_domain(value) in {
        CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
        CanonicalBusinessDomain.BEAUTY,
        CanonicalBusinessDomain.RETAIL,
    }
```

- [ ] **Step 4: Run the domain routing tests**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add orchestrator/tests/test_domain_routing.py orchestrator/app/llm/domain_routing.py
git commit -m "test(srv): document supported domain helper semantics"
```

---

### Task 3: Lock Legacy Visual Route Inventory

**Files:**
- Modify: `orchestrator/tests/test_domain_routing_contract.py`

- [ ] **Step 1: Add the ScenePlan inventory import**

Add this import to `orchestrator/tests/test_domain_routing_contract.py`:

```python
from orchestrator.app.llm.scene_planner import build_scene_plan
```

- [ ] **Step 2: Write the legacy inventory contract test**

Add this test after `test_preset_id_mapping_points_at_real_presets()`:

```python
def test_a7_every_legacy_visual_route_key_has_preset_template_and_sceneplan_inventory():
    for route_key in LegacyVisualRouteKey:
        key = route_key.value
        preset = select_visual_preset(key)
        template = select_visual_template(key, "instagram_feed", "premium", None)
        scene_plan = build_scene_plan(
            user_input="",
            business_type=key,
            ad_format="instagram_feed",
            metadata={
                "business_type": key,
                "item_or_service": "대표 상품",
                "target_persona": None,
                "promotion_goal": "brand_awareness",
            },
        )

        assert preset["business_type"] == key
        assert preset["preset_id"] in VISUAL_PRESETS
        assert key in template.business_types
        assert key in SCENEPLAN_BUSINESS_TYPES
        assert scene_plan.business_type == key
```

This test intentionally allows `restaurant_bbq` as a deprecated legacy visual route key. It does not allow `restaurant_bbq` as a canonical business domain or raw shortcut.

- [ ] **Step 3: Run the inventory test**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing_contract.py::test_a7_every_legacy_visual_route_key_has_preset_template_and_sceneplan_inventory -q
```

Expected: PASS. If it fails, the failure names the missing preset, template, or ScenePlan literal.

- [ ] **Step 4: Commit**

```bash
git add orchestrator/tests/test_domain_routing_contract.py
git commit -m "test(srv): lock legacy visual route inventory"
```

---

### Task 4: Remove Ambiguous Beauty From ScenePlan Route Values

**Files:**
- Modify: `orchestrator/tests/test_domain_routing_contract.py`
- Modify: `orchestrator/tests/test_image_prompt_v3_sceneplan.py`
- Modify: `orchestrator/app/llm/schemas/image_prompt_v3.py`

- [ ] **Step 1: Write the ScenePlan literal exclusion test**

Add this test near `test_all_preset_business_types_are_valid_sceneplan_literals()` in `orchestrator/tests/test_domain_routing_contract.py`:

```python
def test_a7_sceneplan_business_type_excludes_ambiguous_beauty_salon():
    assert "beauty_salon" not in SCENEPLAN_BUSINESS_TYPES
```

- [ ] **Step 2: Write the direct scene planner fail-closed test**

Add this test to `orchestrator/tests/test_image_prompt_v3_sceneplan.py` after `test_scene_planner_fails_closed_for_ambiguous_or_raw_values()`:

```python
def test_scene_planner_direct_beauty_salon_builds_generic_scene_plan():
    scene_plan = build_scene_plan(
        user_input="강남 뷰티샵 헤어 스타일링",
        business_type="beauty_salon",
        ad_format="instagram_feed",
    )

    assert scene_plan.business_type == "generic"
    assert scene_plan.notes == ["Selected preset: generic_clean_ad_background"]
```

- [ ] **Step 3: Run the failing ScenePlan tests**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing_contract.py::test_a7_sceneplan_business_type_excludes_ambiguous_beauty_salon orchestrator/tests/test_image_prompt_v3_sceneplan.py::test_scene_planner_direct_beauty_salon_builds_generic_scene_plan -q
```

Expected before implementation: the first test FAILS because `beauty_salon` is still in the ScenePlan `BusinessType` literal.

- [ ] **Step 4: Remove `beauty_salon` from the ScenePlan literal**

In `orchestrator/app/llm/schemas/image_prompt_v3.py`, change the `BusinessType` literal from:

```python
BusinessType = Literal[
    "cafe",
    "restaurant_bbq",
    "restaurant",
    "beauty_salon",
    "beauty_skincare",
    "beauty_hair",
    "beauty_nail",
    "beauty_spa",
    "generic",
]
```

to:

```python
BusinessType = Literal[
    "cafe",
    "restaurant_bbq",
    "restaurant",
    "beauty_skincare",
    "beauty_hair",
    "beauty_nail",
    "beauty_spa",
    "generic",
]
```

- [ ] **Step 5: Run the ScenePlan tests again**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing_contract.py::test_a7_sceneplan_business_type_excludes_ambiguous_beauty_salon orchestrator/tests/test_image_prompt_v3_sceneplan.py::test_scene_planner_direct_beauty_salon_builds_generic_scene_plan -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add orchestrator/tests/test_domain_routing_contract.py orchestrator/tests/test_image_prompt_v3_sceneplan.py orchestrator/app/llm/schemas/image_prompt_v3.py
git commit -m "test(srv): exclude ambiguous beauty from sceneplan routes"
```

---

### Task 5: Strengthen Production Single Resolved Key Tests

**Files:**
- Modify: `orchestrator/tests/test_image_prompt_planner.py`

- [ ] **Step 1: Add a generic assertion helper**

Add this helper below `_with_product_visual_context()` in `orchestrator/tests/test_image_prompt_planner.py`:

```python
def _assert_single_resolved_visual_key(
    metadata: dict,
    *,
    route_key: str,
    preset_id: str,
    template_id: str,
):
    assert metadata["resolved_visual_route_key"] == route_key
    assert metadata["visual_template_id"] == template_id
    assert metadata["business_visual_preset_id"] == preset_id
    assert metadata["scene_plan"]["business_type"] == route_key
    assert metadata["legacy_routing_projection"]["route_key"] == route_key
```

- [ ] **Step 2: Write the ambiguous/fallback production-path matrix**

Add this test after `test_image_prompt_single_resolved_key_preserves_unsupported_fallback_breadcrumb()`:

```python
def test_image_prompt_single_resolved_key_covers_ambiguous_and_visual_fallback_cases():
    cases = [
        {
            "business_type": "beauty_salon",
            "route_key": "generic",
            "preset_id": "generic_clean_ad_background",
            "template_id": "generic_clean_ad_background",
            "support_status": "needs_evidence",
            "domain_fallback_reason": "ambiguous_beauty_subdomain",
            "projection_fallback_reason": "ambiguous_beauty_subdomain",
            "unsupported_domain_hint": None,
        },
        {
            "business_type": "retail",
            "route_key": "generic",
            "preset_id": "generic_clean_ad_background",
            "template_id": "generic_clean_ad_background",
            "support_status": "specialized",
            "domain_fallback_reason": None,
            "projection_fallback_reason": "no_specialized_visual_profile",
            "unsupported_domain_hint": None,
        },
        {
            "business_type": "education",
            "route_key": "generic",
            "preset_id": "generic_clean_ad_background",
            "template_id": "generic_clean_ad_background",
            "support_status": "generic_fallback",
            "domain_fallback_reason": "unsupported_domain_in_mvp",
            "projection_fallback_reason": "unsupported_domain_in_mvp",
            "unsupported_domain_hint": "education",
        },
        {
            "business_type": "service",
            "route_key": "generic",
            "preset_id": "generic_clean_ad_background",
            "template_id": "generic_clean_ad_background",
            "support_status": "generic_fallback",
            "domain_fallback_reason": "unsupported_domain_in_mvp",
            "projection_fallback_reason": "unsupported_domain_in_mvp",
            "unsupported_domain_hint": "service",
        },
    ]

    for case in cases:
        spec = build_image_prompt_spec_with_critic(_state(case["business_type"]))
        metadata = spec.metadata
        domain = metadata["domain_routing_result"]
        projection = metadata["legacy_routing_projection"]

        _assert_single_resolved_visual_key(
            metadata,
            route_key=case["route_key"],
            preset_id=case["preset_id"],
            template_id=case["template_id"],
        )
        assert domain["support_status"] == case["support_status"]
        assert domain.get("fallback_reason") == case["domain_fallback_reason"]
        assert domain.get("unsupported_domain_hint") == case["unsupported_domain_hint"]
        assert projection.get("fallback_reason") == case["projection_fallback_reason"]
```

- [ ] **Step 3: Refactor existing single-key tests to use the helper**

Update `test_image_prompt_single_resolved_key_downgrades_legacy_bbq_without_visual_evidence()` so its first four assertions use `_assert_single_resolved_visual_key()`:

```python
def test_image_prompt_single_resolved_key_downgrades_legacy_bbq_without_visual_evidence():
    spec = build_image_prompt_spec_with_critic(_state("restaurant_bbq"))
    metadata = spec.metadata

    _assert_single_resolved_visual_key(
        metadata,
        route_key="restaurant",
        preset_id="restaurant_generic_clean",
        template_id="restaurant_generic_clean",
    )
    assert "korean_bbq_without_visual_evidence" in metadata["legacy_routing_projection"]["reason_codes"]
```

Update `test_image_prompt_single_resolved_key_allows_bbq_with_grilled_meat_product_evidence()` so it uses the same helper:

```python
def test_image_prompt_single_resolved_key_allows_bbq_with_grilled_meat_product_evidence():
    state = _with_product_visual_context(
        _state("restaurant_bbq"),
        product_tags=["pork", "grilled_meat"],
    )

    spec = build_image_prompt_spec_with_critic(state)
    metadata = spec.metadata

    _assert_single_resolved_visual_key(
        metadata,
        route_key="restaurant_bbq",
        preset_id="restaurant_bbq_warm_grill",
        template_id="restaurant_bbq_warm_grill",
    )
```

Update `test_image_prompt_single_resolved_key_preserves_unsupported_fallback_breadcrumb()` so it uses the helper and keeps its breadcrumb assertions:

```python
def test_image_prompt_single_resolved_key_preserves_unsupported_fallback_breadcrumb():
    spec = build_image_prompt_spec_with_critic(_state("fitness"))
    metadata = spec.metadata

    _assert_single_resolved_visual_key(
        metadata,
        route_key="generic",
        preset_id="generic_clean_ad_background",
        template_id="generic_clean_ad_background",
    )
    assert metadata["domain_routing_result"]["unsupported_domain_hint"] == "fitness"
    assert metadata["legacy_routing_projection"]["fallback_reason"] == "unsupported_domain_in_mvp"
```

- [ ] **Step 4: Run the image prompt planner contract tests**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_image_prompt_planner.py -q
```

Expected: PASS. If this fails, production path is no longer using one resolved visual key for template, preset, ScenePlan, and metadata.

- [ ] **Step 5: Commit**

```bash
git add orchestrator/tests/test_image_prompt_planner.py
git commit -m "test(srv): strengthen single resolved visual key contract"
```

---

### Task 6: Route Tone Binding Through Neutral Copy Key

**Files:**
- Modify: `orchestrator/tests/test_tone_binding_node.py`
- Modify: `orchestrator/app/llm/copy_tone.py`

- [ ] **Step 1: Make the tone-binding test helper accept a business type**

Change `create_state()` in `orchestrator/tests/test_tone_binding_node.py` from:

```python
def create_state():
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            copy_generation_mode="auto_pilot",
            context=MarketingContext(
                business_type="restaurant",
                item_or_service="삼겹살",
                promotion_goal="reservation_cta",
                extra={"ad_format": "instagram_feed"},
            ),
        )
    )
    state.update(format_planner_node(state))
    return state
```

to:

```python
def create_state(business_type: str = "restaurant"):
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            copy_generation_mode="auto_pilot",
            context=MarketingContext(
                business_type=business_type,
                item_or_service="삼겹살",
                promotion_goal="reservation_cta",
                extra={"ad_format": "instagram_feed"},
            ),
        )
    )
    state.update(format_planner_node(state))
    return state
```

- [ ] **Step 2: Write the tone-binding neutral fallback tests**

Add these tests after `test_tone_binding_returns_profile_for_restaurant_feed()`:

```python
def test_tone_binding_neutralizes_raw_restaurant_business_values():
    for business_type in ["restaurant", "restaurant_bbq", "bbq", "meat_restaurant", "korean_food"]:
        update = tone_binding_node(create_state(business_type))
        output = update["tone_binding_output"]
        tone_profile = output["metadata"]["tone_profile"]

        assert output["tone_profile"] == "friendly_clear"
        assert tone_profile["business_type"] == "generic"
        assert tone_profile["raw_business_type"] == business_type


def test_tone_binding_neutralizes_ambiguous_beauty_business_values():
    for business_type in ["beauty", "beauty_salon", "salon"]:
        update = tone_binding_node(create_state(business_type))
        output = update["tone_binding_output"]
        tone_profile = output["metadata"]["tone_profile"]

        assert output["tone_profile"] == "friendly_clear"
        assert tone_profile["business_type"] == "generic"
        assert tone_profile["raw_business_type"] == business_type
```

- [ ] **Step 3: Run the failing tone-binding tests**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_tone_binding_node.py::test_tone_binding_neutralizes_raw_restaurant_business_values orchestrator/tests/test_tone_binding_node.py::test_tone_binding_neutralizes_ambiguous_beauty_business_values -q
```

Expected before implementation: FAIL because `tone_binding_node` still gets tone metadata through legacy `copy_tone.py`.

- [ ] **Step 4: Route `copy_tone.py` through `resolve_copy_route_key()`**

In `orchestrator/app/llm/copy_tone.py`, add this import:

```python
from orchestrator.app.llm.copy_tone_policy import resolve_copy_route_key
```

Change `get_copy_tone_profile()` from:

```python
def get_copy_tone_profile(business_type: str | None, target_persona: str | None) -> dict[str, Any]:
    profile = dict(COPY_TONE_MAPPING.get(business_type or "", FALLBACK_COPY_TONE_PROFILE))
    profile["business_type"] = business_type or "unknown"
    profile["target_persona"] = target_persona or "unknown"
    profile["persona_hint"] = PERSONA_TONE_HINTS.get(target_persona or "", {})
    return profile
```

to:

```python
def get_copy_tone_profile(business_type: str | None, target_persona: str | None) -> dict[str, Any]:
    route_key = resolve_copy_route_key(business_type)
    profile = dict(COPY_TONE_MAPPING.get(route_key, FALLBACK_COPY_TONE_PROFILE))
    profile["business_type"] = route_key
    profile["raw_business_type"] = business_type or "unknown"
    profile["target_persona"] = target_persona or "unknown"
    profile["persona_hint"] = PERSONA_TONE_HINTS.get(target_persona or "", {})
    return profile
```

- [ ] **Step 5: Run tone-binding and copywriting tests**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_tone_binding_node.py orchestrator/tests/test_copywriting.py -q
```

Expected: PASS. If tests that inspect `get_copy_tone_profile()` fail because they expected raw `restaurant` in `profile["business_type"]`, update those tests to assert `profile["raw_business_type"] == "restaurant"` and `profile["business_type"] == "generic"`.

- [ ] **Step 6: Commit**

```bash
git add orchestrator/tests/test_tone_binding_node.py orchestrator/app/llm/copy_tone.py orchestrator/tests/test_copywriting.py
git commit -m "fix(srv): neutralize graph tone binding route"
```

---

### Task 7: Replace Weak Preset/Template Family Test With Resolved-Key Contract

**Files:**
- Modify: `orchestrator/tests/test_domain_routing_contract.py`

- [ ] **Step 1: Remove the weak raw-family test**

Delete this test from `orchestrator/tests/test_domain_routing_contract.py`:

```python
@pytest.mark.parametrize("business_type", ["cafe", "restaurant_bbq", "restaurant", "beauty_salon"])
def test_preset_and_template_share_domain_family(business_type):
    preset = select_visual_preset(business_type)
    template = select_visual_template(business_type, "instagram_feed", None)
    # Family judged in one place via the SSOT classifier.
    preset_family = to_canonical_domain(preset["business_type"])
    template_family = to_canonical_domain(template.business_types[0])
    assert preset_family == template_family, (
        f"{business_type!r}: preset -> {preset['business_type']!r} ({preset_family}) but "
        f"template -> {template.template_id!r} ({template_family}); different domain families."
    )
```

- [ ] **Step 2: Add a resolved-key projection contract test**

Add this test in the same section:

```python
@pytest.mark.parametrize(
    ("raw_business_type", "product_tags", "scene_tags", "expected_route_key"),
    [
        ("cafe", set(), set(), LegacyVisualRouteKey.CAFE),
        ("restaurant", set(), set(), LegacyVisualRouteKey.RESTAURANT),
        ("restaurant_bbq", set(), set(), LegacyVisualRouteKey.RESTAURANT),
        ("restaurant_bbq", {"grilled_meat"}, set(), LegacyVisualRouteKey.RESTAURANT_BBQ),
        ("restaurant_bbq", set(), {"bbq_grill"}, LegacyVisualRouteKey.RESTAURANT_BBQ),
        ("beauty_salon", set(), set(), LegacyVisualRouteKey.GENERIC),
        ("beauty_skincare", set(), set(), LegacyVisualRouteKey.BEAUTY_SKINCARE),
        ("beauty_hair", set(), set(), LegacyVisualRouteKey.BEAUTY_HAIR),
        ("beauty_nail", set(), set(), LegacyVisualRouteKey.BEAUTY_NAIL),
        ("beauty_spa", set(), set(), LegacyVisualRouteKey.BEAUTY_SPA),
        ("retail", set(), set(), LegacyVisualRouteKey.GENERIC),
        ("fitness", set(), set(), LegacyVisualRouteKey.GENERIC),
        ("education", set(), set(), LegacyVisualRouteKey.GENERIC),
        ("service", set(), set(), LegacyVisualRouteKey.GENERIC),
    ],
)
def test_a7_projection_route_key_controls_preset_template_and_sceneplan(
    raw_business_type,
    product_tags,
    scene_tags,
    expected_route_key,
):
    domain_result = normalize_business_type(raw_business_type)
    projection = project_to_legacy_visual_route(
        domain_result,
        product_tags=product_tags,
        explicit_scene_tags=scene_tags,
    )
    route_key = projection.route_key.value
    preset = select_visual_preset(route_key)
    template = select_visual_template(route_key, "instagram_feed", "premium", None)
    scene_plan = build_scene_plan(
        user_input="",
        business_type=route_key,
        ad_format="instagram_feed",
        metadata={"business_type": route_key, "item_or_service": "대표 상품"},
    )

    assert projection.route_key == expected_route_key
    assert preset["business_type"] == route_key
    assert route_key in template.business_types
    assert scene_plan.business_type == route_key
```

- [ ] **Step 3: Run the resolved-key contract test**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing_contract.py::test_a7_projection_route_key_controls_preset_template_and_sceneplan -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add orchestrator/tests/test_domain_routing_contract.py
git commit -m "test(srv): assert projection controls visual consumers"
```

---

### Task 8: Full A-7 Validation

**Files:**
- Test only

- [ ] **Step 1: Run the focused A-7 suite**

Run:

```bash
PYTHONPATH=. uv run pytest \
  orchestrator/tests/test_domain_routing_contract.py \
  orchestrator/tests/test_domain_routing.py \
  orchestrator/tests/test_image_prompt_planner.py \
  orchestrator/tests/test_image_prompt_v3_sceneplan.py \
  orchestrator/tests/test_tone_binding_node.py \
  orchestrator/tests/test_copywriting.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run the broader visual/copy guard suite**

Run:

```bash
PYTHONPATH=. uv run pytest \
  orchestrator/tests/test_brief_interpreter_llm_v1.py \
  orchestrator/tests/test_image_prompt_planner.py \
  orchestrator/tests/test_image_prompt_v3_integration.py \
  orchestrator/tests/test_image_prompt_v3_sceneplan.py \
  orchestrator/tests/test_visual_templates.py \
  orchestrator/tests/test_visual_strategy_registry.py \
  orchestrator/tests/test_visual_strategy_resolver.py \
  orchestrator/tests/test_copywriting.py \
  orchestrator/tests/test_domain_routing.py \
  orchestrator/tests/test_domain_routing_contract.py \
  orchestrator/tests/test_tone_binding_node.py \
  -q
```

Expected: PASS.

- [ ] **Step 3: Run the stale shortcut search**

Run:

```bash
rg -n \
  "beauty_salon.*ScenePlan|ScenePlan.*beauty_salon|get_copy_tone_profile\\(\"restaurant\"\\).*warm_appetizing|get_copy_tone_profile\\(\"beauty_salon\"\\).*polished|select_visual_template\\(context\\.business_type|select_visual_preset\\(context\\.business_type|build_scene_plan\\([^\\n]*business_type=context\\.business_type" \
  orchestrator/app/llm orchestrator/tests
```

Expected: no output for direct raw selector or direct tone shortcut patterns. Existing inventory references such as `restaurant_bbq_warm_grill` in visual strategy profiles are allowed when they are catalog/profile IDs.

- [ ] **Step 4: Run full orchestrator tests if time allows**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests -q
```

Expected: PASS.

- [ ] **Step 5: Run diff whitespace check**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 6: Commit validation-only adjustments if any test expectations were updated**

If Task 8 required small test expectation fixes, commit them:

```bash
git add orchestrator/tests orchestrator/app/llm
git commit -m "test(srv): finalize a7 contract coverage"
```

If no files changed during Task 8, skip this commit because the prior task commits already captured the work.

---

## PR Notes

Use this PR title:

```text
[feat/srv] A-7 domain routing contract tests 추가
```

Use this PR body shape:

```markdown
## 작업 내용
A-7 Domain Routing contract tests를 추가했습니다. A-1~A-6에서 만든 SSOT, legacy projection, single resolved key, neutral copy fallback 규칙이 다시 raw shortcut으로 무너지지 않도록 테스트로 고정했습니다.

핵심 변경은 아래와 같습니다.

- business option registry 값까지 SSOT 정규화 계약에 포함
- 모든 LegacyVisualRouteKey가 preset/template/ScenePlan inventory와 호환되는지 검증
- `beauty_salon`을 ScenePlan route literal에서 제거하고 production path는 generic fallback으로 검증
- `resolved_visual_route_key` 하나가 template, preset, ScenePlan, metadata에 동일하게 쓰이는지 강화
- graph `tone_binding_node`도 A-6 neutral copy route를 따르도록 보정
- `is_supported_domain()`이 route-readiness가 아니라 canonical-family helper라는 점을 테스트로 명시

## 변경된 파트
- [ ] fe (web)
- [ ] bff
- [ ] llm-service
- [ ] image-service
- [ ] vision-service
- [x] orchestrator
- [x] infra/docs

## 테스트
- [x] 단위 테스트 추가 or 기존 테스트 통과 확인
- [ ] GitHub Actions `docker-build` 통과 확인

검증 내역:

- `PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing_contract.py orchestrator/tests/test_domain_routing.py orchestrator/tests/test_image_prompt_planner.py orchestrator/tests/test_image_prompt_v3_sceneplan.py orchestrator/tests/test_tone_binding_node.py orchestrator/tests/test_copywriting.py -q`
- `PYTHONPATH=. uv run pytest orchestrator/tests/test_brief_interpreter_llm_v1.py orchestrator/tests/test_image_prompt_planner.py orchestrator/tests/test_image_prompt_v3_integration.py orchestrator/tests/test_image_prompt_v3_sceneplan.py orchestrator/tests/test_visual_templates.py orchestrator/tests/test_visual_strategy_registry.py orchestrator/tests/test_visual_strategy_resolver.py orchestrator/tests/test_copywriting.py orchestrator/tests/test_domain_routing.py orchestrator/tests/test_domain_routing_contract.py orchestrator/tests/test_tone_binding_node.py -q`
- `git diff --check`

## API 스펙 변경 여부
- [x] bff ↔ fe 인터페이스 변경 없음
- [ ] 변경 있음 → Zod 스키마 + FE api-client.ts 동시 업데이트 완료
```

---

## Self-Review

Spec coverage:

- Canonical completeness is covered by existing A-1 tests and Task 7 projection matrix.
- Legacy input normalization is covered by existing tests plus Task 1 option-registry matrix.
- BBQ separation is covered by Task 5 production path and Task 7 projection matrix.
- Beauty ambiguity is covered by Task 4 ScenePlan exclusion, Task 5 production path, and Task 7 projection matrix.
- Unsupported domain preservation is covered by Task 1 option-registry matrix and Task 5 production path.
- Registry contract is covered by Task 3 legacy route inventory.
- Single resolved key is covered by Task 5 and Task 7.
- Copy tone regression is covered by Task 6.
- `is_supported_domain()` ambiguity is covered by Task 2.

Placeholder scan:

- The plan does not contain deferred-work marker tokens.
- The plan does not contain unresolved-task marker tokens.
- The plan does not ask the implementer to "add validation" without code.
- The plan does not ask the implementer to write unspecified tests.

Type consistency:

- `CanonicalBusinessDomain`, `DomainSupportStatus`, `DomainFallbackReason`, `LegacyVisualRouteKey`, and `RoutingTagEvidence` names match `orchestrator/app/llm/domain_routing.py`.
- `ScenePlanBusinessType` is imported as `BusinessType` from `orchestrator/app/llm/schemas/image_prompt_v3.py` in the existing contract test.
- `resolve_copy_route_key()` is imported from `orchestrator/app/llm/copy_tone_policy.py`.
- `tone_binding_node()` and `build_scene_plan()` names match their existing modules.
