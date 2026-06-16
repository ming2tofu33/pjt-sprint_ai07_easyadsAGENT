"""Product visual context contracts."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def normalize_required_text(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("value must be a string")

    normalized = value.strip()
    if not normalized:
        raise ValueError("value must not be empty")

    return normalized


def normalize_string_list(
    values: Iterable[str] | None,
    *,
    deduplicate: bool = True,
) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        candidates: Iterable[str] = [values]
    else:
        candidates = values

    normalized: list[str] = []
    seen: set[str] = set()
    for value in candidates:
        if not isinstance(value, str):
            raise ValueError("list values must be strings")
        item = value.strip()
        if not item:
            continue
        if deduplicate and item in seen:
            continue
        normalized.append(item)
        seen.add(item)
    return tuple(normalized)


def normalize_category_path(values: Iterable[str] | None) -> tuple[str, ...]:
    return normalize_string_list(values, deduplicate=False)


class ProductVisualContext(BaseModel):
    """Evidence-backed product facts for visual routing.

    This model projects product identity and explicit visual facts only. It must
    not contain business environment, campaign, copy, provider, or strategy ids.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    product_name: str
    category_path: tuple[str, ...] = ()

    product_tags: tuple[str, ...] = ()
    visible_attributes: tuple[str, ...] = ()
    explicit_preparation_methods: tuple[str, ...] = ()

    permissible_visual_inferences: tuple[str, ...] = ()
    prohibited_visual_inferences: tuple[str, ...] = ()

    evidence_refs: tuple[str, ...] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("product_name", mode="before")
    @classmethod
    def normalize_product_name(cls, value: Any) -> str:
        return normalize_required_text(value)

    @field_validator("category_path", mode="before")
    @classmethod
    def normalize_category(cls, value: Any) -> tuple[str, ...]:
        return normalize_category_path(value)

    @field_validator(
        "product_tags",
        "visible_attributes",
        "explicit_preparation_methods",
        "permissible_visual_inferences",
        "prohibited_visual_inferences",
        "evidence_refs",
        mode="before",
    )
    @classmethod
    def normalize_list_field(cls, value: Any) -> tuple[str, ...]:
        return normalize_string_list(value)

    @model_validator(mode="after")
    def reject_exact_positive_negative_conflicts(self) -> "ProductVisualContext":
        positive_claims = (
            set(self.product_tags)
            | set(self.visible_attributes)
            | set(self.explicit_preparation_methods)
            | set(self.permissible_visual_inferences)
        )
        overlap = positive_claims & set(self.prohibited_visual_inferences)
        if overlap:
            raise ValueError(f"visual claim cannot be both positive and prohibited: {sorted(overlap)[0]}")
        return self
