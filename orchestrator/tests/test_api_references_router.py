import json

from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app
from orchestrator.app.reference_catalog.service import load_reference_templates


LOCAL_PATH_PATTERNS = [
    "C:\\",
    "C:/",
    "\\Users\\",
    "/home/",
    "data/reference_templates",
    "data/outputs",
    "data/processed",
]


def client() -> TestClient:
    return TestClient(create_app())


def assert_no_local_paths(payload: object) -> None:
    text = json.dumps(payload, ensure_ascii=False)
    for pattern in LOCAL_PATH_PATTERNS:
        assert pattern not in text


def test_create_app_openapi_registers_reference_routes():
    app = create_app()
    schema = app.openapi()

    assert schema["info"]["title"] == "EasyAds Orchestrator API"
    assert "/api/v1/references" in schema["paths"]
    assert "/api/v1/references/{template_id}" in schema["paths"]
    assert "/api/v1/references/{template_id}/similar" in schema["paths"]


def test_list_references_returns_items_and_pagination():
    response = client().get("/api/v1/references")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert isinstance(payload["items"], list)
    assert payload["items"]
    assert payload["pagination"]["total"] >= len(payload["items"])
    assert_no_local_paths(payload)


def test_reference_filters_and_sorting_work():
    http = client()

    by_category = http.get("/api/v1/references", params={"category": "cafe"})
    assert by_category.status_code == 200
    assert all(item["category"] == "cafe" for item in by_category.json()["items"])

    by_business = http.get("/api/v1/references", params={"business_type": "cafe"})
    assert by_business.status_code == 200
    assert all("cafe" in item["business_types"] for item in by_business.json()["items"])

    by_format = http.get("/api/v1/references", params={"ad_format": "instagram_feed"})
    assert by_format.status_code == 200
    assert all("instagram_feed" in item["ad_formats"] for item in by_format.json()["items"])

    by_keyword = http.get("/api/v1/references", params={"keyword": "cafe"})
    assert by_keyword.status_code == 200
    assert by_keyword.json()["items"]

    by_tags = http.get("/api/v1/references?tags=CTA&tags=CTA")
    assert by_tags.status_code == 200

    by_style = http.get("/api/v1/references?style_keywords=warm&style_keywords=cute")
    assert by_style.status_code == 200

    popular = http.get("/api/v1/references", params={"sort_by": "popular", "limit": 3})
    assert popular.status_code == 200
    scores = [item["popularity_score"] for item in popular.json()["items"]]
    assert scores == sorted(scores, reverse=True)


def test_limit_offset_and_empty_state():
    http = client()
    limited = http.get("/api/v1/references", params={"limit": 2, "offset": 1})
    assert limited.status_code == 200
    assert len(limited.json()["items"]) <= 2
    assert limited.json()["pagination"]["offset"] == 1

    empty = http.get("/api/v1/references", params={"keyword": "no-such-template-keyword"})
    payload = empty.json()
    assert empty.status_code == 200
    assert payload["items"] == []
    assert payload["empty_state"]["kind"] == "no_reference_templates"


def test_reference_detail_returns_slim_template_and_no_internal_paths():
    template = load_reference_templates()[0]
    response = client().get(f"/api/v1/references/{template.template_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["template"]["template_id"] == template.template_id
    assert "similar_templates" in payload
    assert "has_source_image" in payload["detail"]
    assert_no_local_paths(payload)


def test_reference_detail_not_found_returns_structured_error():
    response = client().get("/api/v1/references/not_found")

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["success"] is False
    assert detail["error_code"] == "reference_template_not_found"


def test_similar_references_excludes_self_and_applies_limit():
    template = load_reference_templates()[0]
    response = client().get(f"/api/v1/references/{template.template_id}/similar", params={"limit": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["template_id"] == template.template_id
    assert len(payload["items"]) <= 2
    assert all(item["template_id"] != template.template_id for item in payload["items"])
    assert_no_local_paths(payload)
