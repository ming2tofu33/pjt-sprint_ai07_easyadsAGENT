from orchestrator.tests.factories.api_payloads import (
    marketing_chat_start_payload,
    marketing_photo_start_payload,
)
from orchestrator.tests.helpers.api_clients import create_app_client


def test_marketing_chat_start_standard_prefix_exists():
    response = create_app_client().post("/api/v1/marketing/chat/start", json=marketing_chat_start_payload())

    assert response.status_code != 404


def test_legacy_marketing_chat_start_prefix_still_exists():
    response = create_app_client().post("/v1/marketing/chat/start", json=marketing_chat_start_payload())

    assert response.status_code != 404


def test_marketing_photo_start_standard_prefix_exists():
    response = create_app_client().post(
        "/api/v1/marketing/photo/start",
        json=marketing_photo_start_payload(),
    )

    assert response.status_code != 404


def test_legacy_marketing_photo_start_prefix_still_exists():
    response = create_app_client().post(
        "/v1/marketing/photo/start",
        json=marketing_photo_start_payload(),
    )

    assert response.status_code != 404
