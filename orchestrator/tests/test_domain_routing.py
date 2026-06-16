"""Unit tests for the domain-routing SSOT (orchestrator.app.llm.domain_routing).

Phase 1 foundation: these pin the single declared source of canonical domains,
the alias layer, and the normalize contract used at the input boundary.
"""

from __future__ import annotations

from typing import get_args

import pytest

from orchestrator.app.llm.domain_routing import (
    CANONICAL_DOMAINS,
    CanonicalDomain,
    SUPPORTED_DOMAINS,
    is_supported_domain,
    normalize_business_type,
    to_canonical_domain,
)


def test_canonical_literal_matches_declared_set():
    assert set(get_args(CanonicalDomain)) == set(CANONICAL_DOMAINS)


def test_seven_canonical_domains_declared():
    assert CANONICAL_DOMAINS == {
        "cafe",
        "restaurant",
        "beauty",
        "fitness",
        "retail",
        "education",
        "service",
    }


def test_supported_is_subset_and_unsupported_are_phase4():
    assert SUPPORTED_DOMAINS <= CANONICAL_DOMAINS
    assert SUPPORTED_DOMAINS == {"cafe", "restaurant", "beauty"}
    assert CANONICAL_DOMAINS - SUPPORTED_DOMAINS == {"fitness", "retail", "education", "service"}


# --- to_canonical_domain: classification (exact + alias, no substring) --------

@pytest.mark.parametrize(
    "value,expected",
    [
        ("cafe", "cafe"),
        ("Cafe", "cafe"),
        ("  CAFE  ", "cafe"),
        ("dessert", "cafe"),
        ("bakery", "cafe"),
        ("restaurant", "restaurant"),
        ("restaurant_bbq", "restaurant"),
        ("bbq", "restaurant"),
        ("korean_food", "restaurant"),
        ("meat_restaurant", "restaurant"),
        ("beauty", "beauty"),
        ("beauty_salon", "beauty"),
        ("beauty_skincare", "beauty"),
        ("beauty_hair", "beauty"),
        ("beauty_nail", "beauty"),
        ("beauty_spa", "beauty"),
        ("salon", "beauty"),
        ("fitness", "fitness"),
        ("retail", "retail"),
        ("education", "education"),
        ("service", "service"),
    ],
)
def test_to_canonical_domain_known_values(value, expected):
    assert to_canonical_domain(value) == expected


@pytest.mark.parametrize("value", [None, "", "   ", "other", "spaceship", "generic"])
def test_to_canonical_domain_unknown_values(value):
    # `generic` is a downstream sentinel, not a canonical input domain.
    assert to_canonical_domain(value) is None


def test_no_substring_matching_in_phase1():
    # "korean cafe restaurant" is not an exact alias key -> unknown (Phase 1 does
    # not do substring heuristics; those remain in scene_planner).
    assert to_canonical_domain("korean cafe restaurant") is None


# --- normalize_business_type: input-boundary contract ------------------------

@pytest.mark.parametrize(
    "value,canonical,business_type,supported",
    [
        ("cafe", "cafe", "cafe", True),
        ("restaurant", "restaurant", "restaurant", True),
        ("beauty", "beauty", "beauty_salon", True),
        ("fitness", "fitness", "fitness", False),
        ("retail", "retail", None, False),
        ("education", "education", None, False),
        ("service", "service", None, False),
    ],
)
def test_normalize_table(value, canonical, business_type, supported):
    result = normalize_business_type(value)
    assert result.canonical == canonical
    assert result.business_type == business_type
    assert result.supported is supported
    # Supported -> no fallback reason; unsupported -> observable reason.
    assert (result.fallback_reason is None) is supported


def test_normalize_subtype_preserves_beauty_family():
    result = normalize_business_type("beauty_salon")
    assert result.canonical == "beauty"
    assert result.supported is True


def test_normalize_unknown_leaves_reason():
    result = normalize_business_type("other")
    assert result.canonical is None
    assert result.business_type is None
    assert result.supported is False
    assert result.fallback_reason and "unknown_business_type" in result.fallback_reason


def test_normalize_missing_value():
    result = normalize_business_type(None)
    assert result.business_type is None
    assert result.fallback_reason == "missing_business_type"


def test_is_supported_domain():
    assert is_supported_domain("cafe")
    assert is_supported_domain("beauty_salon")
    assert not is_supported_domain("fitness")
    assert not is_supported_domain("retail")
    assert not is_supported_domain("other")
    assert not is_supported_domain(None)
