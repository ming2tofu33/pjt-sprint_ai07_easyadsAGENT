from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app


def test_marketing_chat_start_standard_prefix_exists():
    client = TestClient(create_app())
    response = client.post("/api/v1/marketing/chat/start", json={"userInput": "카페 광고"})

    assert response.status_code != 404


def test_legacy_marketing_chat_start_prefix_still_exists():
    client = TestClient(create_app())
    response = client.post("/v1/marketing/chat/start", json={"userInput": "카페 광고"})

    assert response.status_code != 404


def test_marketing_photo_start_standard_prefix_exists():
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/marketing/photo/start",
        json={"userInput": "카페 광고", "sourceImagePath": "data/uploads/sample.png"},
    )

    assert response.status_code != 404


def test_legacy_marketing_photo_start_prefix_still_exists():
    client = TestClient(create_app())
    response = client.post(
        "/v1/marketing/photo/start",
        json={"userInput": "카페 광고", "sourceImagePath": "data/uploads/sample.png"},
    )

    assert response.status_code != 404
