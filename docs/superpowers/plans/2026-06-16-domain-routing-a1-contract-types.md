# Domain Routing A1 Contract Types Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the Track A-1 domain routing contract type cluster so Track B can import stable shared types without changing production routing behavior.

**Architecture:** Add the new v1 contract types to `orchestrator/app/llm/domain_routing.py` above the existing Phase 1 compatibility helpers. Keep current `normalize_business_type()`, `CanonicalDomain`, and brief-interpreter behavior unchanged until A-2. Pin the new contract with focused pydantic validation tests in `orchestrator/tests/test_domain_routing_contract.py`.

**Tech Stack:** Python 3.12, `enum.StrEnum`, Pydantic v2 `BaseModel`, `Field`, `model_validator`, pytest via `PYTHONPATH=. uv run pytest`.

---

### Task 1: Add A-1 Contract Tests

**Files:**
- Modify: `orchestrator/tests/test_domain_routing_contract.py`

- [ ] **Step 1: Write failing imports and enum contract tests**

Append tests that import:

```python
from orchestrator.app.llm.domain_routing import (
    CanonicalBusinessDomain,
    DomainFallbackReason,
    DomainRoutingResult,
    DomainSupportStatus,
    LegacyRoutingProjection,
    LegacyVisualRouteKey,
    ReferenceTemplateRoutingProfile,
    RoutingEvidenceSource,
    RoutingTagEvidence,
)
```

Add tests:

```python
def test_a1_canonical_business_domain_is_mvp_3_plus_other():
    assert {item.value for item in CanonicalBusinessDomain} == {
        "food_and_beverage",
        "beauty",
        "retail",
        "other",
    }


def test_a1_legacy_visual_route_keys_match_current_compatibility_routes():
    assert {item.value for item in LegacyVisualRouteKey} == {
        "cafe",
        "restaurant",
        "restaurant_bbq",
        "beauty_skincare",
        "beauty_hair",
        "beauty_nail",
        "beauty_spa",
        "generic",
    }
```

- [ ] **Step 2: Add DomainRoutingResult validation tests**

Add tests:

```python
def test_a1_domain_routing_result_allows_specialized_without_fallback():
    result = DomainRoutingResult(
        raw_business_type="cafe",
        canonical_domain=CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
        support_status=DomainSupportStatus.SPECIALIZED,
        business_tags=[
            RoutingTagEvidence(
                tag="cafe",
                source=RoutingEvidenceSource.USER_TEXT,
                confidence=0.99,
            )
        ],
        confidence=0.99,
    )

    assert result.contract_version == "1.0"
    assert result.fallback_reason is None
    assert result.clarification_required is False


def test_a1_domain_routing_result_requires_fallback_reason_for_non_specialized():
    with pytest.raises(ValueError, match="non-specialized routing requires fallback_reason"):
        DomainRoutingResult(
            raw_business_type="fitness",
            canonical_domain=CanonicalBusinessDomain.OTHER,
            support_status=DomainSupportStatus.GENERIC_FALLBACK,
            confidence=0.9,
        )


def test_a1_domain_routing_result_requires_clarification_for_needs_evidence():
    with pytest.raises(ValueError, match="needs_evidence/unresolved must require clarification"):
        DomainRoutingResult(
            raw_business_type="beauty_salon",
            canonical_domain=CanonicalBusinessDomain.BEAUTY,
            support_status=DomainSupportStatus.NEEDS_EVIDENCE,
            fallback_reason=DomainFallbackReason.AMBIGUOUS_BEAUTY_SUBDOMAIN,
            clarification_required=False,
            confidence=0.8,
        )


def test_a1_unsupported_domain_hint_is_only_valid_for_other():
    with pytest.raises(ValueError, match="unsupported_domain_hint is only valid for OTHER"):
        DomainRoutingResult(
            raw_business_type="fitness",
            canonical_domain=CanonicalBusinessDomain.RETAIL,
            support_status=DomainSupportStatus.GENERIC_FALLBACK,
            unsupported_domain_hint="fitness",
            fallback_reason=DomainFallbackReason.UNSUPPORTED_DOMAIN_IN_MVP,
            confidence=0.8,
        )
```

- [ ] **Step 3: Add routing tag and reference profile validation tests**

Add tests:

```python
def test_a1_routing_tag_evidence_rejects_unsafe_tag_values():
    with pytest.raises(ValueError):
        RoutingTagEvidence(
            tag="Bad Tag",
            source=RoutingEvidenceSource.USER_TEXT,
            confidence=0.5,
        )


def test_a1_reference_template_profile_requires_routing_dimension():
    with pytest.raises(ValueError, match="routing profile requires at least one routing dimension"):
        ReferenceTemplateRoutingProfile()


def test_a1_reference_template_profile_all_domains_can_be_empty_otherwise():
    profile = ReferenceTemplateRoutingProfile(applies_to_all_domains=True)

    assert profile.applies_to_all_domains is True
    assert profile.business_domains == set()


def test_a1_reference_template_profile_rejects_overlapping_included_and_excluded_tags():
    with pytest.raises(ValueError, match="included and excluded tags must not overlap"):
        ReferenceTemplateRoutingProfile(
            business_domains={CanonicalBusinessDomain.FOOD_AND_BEVERAGE},
            business_tags={"cafe"},
            excluded_tags={"cafe"},
        )
```

- [ ] **Step 4: Add legacy projection smoke test**

Add test:

```python
def test_a1_legacy_projection_is_deprecated_compatibility_result():
    projection = LegacyRoutingProjection(
        route_key=LegacyVisualRouteKey.GENERIC,
        fallback_used=True,
        fallback_reason=DomainFallbackReason.NO_SPECIALIZED_VISUAL_PROFILE,
        reason_codes=["no_specialized_visual_profile"],
    )

    assert projection.projection_version == "1.0"
    assert projection.deprecated is True
```

- [ ] **Step 5: Run tests to verify RED**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing_contract.py -q
```

Expected: FAIL during import because the new A-1 contract types are not yet defined.

### Task 2: Implement A-1 Contract Types

**Files:**
- Modify: `orchestrator/app/llm/domain_routing.py`

- [ ] **Step 1: Add imports**

Update imports near the top:

```python
from enum import StrEnum
from typing import Literal, NamedTuple

from pydantic import BaseModel, Field, model_validator
```

- [ ] **Step 2: Add v1 contract classes above legacy compatibility helpers**

Add these classes before the existing `CanonicalDomain = Literal[...]` block:

```python
class CanonicalBusinessDomain(StrEnum):
    FOOD_AND_BEVERAGE = "food_and_beverage"
    BEAUTY = "beauty"
    RETAIL = "retail"
    OTHER = "other"


class DomainSupportStatus(StrEnum):
    SPECIALIZED = "specialized"
    GENERIC_FALLBACK = "generic_fallback"
    NEEDS_EVIDENCE = "needs_evidence"
    UNRESOLVED = "unresolved"


class DomainFallbackReason(StrEnum):
    UNSUPPORTED_DOMAIN_IN_MVP = "unsupported_domain_in_mvp"
    AMBIGUOUS_BEAUTY_SUBDOMAIN = "ambiguous_beauty_subdomain"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NO_SPECIALIZED_VISUAL_PROFILE = "no_specialized_visual_profile"
    UNRECOGNIZED_BUSINESS_TYPE = "unrecognized_business_type"


class RoutingEvidenceSource(StrEnum):
    USER_TEXT = "user_text"
    IMAGE_VLM = "image_vlm"
    BRIEF_LLM = "brief_llm"
    ASSET_METADATA = "asset_metadata"
    BRAND_PROFILE = "brand_profile"
    REFERENCE_METADATA = "reference_metadata"
    LEGACY_ALIAS = "legacy_alias"


class RoutingTagEvidence(BaseModel):
    tag: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    source: RoutingEvidenceSource
    confidence: float = Field(ge=0.0, le=1.0)
    usable_for_routing: bool = True
    evidence_ref: str | None = None
```

- [ ] **Step 3: Add result and legacy projection models**

Add:

```python
class DomainRoutingResult(BaseModel):
    contract_version: Literal["1.0"] = "1.0"
    raw_business_type: str | None
    canonical_domain: CanonicalBusinessDomain
    support_status: DomainSupportStatus
    unsupported_domain_hint: str | None = None
    business_tags: list[RoutingTagEvidence] = Field(default_factory=list)
    scene_tags: list[RoutingTagEvidence] = Field(default_factory=list)
    style_tags: list[RoutingTagEvidence] = Field(default_factory=list)
    fallback_reason: DomainFallbackReason | None = None
    matched_aliases: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    clarification_required: bool = False
    unresolved_questions: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_status_contract(self) -> "DomainRoutingResult":
        if self.support_status == DomainSupportStatus.SPECIALIZED and self.fallback_reason is not None:
            raise ValueError("specialized routing must not include fallback_reason")
        if self.support_status in {
            DomainSupportStatus.GENERIC_FALLBACK,
            DomainSupportStatus.NEEDS_EVIDENCE,
            DomainSupportStatus.UNRESOLVED,
        } and self.fallback_reason is None:
            raise ValueError("non-specialized routing requires fallback_reason")
        if self.support_status in {
            DomainSupportStatus.NEEDS_EVIDENCE,
            DomainSupportStatus.UNRESOLVED,
        } and not self.clarification_required:
            raise ValueError("needs_evidence/unresolved must require clarification")
        if self.canonical_domain != CanonicalBusinessDomain.OTHER and self.unsupported_domain_hint is not None:
            raise ValueError("unsupported_domain_hint is only valid for OTHER")
        return self


class LegacyVisualRouteKey(StrEnum):
    CAFE = "cafe"
    RESTAURANT = "restaurant"
    RESTAURANT_BBQ = "restaurant_bbq"
    BEAUTY_SKINCARE = "beauty_skincare"
    BEAUTY_HAIR = "beauty_hair"
    BEAUTY_NAIL = "beauty_nail"
    BEAUTY_SPA = "beauty_spa"
    GENERIC = "generic"


class LegacyRoutingProjection(BaseModel):
    projection_version: Literal["1.0"] = "1.0"
    route_key: LegacyVisualRouteKey
    reason_codes: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    fallback_used: bool = False
    fallback_reason: DomainFallbackReason | None = None
    deprecated: Literal[True] = True
```

- [ ] **Step 4: Add reference template routing profile**

Add:

```python
class ReferenceTemplateRoutingProfile(BaseModel):
    contract_version: Literal["1.0"] = "1.0"
    applies_to_all_domains: bool = False
    business_domains: set[CanonicalBusinessDomain] = Field(default_factory=set)
    business_tags: set[str] = Field(default_factory=set)
    product_tags: set[str] = Field(default_factory=set)
    scene_tags: set[str] = Field(default_factory=set)
    style_tags: set[str] = Field(default_factory=set)
    placements: set[str] = Field(default_factory=set)
    excluded_tags: set[str] = Field(default_factory=set)

    @model_validator(mode="after")
    def validate_routing_profile(self) -> "ReferenceTemplateRoutingProfile":
        if (
            not self.applies_to_all_domains
            and not self.business_domains
            and not self.business_tags
            and not self.product_tags
            and not self.scene_tags
            and not self.style_tags
        ):
            raise ValueError("routing profile requires at least one routing dimension")
        included_tags = self.business_tags | self.product_tags | self.scene_tags | self.style_tags
        if included_tags & self.excluded_tags:
            raise ValueError("included and excluded tags must not overlap")
        return self
```

- [ ] **Step 5: Run tests to verify GREEN**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing_contract.py -q
PYTHONPATH=. uv run pytest orchestrator/tests/test_domain_routing.py orchestrator/tests/test_domain_routing_contract.py -q
```

Expected: PASS. Existing Phase 1 compatibility tests still pass.

### Task 3: Final Verification

**Files:**
- Inspect: `orchestrator/app/llm/domain_routing.py`
- Inspect: `orchestrator/tests/test_domain_routing_contract.py`

- [ ] **Step 1: Run import smoke**

Run:

```bash
PYTHONPATH=. uv run python - <<'PY'
from orchestrator.app.llm.domain_routing import (
    CanonicalBusinessDomain,
    DomainRoutingResult,
    LegacyVisualRouteKey,
    ReferenceTemplateRoutingProfile,
)

print(CanonicalBusinessDomain.FOOD_AND_BEVERAGE.value)
print(LegacyVisualRouteKey.GENERIC.value)
print(ReferenceTemplateRoutingProfile(applies_to_all_domains=True).contract_version)
PY
```

Expected output:

```text
food_and_beverage
generic
1.0
```

- [ ] **Step 2: Confirm no production rewiring occurred**

Run:

```bash
git diff -- orchestrator/app/llm/domain_routing.py orchestrator/tests/test_domain_routing_contract.py
```

Expected: only new contract types and contract tests changed. No edits to `brief_interpreter.py`, `scene_planner.py`, `visual_presets.py`, `visual_templates.py`, `copy_tone_policy.py`, or `image_prompt_planner.py`.

- [ ] **Step 3: Commit when requested by the user**

Do not commit automatically unless the user asks. If requested, use:

```bash
git add orchestrator/app/llm/domain_routing.py orchestrator/tests/test_domain_routing_contract.py docs/superpowers/plans/2026-06-16-domain-routing-a1-contract-types.md
git commit -m "feat(domain-routing): add v1 contract types"
```

