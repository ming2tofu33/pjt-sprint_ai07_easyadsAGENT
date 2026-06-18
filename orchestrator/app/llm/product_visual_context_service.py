"""Deterministic assembly for product visual context."""

from __future__ import annotations

from collections.abc import Iterable

from orchestrator.app.schemas.input_evidence import EvidenceItem
from orchestrator.app.schemas.product_understanding import ProductUnderstanding
from orchestrator.app.schemas.product_visual_context import ProductVisualContext, normalize_string_list


def build_product_visual_context(
    *,
    product_name: str,
    category_path: Iterable[str] = (),
    product_tags: Iterable[str] = (),
    visible_attributes: Iterable[str] = (),
    explicit_preparation_methods: Iterable[str] = (),
    permissible_visual_inferences: Iterable[str] = (),
    prohibited_visual_inferences: Iterable[str] = (),
    evidence_refs: Iterable[str],
    confidence: float,
) -> ProductVisualContext:
    return ProductVisualContext(
        product_name=product_name,
        category_path=category_path,
        product_tags=product_tags,
        visible_attributes=visible_attributes,
        explicit_preparation_methods=explicit_preparation_methods,
        permissible_visual_inferences=permissible_visual_inferences,
        prohibited_visual_inferences=prohibited_visual_inferences,
        evidence_refs=evidence_refs,
        confidence=confidence,
    )


def product_visual_context_from_understanding(
    understanding: ProductUnderstanding,
    *,
    product_tags: Iterable[str] = (),
    visible_attributes: Iterable[str] = (),
    explicit_preparation_methods: Iterable[str] = (),
    permissible_visual_inferences: Iterable[str] = (),
    prohibited_visual_inferences: Iterable[str] = (),
    supplement_evidence_refs: Iterable[str] = (),
    confidence: float | None = None,
) -> ProductVisualContext:
    # Source mapping: product_name/category_path/confidence are direct. Tags and
    # visual facts project explicit upstream fields; missing target fields stay empty.
    supplement_product_tags = list(product_tags)
    supplement_visible_attributes = list(visible_attributes)
    supplement_preparation_methods = list(explicit_preparation_methods)
    supplement_permissible = list(permissible_visual_inferences)
    supplement_prohibited = list(prohibited_visual_inferences)
    normalized_supplement_refs = normalize_string_list(supplement_evidence_refs)
    has_supplements = any(
        (
            supplement_product_tags,
            supplement_visible_attributes,
            supplement_preparation_methods,
            supplement_permissible,
            supplement_prohibited,
        )
    )
    if has_supplements and not normalized_supplement_refs:
        raise ValueError("explicit product visual supplements require evidence refs")

    upstream_product_tags = [
        item
        for item in (
            understanding.normalized_product_type,
            understanding.product_variant,
            understanding.product_form,
        )
        if item
    ]
    upstream_visible_attributes = [_evidence_value(item) for item in understanding.visual_observations]
    upstream_permissible = [_evidence_value(item) for item in understanding.permissible_inferences]

    merged_evidence_refs = [
        *understanding.product_name_evidence_ids,
        *[item.evidence_id for item in understanding.verified_facts],
        *[item.evidence_id for item in understanding.visual_observations],
        *[item.evidence_id for item in understanding.permissible_inferences],
        *normalized_supplement_refs,
    ]

    return build_product_visual_context(
        product_name=understanding.product_name,
        category_path=understanding.category_path,
        product_tags=[*upstream_product_tags, *supplement_product_tags],
        visible_attributes=[*upstream_visible_attributes, *supplement_visible_attributes],
        explicit_preparation_methods=supplement_preparation_methods,
        permissible_visual_inferences=[*upstream_permissible, *supplement_permissible],
        prohibited_visual_inferences=supplement_prohibited,
        evidence_refs=merged_evidence_refs,
        confidence=understanding.confidence if confidence is None else confidence,
    )


def _evidence_value(item: EvidenceItem) -> str:
    return item.normalized_value or item.value
