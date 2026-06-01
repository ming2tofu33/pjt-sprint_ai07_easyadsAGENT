from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app
from orchestrator.app.main import app as main_app


def test_create_app_registers_legacy_and_new_routes():
    schema = create_app().openapi()

    assert "/health" in schema["paths"]
    assert "/v1/marketing/chat/start" in schema["paths"]
    assert "/api/v1/references" in schema["paths"]
    assert "/api/v1/brand-kits/current" in schema["paths"]
    assert "/api/v1/generation-jobs" in schema["paths"]


def test_main_app_exposes_unified_routes():
    schema = main_app.openapi()

    assert "/health" in schema["paths"]
    assert "/v1/marketing/chat/start" in schema["paths"]
    assert "/api/v1/references" in schema["paths"]
    assert "/api/v1/brand-kits/current" in schema["paths"]
    assert "/api/v1/generation-jobs" in schema["paths"]


def test_health_route_still_works_from_main_app():
    response = TestClient(main_app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
