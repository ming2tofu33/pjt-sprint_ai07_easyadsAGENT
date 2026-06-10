"""Structured LLM option suggestion schema + slug-safe / confidence guards.

P7-1: The LLM suggests 2-4 context-specific options for free-text fields
(item_or_service, promotion_goal, target_persona).  Static registry options
are kept as the base; LLM options augment, never replace.  "직접 입력"
(value="custom") is always preserved as the last option.  If the LLM call
fails or confidence is too low, the caller falls back to pure static options
(zero-risk floor).
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

from orchestrator.app.schemas.llm_marketing import MissingField, OptionItem


# ── Constants ────────────────────────────────────────────────────────────

# Fields where LLM-generated options augment the static registry.
# Enums (ad_format, copy_generation_mode) and well-enumerated fields
# (business_type, brand_tone, region_type, …) are excluded — they have
# fixed downstream semantics (copy_candidates.py pattern-matches on slugs,
# text_style_binder checks brand_tone, etc.).
ELIGIBLE_FIELDS: frozenset[MissingField] = frozenset({
    "item_or_service",
    "promotion_goal",
    "target_persona",
})

# Minimum confidence for accepting LLM suggestions.  Below this threshold
# the caller discards the output and shows static options only.
OPTION_SUGGESTION_CONFIDENCE_THRESHOLD: float = 0.5

# Maximum total options (static + dynamic, including custom) presented to
# the user.  Keeps the chip grid scannable.
MAX_OPTIONS_AFTER_MERGE: int = 8


# ── Slug utilities ───────────────────────────────────────────────────────

# Slug pattern: lowercase ASCII letters/digits, underscores, hyphens.
# 1-64 chars, must start with a letter or digit.
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

# Characters that are not allowed in a slug.
_NON_SLUG_RE = re.compile(r"[^a-z0-9_-]")
_MULTI_UNDERSCORE_RE = re.compile(r"_{2,}")


def is_slug_safe(value: str) -> bool:
    """Return True if *value* is a valid slug."""
    return bool(_SLUG_RE.match(value))


def slugify(value: str) -> str:
    """Best-effort conversion of an arbitrary string to a slug.

    Lowercases, replaces whitespace and hyphens with underscores, strips
    everything else, then collapses/trims underscores.  Returns "" if
    nothing survives.
    """
    s = value.lower().strip()
    s = s.replace(" ", "_").replace("-", "_")
    s = _NON_SLUG_RE.sub("", s)
    s = _MULTI_UNDERSCORE_RE.sub("_", s)
    s = s.strip("_")
    return s[:64]


# ── Schema ───────────────────────────────────────────────────────────────

class OptionSuggestionItem(BaseModel):
    """A single LLM-suggested option (Korean label + ASCII slug value)."""

    label: str = Field(..., min_length=1, max_length=40)
    value: str = Field(..., min_length=1, max_length=64)

    @field_validator("value")
    @classmethod
    def ensure_slug_safe(cls, v: str) -> str:
        """Auto-sanitise the value to a valid slug.

        The LLM is prompted to output ASCII slugs, but if it doesn't, we
        slugify defensively.  An empty result after slugification means the
        value was un-salvageable → reject.
        """
        if is_slug_safe(v):
            return v
        sanitized = slugify(v)
        if not sanitized:
            raise ValueError(f"Value '{v}' cannot be sanitized to a valid slug")
        return sanitized


class OptionSuggestionOutput(BaseModel):
    """Structured output from the option_suggester LLM subcall.

    Used with ``run_structured_node`` (output_schema argument).
    The LLM should return 2-4 options; ``max_length=6`` is a generous
    upper bound so a slightly chatty model doesn't get rejected outright.
    """

    options: list[OptionSuggestionItem] = Field(
        default_factory=list,
        max_length=6,
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


# ── Helpers ──────────────────────────────────────────────────────────────

def is_field_eligible(field: str) -> bool:
    """Return True if *field* should be augmented with LLM options."""
    return field in ELIGIBLE_FIELDS


def passes_confidence_threshold(output: OptionSuggestionOutput) -> bool:
    """Return True if the LLM output's confidence is high enough to use."""
    return output.confidence >= OPTION_SUGGESTION_CONFIDENCE_THRESHOLD


def suggestion_to_option_item(
    item: OptionSuggestionItem,
    *,
    item_id: int,
) -> OptionItem:
    """Convert an ``OptionSuggestionItem`` to an ``OptionItem``.

    The ``OptionItem`` is what the interrupt payload (and FE) consume.
    """
    return OptionItem(id=item_id, label=item.label, value=item.value)


def merge_options(
    static_options: list[OptionItem],
    dynamic_items: list[OptionSuggestionItem],
    *,
    max_total: int = MAX_OPTIONS_AFTER_MERGE,
) -> list[OptionItem]:
    """Merge static registry options with LLM-generated options.

    Rules
    -----
    1. Static options appear first (order preserved, minus "custom").
    2. Dynamic options are appended after the static block.
    3. Exact duplicates are removed (matched by value **or** label).
    4. Total is capped at *max_total*.
    5. ``value="custom"`` ("직접 입력") is always the very last option.
    6. IDs are re-indexed sequentially from 1.

    If *dynamic_items* is empty the result is identical to *static_options*
    (just re-indexed), so calling this with an empty list is safe.
    """
    # 1. Separate "custom" from the rest of the static list.
    custom_option: OptionItem | None = None
    base: list[OptionItem] = []
    for opt in static_options:
        if opt.value == "custom":
            custom_option = opt
        else:
            base.append(opt)

    # 2. Collect already-seen values and labels for dedup.
    seen_values: set[str] = {opt.value for opt in base}
    seen_labels: set[str] = {opt.label for opt in base}

    # 3. Append non-duplicate dynamic items.
    for item in dynamic_items:
        if item.value in seen_values or item.label in seen_labels:
            continue
        if item.value == "custom":
            continue  # never override the built-in custom option
        base.append(OptionItem(id=0, label=item.label, value=item.value))
        seen_values.add(item.value)
        seen_labels.add(item.label)

    # 4. Cap (reserve 1 slot for custom if it exists).
    cap = max_total - (1 if custom_option else 0)
    base = base[:cap]

    # 5. Append custom at the end.
    if custom_option:
        base.append(custom_option)

    # 6. Re-index IDs starting from 1.
    return [
        opt.model_copy(update={"id": idx})
        for idx, opt in enumerate(base, start=1)
    ]


def label_for_dynamic_value(
    field: str,
    value: str,
    cached_options: dict[str, list[dict]] | None,
) -> str | None:
    """Look up the Korean label for a dynamic slug from the cached options.

    This is the counterpart of ``option_label_for_value`` in option_registry,
    but searches the per-field LLM-generated cache stored in
    ``state["current_brief"]["cached_options"][field]``.

    Returns ``None`` if the field or value is not found in the cache.
    """
    if not cached_options or field not in cached_options:
        return None
    for opt in cached_options[field]:
        if isinstance(opt, dict) and opt.get("value") == value:
            return opt.get("label")
    return None
