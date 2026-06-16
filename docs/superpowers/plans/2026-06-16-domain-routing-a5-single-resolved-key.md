# Domain Routing A5 Single Resolved Key Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Route image prompt template, preset, and scene planning through one evidence-backed `resolved_visual_route_key` produced by the legacy visual adapter.

**Architecture:** `DomainRoutingResult` remains canonical and must not store legacy preset/template keys. A new `project_to_legacy_visual_route()` adapter translates canonical domain + business/product/scene evidence into `LegacyRoutingProjection`; only this projection can produce legacy keys such as `restaurant_bbq`. `image_prompt_planner` computes this projection once and passes the same route key to template, preset, and scene planning while preserving breadcrumbs in metadata.

**Tech Stack:** Python 3.12, Pydantic v2, pytest via `PYTHONPATH=. uv run pytest`.

---

## File Structure

- Modify: `orchestrator/app/llm/domain_routing.py`
  - Add `project_to_legacy_visual_route()`.
  - Add small helpers for normalized tag sets and projection construction.
  - Keep `restaurant_bbq` as `LegacyVisualRouteKey` only; never add it to canonical domain.

- Modify: `orchestrator/app/llm/nodes/image_prompt_planner.py`
  - Compute `DomainRoutingResult` from `context.business_type`.
  - Read `product_visual_context.product_tags` / explicit preparation facts from state.
  - Read explicit scene tags from state/reference routing profile when present.
  - Compute `LegacyRoutingProjection`.
  - Use `projection.route_key.value` for `select_visual_template()`, `build_scene_plan()`, and `select_visual_preset()`.
  - Add `resolved_visual_route_key`, `domain_routing_result`, and `legacy_routing_projection` to image prompt metadata and legacy T2I metadata.

- Modify: `orchestrator/app/llm/metadata_builders.py`
  - Propagate A-5 routing breadcrumbs from `image_prompt_spec.metadata` to `t2i_request.metadata`.

- Modify: `orchestrator/app/llm/visual_presets.py`
  - Remove reference-template direct `preset_id` / `visual_template_id` override from `select_visual_preset()`.

- Modify: `orchestrator/app/llm/scene_planner.py`
  - Stop using `selected_reference_template.business_type/category` as a route source.
  - Treat the incoming `business_type` argument as an already resolved visual route key.

- Modify: `orchestrator/tests/test_domain_routing.py`
  - Add adapter tests for BBQ evidence, ambiguous beauty, retail, unsupported, and explicit beauty subtype projection.

- Modify: `orchestrator/tests/test_image_prompt_planner.py`
  - Add pipeline tests proving template/preset/scene all use one route key.
  - Add a regression test proving selected reference template preset ids cannot override the adapter.

- Modify: `orchestrator/tests/test_image_prompt_v3_sceneplan.py`
  - Update direct scene planner tests so selected reference metadata no longer chooses a route.

- Modify: `orchestrator/tests/test_domain_routing_contract.py`
  - Add metadata/contract assertions for `resolved_visual_route_key` and projection breadcrumbs.

---

### Task 1: Add Legacy Visual Projection Adapter

**Files:**
- Modify: `orchestrator/tests/test_domain_routing.py`
- Modify: `orchestrator/app/llm/domain_routing.py`

- [x] **Step 1: Write failing adapter tests**

Add these imports in `orchestrator/tests/test_domain_routing.py`:

```python
    LegacyVisualRouteKey,
    project_to_legacy_visual_route,
```

Add these tests after `test_normalize_restaurant_bbq_can_accept_explicit_scene_evidence()`:

```python
def test_project_restaurant_bbq_requires_product_or_scene_evidence():
    result = normalize_business_type("restaurant_bbq")

    projection = project_to_legacy_visual_route(
        result,
        product_tags=set(),
        explicit_scene_tags=set(),
    )

    assert projection.route_key == LegacyVisualRouteKey.RESTAURANT
    assert projection.fallback_used is False
    assert projection.fallback_reason is None
    assert "korean_bbq_without_visual_evidence" in projection.reason_codes


def test_project_restaurant_bbq_allows_grilled_meat_product_evidence():
    result = normalize_business_type("restaurant_bbq")

    projection = project_to_legacy_visual_route(
        result,
        product_tags={"grilled_meat"},
        explicit_scene_tags=set(),
    )

    assert projection.route_key == LegacyVisualRouteKey.RESTAURANT_BBQ
    assert projection.fallback_used is False
    assert "bbq_visual_evidence" in projection.reason_codes


def test_project_restaurant_bbq_allows_explicit_bbq_scene_evidence():
    result = normalize_business_type("restaurant_bbq")

    projection = project_to_legacy_visual_route(
        result,
        product_tags=set(),
        explicit_scene_tags={"bbq_grill"},
    )

    assert projection.route_key == LegacyVisualRouteKey.RESTAURANT_BBQ
    assert projection.fallback_used is False
    assert "bbq_visual_evidence" in projection.reason_codes
```

Add these tests after `test_normalize_explicit_beauty_subtypes_are_specialized()`:

```python
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("beauty_skincare", LegacyVisualRouteKey.BEAUTY_SKINCARE),
        ("beauty_hair", LegacyVisualRouteKey.BEAUTY_HAIR),
        ("beauty_nail", LegacyVisualRouteKey.BEAUTY_NAIL),
        ("beauty_spa", LegacyVisualRouteKey.BEAUTY_SPA),
    ],
)
def test_project_explicit_beauty_subtypes(value, expected):
    projection = project_to_legacy_visual_route(
        normalize_business_type(value),
        product_tags=set(),
        explicit_scene_tags=set(),
    )

    assert projection.route_key == expected
    assert projection.fallback_used is False
```

Add these tests after `test_normalize_unsupported_domains_preserves_hint()`:

```python
def test_project_ambiguous_beauty_to_generic_with_reason():
    projection = project_to_legacy_visual_route(
        normalize_business_type("beauty_salon"),
        product_tags=set(),
        explicit_scene_tags=set(),
    )

    assert projection.route_key == LegacyVisualRouteKey.GENERIC
    assert projection.fallback_used is True
    assert projection.fallback_reason == DomainFallbackReason.AMBIGUOUS_BEAUTY_SUBDOMAIN
    assert "ambiguous_beauty_subdomain" in projection.reason_codes


def test_project_retail_to_generic_with_no_visual_profile_reason():
    projection = project_to_legacy_visual_route(
        normalize_business_type("retail"),
        product_tags=set(),
        explicit_scene_tags=set(),
    )

    assert projection.route_key == LegacyVisualRouteKey.GENERIC
    assert projection.fallback_used is True
    assert projection.fallback_reason == DomainFallbackReason.NO_SPECIALIZED_VISUAL_PROFILE
    assert "no_specialized_visual_profile" in projection.reason_codes


def test_project_unsupported_domain_keeps_original_fallback_reason():
    projection = project_to_legacy_visual_route(
        normalize_business_type("fitness"),
        product_tags=set(),
        explicit_scene_tags=set(),
    )

    assert projection.route_key == LegacyVisualRouteKey.GENERIC
    assert projection.fallback_used is True
    assert projection.fallback_reason == DomainFallbackReason.UNSUPPORTED_DOMAIN_IN_MVP
    assert "unsupported_domain_in_mvp" in projection.reason_codes
```

- [x] **Step 2: Run adapter tests to verify RED**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing.py::test_project_restaurant_bbq_requires_product_or_scene_evidence orchestrator/tests/test_domain_routing.py::test_project_restaurant_bbq_allows_grilled_meat_product_evidence orchestrator/tests/test_domain_routing.py::test_project_restaurant_bbq_allows_explicit_bbq_scene_evidence orchestrator/tests/test_domain_routing.py::test_project_explicit_beauty_subtypes orchestrator/tests/test_domain_routing.py::test_project_ambiguous_beauty_to_generic_with_reason orchestrator/tests/test_domain_routing.py::test_project_retail_to_generic_with_no_visual_profile_reason orchestrator/tests/test_domain_routing.py::test_project_unsupported_domain_keeps_original_fallback_reason -q
```

Expected: FAIL because `project_to_legacy_visual_route` does not exist.

- [x] **Step 3: Implement adapter**

Add this code in `orchestrator/app/llm/domain_routing.py` after `_scene_tags_from_evidence()`:

```python
_BBQ_PRODUCT_EVIDENCE_TAGS = frozenset({"grilled_meat"})
_BBQ_SCENE_EVIDENCE_TAGS = frozenset({"bbq_grill", "charcoal_grill", "table_grill"})


def _normalized_tag_set(values: set[str] | list[str] | tuple[str, ...] | None) -> set[str]:
    return {str(value).strip().lower() for value in values or () if str(value).strip()}


def _usable_tag_set(tags: list[RoutingTagEvidence]) -> set[str]:
    return {tag.tag for tag in tags if tag.usable_for_routing}


def _generic_projection(
    *,
    reason: DomainFallbackReason,
    evidence_refs: list[str],
) -> LegacyRoutingProjection:
    return LegacyRoutingProjection(
        route_key=LegacyVisualRouteKey.GENERIC,
        reason_codes=[reason.value],
        evidence_refs=evidence_refs,
        fallback_used=True,
        fallback_reason=reason,
    )


def project_to_legacy_visual_route(
    domain_result: DomainRoutingResult,
    *,
    product_tags: set[str],
    explicit_scene_tags: set[str],
) -> LegacyRoutingProjection:
    business_tags = _usable_tag_set(domain_result.business_tags)
    scene_tags = _usable_tag_set(domain_result.scene_tags) | _normalized_tag_set(explicit_scene_tags)
    product_tag_set = _normalized_tag_set(product_tags)
    evidence_refs = list(domain_result.evidence_refs)

    if domain_result.canonical_domain == CanonicalBusinessDomain.FOOD_AND_BEVERAGE:
        if "cafe" in business_tags:
            return LegacyRoutingProjection(
                route_key=LegacyVisualRouteKey.CAFE,
                reason_codes=["cafe_business_tag"],
                evidence_refs=evidence_refs,
            )
        if "restaurant" in business_tags:
            has_bbq_visual_evidence = bool(
                ("korean_bbq" in business_tags)
                and (
                    product_tag_set & _BBQ_PRODUCT_EVIDENCE_TAGS
                    or scene_tags & _BBQ_SCENE_EVIDENCE_TAGS
                )
            )
            if has_bbq_visual_evidence:
                return LegacyRoutingProjection(
                    route_key=LegacyVisualRouteKey.RESTAURANT_BBQ,
                    reason_codes=["bbq_visual_evidence"],
                    evidence_refs=evidence_refs,
                )
            reason_codes = ["restaurant_business_tag"]
            if "korean_bbq" in business_tags:
                reason_codes.append("korean_bbq_without_visual_evidence")
            return LegacyRoutingProjection(
                route_key=LegacyVisualRouteKey.RESTAURANT,
                reason_codes=reason_codes,
                evidence_refs=evidence_refs,
            )
        return _generic_projection(
            reason=DomainFallbackReason.NO_SPECIALIZED_VISUAL_PROFILE,
            evidence_refs=evidence_refs,
        )

    if domain_result.canonical_domain == CanonicalBusinessDomain.BEAUTY:
        if "skincare" in business_tags:
            return LegacyRoutingProjection(route_key=LegacyVisualRouteKey.BEAUTY_SKINCARE, reason_codes=["beauty_subtype_evidence"], evidence_refs=evidence_refs)
        if "hair" in business_tags:
            return LegacyRoutingProjection(route_key=LegacyVisualRouteKey.BEAUTY_HAIR, reason_codes=["beauty_subtype_evidence"], evidence_refs=evidence_refs)
        if "nail" in business_tags:
            return LegacyRoutingProjection(route_key=LegacyVisualRouteKey.BEAUTY_NAIL, reason_codes=["beauty_subtype_evidence"], evidence_refs=evidence_refs)
        if "spa" in business_tags:
            return LegacyRoutingProjection(route_key=LegacyVisualRouteKey.BEAUTY_SPA, reason_codes=["beauty_subtype_evidence"], evidence_refs=evidence_refs)
        return _generic_projection(
            reason=domain_result.fallback_reason or DomainFallbackReason.AMBIGUOUS_BEAUTY_SUBDOMAIN,
            evidence_refs=evidence_refs,
        )

    if domain_result.canonical_domain == CanonicalBusinessDomain.RETAIL:
        return _generic_projection(
            reason=DomainFallbackReason.NO_SPECIALIZED_VISUAL_PROFILE,
            evidence_refs=evidence_refs,
        )

    return _generic_projection(
        reason=domain_result.fallback_reason or DomainFallbackReason.UNRECOGNIZED_BUSINESS_TYPE,
        evidence_refs=evidence_refs,
    )
```

- [x] **Step 4: Run adapter tests to verify GREEN**

Run the same command from Step 2.

Expected: PASS.

- [x] **Step 5: Commit adapter task**

```bash
git add orchestrator/app/llm/domain_routing.py orchestrator/tests/test_domain_routing.py
git commit -m "feat(srv): add legacy visual route projection"
```

### Task 2: Wire Image Prompt Planner to One Resolved Key

**Files:**
- Modify: `orchestrator/tests/test_image_prompt_planner.py`
- Modify: `orchestrator/app/llm/nodes/image_prompt_planner.py`

- [x] **Step 1: Write failing single-key pipeline tests**

In `orchestrator/tests/test_image_prompt_planner.py`, add this helper after `_state()`:

```python
def _with_product_visual_context(state: dict, *, product_tags: list[str]) -> dict:
    state = dict(state)
    state["product_visual_context"] = {
        "product_name": state["context"]["item_or_service"],
        "product_tags": product_tags,
        "evidence_refs": ["test:product_visual_context"],
        "confidence": 0.95,
    }
    return state
```

Change the `restaurant_bbq` expectation in `test_image_prompt_template_selection_variants()`:

```python
assert build_image_prompt_spec_with_critic(_state("restaurant_bbq")).metadata["visual_template_id"] == "restaurant_generic_clean"
```

Add these tests:

```python
def test_image_prompt_single_resolved_key_downgrades_legacy_bbq_without_visual_evidence():
    spec = build_image_prompt_spec_with_critic(_state("restaurant_bbq"))
    metadata = spec.metadata

    assert metadata["resolved_visual_route_key"] == "restaurant"
    assert metadata["visual_template_id"] == "restaurant_generic_clean"
    assert metadata["business_visual_preset_id"] == "restaurant_generic_clean"
    assert metadata["scene_plan"]["business_type"] == "restaurant"
    assert metadata["legacy_routing_projection"]["route_key"] == "restaurant"
    assert "korean_bbq_without_visual_evidence" in metadata["legacy_routing_projection"]["reason_codes"]


def test_image_prompt_single_resolved_key_allows_bbq_with_grilled_meat_product_evidence():
    state = _with_product_visual_context(
        _state("restaurant_bbq"),
        product_tags=["pork", "grilled_meat"],
    )

    spec = build_image_prompt_spec_with_critic(state)
    metadata = spec.metadata

    assert metadata["resolved_visual_route_key"] == "restaurant_bbq"
    assert metadata["visual_template_id"] == "restaurant_bbq_warm_grill"
    assert metadata["business_visual_preset_id"] == "restaurant_bbq_warm_grill"
    assert metadata["scene_plan"]["business_type"] == "restaurant_bbq"
    assert metadata["legacy_routing_projection"]["route_key"] == "restaurant_bbq"


def test_image_prompt_single_resolved_key_preserves_unsupported_fallback_breadcrumb():
    spec = build_image_prompt_spec_with_critic(_state("fitness"))
    metadata = spec.metadata

    assert metadata["resolved_visual_route_key"] == "generic"
    assert metadata["visual_template_id"] == "generic_clean_ad_background"
    assert metadata["business_visual_preset_id"] == "generic_clean_ad_background"
    assert metadata["domain_routing_result"]["unsupported_domain_hint"] == "fitness"
    assert metadata["legacy_routing_projection"]["fallback_reason"] == "unsupported_domain_in_mvp"
```

- [x] **Step 2: Run image prompt tests to verify RED**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_image_prompt_planner.py::test_image_prompt_template_selection_variants orchestrator/tests/test_image_prompt_planner.py::test_image_prompt_single_resolved_key_downgrades_legacy_bbq_without_visual_evidence orchestrator/tests/test_image_prompt_planner.py::test_image_prompt_single_resolved_key_allows_bbq_with_grilled_meat_product_evidence orchestrator/tests/test_image_prompt_planner.py::test_image_prompt_single_resolved_key_preserves_unsupported_fallback_breadcrumb -q
```

Expected: FAIL because `resolved_visual_route_key`, `domain_routing_result`, and `legacy_routing_projection` metadata do not exist and `restaurant_bbq` still reaches the BBQ template directly.

- [x] **Step 3: Implement planner routing helpers and single-key wiring**

In `orchestrator/app/llm/nodes/image_prompt_planner.py`, add imports:

```python
from orchestrator.app.llm.domain_routing import normalize_business_type, project_to_legacy_visual_route
```

Add these helpers near `TEXT_NEGATIVE`:

```python
def _string_set_from_mapping(source: Any, field: str) -> set[str]:
    if not source:
        return set()
    if hasattr(source, "model_dump"):
        source = source.model_dump()
    if not isinstance(source, dict):
        return set()
    values = source.get(field) or []
    if isinstance(values, str):
        values = [values]
    return {str(value).strip().lower() for value in values if str(value).strip()}


def _product_tags_from_state(state: MarketingState) -> set[str]:
    product_context = state.get("product_visual_context") or {}
    return (
        _string_set_from_mapping(product_context, "product_tags")
        | _string_set_from_mapping(product_context, "explicit_preparation_methods")
    )


def _explicit_scene_tags_from_state(state: MarketingState) -> set[str]:
    selected_reference_template = state.get("selected_reference_template") or {}
    reference_template_selection = state.get("reference_template_selection") or {}
    routing_profile = (
        reference_template_selection.get("routing_profile")
        if isinstance(reference_template_selection, dict)
        else {}
    ) or {}
    return (
        _string_set_from_mapping(state, "explicit_scene_tags")
        | _string_set_from_mapping(selected_reference_template, "scene_tags")
        | _string_set_from_mapping(routing_profile, "scene_tags")
    )
```

Inside `build_image_prompt_spec_with_critic()`, replace the current `visual_template = ...` line with:

```python
    domain_result = normalize_business_type(context.business_type)
    legacy_projection = project_to_legacy_visual_route(
        domain_result,
        product_tags=_product_tags_from_state(state),
        explicit_scene_tags=_explicit_scene_tags_from_state(state),
    )
    resolved_visual_route_key = legacy_projection.route_key.value
    visual_template = select_visual_template(resolved_visual_route_key, ad_format_spec.get("ad_format"), style_profile or selected_tone, selected_reference_template)
```

Change the `build_scene_plan()` call to pass `resolved_visual_route_key`:

```python
        business_type=resolved_visual_route_key,
```

Change the `metadata={...}` argument in `build_scene_plan()`:

```python
            "business_type": resolved_visual_route_key,
```

Change the `select_visual_preset()` call:

```python
        business_type=resolved_visual_route_key,
```

Add these metadata keys to `ImagePromptSpec(metadata={...})`:

```python
            "resolved_visual_route_key": resolved_visual_route_key,
            "domain_routing_result": domain_result.model_dump(mode="json"),
            "legacy_routing_projection": legacy_projection.model_dump(mode="json"),
```

In `build_legacy_image_prompt()`, extend the v3 metadata copy list:

```python
    for key in [
        "image_prompt_version",
        "scene_plan",
        "prompt_quality_policy",
        "prompt_adapter",
        "business_visual_preset_id",
        "beauty_subtype",
        "resolved_visual_route_key",
        "domain_routing_result",
        "legacy_routing_projection",
    ]:
```

- [x] **Step 4: Run image prompt tests to verify GREEN**

Run the command from Step 2.

Expected: PASS.

- [x] **Step 5: Commit planner task**

```bash
git add orchestrator/app/llm/nodes/image_prompt_planner.py orchestrator/tests/test_image_prompt_planner.py
git commit -m "feat(srv): route image prompts through single visual key"
```

### Task 3: Remove Reference Template Route Override

**Files:**
- Modify: `orchestrator/tests/test_image_prompt_planner.py`
- Modify: `orchestrator/tests/test_image_prompt_v3_sceneplan.py`
- Modify: `orchestrator/app/llm/visual_presets.py`
- Modify: `orchestrator/app/llm/scene_planner.py`

- [x] **Step 1: Write failing override tests**

Add this test to `orchestrator/tests/test_image_prompt_planner.py`:

```python
def test_reference_template_preset_id_cannot_override_resolved_visual_key():
    state = _state(
        "unknown",
        {
            "title": "Legacy BBQ Reference",
            "preset_id": "restaurant_bbq_warm_grill",
            "visual_template_id": "restaurant_bbq_warm_grill",
        },
    )

    spec = build_image_prompt_spec_with_critic(state)
    metadata = spec.metadata

    assert metadata["resolved_visual_route_key"] == "generic"
    assert metadata["visual_template_id"] == "generic_clean_ad_background"
    assert metadata["business_visual_preset_id"] == "generic_clean_ad_background"
    assert metadata["scene_plan"]["business_type"] == "generic"
```

Replace `test_scene_planner_accepts_exact_reference_route_keys_only()` in `orchestrator/tests/test_image_prompt_v3_sceneplan.py` with:

```python
def test_scene_planner_does_not_route_from_reference_business_type():
    assert resolve_business_type(
        user_input="",
        business_type=None,
        selected_reference_template={"business_type": "restaurant_bbq"},
    ) == "generic"
    assert resolve_business_type(
        user_input="헤어 스타일링",
        business_type=None,
        selected_reference_template={"category": "beauty_salon"},
    ) == "generic"
```

- [x] **Step 2: Run override tests to verify RED**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_image_prompt_planner.py::test_reference_template_preset_id_cannot_override_resolved_visual_key orchestrator/tests/test_image_prompt_v3_sceneplan.py::test_scene_planner_does_not_route_from_reference_business_type -q
```

Expected: FAIL because `select_visual_preset()` still accepts reference preset ids and `resolve_business_type()` still reads reference `business_type/category`.

- [x] **Step 3: Remove override paths**

In `orchestrator/app/llm/visual_presets.py`, delete this block from `select_visual_preset()`:

```python
    # Check selected reference template first for hints if present
    ref_preset_id = (selected_reference_template or {}).get("preset_id") or (selected_reference_template or {}).get("visual_template_id")
    if ref_preset_id and ref_preset_id in VISUAL_PRESETS:
        return VISUAL_PRESETS[ref_preset_id]
```

In `orchestrator/app/llm/scene_planner.py`, change `resolve_business_type()` candidates to:

```python
    candidates: list[str | None] = [
        str((metadata or {}).get("business_type")) if (metadata or {}).get("business_type") else None,
        business_type,
    ]
```

- [x] **Step 4: Run override tests to verify GREEN**

Run the command from Step 2.

Expected: PASS.

- [x] **Step 5: Commit override task**

```bash
git add orchestrator/app/llm/visual_presets.py orchestrator/app/llm/scene_planner.py orchestrator/tests/test_image_prompt_planner.py orchestrator/tests/test_image_prompt_v3_sceneplan.py
git commit -m "fix(srv): prevent reference template visual route override"
```

### Task 4: Add Cross-Module Contract Coverage

**Files:**
- Modify: `orchestrator/tests/test_domain_routing_contract.py`
- Modify: `orchestrator/tests/test_image_prompt_v3_integration.py`
- Modify: `orchestrator/app/llm/metadata_builders.py`

- [x] **Step 1: Write failing contract tests**

Add this import to `orchestrator/tests/test_domain_routing_contract.py`:

```python
    project_to_legacy_visual_route,
```

Add these tests near the A-4 selector tests:

```python
def test_legacy_projection_is_the_only_place_that_can_select_bbq_visual_route():
    projection = project_to_legacy_visual_route(
        normalize_business_type("restaurant_bbq"),
        product_tags=set(),
        explicit_scene_tags=set(),
    )

    assert projection.route_key == LegacyVisualRouteKey.RESTAURANT
    assert projection.route_key != LegacyVisualRouteKey.RESTAURANT_BBQ


def test_legacy_projection_selects_bbq_only_with_visual_evidence():
    projection = project_to_legacy_visual_route(
        normalize_business_type("restaurant_bbq"),
        product_tags={"grilled_meat"},
        explicit_scene_tags=set(),
    )

    assert projection.route_key == LegacyVisualRouteKey.RESTAURANT_BBQ
```

In `orchestrator/tests/test_image_prompt_v3_integration.py`, add after `assert spec_meta.get("image_prompt_version") == "v3"` in `test_image_prompt_v3_integration_flow()`:

```python
    assert spec_meta.get("resolved_visual_route_key") == "cafe"
    assert spec_meta.get("legacy_routing_projection", {}).get("route_key") == "cafe"
```

Add after the `t2i_meta` assertions:

```python
    assert t2i_meta.get("resolved_visual_route_key") == spec_meta.get("resolved_visual_route_key")
    assert t2i_meta.get("legacy_routing_projection") == spec_meta.get("legacy_routing_projection")
```

- [x] **Step 2: Run contract tests**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing_contract.py::test_legacy_projection_is_the_only_place_that_can_select_bbq_visual_route orchestrator/tests/test_domain_routing_contract.py::test_legacy_projection_selects_bbq_only_with_visual_evidence orchestrator/tests/test_image_prompt_v3_integration.py::test_image_prompt_v3_integration_flow -q
```

Expected: PASS if Tasks 1-3 are complete.

- [x] **Step 3: Commit contract task**

```bash
git add orchestrator/tests/test_domain_routing_contract.py orchestrator/tests/test_image_prompt_v3_integration.py
git commit -m "test(srv): pin single resolved route metadata contract"
```

### Task 5: Final Verification

**Files:**
- Inspect: `orchestrator/app/llm/domain_routing.py`
- Inspect: `orchestrator/app/llm/nodes/image_prompt_planner.py`
- Inspect: `orchestrator/app/llm/scene_planner.py`
- Inspect: `orchestrator/app/llm/visual_presets.py`
- Inspect: `orchestrator/tests/test_domain_routing.py`
- Inspect: `orchestrator/tests/test_domain_routing_contract.py`
- Inspect: `orchestrator/tests/test_image_prompt_planner.py`
- Inspect: `orchestrator/tests/test_image_prompt_v3_sceneplan.py`
- Inspect: `orchestrator/tests/test_image_prompt_v3_integration.py`

- [x] **Step 1: Run focused A-5 suite**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing.py orchestrator/tests/test_domain_routing_contract.py orchestrator/tests/test_visual_templates.py orchestrator/tests/test_image_prompt_planner.py orchestrator/tests/test_image_prompt_v3_sceneplan.py orchestrator/tests/test_image_prompt_v3_integration.py -q
```

Expected: PASS.

- [x] **Step 2: Run broader routing/copy guard suite**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_brief_interpreter_llm_v1.py orchestrator/tests/test_business_context.py orchestrator/tests/test_product_visual_context.py orchestrator/tests/test_copywriting.py::test_restaurant_bbq_policy_uses_reservation_cta orchestrator/tests/test_domain_routing_contract.py::test_plain_restaurant_copy_is_not_aliased_to_bbq -q
```

Expected: PASS.

- [x] **Step 3: Run selector smoke script**

Run:

```bash
PYTHONPATH=. uv run python - <<'PY'
from orchestrator.app.llm.domain_routing import normalize_business_type, project_to_legacy_visual_route

cases = [
    ("restaurant_bbq", set(), set()),
    ("restaurant_bbq", {"grilled_meat"}, set()),
    ("restaurant_bbq", set(), {"bbq_grill"}),
    ("beauty_salon", set(), set()),
    ("retail", set(), set()),
    ("fitness", set(), set()),
]

for raw, product_tags, scene_tags in cases:
    projection = project_to_legacy_visual_route(
        normalize_business_type(raw),
        product_tags=product_tags,
        explicit_scene_tags=scene_tags,
    )
    print(raw, sorted(product_tags), sorted(scene_tags), projection.route_key.value, projection.fallback_reason.value if projection.fallback_reason else None)
PY
```

Expected output:

```text
restaurant_bbq [] [] restaurant None
restaurant_bbq ['grilled_meat'] [] restaurant_bbq None
restaurant_bbq [] ['bbq_grill'] restaurant_bbq None
beauty_salon [] [] generic ambiguous_beauty_subdomain
retail [] [] generic no_specialized_visual_profile
fitness [] [] generic unsupported_domain_in_mvp
```

- [x] **Step 4: Run whitespace diff check**

Run:

```bash
git diff --check
```

Expected: no output.

- [x] **Step 5: Confirm branch status**

Run:

```bash
git status --short --branch
```

Expected: branch `feat/srv/domain-routing-a5-single-resolved-key` with no uncommitted changes after commits.

## Self-Review

- Spec coverage: This plan implements `project_to_legacy_visual_route()`, prevents `restaurant_bbq` from being selected without product/scene evidence, routes template/preset/scene through one `resolved_visual_route_key`, preserves fallback breadcrumbs, and removes reference preset/template override paths.
- Placeholder scan: No placeholder steps are present; every code-changing step contains concrete code or exact code to remove.
- Type consistency: `DomainRoutingResult`, `LegacyRoutingProjection`, `LegacyVisualRouteKey`, `DomainFallbackReason`, `normalize_business_type()`, and `project_to_legacy_visual_route()` are used consistently across tests and implementation.
