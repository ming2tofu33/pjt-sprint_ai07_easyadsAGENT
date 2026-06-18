# Domain Routing A-6 Copy Tone Neutral Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent copy generation from reintroducing legacy business/scene shortcuts, so ambiguous restaurant/BBQ and beauty inputs use neutral copy behavior until a product/scene/campaign-aware resolver explicitly selects a specialized strategy.

**Architecture:** A-6 adds a small copy-route normalization boundary in `copy_tone_policy.py` and makes copy policy, deterministic copy fallback, and grounded copy prompt descriptions consume that boundary. Deprecated specialized inventory can remain present for registry compatibility, but raw `business_type` strings such as `restaurant_bbq`, `bbq`, `korean_food`, `beauty`, `beauty_salon`, and `salon` must not directly select BBQ or skincare copy behavior.

**Tech Stack:** Python 3.11+, Pydantic models in `orchestrator/app/schemas`, pytest, uv, existing `orchestrator/app/llm` copy pipeline modules.

---

## Scope And Base

Execute this plan only after A-5 single resolved visual route key work is available on the implementation branch. The expected base is `develop` after PR #214, or a feature branch stacked on top of `feat/srv/domain-routing-a5-single-resolved-key`.

A-6 is not a visual routing change. Do not edit `visual_presets.py`, `visual_templates.py`, `scene_planner.py`, or `image_prompt_planner.py` unless a merge conflict from the A-5 base requires mechanical reconciliation.

The main rule from `docs/two track.md` is:

```text
restaurant_bbq is not a canonical business domain.
restaurant_bbq is a deprecated legacy visual route key only.
Copy tone must not choose BBQ or skincare behavior from raw business_type shortcuts.
Until business/product/scene/campaign tone selection is split, ambiguous values use neutral fallback.
```

## File Structure

- Modify: `orchestrator/app/llm/copy_tone_policy.py`
  - Owns deterministic copy policy lookup.
  - Add `resolve_copy_route_key()` as the single boundary for raw copy route strings.
  - Keep deprecated policy inventory available for registry consumers, but block raw legacy keys from selecting it.

- Modify: `orchestrator/app/llm/copy_fallbacks.py`
  - Owns deterministic fallback copy theme selection.
  - Make `resolve_copy_theme()` consume `resolve_copy_route_key()`.
  - Remove raw restaurant/BBQ and ambiguous beauty aliases from fallback themes.

- Modify: `orchestrator/app/llm/copy_prompts.py`
  - Owns public-safe business category text in copy generation prompts.
  - Make `_business_description()` consume `resolve_copy_route_key()` so raw `restaurant_bbq` does not become "숯불구이 음식점" in the prompt.

- Modify: `orchestrator/tests/test_domain_routing_contract.py`
  - Owns cross-cutting domain-routing contract regressions.
  - Add A-6 contract tests for neutral copy route behavior.
  - Replace old expectations that explicit raw BBQ aliases route to BBQ copy policy.

- Modify: `orchestrator/tests/test_copywriting.py`
  - Owns consolidated copywriting and copy policy tests.
  - Add deterministic fallback and prompt regression tests.
  - Replace old direct `get_copy_tone_policy("restaurant_bbq")` reservation expectation with inventory-only semantics.

- Optional Read Only: `orchestrator/tests/test_visual_strategy_registry.py`
  - Run this suite to confirm retained `POLICIES` inventory still satisfies B-track visual strategy registry checks.

## Definitions

Use these route groups exactly in the implementation:

```python
COPY_NEUTRAL_FALLBACK_KEYS = frozenset(
    {
        "restaurant",
        "restaurant_bbq",
        "bbq",
        "meat_restaurant",
        "korean_food",
        "beauty",
        "beauty_salon",
        "salon",
    }
)

COPY_ROUTE_ALIASES = {
    "dessert": "cafe",
    "dessert_macaron": "macaron",
    "bakery": "cafe",
    "skincare": "beauty_skincare",
    "hair_salon": "beauty_hair",
    "hair": "beauty_hair",
    "nail": "beauty_nail",
    "spa": "beauty_spa",
}
```

Expected route behavior:

```text
restaurant -> generic
restaurant_bbq -> generic
bbq -> generic
meat_restaurant -> generic
korean_food -> generic
beauty -> generic
beauty_salon -> generic
salon -> generic
beauty_skincare -> beauty_skincare
skincare -> beauty_skincare
beauty_hair -> beauty_hair
hair -> beauty_hair
beauty_nail -> beauty_nail
nail -> beauty_nail
beauty_spa -> beauty_spa
spa -> beauty_spa
cafe -> cafe
dessert -> cafe
bakery -> cafe
macaron -> macaron
unknown -> generic
```

---

### Task 1: Add A-6 Copy Route Contract Tests

**Files:**
- Modify: `orchestrator/tests/test_domain_routing_contract.py`
- Test: `orchestrator/tests/test_domain_routing_contract.py`

- [ ] **Step 1: Update imports**

Add `resolve_copy_route_key` to the existing `copy_tone_policy` import.

```python
from orchestrator.app.llm.copy_tone_policy import get_copy_tone_policy, resolve_copy_route_key
```

- [ ] **Step 2: Replace the old explicit BBQ alias expectation**

Find the old test named `test_explicit_bbq_copy_still_routes_to_bbq_policy` and replace that test block with the following tests.

```python
@pytest.mark.parametrize(
    "business_type",
    ["restaurant", "restaurant_bbq", "bbq", "meat_restaurant", "korean_food"],
)
def test_a6_restaurant_and_bbq_like_copy_inputs_use_neutral_policy(business_type):
    assert resolve_copy_route_key(business_type) == "generic"

    policy = get_copy_tone_policy(business_type)

    assert policy["policy_id"] == "generic_v1"
    assert policy["business_type"] == "generic"


@pytest.mark.parametrize("business_type", ["beauty", "beauty_salon", "salon"])
def test_a6_ambiguous_beauty_copy_inputs_use_neutral_policy(business_type):
    assert resolve_copy_route_key(business_type) == "generic"

    policy = get_copy_tone_policy(business_type)

    assert policy["policy_id"] == "generic_v1"
    assert policy["business_type"] == "generic"


@pytest.mark.parametrize(
    ("business_type", "route_key", "policy_id"),
    [
        ("beauty_skincare", "beauty_skincare", "beauty_skincare_v1"),
        ("skincare", "beauty_skincare", "beauty_skincare_v1"),
        ("beauty_hair", "beauty_hair", "beauty_hair_v1"),
        ("hair", "beauty_hair", "beauty_hair_v1"),
        ("beauty_nail", "beauty_nail", "beauty_nail_v1"),
        ("nail", "beauty_nail", "beauty_nail_v1"),
        ("beauty_spa", "beauty_spa", "beauty_spa_v1"),
        ("spa", "beauty_spa", "beauty_spa_v1"),
    ],
)
def test_a6_exact_beauty_subtype_copy_inputs_still_use_specialized_policy(
    business_type,
    route_key,
    policy_id,
):
    assert resolve_copy_route_key(business_type) == route_key

    policy = get_copy_tone_policy(business_type)

    assert policy["policy_id"] == policy_id
```

- [ ] **Step 3: Run the new contract tests and verify they fail**

Run:

```bash
PYTHONPATH=. uv run pytest \
  orchestrator/tests/test_domain_routing_contract.py::test_a6_restaurant_and_bbq_like_copy_inputs_use_neutral_policy \
  orchestrator/tests/test_domain_routing_contract.py::test_a6_ambiguous_beauty_copy_inputs_use_neutral_policy \
  orchestrator/tests/test_domain_routing_contract.py::test_a6_exact_beauty_subtype_copy_inputs_still_use_specialized_policy \
  -q
```

Expected: FAIL because `resolve_copy_route_key` is not exported yet, or because old aliases still route to specialized policies.

- [ ] **Step 4: Commit the failing tests**

```bash
git add orchestrator/tests/test_domain_routing_contract.py
git commit -m "test(srv): pin neutral copy route contract"
```

---

### Task 2: Implement Copy Route Normalization In Copy Tone Policy

**Files:**
- Modify: `orchestrator/app/llm/copy_tone_policy.py`
- Test: `orchestrator/tests/test_domain_routing_contract.py`

- [ ] **Step 1: Replace `ALIASES` with neutral-aware route tables**

In `orchestrator/app/llm/copy_tone_policy.py`, replace the existing `ALIASES = { ... }` block with this block.

```python
COPY_NEUTRAL_FALLBACK_KEYS = frozenset(
    {
        # A-6: raw business strings must not select BBQ copy behavior.
        # BBQ copy requires a future product/scene/campaign-aware strategy resolver.
        "restaurant",
        "restaurant_bbq",
        "bbq",
        "meat_restaurant",
        "korean_food",
        # Ambiguous beauty values must not silently become skincare copy.
        "beauty",
        "beauty_salon",
        "salon",
    }
)

COPY_ROUTE_ALIASES = {
    "dessert": "cafe",
    "dessert_macaron": "macaron",
    "macaron": "macaron",
    "bakery": "cafe",
    "skincare": "beauty_skincare",
    "hair_salon": "beauty_hair",
    "hair": "beauty_hair",
    "nail": "beauty_nail",
    "spa": "beauty_spa",
}
```

- [ ] **Step 2: Add `resolve_copy_route_key()`**

Add this function immediately above `get_copy_tone_policy()`.

```python
def resolve_copy_route_key(business_type: str | None) -> str:
    """Resolve raw copy business strings without legacy scene/subtype shortcuts."""
    key = (business_type or "generic").strip().lower()
    if not key:
        return "generic"
    if key in COPY_NEUTRAL_FALLBACK_KEYS:
        return "generic"
    return COPY_ROUTE_ALIASES.get(key, key)
```

- [ ] **Step 3: Update `get_copy_tone_policy()` to use the resolver**

Replace the existing function body with this exact implementation.

```python
def get_copy_tone_policy(business_type: str | None) -> dict[str, Any]:
    key = resolve_copy_route_key(business_type)
    return deepcopy(POLICIES.get(key, POLICIES["generic"]))
```

- [ ] **Step 4: Run Task 1 contract tests and verify they pass**

Run:

```bash
PYTHONPATH=. uv run pytest \
  orchestrator/tests/test_domain_routing_contract.py::test_a6_restaurant_and_bbq_like_copy_inputs_use_neutral_policy \
  orchestrator/tests/test_domain_routing_contract.py::test_a6_ambiguous_beauty_copy_inputs_use_neutral_policy \
  orchestrator/tests/test_domain_routing_contract.py::test_a6_exact_beauty_subtype_copy_inputs_still_use_specialized_policy \
  -q
```

Expected: PASS.

- [ ] **Step 5: Run the visual strategy registry guard**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_visual_strategy_registry.py -q
```

Expected: PASS. This confirms `POLICIES["restaurant_bbq"]` can remain as deprecated inventory without being selected by raw copy routing.

- [ ] **Step 6: Commit the resolver**

```bash
git add orchestrator/app/llm/copy_tone_policy.py orchestrator/tests/test_domain_routing_contract.py
git commit -m "feat(srv): neutralize raw copy route shortcuts"
```

---

### Task 3: Add Deterministic Fallback Copy Regression Tests

**Files:**
- Modify: `orchestrator/tests/test_copywriting.py`
- Test: `orchestrator/tests/test_copywriting.py`

- [ ] **Step 1: Update copy fallback imports**

Find the import block that imports from `orchestrator.app.llm.copy_fallbacks` and make sure it includes these names.

```python
from orchestrator.app.llm.copy_fallbacks import (
    THEMES,
    build_message_strategy,
    generate_fallback_candidates,
    resolve_copy_theme,
)
```

- [ ] **Step 2: Add neutral fallback tests near `test_copy_fallbacks_cover_at_least_ten_themes`**

Add these tests in the copy fallback section of `orchestrator/tests/test_copywriting.py`.

```python
BBQ_BIASED_COPY_TERMS = ("숯불", "불판", "회식", "구워", "구이", "한상")


@pytest.mark.parametrize("business_type", ["restaurant", "restaurant_bbq", "bbq", "meat_restaurant", "korean_food"])
def test_a6_restaurant_and_bbq_like_fallback_theme_is_neutral(business_type):
    theme = resolve_copy_theme(business_type)

    assert theme.key == "generic"


@pytest.mark.parametrize("business_type", ["restaurant", "restaurant_bbq", "bbq", "meat_restaurant", "korean_food"])
def test_a6_restaurant_and_bbq_like_fallback_copy_avoids_bbq_language(business_type):
    candidates = generate_fallback_candidates(
        MarketingContext(
            business_type=business_type,
            item_or_service="감자튀김",
            promotion_goal="brand_awareness",
        )
    )
    joined = " ".join(
        " ".join(filter(None, [candidate.headline, candidate.subcopy, candidate.cta]))
        for candidate in candidates
    )

    assert all(term not in joined for term in BBQ_BIASED_COPY_TERMS)


@pytest.mark.parametrize("business_type", ["beauty", "beauty_salon", "salon"])
def test_a6_ambiguous_beauty_fallback_theme_is_neutral(business_type):
    theme = resolve_copy_theme(business_type)

    assert theme.key == "generic"


@pytest.mark.parametrize(
    ("business_type", "expected_theme"),
    [
        ("beauty_skincare", "beauty_skincare"),
        ("skincare", "beauty_skincare"),
        ("beauty_hair", "beauty_hair"),
        ("hair", "beauty_hair"),
        ("beauty_nail", "beauty_nail"),
        ("nail", "beauty_nail"),
        ("beauty_spa", "beauty_spa"),
        ("spa", "beauty_spa"),
    ],
)
def test_a6_exact_beauty_subtype_fallback_theme_stays_specialized(business_type, expected_theme):
    theme = resolve_copy_theme(business_type)

    assert theme.key == expected_theme
```

- [ ] **Step 3: Replace old `test_restaurant_bbq_policy_uses_reservation_cta`**

Replace the old direct policy selection test with this inventory-only test.

```python
def test_a6_deprecated_bbq_policy_is_inventory_only_for_now():
    from orchestrator.app.llm.copy_tone_policy import POLICIES, get_copy_tone_policy, resolve_copy_route_key

    deprecated_policy = POLICIES["restaurant_bbq"]

    assert deprecated_policy["policy_id"] == "restaurant_bbq_v1"
    assert deprecated_policy["promotion_style"] == "reservation_visit"
    assert resolve_copy_route_key("restaurant_bbq") == "generic"
    assert get_copy_tone_policy("restaurant_bbq")["policy_id"] == "generic_v1"
```

- [ ] **Step 4: Run the fallback tests and verify they fail**

Run:

```bash
PYTHONPATH=. uv run pytest \
  orchestrator/tests/test_copywriting.py::test_a6_restaurant_and_bbq_like_fallback_theme_is_neutral \
  orchestrator/tests/test_copywriting.py::test_a6_restaurant_and_bbq_like_fallback_copy_avoids_bbq_language \
  orchestrator/tests/test_copywriting.py::test_a6_ambiguous_beauty_fallback_theme_is_neutral \
  orchestrator/tests/test_copywriting.py::test_a6_exact_beauty_subtype_fallback_theme_stays_specialized \
  orchestrator/tests/test_copywriting.py::test_a6_deprecated_bbq_policy_is_inventory_only_for_now \
  -q
```

Expected: FAIL because `resolve_copy_theme()` still routes raw restaurant/BBQ and ambiguous beauty strings through specialized fallback themes.

- [ ] **Step 5: Commit the failing fallback tests**

```bash
git add orchestrator/tests/test_copywriting.py
git commit -m "test(srv): pin neutral deterministic copy fallback"
```

---

### Task 4: Make Deterministic Copy Fallback Use The Copy Route Resolver

**Files:**
- Modify: `orchestrator/app/llm/copy_fallbacks.py`
- Test: `orchestrator/tests/test_copywriting.py`

- [ ] **Step 1: Import the route resolver**

Add this import near the top of `orchestrator/app/llm/copy_fallbacks.py`.

```python
from orchestrator.app.llm.copy_tone_policy import resolve_copy_route_key
```

- [ ] **Step 2: Remove raw shortcut aliases from risky themes**

Replace the `restaurant_bbq` and `beauty_skincare` theme declarations with these declarations. Keep the copy text itself unchanged so deprecated inventory stays available for a future explicit strategy resolver.

```python
    CopyTheme("restaurant_bbq", (), ("예약 문의하기", "지금 예약하기", "회식 문의하기"), "숯불향 가득한 한상", "회식은 역시 {item}", "{item} 예약 가능", "따뜻하게 구워 즐기는 프리미엄 메뉴", "모임과 회식에 어울리는 든든한 시간", "편한 저녁 자리를 미리 준비하세요", "appetizing reservation copy"),
    CopyTheme("beauty_skincare", ("beauty_skincare", "skincare"), ("상담 예약하기", "케어 문의하기", "예약 문의하기"), "맑은 피부 루틴", "깨끗하게 빛나는 시간", "맞춤 케어 상담", "차분한 프리미엄 스킨케어", "깨끗한 무드를 위한 케어 경험", "피부 컨디션을 상담해보세요", "clean trustworthy beauty copy"),
```

- [ ] **Step 3: Update `resolve_copy_theme()`**

Replace the existing function with this implementation.

```python
def resolve_copy_theme(business_type: str | None) -> CopyTheme:
    key = resolve_copy_route_key(business_type)
    for theme in THEMES:
        if key == theme.key or key in theme.aliases:
            return theme
    return THEMES[-1]
```

- [ ] **Step 4: Run Task 3 tests and verify they pass**

Run:

```bash
PYTHONPATH=. uv run pytest \
  orchestrator/tests/test_copywriting.py::test_a6_restaurant_and_bbq_like_fallback_theme_is_neutral \
  orchestrator/tests/test_copywriting.py::test_a6_restaurant_and_bbq_like_fallback_copy_avoids_bbq_language \
  orchestrator/tests/test_copywriting.py::test_a6_ambiguous_beauty_fallback_theme_is_neutral \
  orchestrator/tests/test_copywriting.py::test_a6_exact_beauty_subtype_fallback_theme_stays_specialized \
  orchestrator/tests/test_copywriting.py::test_a6_deprecated_bbq_policy_is_inventory_only_for_now \
  -q
```

Expected: PASS.

- [ ] **Step 5: Run copy fallback matrix guard**

Run:

```bash
PYTHONPATH=. uv run pytest \
  orchestrator/tests/test_copywriting.py::test_copy_fallbacks_cover_at_least_ten_themes \
  orchestrator/tests/test_copywriting.py::test_fallback_candidates_use_three_distinct_angles \
  orchestrator/tests/test_copywriting.py::test_fallback_matrix_has_no_generic_meta_phrases_for_core_cases \
  -q
```

Expected: PASS. If `test_fallback_matrix_has_no_generic_meta_phrases_for_core_cases` still constructs `MarketingContext(business_type="restaurant_bbq", ...)`, it should pass through the neutral route and remain grounded by `item_or_service`.

- [ ] **Step 6: Commit fallback implementation**

```bash
git add orchestrator/app/llm/copy_fallbacks.py orchestrator/tests/test_copywriting.py
git commit -m "fix(srv): route fallback copy through neutral copy key"
```

---

### Task 5: Neutralize Copy Prompt Business Descriptions

**Files:**
- Modify: `orchestrator/app/llm/copy_prompts.py`
- Modify: `orchestrator/tests/test_copywriting.py`
- Test: `orchestrator/tests/test_copywriting.py`

- [ ] **Step 1: Add prompt regression tests**

Add these tests in the copy prompt or copy quality section of `orchestrator/tests/test_copywriting.py`, near `test_actual_prompt_contains_context_strategy_and_wrong_domain_examples`.

```python
def test_a6_copy_prompt_does_not_describe_raw_bbq_value_as_grill_business():
    context = MarketingContext(
        business_type="restaurant_bbq",
        item_or_service="감자튀김",
        promotion_goal="brand_awareness",
    )
    strategy = build_message_strategy(context)
    intent = resolve_copy_visual_intent(context)
    prompt = build_copy_generation_v2_prompt(context=context, strategy=strategy, visual_intent=intent)

    assert "숯불구이 음식점" not in prompt
    assert "'business_category': 'local business'" in prompt


def test_a6_copy_prompt_does_not_describe_ambiguous_beauty_as_skincare():
    context = MarketingContext(
        business_type="beauty_salon",
        item_or_service="첫 방문 혜택",
        promotion_goal="brand_awareness",
    )
    strategy = build_message_strategy(context)
    intent = resolve_copy_visual_intent(context)
    prompt = build_copy_generation_v2_prompt(context=context, strategy=strategy, visual_intent=intent)

    assert "스킨케어" not in prompt
    assert "'business_category': 'local business'" in prompt
```

- [ ] **Step 2: Run the prompt tests and verify they fail**

Run:

```bash
PYTHONPATH=. uv run pytest \
  orchestrator/tests/test_copywriting.py::test_a6_copy_prompt_does_not_describe_raw_bbq_value_as_grill_business \
  orchestrator/tests/test_copywriting.py::test_a6_copy_prompt_does_not_describe_ambiguous_beauty_as_skincare \
  -q
```

Expected: FAIL because `_business_description("restaurant_bbq")` still returns "숯불구이 음식점".

- [ ] **Step 3: Import the route resolver in `copy_prompts.py`**

Add this import below the existing imports.

```python
from orchestrator.app.llm.copy_tone_policy import resolve_copy_route_key
```

- [ ] **Step 4: Replace `_business_description()`**

Replace the existing `_business_description()` with this implementation.

```python
def _business_description(business_type: str | None) -> str:
    route_key = resolve_copy_route_key(business_type)
    if route_key == "generic":
        return "local business"
    return {
        "macaron": "마카롱 디저트",
        "cafe": "카페",
        "beauty_skincare": "스킨케어 뷰티",
        "beauty_hair": "헤어 뷰티",
        "beauty_nail": "네일 뷰티",
        "beauty_spa": "스파 뷰티",
        "retail": "리테일 스토어",
    }.get(route_key, route_key)
```

- [ ] **Step 5: Run the prompt tests and verify they pass**

Run:

```bash
PYTHONPATH=. uv run pytest \
  orchestrator/tests/test_copywriting.py::test_a6_copy_prompt_does_not_describe_raw_bbq_value_as_grill_business \
  orchestrator/tests/test_copywriting.py::test_a6_copy_prompt_does_not_describe_ambiguous_beauty_as_skincare \
  -q
```

Expected: PASS.

- [ ] **Step 6: Commit prompt normalization**

```bash
git add orchestrator/app/llm/copy_prompts.py orchestrator/tests/test_copywriting.py
git commit -m "fix(srv): neutralize copy prompt business descriptions"
```

---

### Task 6: Update Existing Copy Expectations That Still Assume Direct BBQ Selection

**Files:**
- Modify: `orchestrator/tests/test_copywriting.py`
- Modify: `orchestrator/tests/test_domain_routing_contract.py`
- Test: `orchestrator/tests/test_copywriting.py`
- Test: `orchestrator/tests/test_domain_routing_contract.py`

- [ ] **Step 1: Search for stale A-6 expectations**

Run:

```bash
rg -n "restaurant_bbq_policy_uses_reservation_cta|explicit_bbq_copy_still_routes|restaurant_bbq.*policy|bbq.*policy|beauty_salon.*skincare|salon.*skincare" orchestrator/tests
```

Expected: Any remaining results must either assert neutral fallback or inspect deprecated inventory directly through `POLICIES["restaurant_bbq"]`.

- [ ] **Step 2: Replace stale direct policy assertions**

If any test still asserts `get_copy_tone_policy("restaurant_bbq")["business_type"] == "restaurant_bbq"`, replace the assertion block with this pattern.

```python
from orchestrator.app.llm.copy_tone_policy import POLICIES, get_copy_tone_policy, resolve_copy_route_key

assert POLICIES["restaurant_bbq"]["business_type"] == "restaurant_bbq"
assert resolve_copy_route_key("restaurant_bbq") == "generic"
assert get_copy_tone_policy("restaurant_bbq")["business_type"] == "generic"
```

- [ ] **Step 3: Replace stale ambiguous beauty assertions**

If any test still asserts `get_copy_tone_policy("beauty_salon")["business_type"] == "beauty_skincare"` or `get_copy_tone_policy("salon")["business_type"] == "beauty_skincare"`, replace the assertion block with this pattern.

```python
from orchestrator.app.llm.copy_tone_policy import get_copy_tone_policy, resolve_copy_route_key

assert resolve_copy_route_key("beauty_salon") == "generic"
assert get_copy_tone_policy("beauty_salon")["business_type"] == "generic"
assert resolve_copy_route_key("salon") == "generic"
assert get_copy_tone_policy("salon")["business_type"] == "generic"
```

- [ ] **Step 4: Run the stale expectation search again**

Run:

```bash
rg -n "restaurant_bbq_policy_uses_reservation_cta|explicit_bbq_copy_still_routes|get_copy_tone_policy\\(\"restaurant_bbq\"\\).*restaurant_bbq|get_copy_tone_policy\\(\"beauty_salon\"\\).*beauty_skincare|get_copy_tone_policy\\(\"salon\"\\).*beauty_skincare" orchestrator/tests
```

Expected: No output.

- [ ] **Step 5: Run contract and copywriting tests**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing_contract.py orchestrator/tests/test_copywriting.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit expectation cleanup**

```bash
git add orchestrator/tests/test_copywriting.py orchestrator/tests/test_domain_routing_contract.py
git commit -m "test(srv): remove direct bbq copy policy assumptions"
```

---

### Task 7: Focused Verification And Smoke Checks

**Files:**
- Test: `orchestrator/tests/test_domain_routing_contract.py`
- Test: `orchestrator/tests/test_copywriting.py`
- Test: `orchestrator/tests/test_visual_strategy_registry.py`

- [ ] **Step 1: Run focused A-6 tests**

Run:

```bash
PYTHONPATH=. uv run pytest \
  orchestrator/tests/test_domain_routing_contract.py \
  orchestrator/tests/test_copywriting.py \
  orchestrator/tests/test_visual_strategy_registry.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run copy route smoke script**

Run:

```bash
PYTHONPATH=. uv run python - <<'PY'
from orchestrator.app.llm.copy_fallbacks import resolve_copy_theme
from orchestrator.app.llm.copy_tone_policy import get_copy_tone_policy, resolve_copy_route_key

for value in [
    "restaurant",
    "restaurant_bbq",
    "bbq",
    "meat_restaurant",
    "korean_food",
    "beauty",
    "beauty_salon",
    "salon",
    "beauty_skincare",
    "skincare",
    "beauty_hair",
    "hair",
    "cafe",
    "macaron",
]:
    print(
        value,
        resolve_copy_route_key(value),
        get_copy_tone_policy(value)["policy_id"],
        resolve_copy_theme(value).key,
    )
PY
```

Expected output:

```text
restaurant generic generic_v1 generic
restaurant_bbq generic generic_v1 generic
bbq generic generic_v1 generic
meat_restaurant generic generic_v1 generic
korean_food generic generic_v1 generic
beauty generic generic_v1 generic
beauty_salon generic generic_v1 generic
salon generic generic_v1 generic
beauty_skincare beauty_skincare beauty_skincare_v1 beauty_skincare
skincare beauty_skincare beauty_skincare_v1 beauty_skincare
beauty_hair beauty_hair beauty_hair_v1 beauty_hair
hair beauty_hair beauty_hair_v1 beauty_hair
cafe cafe cafe_v1 cafe
macaron macaron macaron_v1 macaron
```

- [ ] **Step 3: Run broader guard suite**

Run:

```bash
PYTHONPATH=. uv run pytest \
  orchestrator/tests/test_brief_interpreter_llm_v1.py \
  orchestrator/tests/test_image_prompt_planner.py \
  orchestrator/tests/test_image_prompt_v3_integration.py \
  orchestrator/tests/test_image_prompt_v3_sceneplan.py \
  orchestrator/tests/test_copywriting.py \
  orchestrator/tests/test_domain_routing_contract.py \
  orchestrator/tests/test_visual_strategy_registry.py \
  -q
```

Expected: PASS. Existing deprecation warnings are acceptable if no test fails.

- [ ] **Step 4: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: No output.

- [ ] **Step 5: Commit verification notes if plan checklist is updated**

If the implementation worker updates this plan with checked boxes or command results, commit only the plan file change.

```bash
git add docs/superpowers/plans/2026-06-16-domain-routing-a6-copy-tone-neutral-fallback.md
git commit -m "docs(srv): update a6 execution checklist"
```

---

## Non-Goals

- Do not remove `LegacyVisualRouteKey.RESTAURANT_BBQ`; it remains a deprecated visual adapter output during the transition.
- Do not delete `POLICIES["restaurant_bbq"]`; B-track registry or future explicit strategy selection may still need the inventory entry.
- Do not add a new restaurant-specific copy policy in A-6. Neutral fallback is the agreed transition behavior.
- Do not wire product/scene/campaign evidence into copy tone selection in A-6. That belongs to a later strategy resolver integration.
- Do not treat raw `business_type="restaurant_bbq"` as evidence. The document explicitly says historical `business_type` alone is not enough.

## Self-Review

Spec coverage:

- `restaurant -> restaurant_bbq 제거`: covered by Tasks 1, 2, 3, and 4.
- `business domain과 product/campaign tone 분리 전까지 neutral fallback`: covered by `COPY_NEUTRAL_FALLBACK_KEYS`, prompt neutralization, and fallback theme tests.
- `restaurant_bbq는 canonical domain이 아니다`: A-6 does not edit canonical domain code and blocks copy from treating raw `restaurant_bbq` as a new normal route.
- `beauty subtype은 exact evidence 없이 선택 금지`: covered by ambiguous beauty neutral tests and exact subtype allowlist tests.
- `template/preset/copy tone가 하나의 decision에서 결정`: A-6 prevents copy from making independent BBQ/skincare decisions before the shared strategy resolver exists.

Placeholder scan:

- Placeholder scan completed; no banned placeholder markers or unspecified test-writing steps are present.
- Every code-changing step includes exact code.
- Every test step includes exact commands and expected outcomes.

Type consistency:

- `resolve_copy_route_key()` is introduced in Task 2 and imported by later tasks.
- `COPY_NEUTRAL_FALLBACK_KEYS` and `COPY_ROUTE_ALIASES` are defined before use.
- `resolve_copy_theme()` continues to return `CopyTheme`.
- `get_copy_tone_policy()` continues to return `dict[str, Any]`.

Execution handoff:

Plan complete and saved to `docs/superpowers/plans/2026-06-16-domain-routing-a6-copy-tone-neutral-fallback.md`. Two execution options:

1. Subagent-Driven (recommended) - Dispatch a fresh subagent per task, review between tasks, fast iteration.
2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints.
