from orchestrator.app.reference_catalog.service import db_reference_template_from_row, resolve_reference_template_selection


def test_db_reference_template_maps_asset_metadata():
    template = db_reference_template_from_row({
        "template_id": "ref_admin_cafe",
        "title": "관리자 카페 샘플",
        "category": "cafe",
        "tags": ["음료"],
        "business_types": ["cafe"],
        "ad_formats": ["instagram_feed"],
        "platforms": ["instagram"],
        "width": 1200,
        "height": 900,
        "asset_public_id": "asset_abc",
        "source_image_path": "r2://workspaces/ws/uploads/asset_abc/original.png",
        "style_keywords": ["clean"],
        "color_palette": ["#FFFFFF"],
        "metadata": {"storage_provider": "r2"},
        "status": "active",
    })

    assert template.metadata["reference_asset_id"] == "asset_abc"
    assert template.assets.source_image_path == "r2://workspaces/ws/uploads/asset_abc/original.png"


def test_selection_exposes_reference_asset_id(monkeypatch):
    template = db_reference_template_from_row({
        "template_id": "ref_admin_cafe",
        "title": "관리자 카페 샘플",
        "category": "cafe",
        "tags": ["음료"],
        "business_types": ["cafe"],
        "ad_formats": ["instagram_feed"],
        "platforms": ["instagram"],
        "asset_public_id": "asset_abc",
        "source_image_path": "r2://workspaces/ws/uploads/asset_abc/original.png",
        "style_keywords": ["clean"],
        "color_palette": ["#FFFFFF"],
        "metadata": {"storage_provider": "r2"},
        "status": "active",
    })
    monkeypatch.setattr("orchestrator.app.reference_catalog.service.load_reference_templates", lambda: [template])

    selection = resolve_reference_template_selection("ref_admin_cafe")

    assert selection.reference_asset_id == "asset_abc"
    assert selection.reference_image_path == "r2://workspaces/ws/uploads/asset_abc/original.png"
