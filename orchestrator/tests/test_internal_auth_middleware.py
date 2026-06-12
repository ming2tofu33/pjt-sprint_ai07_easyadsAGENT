"""Tests for the internal API secret middleware."""

from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_requests_pass_when_secret_not_configured(monkeypatch):
    # Empty value counts as "present in os.environ" for _get_env, so this
    # also shields the test from any future .env fallback entry.
    monkeypatch.setenv("EASYADS_INTERNAL_API_SECRET", "")
    client = _client()
    assert client.get("/health").status_code == 200
    # Nonexistent route reaches the router (404), proving no 401 gate.
    assert client.get("/api/v1/this-route-does-not-exist").status_code == 404


def test_missing_secret_header_is_rejected_when_configured(monkeypatch):
    monkeypatch.setenv("EASYADS_INTERNAL_API_SECRET", "test-internal-secret")
    client = _client()
    response = client.get("/api/v1/this-route-does-not-exist")
    assert response.status_code == 401
    body = response.json()
    assert body["error_code"] == "invalid_internal_secret"
    assert body["success"] is False


def test_wrong_secret_header_is_rejected(monkeypatch):
    monkeypatch.setenv("EASYADS_INTERNAL_API_SECRET", "test-internal-secret")
    client = _client()
    response = client.get(
        "/api/v1/this-route-does-not-exist",
        headers={"X-EasyAds-Internal-Secret": "wrong-secret"},
    )
    assert response.status_code == 401


def test_correct_secret_header_passes_middleware(monkeypatch):
    monkeypatch.setenv("EASYADS_INTERNAL_API_SECRET", "test-internal-secret")
    client = _client()
    response = client.get(
        "/api/v1/this-route-does-not-exist",
        headers={"X-EasyAds-Internal-Secret": "test-internal-secret"},
    )
    # 404 (not 401): the request got past the middleware to the router.
    assert response.status_code == 404


def test_health_is_exempt_even_when_secret_configured(monkeypatch):
    monkeypatch.setenv("EASYADS_INTERNAL_API_SECRET", "test-internal-secret")
    client = _client()
    assert client.get("/health").status_code == 200
