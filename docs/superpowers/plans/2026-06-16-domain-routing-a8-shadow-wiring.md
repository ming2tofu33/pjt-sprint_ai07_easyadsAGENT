# Domain Routing A-8 Shadow Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire B's canonical visual strategy resolver into the production image prompt path in shadow mode while preserving every legacy production routing output.

**Architecture:** A-8 is a shadow-only integration. `image_prompt_planner.py` keeps using the legacy `DomainRoutingResult -> LegacyRoutingProjection -> resolved_visual_route_key` path for actual template, preset, scene plan, prompt adapter, and generated output. A new integration helper assembles deterministic canonical resolver inputs, runs the canonical resolver in fail-open shadow mode, compares canonical vs legacy route resources, and stores sanitized diagnostics under image prompt metadata.

**Tech Stack:** Python 3.12, Pydantic v2, LangGraph state dicts, pytest, existing `domain_routing`, `visual_routing_shadow`, `visual_routing_trace`, `visual_strategy_resolver`, and visual strategy registry modules.

---

## Safety Contract

A-8 first PR is observation-only.

Allowed output changes:

- Add `metadata["visual_routing"]` to `ImagePromptSpec`.
- Add `metadata["visual_routing"]` to legacy `ImagePrompt`.
- Add tests and a focused integration helper.

Forbidden output changes:

- Do not change `metadata["resolved_visual_route_key"]`.
- Do not change `metadata["visual_template_id"]`.
- Do not change `metadata["business_visual_preset_id"]`.
- Do not change `metadata["scene_plan"]["business_type"]`.
- Do not use canonical `VisualStrategyDecision` to choose the production preset, template, scene plan, prompt adapter, or copy tone.
- Do not call async/LLM semantic intent generation from `image_prompt_planner.py`.
- Do not remove legacy route keys or legacy selectors.
- Do not add a new beauty generic preset in this PR.

Fail-open rule:

- Canonical resolver failures must not fail image prompt generation.
- Route comparison failures must not fail image prompt generation.
- Visual routing trace build failures must not fail image prompt generation.
- Failures are recorded as sanitized metadata with exception class names only.

Plan basis:

- Latest checked `origin/develop`: `be892c25`.
- A-7 PR `#224` is merged.
- B resolver/shadow/trace modules are present and their focused tests pass.
- `docs/two track.md` is currently an untracked planning reference in the main workspace, not a file on `develop`.

---

## File Structure

Create:

- `orchestrator/app/llm/visual_routing_integration.py`
  - Owns A-8 production wiring helpers.
  - Builds deterministic shadow inputs from current state.
  - Runs `execute_visual_routing_mode(RoutingMode.SHADOW, ...)`.
  - Builds sanitized visual routing metadata.
  - Contains a catalog family resolver for route comparison.

Modify:

- `orchestrator/app/llm/nodes/image_prompt_planner.py`
  - Calls the new helper after legacy template/preset selection.
  - Adds nested `visual_routing` metadata to `ImagePromptSpec`.
  - Keeps legacy production route values unchanged.
  - Copies `visual_routing` metadata into legacy `ImagePrompt`.

- `orchestrator/tests/test_image_prompt_planner.py`
  - Locks shadow-only production behavior.
  - Locks fail-open behavior.
  - Locks no copy-tone rebinding.

Create:

- `orchestrator/tests/test_visual_routing_integration.py`
  - Unit tests for the helper module.
  - Covers mode resolution, deterministic fallback contexts, family resolver, trace sanitization, and fail-open metadata.

Do not modify in A-8:

- `orchestrator/app/llm/domain_routing.py`
- `orchestrator/app/llm/visual_strategy_resolver.py`
- `orchestrator/app/llm/visual_strategy_profiles.py`
- `orchestrator/app/llm/visual_routing_shadow.py`
- `orchestrator/app/llm/visual_routing_trace.py`
- `orchestrator/app/llm/copy_tone_policy.py`
- `orchestrator/app/llm/scene_planner.py`
- `orchestrator/app/llm/visual_presets.py`
- `orchestrator/app/llm/visual_templates.py`

---

## Task 1: Start From Latest Develop And Add Failing Metadata Contract Tests

**Files:**

- Modify: `orchestrator/tests/test_image_prompt_planner.py`

- [ ] **Step 1: Create the implementation branch from latest develop**

```bash
git fetch origin develop
git switch develop
git pull --ff-only origin develop
git switch -c feat/srv/domain-routing-a8-shadow-wiring
```

Expected:

```text
Switched to a new branch 'feat/srv/domain-routing-a8-shadow-wiring'
```

- [ ] **Step 2: Add imports to image prompt planner tests**

Add these imports near the top of `orchestrator/tests/test_image_prompt_planner.py`:

```python
from orchestrator.app.schemas.visual_routing_shadow import RoutingMode, RoutingSource
```

- [ ] **Step 3: Add the shadow metadata preservation test**

Add this test after `test_image_prompt_single_resolved_key_allows_bbq_with_grilled_meat_product_evidence()`:

```python
def test_a8_shadow_metadata_preserves_legacy_production_route():
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
    visual_routing = metadata["visual_routing"]
    assert visual_routing["routing_mode"] == RoutingMode.SHADOW.value
    assert visual_routing["active_source"] == RoutingSource.LEGACY.value
    assert visual_routing["trace_available"] is True
    assert visual_routing["trace"]["routing_mode"] == RoutingMode.SHADOW.value
    assert visual_routing["trace"]["active_route"]["source"] == RoutingSource.LEGACY.value
    assert visual_routing["trace"]["active_route"]["preset_id"] == "restaurant_bbq_warm_grill"
    assert visual_routing["trace"]["active_route"]["template_id"] == "restaurant_bbq_warm_grill"
```

- [ ] **Step 4: Add the copy-tone isolation test**

Add this test after the previous test:

```python
def test_a8_shadow_metadata_does_not_rebind_copy_tone_from_visual_route():
    state = _with_product_visual_context(
        _state("restaurant_bbq"),
        product_tags=["pork", "grilled_meat"],
    )

    spec = build_image_prompt_spec_with_critic(state)
    visual_routing = spec.metadata["visual_routing"]
    legacy = visual_routing["trace"]["legacy_observation"]

    assert spec.metadata["resolved_visual_route_key"] == "restaurant_bbq"
    assert legacy["copy_tone_profile_id"] is None
    assert "restaurant_bbq_v1" not in str(visual_routing)
```

- [ ] **Step 5: Add the fail-open test**

Add this test after the copy-tone isolation test:

```python
def test_a8_shadow_metadata_fail_open_when_canonical_resolution_fails(monkeypatch):
    def raise_canonical_error(*args, **kwargs):
        raise RuntimeError("canonical resolver unavailable")

    monkeypatch.setattr(
        "orchestrator.app.llm.visual_routing_integration.resolve_visual_strategy",
        raise_canonical_error,
    )

    spec = build_image_prompt_spec_with_critic(_state("cafe"))
    metadata = spec.metadata

    _assert_single_resolved_visual_key(
        metadata,
        route_key="cafe",
        preset_id="cafe_dessert_soft_premium",
        template_id="cafe_dessert_soft_premium",
    )
    visual_routing = metadata["visual_routing"]
    assert visual_routing["routing_mode"] == RoutingMode.SHADOW.value
    assert visual_routing["active_source"] == RoutingSource.LEGACY.value
    assert visual_routing["trace_available"] is True
    assert visual_routing["trace"]["completeness"] == "partial"
    assert visual_routing["trace"]["shadow_error"]["code"] == "canonical_resolution_failed"
```

- [ ] **Step 6: Run the focused failing tests**

```bash
PYTHONPATH=. uv run pytest \
  orchestrator/tests/test_image_prompt_planner.py::test_a8_shadow_metadata_preserves_legacy_production_route \
  orchestrator/tests/test_image_prompt_planner.py::test_a8_shadow_metadata_does_not_rebind_copy_tone_from_visual_route \
  orchestrator/tests/test_image_prompt_planner.py::test_a8_shadow_metadata_fail_open_when_canonical_resolution_fails \
  -q
```

Expected:

```text
FAILED ... KeyError: 'visual_routing'
```

- [ ] **Step 7: Commit the failing tests**

```bash
git add orchestrator/tests/test_image_prompt_planner.py
git commit -m "test(srv): define a8 shadow routing metadata contract"
```

---

## Task 2: Add Visual Routing Integration Helper Skeleton

**Files:**

- Create: `orchestrator/app/llm/visual_routing_integration.py`
- Create: `orchestrator/tests/test_visual_routing_integration.py`

- [ ] **Step 1: Add helper unit tests for mode and sanitized failure metadata**

Create `orchestrator/tests/test_visual_routing_integration.py` with this content:

```python
from __future__ import annotations

from orchestrator.app.llm.visual_routing_integration import (
    build_fail_open_visual_routing_metadata,
    resolve_visual_routing_mode,
)
from orchestrator.app.schemas.visual_routing_shadow import RoutingMode, RoutingSource


def test_a8_visual_routing_mode_defaults_to_shadow():
    assert resolve_visual_routing_mode({}) == RoutingMode.SHADOW


def test_a8_visual_routing_mode_reads_render_options():
    state = {"render_options": {"visual_routing_mode": "legacy"}}

    assert resolve_visual_routing_mode(state) == RoutingMode.LEGACY


def test_a8_visual_routing_mode_rejects_canonical_for_first_shadow_pr():
    state = {"render_options": {"visual_routing_mode": "canonical"}}

    assert resolve_visual_routing_mode(state) == RoutingMode.SHADOW


def test_a8_fail_open_metadata_is_sanitized():
    metadata = build_fail_open_visual_routing_metadata(
        mode=RoutingMode.SHADOW,
        exception=RuntimeError("contains user prompt or secret"),
        stage="trace_build",
    )

    assert metadata == {
        "routing_mode": "shadow",
        "active_source": "legacy",
        "trace_available": False,
        "trace_error": {
            "stage": "trace_build",
            "exception_type": "RuntimeError",
        },
    }
    assert "secret" not in str(metadata)
```

- [ ] **Step 2: Run helper tests to verify they fail**

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_visual_routing_integration.py -q
```

Expected:

```text
FAILED ... ModuleNotFoundError: No module named 'orchestrator.app.llm.visual_routing_integration'
```

- [ ] **Step 3: Create the helper module with mode and failure metadata**

Create `orchestrator/app/llm/visual_routing_integration.py` with this content:

```python
"""A-8 shadow-only visual routing integration for image prompt planning."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from orchestrator.app.schemas.visual_routing_shadow import RoutingMode, RoutingSource


VISUAL_ROUTING_METADATA_VERSION = "image-prompt-visual-routing-shadow-v1"


def resolve_visual_routing_mode(state: Mapping[str, Any] | None) -> RoutingMode:
    """Resolve the A-8 routing mode.

    The first A-8 PR is shadow-only. A requested canonical mode is coerced to
    SHADOW so production output cannot switch to canonical route selection.
    """

    state = state or {}
    render_options = state.get("render_options") if isinstance(state, Mapping) else {}
    raw_mode = None
    if isinstance(render_options, Mapping):
        raw_mode = render_options.get("visual_routing_mode")
    raw_mode = raw_mode or state.get("visual_routing_mode")
    normalized = str(raw_mode or RoutingMode.SHADOW.value).strip().lower()
    if normalized == RoutingMode.LEGACY.value:
        return RoutingMode.LEGACY
    return RoutingMode.SHADOW


def build_fail_open_visual_routing_metadata(
    *,
    mode: RoutingMode,
    exception: Exception,
    stage: str,
) -> dict[str, Any]:
    return {
        "routing_mode": mode.value,
        "active_source": RoutingSource.LEGACY.value,
        "trace_available": False,
        "trace_error": {
            "stage": str(stage),
            "exception_type": exception.__class__.__name__,
        },
    }
```

- [ ] **Step 4: Run helper tests to verify they pass**

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_visual_routing_integration.py -q
```

Expected:

```text
4 passed
```

- [ ] **Step 5: Commit helper skeleton**

```bash
git add orchestrator/app/llm/visual_routing_integration.py orchestrator/tests/test_visual_routing_integration.py
git commit -m "feat(srv): add visual routing shadow integration skeleton"
```

---

## Task 3: Build Deterministic Canonical Resolver Inputs

**Files:**

- Modify: `orchestrator/app/llm/visual_routing_integration.py`
- Modify: `orchestrator/tests/test_visual_routing_integration.py`

- [ ] **Step 1: Add tests for deterministic context fallbacks**

Append these tests to `orchestrator/tests/test_visual_routing_integration.py`:

```python
from orchestrator.app.llm.domain_routing import normalize_business_type
from orchestrator.app.llm.visual_routing_integration import (
    build_visual_semantic_intent_for_shadow,
    build_visual_strategy_context_for_shadow,
    build_visual_strategy_runtime_context,
)
from orchestrator.app.schemas.llm_marketing import MarketingContext


def test_a8_builds_context_from_state_without_product_visual_context():
    marketing_context = MarketingContext(
        business_type="restaurant",
        item_or_service="감자튀김",
        promotion_goal="new_menu",
        brand_tone="premium",
    )
    state = {
        "context": marketing_context.model_dump(),
        "ad_format_spec": {"ad_format": "instagram_feed", "width": 1024, "height": 1024, "aspect_ratio": "1:1"},
        "product_understanding": {
            "schema_version": "product_understanding_v1",
            "product_name": "감자튀김",
            "normalized_product_type": "fried_potato",
            "broad_category": "food_and_beverage",
            "category_path": ["food_and_beverage", "fried_potato"],
            "product_name_evidence_ids": ["test:product"],
            "confidence": 0.91,
        },
    }

    domain = normalize_business_type("restaurant")
    routing_context = build_visual_strategy_context_for_shadow(
        state=state,
        marketing_context=marketing_context,
        domain_result=domain,
    )

    assert routing_context.domain == domain
    assert routing_context.product.product_name == "감자튀김"
    assert routing_context.product_visual.product_name == "감자튀김"
    assert routing_context.product_visual.evidence_refs == ("test:product",)
    assert routing_context.business.business_tags == ("restaurant",)
    assert routing_context.ad_format.ad_format == "instagram_feed"


def test_a8_minimal_context_does_not_infer_grill_from_business_type():
    marketing_context = MarketingContext(
        business_type="restaurant_bbq",
        item_or_service="감자튀김",
        promotion_goal="new_menu",
    )
    state = {
        "context": marketing_context.model_dump(),
        "ad_format_spec": {"ad_format": "instagram_feed", "width": 1024, "height": 1024, "aspect_ratio": "1:1"},
    }

    domain = normalize_business_type("restaurant_bbq")
    routing_context = build_visual_strategy_context_for_shadow(
        state=state,
        marketing_context=marketing_context,
        domain_result=domain,
    )

    assert "korean_bbq" in routing_context.business.business_tags
    assert "grilled_meat" not in routing_context.product_visual.product_tags
    assert "table_grilled" not in routing_context.product_visual.explicit_preparation_methods


def test_a8_visual_semantic_intent_uses_open_tokens_only():
    marketing_context = MarketingContext(
        business_type="restaurant",
        item_or_service="감자튀김",
        promotion_goal="new_menu",
    )
    state = {
        "context": marketing_context.model_dump(),
        "ad_format_spec": {"ad_format": "instagram_feed", "width": 1024, "height": 1024, "aspect_ratio": "1:1"},
        "product_visual_context": {
            "product_name": "감자튀김",
            "product_tags": ["fried_potato"],
            "prohibited_visual_inferences": ["grill", "charcoal"],
            "evidence_refs": ["test:product_visual"],
            "confidence": 0.93,
        },
        "text_style_spec": {"profile": "premium"},
    }
    domain = normalize_business_type("restaurant")
    routing_context = build_visual_strategy_context_for_shadow(
        state=state,
        marketing_context=marketing_context,
        domain_result=domain,
    )

    intent = build_visual_semantic_intent_for_shadow(state, routing_context)

    assert intent.required_visual_facts == ("fried_potato",)
    assert intent.prohibited_visual_elements == ("grill", "charcoal")
    assert intent.desired_moods == ("premium",)
    assert "preset_id" not in intent.model_dump()
    assert "template_id" not in intent.model_dump()


def test_a8_runtime_context_uses_ad_format_placement():
    runtime = build_visual_strategy_runtime_context(
        state={"ad_format_spec": {"ad_format": "poster"}},
        ad_format_spec={"ad_format": "poster"},
    )

    assert runtime.placement == "poster"
    assert runtime.campaign_roles == frozenset()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_visual_routing_integration.py -q
```

Expected:

```text
FAILED ... ImportError: cannot import name 'build_visual_strategy_context_for_shadow'
```

- [ ] **Step 3: Add deterministic context builders**

Add these imports to `orchestrator/app/llm/visual_routing_integration.py`:

```python
from orchestrator.app.llm.business_context_service import build_business_environment_context_from_domain_routing
from orchestrator.app.llm.creative_routing_context_service import build_creative_routing_context
from orchestrator.app.llm.product_visual_context_service import product_visual_context_from_understanding
from orchestrator.app.schemas.llm_marketing import AdFormatSpec, MarketingContext
from orchestrator.app.schemas.product_understanding import ProductUnderstanding
from orchestrator.app.schemas.product_visual_context import ProductVisualContext
from orchestrator.app.schemas.visual_semantic_intent import VisualSemanticIntent
from orchestrator.app.schemas.visual_strategy_resolution import VisualStrategyRuntimeContext
from orchestrator.app.schemas.campaign_context import CampaignContext
from orchestrator.app.llm.domain_routing import DomainRoutingResult
```

Then append these helpers to the module:

```python
def build_visual_strategy_runtime_context(
    *,
    state: Mapping[str, Any],
    ad_format_spec: Mapping[str, Any],
) -> VisualStrategyRuntimeContext:
    placement = _string_or_none(ad_format_spec.get("ad_format") or state.get("selected_ad_format"))
    return VisualStrategyRuntimeContext(placement=placement)


def build_visual_strategy_context_for_shadow(
    *,
    state: Mapping[str, Any],
    marketing_context: MarketingContext,
    domain_result: DomainRoutingResult,
):
    product = _read_or_build_product_understanding(state, marketing_context)
    product_visual = _read_or_build_product_visual_context(state, product)
    business = build_business_environment_context_from_domain_routing(domain_result)
    campaign = CampaignContext(
        promotion_goal=_string_or_none(marketing_context.promotion_goal),
        evidence_refs=("state:context.promotion_goal",) if marketing_context.promotion_goal else (),
        confidence=0.7,
    )
    ad_format = AdFormatSpec(**(state.get("ad_format_spec") or {}))
    return build_creative_routing_context(
        domain=domain_result,
        business=business,
        product=product,
        product_visual=product_visual,
        campaign=campaign,
        ad_format=ad_format,
        reference_style_profile=state.get("reference_style_profile") if isinstance(state.get("reference_style_profile"), Mapping) else None,
        ambiguity_flags=domain_result.unresolved_questions,
        input_conflicts=(),
        resolver_version=VISUAL_ROUTING_METADATA_VERSION,
    )


def build_visual_semantic_intent_for_shadow(
    state: Mapping[str, Any],
    routing_context,
) -> VisualSemanticIntent:
    style = state.get("text_style_spec") if isinstance(state.get("text_style_spec"), Mapping) else {}
    selected_tone = _string_or_none(state.get("selected_tone") or style.get("profile"))
    desired_moods = (selected_tone,) if selected_tone else ()
    required_visual_facts = _dedupe_strings(
        [
            *routing_context.product_visual.product_tags,
            *routing_context.product_visual.visible_attributes,
            *routing_context.product_visual.explicit_preparation_methods,
        ]
    )
    prohibited = _dedupe_strings(routing_context.product_visual.prohibited_visual_inferences)
    return VisualSemanticIntent(
        subject_priority=0.8,
        environment_priority=0.5,
        text_priority=0.5,
        desired_moods=desired_moods,
        desired_materials=(),
        lighting_preferences=(),
        composition_preferences=(),
        required_visual_facts=required_visual_facts,
        prohibited_visual_elements=prohibited,
        copy_presence_mode="copy_reserved",
        confidence=min(routing_context.product_visual.confidence, routing_context.domain.confidence),
    )


def _read_or_build_product_understanding(
    state: Mapping[str, Any],
    marketing_context: MarketingContext,
) -> ProductUnderstanding:
    raw = state.get("product_understanding")
    if isinstance(raw, ProductUnderstanding):
        return raw
    if isinstance(raw, Mapping):
        return ProductUnderstanding(**raw)
    product_name = marketing_context.item_or_service or "advertising subject"
    return ProductUnderstanding(
        product_name=product_name,
        normalized_product_type=None,
        broad_category="other",
        category_path=["other"],
        product_name_evidence_ids=("state:context.item_or_service",),
        confidence_by_field={"product_name": 0.55},
        confidence=0.55,
        provider_metadata={"provider": "deterministic", "fallback_used": True},
    )


def _read_or_build_product_visual_context(
    state: Mapping[str, Any],
    product: ProductUnderstanding,
) -> ProductVisualContext:
    raw = state.get("product_visual_context")
    if isinstance(raw, ProductVisualContext):
        return raw
    if isinstance(raw, Mapping):
        data = dict(raw)
        data.setdefault("product_name", product.product_name)
        data.setdefault("category_path", product.category_path)
        data.setdefault("evidence_refs", product.product_name_evidence_ids or ("state:product_visual_context",))
        data.setdefault("confidence", product.confidence)
        return ProductVisualContext(**data)
    return product_visual_context_from_understanding(product)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _dedupe_strings(values) -> tuple[str, ...]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        output.append(normalized)
        seen.add(normalized)
    return tuple(output)
```

- [ ] **Step 4: Run helper tests**

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_visual_routing_integration.py -q
```

Expected:

```text
8 passed
```

- [ ] **Step 5: Commit deterministic input builders**

```bash
git add orchestrator/app/llm/visual_routing_integration.py orchestrator/tests/test_visual_routing_integration.py
git commit -m "feat(srv): build deterministic visual strategy shadow inputs"
```

---

## Task 4: Add Legacy Observation And Family Resolver

**Files:**

- Modify: `orchestrator/app/llm/visual_routing_integration.py`
- Modify: `orchestrator/tests/test_visual_routing_integration.py`

- [ ] **Step 1: Add tests for legacy observation and family resolver**

Append these tests to `orchestrator/tests/test_visual_routing_integration.py`:

```python
from orchestrator.app.llm.domain_routing import project_to_legacy_visual_route
from orchestrator.app.llm.visual_presets import select_visual_preset
from orchestrator.app.llm.visual_routing_integration import (
    CatalogVisualRouteFamilyResolver,
    ImagePromptLegacyVisualRouteResult,
    observe_legacy_visual_route,
)
from orchestrator.app.llm.visual_templates import select_visual_template


def test_a8_observes_legacy_visual_route_without_copy_tone_binding():
    domain = normalize_business_type("restaurant_bbq")
    projection = project_to_legacy_visual_route(domain, product_tags={"grilled_meat"}, explicit_scene_tags=set())
    template = select_visual_template("restaurant_bbq", "instagram_feed", "premium")
    preset = select_visual_preset("restaurant_bbq")
    legacy_result = ImagePromptLegacyVisualRouteResult(
        legacy_projection=projection,
        template_id=template.template_id,
        preset_id=preset["preset_id"],
        route_family_id="restaurant_bbq",
    )

    observation = observe_legacy_visual_route(legacy_result)

    assert observation.legacy_route_key.value == "restaurant_bbq"
    assert observation.template_id == "restaurant_bbq_warm_grill"
    assert observation.preset_id == "restaurant_bbq_warm_grill"
    assert observation.copy_tone_profile_id is None
    assert observation.route_family_id == "restaurant_bbq"
    assert observation.route_version == "1.0"


def test_a8_catalog_family_resolver_matches_known_legacy_route_resources():
    resolver = CatalogVisualRouteFamilyResolver()

    assert resolver.resolve_family("restaurant_bbq_warm_grill", "restaurant_bbq_warm_grill") == "restaurant_bbq"
    assert resolver.resolve_family("restaurant_generic_clean", "restaurant_generic_clean") == "restaurant"
    assert resolver.resolve_family("generic_clean_ad_background", "generic_clean_ad_background") == "generic"


def test_a8_catalog_family_resolver_returns_none_for_mixed_resource_pair():
    resolver = CatalogVisualRouteFamilyResolver()

    assert resolver.resolve_family("restaurant_bbq_warm_grill", "restaurant_generic_clean") is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_visual_routing_integration.py -q
```

Expected:

```text
FAILED ... ImportError: cannot import name 'ImagePromptLegacyVisualRouteResult'
```

- [ ] **Step 3: Implement observation and family resolver**

Add these imports to `orchestrator/app/llm/visual_routing_integration.py`:

```python
from dataclasses import dataclass

from orchestrator.app.llm.domain_routing import LegacyRoutingProjection
from orchestrator.app.llm.visual_presets import PRESET_ID_BY_BUSINESS_TYPE
from orchestrator.app.llm.visual_templates import get_visual_templates
from orchestrator.app.schemas.visual_routing_shadow import LegacyVisualRouteObservation
```

Then append this code:

```python
@dataclass(frozen=True)
class ImagePromptLegacyVisualRouteResult:
    legacy_projection: LegacyRoutingProjection
    template_id: str
    preset_id: str
    route_family_id: str | None


def observe_legacy_visual_route(
    result: ImagePromptLegacyVisualRouteResult,
) -> LegacyVisualRouteObservation:
    return LegacyVisualRouteObservation(
        legacy_route_key=result.legacy_projection.route_key,
        preset_id=result.preset_id,
        template_id=result.template_id,
        copy_tone_profile_id=None,
        route_family_id=result.route_family_id,
        route_version=result.legacy_projection.projection_version,
    )


class CatalogVisualRouteFamilyResolver:
    def __init__(self) -> None:
        self._preset_to_family = {
            preset_id: route_key
            for route_key, preset_id in PRESET_ID_BY_BUSINESS_TYPE.items()
        }
        self._template_to_family = {
            template.template_id: template.business_types[0]
            for template in get_visual_templates()
            if template.business_types and template.business_types[0] != "*"
        }

    def resolve_family(self, preset_id: str, template_id: str) -> str | None:
        preset_family = self._preset_to_family.get(preset_id)
        template_family = self._template_to_family.get(template_id)
        if preset_family is None or template_family is None:
            return None
        if preset_family != template_family:
            return None
        return preset_family
```

- [ ] **Step 4: Run helper tests**

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_visual_routing_integration.py -q
```

Expected:

```text
11 passed
```

- [ ] **Step 5: Commit observation helpers**

```bash
git add orchestrator/app/llm/visual_routing_integration.py orchestrator/tests/test_visual_routing_integration.py
git commit -m "feat(srv): observe legacy visual route for shadow comparison"
```

---

## Task 5: Run Shadow Resolver And Build Visual Routing Metadata

**Files:**

- Modify: `orchestrator/app/llm/visual_routing_integration.py`
- Modify: `orchestrator/tests/test_visual_routing_integration.py`

- [ ] **Step 1: Add a helper test for successful shadow metadata**

Append this test to `orchestrator/tests/test_visual_routing_integration.py`:

```python
from orchestrator.app.llm.visual_routing_integration import build_image_prompt_visual_routing_metadata


def test_a8_builds_successful_shadow_metadata_for_image_prompt_path():
    marketing_context = MarketingContext(
        business_type="restaurant_bbq",
        item_or_service="삼겹살",
        promotion_goal="new_menu",
        brand_tone="premium",
    )
    state = {
        "context": marketing_context.model_dump(),
        "ad_format_spec": {"ad_format": "instagram_feed", "width": 1024, "height": 1024, "aspect_ratio": "1:1"},
        "product_visual_context": {
            "product_name": "삼겹살",
            "product_tags": ["grilled_meat"],
            "explicit_preparation_methods": ["table_grilled"],
            "permissible_visual_inferences": ["charcoal"],
            "evidence_refs": ["test:product_visual"],
            "confidence": 0.93,
        },
    }
    domain = normalize_business_type("restaurant_bbq")
    projection = project_to_legacy_visual_route(domain, product_tags={"grilled_meat"}, explicit_scene_tags=set())
    template = select_visual_template("restaurant_bbq", "instagram_feed", "premium")
    preset = select_visual_preset("restaurant_bbq")

    metadata = build_image_prompt_visual_routing_metadata(
        state=state,
        marketing_context=marketing_context,
        domain_result=domain,
        legacy_projection=projection,
        visual_template=template,
        preset=preset,
        ad_format_spec=state["ad_format_spec"],
        route_family_id="restaurant_bbq",
    )

    assert metadata["routing_mode"] == "shadow"
    assert metadata["active_source"] == "legacy"
    assert metadata["trace_available"] is True
    assert metadata["trace"]["routing_mode"] == "shadow"
    assert metadata["trace"]["legacy_observation"]["legacy_route_key"] == "restaurant_bbq"
    assert metadata["trace"]["canonical_decision"]["strategy_id"] == "restaurant_bbq_warm_grill"
    assert metadata["trace"]["route_disagreement"]["new_strategy_id"] == "restaurant_bbq_warm_grill"
```

- [ ] **Step 2: Add a helper test for legacy mode metadata**

Append this test:

```python
def test_a8_legacy_mode_skips_canonical_resolver():
    marketing_context = MarketingContext(
        business_type="cafe",
        item_or_service="라떼",
        promotion_goal="new_menu",
    )
    state = {
        "context": marketing_context.model_dump(),
        "render_options": {"visual_routing_mode": "legacy"},
        "ad_format_spec": {"ad_format": "instagram_feed", "width": 1024, "height": 1024, "aspect_ratio": "1:1"},
    }
    domain = normalize_business_type("cafe")
    projection = project_to_legacy_visual_route(domain, product_tags=set(), explicit_scene_tags=set())
    template = select_visual_template("cafe", "instagram_feed", "premium")
    preset = select_visual_preset("cafe")

    metadata = build_image_prompt_visual_routing_metadata(
        state=state,
        marketing_context=marketing_context,
        domain_result=domain,
        legacy_projection=projection,
        visual_template=template,
        preset=preset,
        ad_format_spec=state["ad_format_spec"],
        route_family_id="cafe",
    )

    assert metadata["routing_mode"] == "legacy"
    assert metadata["active_source"] == "legacy"
    assert metadata["trace_available"] is True
    assert metadata["trace"]["routing_mode"] == "legacy"
    assert "canonical_decision" not in metadata["trace"]
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_visual_routing_integration.py -q
```

Expected:

```text
FAILED ... ImportError: cannot import name 'build_image_prompt_visual_routing_metadata'
```

- [ ] **Step 4: Implement the metadata builder**

Add these imports to `orchestrator/app/llm/visual_routing_integration.py`:

```python
from orchestrator.app.llm.visual_routing_shadow import execute_visual_routing_mode
from orchestrator.app.llm.visual_routing_trace import build_visual_routing_trace
from orchestrator.app.llm.visual_strategy_profiles import build_default_visual_strategy_registry
from orchestrator.app.llm.visual_strategy_resolver import resolve_visual_strategy
```

Then append this function:

```python
def build_image_prompt_visual_routing_metadata(
    *,
    state: Mapping[str, Any],
    marketing_context: MarketingContext,
    domain_result: DomainRoutingResult,
    legacy_projection: LegacyRoutingProjection,
    visual_template: Any,
    preset: Mapping[str, Any],
    ad_format_spec: Mapping[str, Any],
    route_family_id: str | None,
) -> dict[str, Any]:
    mode = resolve_visual_routing_mode(state)
    legacy_result = ImagePromptLegacyVisualRouteResult(
        legacy_projection=legacy_projection,
        template_id=visual_template.template_id,
        preset_id=str(preset["preset_id"]),
        route_family_id=route_family_id,
    )
    try:
        routing_context = build_visual_strategy_context_for_shadow(
            state=state,
            marketing_context=marketing_context,
            domain_result=domain_result,
        )
        runtime_context = build_visual_strategy_runtime_context(
            state=state,
            ad_format_spec=ad_format_spec,
        )
        intent = build_visual_semantic_intent_for_shadow(state, routing_context)
        registry = build_default_visual_strategy_registry()
        execution = execute_visual_routing_mode(
            mode,
            legacy_runner=lambda: legacy_result,
            legacy_observer=observe_legacy_visual_route,
            canonical_runner=lambda: resolve_visual_strategy(
                routing_context,
                intent,
                registry,
                runtime=runtime_context,
            ),
            family_resolver=CatalogVisualRouteFamilyResolver(),
        )
        legacy_observation = observe_legacy_visual_route(legacy_result)
        trace = build_visual_routing_trace(
            execution=execution,
            context=routing_context,
            raw_business_type=domain_result.raw_business_type,
            runtime_context=runtime_context if execution.canonical_decision is not None or mode == RoutingMode.SHADOW else None,
            placement=runtime_context.placement,
            legacy_observation=legacy_observation,
            additional_evidence_refs=("image_prompt_planner:visual_routing_shadow",),
        )
        return {
            "metadata_version": VISUAL_ROUTING_METADATA_VERSION,
            "routing_mode": mode.value,
            "active_source": RoutingSource.LEGACY.value,
            "trace_available": True,
            "trace": trace.model_dump(mode="json"),
        }
    except Exception as exc:
        return {
            "metadata_version": VISUAL_ROUTING_METADATA_VERSION,
            **build_fail_open_visual_routing_metadata(
                mode=mode,
                exception=exc,
                stage="visual_routing_shadow",
            ),
        }
```

- [ ] **Step 5: Run helper tests**

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_visual_routing_integration.py -q
```

Expected:

```text
13 passed
```

- [ ] **Step 6: Commit shadow metadata builder**

```bash
git add orchestrator/app/llm/visual_routing_integration.py orchestrator/tests/test_visual_routing_integration.py
git commit -m "feat(srv): build image prompt visual routing shadow metadata"
```

---

## Task 6: Wire Metadata Into Image Prompt Planner

**Files:**

- Modify: `orchestrator/app/llm/nodes/image_prompt_planner.py`
- Modify: `orchestrator/tests/test_image_prompt_planner.py`

- [ ] **Step 1: Import the integration helper**

Add this import to `orchestrator/app/llm/nodes/image_prompt_planner.py`:

```python
from orchestrator.app.llm.visual_routing_integration import build_image_prompt_visual_routing_metadata
```

- [ ] **Step 2: Build visual routing metadata after legacy preset selection**

After this existing line:

```python
preset_id = preset["preset_id"]
```

Add:

```python
    visual_routing_metadata = build_image_prompt_visual_routing_metadata(
        state=state,
        marketing_context=context,
        domain_result=domain_result,
        legacy_projection=legacy_projection,
        visual_template=visual_template,
        preset=preset,
        ad_format_spec=ad_format_spec,
        route_family_id=resolved_visual_route_key,
    )
```

- [ ] **Step 3: Add metadata to ImagePromptSpec**

Inside the `ImagePromptSpec(... metadata={...})` dict, after:

```python
"legacy_routing_projection": legacy_projection.model_dump(mode="json"),
```

Add:

```python
            "visual_routing": visual_routing_metadata,
```

- [ ] **Step 4: Copy metadata into legacy ImagePrompt**

In `build_legacy_image_prompt()`, add `"visual_routing"` to the `v3_meta` key list:

```python
        "visual_routing",
```

- [ ] **Step 5: Run A-8 image prompt tests**

```bash
PYTHONPATH=. uv run pytest \
  orchestrator/tests/test_image_prompt_planner.py::test_a8_shadow_metadata_preserves_legacy_production_route \
  orchestrator/tests/test_image_prompt_planner.py::test_a8_shadow_metadata_does_not_rebind_copy_tone_from_visual_route \
  orchestrator/tests/test_image_prompt_planner.py::test_a8_shadow_metadata_fail_open_when_canonical_resolution_fails \
  -q
```

Expected:

```text
3 passed
```

- [ ] **Step 6: Run full image prompt planner tests**

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_image_prompt_planner.py -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 7: Commit planner wiring**

```bash
git add orchestrator/app/llm/nodes/image_prompt_planner.py orchestrator/tests/test_image_prompt_planner.py
git commit -m "feat(srv): wire visual routing shadow metadata into image prompts"
```

---

## Task 7: Add Regression Guards For No Production Route Change

**Files:**

- Modify: `orchestrator/tests/test_image_prompt_planner.py`

- [ ] **Step 1: Add a route matrix test that ignores the new metadata**

Append this test to `orchestrator/tests/test_image_prompt_planner.py`:

```python
def test_a8_shadow_wiring_keeps_existing_legacy_route_matrix():
    cases = [
        ("cafe", "cafe", "cafe_dessert_soft_premium", "cafe_dessert_soft_premium"),
        ("restaurant", "restaurant", "restaurant_generic_clean", "restaurant_generic_clean"),
        ("restaurant_bbq", "restaurant", "restaurant_generic_clean", "restaurant_generic_clean"),
        ("beauty_salon", "generic", "generic_clean_ad_background", "generic_clean_ad_background"),
        ("beauty_skincare", "beauty_skincare", "beauty_skincare_clean_premium", "beauty_salon_clean_pastel"),
        ("retail", "generic", "generic_clean_ad_background", "generic_clean_ad_background"),
        ("education", "generic", "generic_clean_ad_background", "generic_clean_ad_background"),
        ("service", "generic", "generic_clean_ad_background", "generic_clean_ad_background"),
    ]

    for business_type, route_key, preset_id, template_id in cases:
        spec = build_image_prompt_spec_with_critic(_state(business_type))
        metadata = spec.metadata

        _assert_single_resolved_visual_key(
            metadata,
            route_key=route_key,
            preset_id=preset_id,
            template_id=template_id,
        )
        assert metadata["visual_routing"]["active_source"] == "legacy"
```

- [ ] **Step 2: Add a legacy ImagePrompt metadata propagation test**

Append this test:

```python
def test_a8_legacy_image_prompt_carries_visual_routing_metadata():
    from orchestrator.app.llm.nodes.image_prompt_planner import build_legacy_image_prompt

    spec = build_image_prompt_spec_with_critic(_state("cafe"))
    image_prompt = build_legacy_image_prompt(_state("cafe"), spec)

    assert image_prompt.metadata["resolved_visual_route_key"] == "cafe"
    assert image_prompt.metadata["visual_routing"]["routing_mode"] == "shadow"
    assert image_prompt.metadata["visual_routing"]["active_source"] == "legacy"
```

- [ ] **Step 3: Run regression tests**

```bash
PYTHONPATH=. uv run pytest \
  orchestrator/tests/test_image_prompt_planner.py::test_a8_shadow_wiring_keeps_existing_legacy_route_matrix \
  orchestrator/tests/test_image_prompt_planner.py::test_a8_legacy_image_prompt_carries_visual_routing_metadata \
  -q
```

Expected:

```text
2 passed
```

- [ ] **Step 4: Run the focused image prompt planner suite**

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_image_prompt_planner.py -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 5: Commit regression guards**

```bash
git add orchestrator/tests/test_image_prompt_planner.py
git commit -m "test(srv): guard a8 shadow wiring from production route changes"
```

---

## Task 8: Validate A-8 With Existing Routing Suites

**Files:**

- No source edits unless validation reveals a defect in the A-8 helper.

- [ ] **Step 1: Run focused A-8 tests**

```bash
PYTHONPATH=. uv run pytest \
  orchestrator/tests/test_visual_routing_integration.py \
  orchestrator/tests/test_image_prompt_planner.py \
  -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 2: Run existing domain and visual routing suites**

```bash
PYTHONPATH=. uv run pytest \
  orchestrator/tests/test_domain_routing.py \
  orchestrator/tests/test_domain_routing_contract.py \
  orchestrator/tests/test_visual_routing_shadow.py \
  orchestrator/tests/test_visual_routing_trace.py \
  orchestrator/tests/test_visual_strategy_resolver.py \
  orchestrator/tests/test_visual_strategy_integrity.py \
  orchestrator/tests/test_visual_strategy_registry.py \
  -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 3: Run image prompt integration and copy regression tests**

```bash
PYTHONPATH=. uv run pytest \
  orchestrator/tests/test_image_prompt_v3_integration.py \
  orchestrator/tests/test_image_prompt_v3_sceneplan.py \
  orchestrator/tests/test_visual_templates.py \
  orchestrator/tests/test_copywriting.py \
  orchestrator/tests/test_tone_binding_node.py \
  -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 4: Run stale shortcut guard**

```bash
rg -n "select_visual_template\\(context\\.business_type|select_visual_preset\\(context\\.business_type|build_scene_plan\\([^\\n]*business_type=context\\.business_type|restaurant_bbq_v1.*legacy_observation|copy_tone_profile_id.*restaurant_bbq_v1" orchestrator/app/llm orchestrator/tests; test $? -eq 1
```

Expected:

```text
no output
```

- [ ] **Step 5: Run full orchestrator tests**

```bash
PYTHONPATH=. uv run pytest orchestrator/tests -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 6: Run diff hygiene**

```bash
git diff --check
```

Expected:

```text
no output
```

- [ ] **Step 7: Commit validation-only fixes if needed**

If Step 1 through Step 6 already pass without source edits, skip this commit.

If a validation failure requires a source fix, commit only the A-8 files:

```bash
git add orchestrator/app/llm/visual_routing_integration.py orchestrator/app/llm/nodes/image_prompt_planner.py orchestrator/tests/test_visual_routing_integration.py orchestrator/tests/test_image_prompt_planner.py
git commit -m "fix(srv): harden a8 visual routing shadow wiring"
```

---

## Task 9: Prepare PR

**Files:**

- No source edits.

- [ ] **Step 1: Confirm branch and diff**

```bash
git status -sb
git log --oneline origin/develop..HEAD
git diff --stat origin/develop..HEAD
```

Expected:

```text
branch is feat/srv/domain-routing-a8-shadow-wiring
working tree is clean
diff includes visual_routing_integration.py, image_prompt_planner.py, and A-8 tests
```

- [ ] **Step 2: Push branch**

```bash
git push -u origin feat/srv/domain-routing-a8-shadow-wiring
```

Expected:

```text
branch set up to track origin/feat/srv/domain-routing-a8-shadow-wiring
```

- [ ] **Step 3: Open draft PR to develop**

Use this title:

```text
[feat/srv] A-8 visual routing shadow wiring 추가
```

Use this PR body:

```markdown
## 작업 내용
A-8 visual routing shadow wiring을 추가했습니다. 기존 legacy route가 production template/preset/scene/prompt를 계속 만들고, B의 canonical visual strategy resolver는 병렬 shadow 실행으로만 돌려 legacy/canonical 차이를 metadata에 기록합니다.

핵심 변경은 아래와 같습니다.

- `image_prompt_planner` production output은 legacy route 그대로 유지
- canonical resolver를 fail-open shadow mode로 실행
- `ImagePromptSpec.metadata.visual_routing`에 sanitized trace/comparison 저장
- legacy `ImagePrompt.metadata.visual_routing`에도 동일 metadata 전파
- `product_visual_context`가 없을 때 `product_understanding` 기반 deterministic fallback 사용
- copy tone은 A-8에서 전환하지 않고 legacy observation에 binding하지 않음
- route family resolver로 legacy/canonical family comparison 관측성 보강

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
- [ ] Docker build 로컬 확인
- [ ] GitHub Actions `docker-build` 통과 확인

검증 내역:

- `PYTHONPATH=. uv run pytest orchestrator/tests/test_visual_routing_integration.py orchestrator/tests/test_image_prompt_planner.py -q`
- `PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing.py orchestrator/tests/test_domain_routing_contract.py orchestrator/tests/test_visual_routing_shadow.py orchestrator/tests/test_visual_routing_trace.py orchestrator/tests/test_visual_strategy_resolver.py orchestrator/tests/test_visual_strategy_integrity.py orchestrator/tests/test_visual_strategy_registry.py -q`
- `PYTHONPATH=. uv run pytest orchestrator/tests/test_image_prompt_v3_integration.py orchestrator/tests/test_image_prompt_v3_sceneplan.py orchestrator/tests/test_visual_templates.py orchestrator/tests/test_copywriting.py orchestrator/tests/test_tone_binding_node.py -q`
- `PYTHONPATH=. uv run pytest orchestrator/tests -q`
- `git diff --check`

## API 스펙 변경 여부
- [x] bff ↔ fe 인터페이스 변경 없음
- [ ] 변경 있음 → Zod 스키마 + FE api-client.ts 동시 업데이트 완료

## 안전 경계
- 실제 output source는 계속 legacy입니다.
- canonical resolver 실패는 production 실패가 아닙니다.
- copy tone은 이번 PR에서 canonical decision으로 전환하지 않습니다.
- canonical cutover는 shadow mismatch 검토 이후 별도 PR에서 진행합니다.
```

- [ ] **Step 4: Confirm PR checks**

```bash
gh pr checks --watch=false
```

Expected:

```text
checks are pending or passing
```

---

## Self-Review Checklist

- [x] A-8 scope is shadow-only and forbids production output changes.
- [x] Fail-open behavior is specified for canonical resolver, comparison, and trace failures.
- [x] `runtime_context` is included when building visual routing traces.
- [x] Missing `product_visual_context` is handled through deterministic fallback.
- [x] Copy tone rebinding is explicitly blocked.
- [x] Family resolver is included to reduce unavailable family comparisons.
- [x] Tests prove legacy route matrix remains unchanged.
- [x] No canonical cutover work is included.
