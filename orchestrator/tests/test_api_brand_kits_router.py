import pytest
from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app
from orchestrator.app.brand_kits.service import reset_brand_kit_store_for_tests


@pytest.fixture(autouse=True)
def reset_store():
    reset_brand_kit_store_for_tests()
    yield
    reset_brand_kit_store_for_tests()


def client() -> TestClient:
    return TestClient(create_app())


def test_openapi_registers_references_and_brand_kit_routes():
    schema = create_app().openapi()

    assert "/api/v1/references" in schema["paths"]
    assert "/api/v1/brand-kits/current" in schema["paths"]
    assert "/api/v1/brand-kits" in schema["paths"]
    assert "/api/v1/brand-kits/{brand_kit_id}" in schema["paths"]


def test_current_brand_kit_empty_state_then_created_current():
    http = client()

    empty = http.get("/api/v1/brand-kits/current")
    assert empty.status_code == 200
    empty_payload = empty.json()
    assert empty_payload["success"] is True
    assert empty_payload["has_brand_kit"] is False
    assert empty_payload["empty_state"]["kind"] == "no_brand_kit"

    created = http.post(
        "/api/v1/brand-kits",
        json={"store_name": "Moon Cafe", "business_type": "cafe", "brand_colors": ["#F6A5B8"]},
    )
    assert created.status_code == 200
    created_payload = created.json()
    assert created_payload["success"] is True
    assert created_payload["brand_kit"]["brand_kit_id"].startswith("bk_")

    current = http.get("/api/v1/brand-kits/current")
    assert current.status_code == 200
    assert current.json()["brand_kit"]["brand_kit_id"] == created_payload["brand_kit"]["brand_kit_id"]


def test_get_and_patch_brand_kit():
    http = client()
    created = http.post(
        "/api/v1/brand-kits",
        json={"user_id": "user_1", "store_name": "Moon Cafe", "business_type": "cafe"},
    ).json()
    brand_kit_id = created["brand_kit"]["brand_kit_id"]

    fetched = http.get(f"/api/v1/brand-kits/{brand_kit_id}")
    assert fetched.status_code == 200
    assert fetched.json()["brand_kit"]["brand_kit_id"] == brand_kit_id

    patched = http.patch(
        f"/api/v1/brand-kits/{brand_kit_id}",
        json={"store_name": "Sun Cafe", "brand_tones": ["premium"], "brand_colors": []},
    )
    assert patched.status_code == 200
    patched_payload = patched.json()["brand_kit"]
    assert patched_payload["store_name"] == "Sun Cafe"
    assert patched_payload["brand_tones"] == ["premium"]
    assert patched_payload["brand_colors"] == []


def test_invalid_brand_kit_id_returns_structured_404():
    response = client().get("/api/v1/brand-kits/bk_missing")

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["success"] is False
    assert detail["error_code"] == "brand_kit_not_found"


def test_invalid_update_returns_structured_400():
    http = client()
    brand_kit_id = http.post(
        "/api/v1/brand-kits",
        json={"store_name": "Moon Cafe", "business_type": "cafe"},
    ).json()["brand_kit"]["brand_kit_id"]

    response = http.patch(f"/api/v1/brand-kits/{brand_kit_id}", json={"store_name": ""})

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["error_code"] == "invalid_brand_kit_request"


def test_brand_colors_validation_returns_400():
    response = client().post(
        "/api/v1/brand-kits",
        json={"store_name": "Moon Cafe", "business_type": "cafe", "brand_colors": ["F6A5B8"]},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "invalid_brand_kit_request"
