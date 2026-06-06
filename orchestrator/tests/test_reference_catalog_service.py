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
    assert search_reference_templates({"tags": ["딸기"]}).items
    assert search_reference_templates({"style_keywords": ["premium"]}).items
    assert search_reference_templates({"keyword": "딸기"}).items

    popular = search_reference_templates({"sort_by": "popular"}).items
    title = search_reference_templates({"sort_by": "title"}).items

    assert popular[0].popularity_score >= popular[-1].popularity_score
    assert title == sorted(title, key=lambda item: item.title)


def test_food_and_drink_keywords_include_cafe_results(monkeypatch):
    monkeypatch.delenv("EASYADS_ENABLE_TEMP_REFERENCES", raising=False)

    food_items = search_reference_templates({"keyword": "음식", "limit": 20}).items
    drink_items = search_reference_templates({"keyword": "음료", "limit": 20}).items
    english_drink_items = search_reference_templates({"keyword": "drink", "limit": 20}).items

    assert any(item.category == "cafe" for item in food_items)
    assert any(item.category == "restaurant" for item in food_items)
    assert any(item.category == "cafe" for item in drink_items)
    assert any(item.category == "cafe" for item in english_drink_items)


def test_multi_tag_search_matches_any_expanded_reference_term(monkeypatch):
    monkeypatch.delenv("EASYADS_ENABLE_TEMP_REFERENCES", raising=False)

    items = search_reference_templates({"tags": ["음료", "삼겹살"], "limit": 20}).items
    categories = {item.category for item in items}

    assert {"cafe", "restaurant"} <= categories


def test_permanent_references_load_from_manifest(monkeypatch, tmp_path):
    manifest_path = tmp_path / "permanent-catalog.json"
    manifest = {
        "items": [
            {
                "template_id": "ref_test_cafe_owned_001",
                "title": "운영 카페 샘플 테스트",
                "category": "cafe",
                "tags": ["음료"],
                "business_types": ["cafe"],
                "ad_formats": ["instagram_feed"],
                "platforms": ["instagram"],
                "assets": {
                    "thumbnail_path": "r2://reference-templates/v1/ref_test_cafe_owned_001/source.png"
                },
                "style_keywords": ["clean"],
                "popularity_score": 0.5,
            }
        ]
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("EASYADS_PERMANENT_REFERENCE_MANIFEST", str(manifest_path))

    template = get_reference_template("ref_test_cafe_owned_001")
    selection = resolve_reference_template_selection("ref_test_cafe_owned_001")

    assert template is not None
    assert template.source == "admin_upload"
    assert template.metadata["permanent"] is True
    assert template.metadata["copyright_status"] == "owned_or_licensed"
    assert template.assets.preview_path == "r2://reference-templates/v1/ref_test_cafe_owned_001/source.png"
    assert template.assets.source_image_path == "r2://reference-templates/v1/ref_test_cafe_owned_001/source.png"
    assert selection.reference_image_path == "r2://reference-templates/v1/ref_test_cafe_owned_001/source.png"
    assert "reference_template_has_no_source_image_path" not in selection.warnings


def test_broad_food_category_includes_cafe_and_restaurant(monkeypatch):
    monkeypatch.delenv("EASYADS_ENABLE_TEMP_REFERENCES", raising=False)

    food_items = search_reference_templates({"category": "food", "limit": 20}).items

    assert any(item.category == "cafe" for item in food_items)
    assert any(item.category == "restaurant" for item in food_items)


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
