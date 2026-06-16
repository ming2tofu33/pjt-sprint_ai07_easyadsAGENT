# Domain Routing A2 Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the old seven-domain `NormalizedBusinessType` normalization model with the A-1 `DomainRoutingResult` contract while preserving current production callers through temporary compatibility properties.

**Architecture:** Keep A-2 scoped to `domain_routing.py` and domain-routing tests. `normalize_business_type()` becomes the public contract function returning `DomainRoutingResult`; `to_canonical_domain()` and `is_supported_domain()` move to the new `CanonicalBusinessDomain` semantics. Existing callers that read `.business_type`, `.supported`, `.canonical`, and fallback reason values continue to work through computed compatibility properties that are not serialized into the canonical model. Production wiring in `brief_interpreter.py`, selectors, scene planning, and image prompt planning stays untouched until later A phases.

**Tech Stack:** Python 3.12, `enum.StrEnum`, Pydantic v2 models and validators, pytest via `PYTHONPATH=. uv run pytest`.

---

### Task 1: Add A-2 Normalization Tests

**Files:**
- Modify: `orchestrator/tests/test_domain_routing.py`
- Modify: `orchestrator/tests/test_domain_routing_contract.py`

- [x] **Step 1: Replace old seven-domain tests with 3+1 canonical domain tests**

Assert `CANONICAL_DOMAINS == {"food_and_beverage", "beauty", "retail", "other"}` and `SUPPORTED_DOMAINS == {"food_and_beverage", "beauty", "retail"}`.

- [x] **Step 2: Add `to_canonical_domain()` tests for new semantics**

Assert food aliases (`cafe`, `restaurant`, `restaurant_bbq`) map to `CanonicalBusinessDomain.FOOD_AND_BEVERAGE`, beauty aliases map to `BEAUTY`, retail maps to `RETAIL`, and unsupported MVP domains (`fitness`, `education`, `service`, `other`) map to `OTHER`.

- [x] **Step 3: Add `normalize_business_type()` tests for supported domains**

Assert `cafe` becomes specialized food-and-beverage with a `cafe` business tag. Assert `restaurant_bbq` becomes specialized food-and-beverage with `restaurant` and `korean_bbq` business tags, but no `bbq_grill` scene tag without explicit evidence.

- [x] **Step 4: Add beauty and unsupported-domain tests**

Assert `beauty_salon` becomes `BEAUTY + NEEDS_EVIDENCE + AMBIGUOUS_BEAUTY_SUBDOMAIN + clarification_required`. Assert `fitness`, `education`, and `service` become `OTHER + GENERIC_FALLBACK + unsupported_domain_hint + UNSUPPORTED_DOMAIN_IN_MVP`.

- [x] **Step 5: Add unknown input and compatibility property tests**

Assert unknown values become `OTHER + UNRESOLVED + UNRECOGNIZED_BUSINESS_TYPE + clarification_required`. Assert compatibility properties (`canonical`, `business_type`, `supported`, `legacy_fallback_reason`) exist but are not emitted by `model_dump()`.

- [x] **Step 6: Update contract test expectations**

Update `test_supported_domains_are_a_declared_subset_of_canonical()` to the new 3+1 canonical model. Keep visual preset/template compatibility assertions unchanged because A-2 does not rewire production selectors yet.

- [x] **Step 7: Run tests to verify RED**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing.py orchestrator/tests/test_domain_routing_contract.py -q
```

Expected: FAIL because the implementation still returns the old `NormalizedBusinessType`, old seven-domain constants, and old string canonical values.

### Task 2: Implement A-2 Normalization Contract

**Files:**
- Modify: `orchestrator/app/llm/domain_routing.py`

- [x] **Step 1: Replace old canonical constants**

Set `CanonicalDomain` to a `Literal["food_and_beverage", "beauty", "retail", "other"]`, set `CANONICAL_DOMAINS` from `CanonicalBusinessDomain`, and set `SUPPORTED_DOMAINS` to `food_and_beverage`, `beauty`, and `retail`.

- [x] **Step 2: Add exact alias metadata**

Create exact alias dictionaries for domain classification, business tags, ambiguous beauty aliases, beauty subtype tags, and unsupported-domain hints. Include current legacy keys such as `restaurant_bbq`, `beauty_skincare`, `beauty_hair`, `beauty_nail`, and `beauty_spa`.

- [x] **Step 3: Add helpers for evidence tags**

Add small helpers to create `RoutingTagEvidence` and read tag sets. Keep the helpers local to `domain_routing.py`.

- [x] **Step 4: Add compatibility properties to `DomainRoutingResult`**

Add read-only properties:

- `canonical -> str`
- `supported -> bool`
- `legacy_fallback_reason -> str | None`
- `business_type -> str | None`

Do not add these as Pydantic fields.

- [x] **Step 5: Implement `to_canonical_domain()` and `is_supported_domain()`**

Use exact alias lookup only. Unknown or empty values should return `CanonicalBusinessDomain.OTHER`, not `None`.

- [x] **Step 6: Implement `normalize_business_type()` returning `DomainRoutingResult`**

Minimum behavior:

- empty or unknown -> `OTHER`, `UNRESOLVED`, `UNRECOGNIZED_BUSINESS_TYPE`, `clarification_required=True`
- `cafe` -> F&B specialized with `cafe`
- `restaurant` -> F&B specialized with `restaurant`
- `restaurant_bbq` -> F&B specialized with `restaurant`, `korean_bbq`, no `bbq_grill`
- `beauty_salon`/`beauty`/`salon` -> BEAUTY `NEEDS_EVIDENCE`
- `beauty_skincare`/`hair`/`nail`/`spa` -> BEAUTY specialized with matching tags
- `retail`/`store`/`ecommerce` -> RETAIL specialized
- `fitness`/`education`/`service`/`other` -> OTHER `GENERIC_FALLBACK`, `unsupported_domain_hint`

- [x] **Step 7: Remove old `NormalizedBusinessType` return path**

Delete the old `NamedTuple` class if no imports remain. Do not return it from `normalize_business_type()`.

- [x] **Step 8: Run tests to verify GREEN**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing.py orchestrator/tests/test_domain_routing_contract.py -q
```

Expected: PASS.

### Task 3: Final Verification

**Files:**
- Inspect: `orchestrator/app/llm/domain_routing.py`
- Inspect: `orchestrator/tests/test_domain_routing.py`
- Inspect: `orchestrator/tests/test_domain_routing_contract.py`

- [x] **Step 1: Run import smoke**

Run:

```bash
PYTHONPATH=. uv run python - <<'PY'
from orchestrator.app.llm.domain_routing import normalize_business_type

result = normalize_business_type("beauty_salon")
print(result.canonical_domain.value)
print(result.support_status.value)
print(result.fallback_reason.value)
print("business_type" in result.model_dump(mode="json"))
PY
```

Expected output:

```text
beauty
needs_evidence
ambiguous_beauty_subdomain
False
```

- [x] **Step 2: Confirm A-2 did not rewire production**

Run:

```bash
git diff --name-only
```

Expected changed files:

```text
docs/superpowers/plans/2026-06-16-domain-routing-a2-normalization.md
orchestrator/app/llm/domain_routing.py
orchestrator/tests/test_domain_routing.py
orchestrator/tests/test_domain_routing_contract.py
```

- [ ] **Step 3: Commit only when requested**

Do not commit automatically unless the user asks.
