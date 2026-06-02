import json

from orchestrator.app.reference_catalog.service import (
    find_similar_templates,
    get_reference_template,
    list_reference_templates,
    load_reference_templates,
    resolve_reference_template_selection,
    search_reference_templates,
)


def test_seed_templates_load_with_diverse_categories():
    templates = load_reference_templates()
    categories = {template.category for template in templates}

    assert len(templates) >= 8
    assert {"cafe", "restaurant", "beauty", "fitness", "retail", "event", "flyer", "banner"} <= categories


def test_search_filters_and_sorting():
    assert all(item.category == "cafe" for item in search_reference_templates({"category": "cafe"}).items)
    assert all("cafe" in item.business_types for item in search_reference_templates({"business_type": "cafe"}).items)
    assert all("instagram_feed" in item.ad_formats for item in search_reference_templates({"ad_format": "instagram_feed"}).items)
    assert all("instagram" in item.platforms for item in search_reference_templates({"platform": "instagram"}).items)
    assert search_reference_templates({"tags": ["딸기"]}).items[0].template_id == "seed_cafe_strawberry_feed_001"
    assert search_reference_templates({"style_keywords": ["premium"]}).items
    assert search_reference_templates({"keyword": "딸기"}).items

    popular = search_reference_templates({"sort_by": "popular"}).items
    title = search_reference_templates({"sort_by": "title"}).items

    assert popular[0].popularity_score >= popular[-1].popularity_score
    assert title == sorted(title, key=lambda item: item.title)


def test_limit_offset_and_list_alias():
    page = search_reference_templates({"limit": 2, "offset": 1})
    listed = list_reference_templates({"limit": 2, "offset": 1})

    assert len(page.items) == 2
    assert page.offset == 1
    assert [item.template_id for item in page.items] == [item.template_id for item in listed.items]


def test_detail_similar_and_selection():
    template = get_reference_template("seed_cafe_strawberry_feed_001")
    missing = get_reference_template("missing")
    similar = find_similar_templates("seed_cafe_strawberry_feed_001", limit=3)
    selection = resolve_reference_template_selection("seed_cafe_strawberry_feed_001")
    invalid = resolve_reference_template_selection("missing")

    assert template is not None
    assert missing is None
    assert similar
    assert all(item.template_id != "seed_cafe_strawberry_feed_001" for item in similar)
    assert len(similar) <= 3
    assert selection.resolved_template is not None
    assert "reference_template_has_no_source_image_path" in selection.warnings
    assert invalid.resolved_template is None
    assert "reference_template_not_found" in invalid.warnings


def test_temporary_references_require_local_flag(monkeypatch, tmp_path):
    manifest_dir = tmp_path / "2026-06-user-refs"
    manifest_dir.mkdir()
    image_path = manifest_dir / "watermelon-juice.png"
    image_path.write_bytes(b"temporary image")
    manifest = {
        "removal_group": "2026-06-user-refs",
        "items": [
            {
                "template_id": "temp_watermelon_juice_feed",
                "title": "수박주스 블루 여름 피드",
                "category": "cafe",
                "tags": ["수박", "여름"],
                "business_types": ["cafe"],
                "ad_formats": ["instagram_feed"],
                "platforms": ["instagram"],
                "assets": {
                    "thumbnail_path": "watermelon-juice.png",
                    "preview_path": "watermelon-juice.png",
                },
                "style_keywords": ["summer", "blue"],
                "color_palette": ["#5AB4F2", "#EF3B3B"],
                "layout_hint": "top_large_headline_center_product_bottom_copy",
                "background_style": "bright blue summer beverage poster",
                "popularity_score": 0.5,
            }
        ],
    }
    (manifest_dir / "catalog.local.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("EASYADS_TEMP_REFERENCE_ROOT", str(tmp_path))
    monkeypatch.delenv("EASYADS_ENABLE_TEMP_REFERENCES", raising=False)

    assert get_reference_template("temp_watermelon_juice_feed") is None

    monkeypatch.setenv("EASYADS_ENABLE_TEMP_REFERENCES", "true")

    template = get_reference_template("temp_watermelon_juice_feed")
    selection = resolve_reference_template_selection("temp_watermelon_juice_feed")

    assert template is not None
    assert template.metadata["temporary"] is True
    assert template.metadata["copyright_status"] == "unverified"
    assert template.metadata["removal_group"] == "2026-06-user-refs"
    assert template.assets.source_image_path == str(image_path)
    assert selection.reference_image_path == str(image_path)
    assert "reference_template_has_no_source_image_path" not in selection.warnings
