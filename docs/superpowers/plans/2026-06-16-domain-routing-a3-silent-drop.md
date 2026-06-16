# Domain Routing A3 Silent Drop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent supported and unsupported business domains from silently disappearing at the brief/context boundary after A-2 normalization.

**Architecture:** Keep A-3 narrow: the canonical `DomainRoutingResult` model remains the source of truth, and legacy callers continue to consume the temporary `.business_type` projection. `retail` must project to legacy `context.business_type="retail"` because it is an MVP specialized domain, while unsupported domains keep explicit `OTHER + unsupported_domain_hint + fallback_reason` breadcrumbs. Open-domain service hints are accepted as exact aliases only and remain generic fallback until later visual strategy wiring.

**Tech Stack:** Python 3.12, Pydantic v2, `enum.StrEnum`, pytest via `PYTHONPATH=. uv run pytest`.

---

## File Structure

- Modify: `orchestrator/app/llm/domain_routing.py`
  - Owns canonical domain normalization and legacy compatibility projection.
  - A-3 adds `retail` legacy projection and exact unsupported service aliases.

- Modify: `orchestrator/tests/test_domain_routing.py`
  - Owns unit tests for `normalize_business_type()` and compatibility properties.
  - A-3 pins `retail.business_type == "retail"` and open-domain unsupported hint preservation.

- Modify: `orchestrator/tests/test_domain_routing_contract.py`
  - Owns cross-module contract tests for brief interpreter and legacy visual routing.
  - A-3 pins `BriefBusinessType` values do not silently evaporate from context/warnings.

- Modify: `orchestrator/tests/test_brief_interpreter_llm_v1.py`
  - Owns direct brief interpreter context update tests.
  - A-3 updates stale retail expectations and adds a focused retail context test.

- Modify: `orchestrator/tests/test_business_context.py`
  - Owns B-track `BusinessEnvironmentContext` boundary tests.
  - A-3 documents that the builder remains explicit: it does not auto-copy `DomainRoutingResult.business_tags`.

---

### Task 1: Pin Retail Brief Context Preservation

**Files:**
- Modify: `orchestrator/tests/test_domain_routing.py`
- Modify: `orchestrator/tests/test_domain_routing_contract.py`
- Modify: `orchestrator/tests/test_brief_interpreter_llm_v1.py`
- Modify: `orchestrator/app/llm/domain_routing.py`

- [x] **Step 1: Write failing unit test for retail projection**

Add this assertion to `test_normalize_retail_is_supported_specialized_domain()` in `orchestrator/tests/test_domain_routing.py`:

```python
def test_normalize_retail_is_supported_specialized_domain():
    result = normalize_business_type("retail")

    assert result.canonical_domain == CanonicalBusinessDomain.RETAIL
    assert result.support_status == DomainSupportStatus.SPECIALIZED
    assert result.fallback_reason is None
    assert _tags(result) == {"retail"}
    assert result.business_type == "retail"
    assert result.supported is True
```

- [x] **Step 2: Write failing contract test for retail brief updates**

Add this test to `orchestrator/tests/test_domain_routing_contract.py` near the P4 brief routing tests:

```python
def test_retail_brief_business_type_is_not_silently_dropped():
    normalized = normalize_business_type("retail")
    updates, warnings = build_context_updates_from_brief_interpreter(
        BriefInterpreterOutput(business_type="retail")
    )

    assert normalized.canonical_domain == CanonicalBusinessDomain.RETAIL
    assert normalized.support_status == DomainSupportStatus.SPECIALIZED
    assert normalized.business_type == "retail"
    assert updates.get("business_type") == "retail"
    assert not any("business_type_fallback_generic" in warning for warning in warnings)
```

- [x] **Step 3: Write failing direct brief interpreter test**

Add this test to `orchestrator/tests/test_brief_interpreter_llm_v1.py` before `test_romanized_item_recovered_from_korean_source()`:

```python
def test_retail_business_type_is_preserved_from_brief_interpreter():
    output = BriefInterpreterOutput(
        business_type="retail",
        item_or_service="돌반지",
        promotion_goal="discount_event",
        confidence=0.95,
    )

    updates, warnings = build_context_updates_from_brief_interpreter(
        output,
        source_text="돌반지 할인 이벤트",
    )

    assert updates["business_type"] == "retail"
    assert updates["item_or_service"] == "돌반지"
    assert updates["promotion_goal"] == "discount_event"
    assert not any("business_type_fallback_generic" in warning for warning in warnings)
```

- [x] **Step 4: Run tests to verify RED**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing.py::test_normalize_retail_is_supported_specialized_domain orchestrator/tests/test_domain_routing_contract.py::test_retail_brief_business_type_is_not_silently_dropped orchestrator/tests/test_brief_interpreter_llm_v1.py::test_retail_business_type_is_preserved_from_brief_interpreter -q
```

Expected: FAIL because `DomainRoutingResult.business_type` currently returns `None` for `CanonicalBusinessDomain.RETAIL`.

- [x] **Step 5: Implement minimal retail projection**

In `orchestrator/app/llm/domain_routing.py`, update `DomainRoutingResult.business_type`:

```python
        if self.canonical_domain == CanonicalBusinessDomain.RETAIL:
            return "retail"
        if self.canonical_domain == CanonicalBusinessDomain.OTHER:
            return self.unsupported_domain_hint
```

- [x] **Step 6: Run tests to verify GREEN**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing.py::test_normalize_retail_is_supported_specialized_domain orchestrator/tests/test_domain_routing_contract.py::test_retail_brief_business_type_is_not_silently_dropped orchestrator/tests/test_brief_interpreter_llm_v1.py::test_retail_business_type_is_preserved_from_brief_interpreter -q
```

Expected: PASS.

### Task 2: Pin Unsupported Hint Breadcrumbs

**Files:**
- Modify: `orchestrator/tests/test_domain_routing.py`
- Modify: `orchestrator/tests/test_domain_routing_contract.py`
- Modify: `orchestrator/app/llm/domain_routing.py`

- [x] **Step 1: Write failing tests for open-domain service aliases**

Add these values to `test_to_canonical_domain_returns_a1_domain()` in `orchestrator/tests/test_domain_routing.py`:

```python
        ("professional_service", CanonicalBusinessDomain.OTHER),
        ("local_service", CanonicalBusinessDomain.OTHER),
        ("home_service", CanonicalBusinessDomain.OTHER),
```

Add these values to `test_normalize_unsupported_domains_preserves_hint()` in the same file:

```python
        ("professional_service", "professional_service"),
        ("local_service", "local_service"),
        ("home_service", "home_service"),
```

- [x] **Step 2: Write contract test for unsupported brief breadcrumbs**

Add this test to `orchestrator/tests/test_domain_routing_contract.py` near the P4 brief routing tests:

```python
@pytest.mark.parametrize("value", ["fitness", "education", "service", "other"])
def test_unsupported_brief_business_type_preserves_hint_and_warning(value):
    normalized = normalize_business_type(value)
    updates, warnings = build_context_updates_from_brief_interpreter(
        BriefInterpreterOutput(business_type=value)
    )

    assert normalized.canonical_domain == CanonicalBusinessDomain.OTHER
    assert normalized.support_status == DomainSupportStatus.GENERIC_FALLBACK
    assert normalized.unsupported_domain_hint == value
    assert normalized.fallback_reason == DomainFallbackReason.UNSUPPORTED_DOMAIN_IN_MVP
    assert updates.get("business_type") == value
    assert any("business_type_fallback_generic: unsupported_domain_in_mvp" in warning for warning in warnings)
```

- [x] **Step 3: Run tests to verify RED**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing.py::test_to_canonical_domain_returns_a1_domain orchestrator/tests/test_domain_routing.py::test_normalize_unsupported_domains_preserves_hint orchestrator/tests/test_domain_routing_contract.py::test_unsupported_brief_business_type_preserves_hint_and_warning -q
```

Expected: FAIL for the new `professional_service`, `local_service`, and `home_service` cases because those aliases are not yet in `_DOMAIN_ALIASES` or `_UNSUPPORTED_DOMAIN_HINTS`.

- [x] **Step 4: Implement exact unsupported service aliases**

In `orchestrator/app/llm/domain_routing.py`, add aliases:

```python
    "professional_service": CanonicalBusinessDomain.OTHER,
    "local_service": CanonicalBusinessDomain.OTHER,
    "home_service": CanonicalBusinessDomain.OTHER,
```

Add business tags:

```python
    "professional_service": ("professional_service",),
    "local_service": ("local_service",),
    "home_service": ("home_service",),
```

Add unsupported hints:

```python
    "professional_service": "professional_service",
    "local_service": "local_service",
    "home_service": "home_service",
```

- [x] **Step 5: Run tests to verify GREEN**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing.py::test_to_canonical_domain_returns_a1_domain orchestrator/tests/test_domain_routing.py::test_normalize_unsupported_domains_preserves_hint orchestrator/tests/test_domain_routing_contract.py::test_unsupported_brief_business_type_preserves_hint_and_warning -q
```

Expected: PASS.

### Task 3: Document Business Context Boundary

**Files:**
- Modify: `orchestrator/tests/test_business_context.py`
- Modify: `orchestrator/tests/test_brief_interpreter_llm_v1.py`

- [x] **Step 1: Add explicit business context boundary test**

Add imports to `orchestrator/tests/test_business_context.py`:

```python
    RoutingEvidenceSource,
    RoutingTagEvidence,
```

Add this test near the builder tests:

```python
def test_builder_does_not_auto_copy_domain_result_business_tags():
    domain_result = DomainRoutingResult(
        raw_business_type="restaurant_bbq",
        canonical_domain=CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
        support_status=DomainSupportStatus.SPECIALIZED,
        business_tags=[
            RoutingTagEvidence(
                tag="restaurant",
                source=RoutingEvidenceSource.LEGACY_ALIAS,
                confidence=1.0,
            ),
            RoutingTagEvidence(
                tag="korean_bbq",
                source=RoutingEvidenceSource.LEGACY_ALIAS,
                confidence=1.0,
            ),
        ],
        confidence=0.95,
    )

    context = build_business_environment_context(domain_result)

    assert context.broad_domain == CanonicalBusinessDomain.FOOD_AND_BEVERAGE
    assert context.business_tags == []
    assert context.evidence_refs == []
```

This test should PASS without production changes. It documents that B-track `BusinessEnvironmentContext` still requires explicit tag/evidence wiring and A-3 does not silently infer it.

- [x] **Step 2: Update stale retail test comments**

In `orchestrator/tests/test_brief_interpreter_llm_v1.py`, replace the stale comment in `test_korean_item_kept_when_not_romanized()`:

```python
    assert updates["business_type"] == "retail"
    assert not any("item_or_service" in w or "recovered" in w for w in warnings)
```

The comment should be removed because `retail` is now a specialized domain and should not be described as having no domain routing.

- [x] **Step 3: Run business context and brief interpreter tests**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_business_context.py::test_builder_does_not_auto_copy_domain_result_business_tags orchestrator/tests/test_brief_interpreter_llm_v1.py::test_korean_item_kept_when_not_romanized -q
```

Expected: PASS after Task 1 implementation, because retail is preserved and the business context builder remains explicit.

### Task 4: Final Verification

**Files:**
- Inspect: `orchestrator/app/llm/domain_routing.py`
- Inspect: `orchestrator/tests/test_domain_routing.py`
- Inspect: `orchestrator/tests/test_domain_routing_contract.py`
- Inspect: `orchestrator/tests/test_brief_interpreter_llm_v1.py`
- Inspect: `orchestrator/tests/test_business_context.py`

- [x] **Step 1: Run focused A-3 test suite**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing.py orchestrator/tests/test_domain_routing_contract.py orchestrator/tests/test_brief_interpreter_llm_v1.py orchestrator/tests/test_business_context.py -q
```

Expected: PASS.

- [x] **Step 2: Run smoke script for observed A-3 behavior**

Run:

```bash
PYTHONPATH=. uv run python - <<'PY'
import orchestrator.app.graph.nodes  # noqa: F401
from orchestrator.app.llm.domain_routing import normalize_business_type
from orchestrator.app.llm.nodes.brief_interpreter import build_context_updates_from_brief_interpreter
from orchestrator.app.schemas.brief_llm import BriefInterpreterOutput

for value in ["retail", "fitness", "education", "service", "other"]:
    result = normalize_business_type(value)
    updates, warnings = build_context_updates_from_brief_interpreter(BriefInterpreterOutput(business_type=value))
    print(value, result.canonical_domain.value, result.support_status.value, result.unsupported_domain_hint, result.business_type, updates, warnings)
PY
```

Expected output includes:

```text
retail retail specialized None retail {'business_type': 'retail'} []
fitness other generic_fallback fitness fitness {'business_type': 'fitness'} ['business_type_fallback_generic: unsupported_domain_in_mvp']
education other generic_fallback education education {'business_type': 'education'} ['business_type_fallback_generic: unsupported_domain_in_mvp']
service other generic_fallback service service {'business_type': 'service'} ['business_type_fallback_generic: unsupported_domain_in_mvp']
other other generic_fallback other other {'business_type': 'other'} ['business_type_fallback_generic: unsupported_domain_in_mvp']
```

- [x] **Step 3: Run diff check**

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

Expected changed files:

```text
docs/superpowers/plans/2026-06-16-domain-routing-a3-silent-drop.md
orchestrator/app/llm/domain_routing.py
orchestrator/tests/test_business_context.py
orchestrator/tests/test_brief_interpreter_llm_v1.py
orchestrator/tests/test_domain_routing.py
orchestrator/tests/test_domain_routing_contract.py
```

### Self-Review

- Spec coverage: The plan covers retail preservation, unsupported-domain breadcrumbs, open-domain service hints, and the B-track business context boundary.
- Placeholder scan: The plan contains no `TBD`, `TODO`, or unspecified implementation steps.
- Type consistency: All referenced names already exist in A-2 code: `DomainRoutingResult`, `CanonicalBusinessDomain`, `DomainSupportStatus`, `DomainFallbackReason`, `RoutingEvidenceSource`, `RoutingTagEvidence`, `normalize_business_type()`, and `build_context_updates_from_brief_interpreter()`.
