"""Deterministic reference template catalog service."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

from orchestrator.app.reference_catalog.seed_templates import SEED_REFERENCE_TEMPLATES
from orchestrator.app.schemas.reference_catalog import (
    ReferenceTemplate,
    ReferenceTemplateSearchQuery,
    ReferenceTemplateSearchResult,
    ReferenceTemplateSelection,
)


TEMP_REFERENCE_FLAG_ENV = "EASYADS_ENABLE_TEMP_REFERENCES"
TEMP_REFERENCE_ROOT_ENV = "EASYADS_TEMP_REFERENCE_ROOT"
TEMP_REFERENCE_MANIFEST_NAME = "catalog.local.json"
DEFAULT_TEMP_REFERENCE_ROOT = Path("data/reference_templates/_temporary_unlicensed")
TEMP_REFERENCE_LICENSE_NOTE = "temporary local reference only; remove before release"


def temporary_references_enabled() -> bool:
    value = os.environ.get(TEMP_REFERENCE_FLAG_ENV, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def temporary_reference_root(root: str | Path | None = None) -> Path:
    if root is not None:
        return Path(root)
    return Path(os.environ.get(TEMP_REFERENCE_ROOT_ENV, DEFAULT_TEMP_REFERENCE_ROOT))


def load_reference_templates(include_temporary: bool | None = None) -> list[ReferenceTemplate]:
    templates = [ReferenceTemplate(**item) for item in SEED_REFERENCE_TEMPLATES]
    should_include_temporary = temporary_references_enabled() if include_temporary is None else include_temporary
    if should_include_temporary:
        templates.extend(load_temporary_reference_templates())
    return unique_templates_by_id(templates)


def load_temporary_reference_templates(root: str | Path | None = None) -> list[ReferenceTemplate]:
    root_path = temporary_reference_root(root)
    if not root_path.exists():
        return []

    templates: list[ReferenceTemplate] = []
    for manifest_path in temporary_reference_manifest_paths(root_path):
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        templates.extend(temporary_templates_from_manifest(payload, manifest_path))
    return templates


def temporary_reference_manifest_paths(root_path: Path) -> list[Path]:
    direct_manifest = root_path / TEMP_REFERENCE_MANIFEST_NAME
    manifests = [direct_manifest] if direct_manifest.is_file() else []
    manifests.extend(sorted(root_path.glob(f"*/{TEMP_REFERENCE_MANIFEST_NAME}")))
    return manifests


def temporary_templates_from_manifest(payload: Any, manifest_path: Path) -> list[ReferenceTemplate]:
    manifest_dir = manifest_path.parent
    if isinstance(payload, list):
        items = payload
        manifest_meta: dict[str, Any] = {}
    elif isinstance(payload, dict):
        items = payload.get("items") or payload.get("templates") or []
        manifest_meta = payload
    else:
        return []

    removal_group = str(manifest_meta.get("removal_group") or manifest_dir.name)
    return [temporary_template_from_item(item, manifest_dir=manifest_dir, removal_group=removal_group) for item in items]


def temporary_template_from_item(item: dict[str, Any], *, manifest_dir: Path, removal_group: str) -> ReferenceTemplate:
    data = dict(item)
    assets = dict(data.get("assets") or {})
    for field in ("thumbnail_path", "preview_path", "source_image_path"):
        if assets.get(field):
            assets[field] = normalize_temporary_asset_path(str(assets[field]), manifest_dir)
    if assets.get("thumbnail_path") and not assets.get("preview_path"):
        assets["preview_path"] = assets["thumbnail_path"]
    if (assets.get("preview_path") or assets.get("thumbnail_path")) and not assets.get("source_image_path"):
        assets["source_image_path"] = assets.get("preview_path") or assets.get("thumbnail_path")

    metadata = dict(data.get("metadata") or {})
    metadata.setdefault("temporary", True)
    metadata.setdefault("copyright_status", "unverified")
    metadata.setdefault("removal_group", removal_group)
    metadata.setdefault("local_only", True)

    data["assets"] = assets
    data["metadata"] = metadata
    data.setdefault("source", "external_placeholder")
    data.setdefault("status", "active")
    data.setdefault("license_note", TEMP_REFERENCE_LICENSE_NOTE)
    return ReferenceTemplate(**data)


def normalize_temporary_asset_path(value: str, manifest_dir: Path) -> str:
    asset_path = Path(value)
    if asset_path.is_absolute():
        return str(asset_path)
    return str(manifest_dir / asset_path)


def unique_templates_by_id(templates: list[ReferenceTemplate]) -> list[ReferenceTemplate]:
    seen: set[str] = set()
    result: list[ReferenceTemplate] = []
    for template in templates:
        if template.template_id in seen:
            continue
        seen.add(template.template_id)
        result.append(template)
    return result


def temporary_reference_asset_url(template: ReferenceTemplate, asset_kind: str) -> str | None:
    if not template.metadata.get("temporary"):
        return None
    removal_group = template.metadata.get("removal_group")
    if not removal_group:
        return None
    asset_path = getattr(template.assets, f"{asset_kind}_path", None)
    if not asset_path:
        return None
    filename = Path(asset_path).name
    if not filename:
        return None
    return f"/api/v1/references/temp-assets/{quote(str(removal_group), safe='')}/{quote(filename, safe='')}"


def temporary_reference_asset_path(removal_group: str, filename: str, root: str | Path | None = None) -> Path | None:
    root_path = temporary_reference_root(root).resolve()
    candidate = (root_path / Path(removal_group).name / Path(filename).name).resolve()
    try:
        candidate.relative_to(root_path)
    except ValueError:
        return None
    return candidate


def list_reference_templates(query: ReferenceTemplateSearchQuery | dict[str, Any] | None = None) -> ReferenceTemplateSearchResult:
    return search_reference_templates(query or ReferenceTemplateSearchQuery())


def get_reference_template(template_id: str) -> ReferenceTemplate | None:
    for template in load_reference_templates():
        if template.template_id == template_id:
            return template
    return None


def search_reference_templates(query: ReferenceTemplateSearchQuery | dict[str, Any]) -> ReferenceTemplateSearchResult:
    query_model = query if isinstance(query, ReferenceTemplateSearchQuery) else ReferenceTemplateSearchQuery(**query)
    scored: list[tuple[float, int, ReferenceTemplate]] = []
    for index, template in enumerate(load_reference_templates()):
        if not matches_query(template, query_model):
            continue
        scored.append((relevance_score(template, query_model), index, template))

    if query_model.sort_by == "popular":
        scored.sort(key=lambda item: item[2].popularity_score, reverse=True)
    elif query_model.sort_by == "title":
        scored.sort(key=lambda item: item[2].title)
    elif query_model.sort_by == "recent":
        scored.sort(key=lambda item: item[1], reverse=True)
    else:
        scored.sort(key=lambda item: (item[0], item[2].popularity_score), reverse=True)

    total = len(scored)
    page = [template for _, _, template in scored[query_model.offset : query_model.offset + query_model.limit]]
    return ReferenceTemplateSearchResult(
        items=page,
        total=total,
        limit=query_model.limit,
        offset=query_model.offset,
        query=query_model,
        metadata={"source": "seed", "deterministic": True},
    )


def find_similar_templates(template_id: str, limit: int = 8) -> list[ReferenceTemplate]:
    target = get_reference_template(template_id)
    if not target:
        return []
    scored = []
    for template in load_reference_templates():
        if template.template_id == template_id or template.status != "active":
            continue
        scored.append((similarity_score(target, template), template))
    scored.sort(key=lambda item: (item[0], item[1].popularity_score), reverse=True)
    return [template for score, template in scored[:limit] if score > 0]


def resolve_reference_template_selection(template_id: str) -> ReferenceTemplateSelection:
    template = get_reference_template(template_id)
    if not template:
        return ReferenceTemplateSelection(template_id=template_id, warnings=["reference_template_not_found"])
    style_hint = {
        "style_keywords": template.style_keywords,
        "color_palette": template.color_palette,
        "layout_hint": template.layout_hint,
        "typography_hint": template.typography_hint,
        "background_style": template.background_style,
        "category": template.category,
    }
    warnings: list[str] = []
    if not template.assets.source_image_path:
        warnings.append("reference_template_has_no_source_image_path")
    return ReferenceTemplateSelection(
        template_id=template_id,
        resolved_template=template,
        reference_image_path=template.assets.source_image_path,
        style_profile_hint=style_hint,
        warnings=warnings,
        metadata={"source": "seed", "deterministic": True},
    )


def matches_query(template: ReferenceTemplate, query: ReferenceTemplateSearchQuery) -> bool:
    if query.active_only and template.status != "active":
        return False
    if query.category and normalize(template.category) != normalize(query.category):
        return False
    if query.business_type and not contains(template.business_types, query.business_type):
        return False
    if query.ad_format and not contains(template.ad_formats, query.ad_format):
        return False
    if query.platform and not contains(template.platforms, query.platform):
        return False
    if query.aspect_ratio and normalize(template.aspect_ratio or "") != normalize(query.aspect_ratio):
        return False
    if query.tags and not all(contains(template.tags, tag) for tag in query.tags):
        return False
    if query.style_keywords and not all(contains(template.style_keywords, key) for key in query.style_keywords):
        return False
    if query.keyword and normalize(query.keyword) not in searchable_text(template):
        return False
    return True


def relevance_score(template: ReferenceTemplate, query: ReferenceTemplateSearchQuery) -> float:
    score = template.popularity_score
    if query.keyword and normalize(query.keyword) in normalize(template.title):
        score += 5
    if query.category and normalize(template.category) == normalize(query.category):
        score += 3
    if query.ad_format and contains(template.ad_formats, query.ad_format):
        score += 3
    if query.business_type and contains(template.business_types, query.business_type):
        score += 2
    score += overlap_count(template.tags, query.tags)
    score += overlap_count(template.style_keywords, query.style_keywords)
    return score


def similarity_score(left: ReferenceTemplate, right: ReferenceTemplate) -> float:
    score = 0.0
    if left.category == right.category:
        score += 3
    if set(left.ad_formats) & set(right.ad_formats):
        score += 3
    if left.aspect_ratio and left.aspect_ratio == right.aspect_ratio:
        score += 2
    score += len(set(map(normalize, left.tags)) & set(map(normalize, right.tags)))
    score += len(set(map(normalize, left.style_keywords)) & set(map(normalize, right.style_keywords)))
    score += len(set(map(normalize, left.business_types)) & set(map(normalize, right.business_types)))
    score += min(right.popularity_score, 1.0)
    return score


def searchable_text(template: ReferenceTemplate) -> str:
    parts = [
        template.title,
        template.description or "",
        template.category,
        *(template.tags or []),
        *(template.style_keywords or []),
        *(template.business_types or []),
    ]
    return normalize(" ".join(parts))


def normalize(value: str | None) -> str:
    return (value or "").strip().lower()


def contains(values: list[str], value: str) -> bool:
    return normalize(value) in {normalize(item) for item in values}


def overlap_count(left: list[str], right: list[str]) -> int:
    return len({normalize(item) for item in left} & {normalize(item) for item in right})
