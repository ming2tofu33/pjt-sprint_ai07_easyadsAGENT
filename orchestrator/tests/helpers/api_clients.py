from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app
from orchestrator.app.main import app as main_app


def create_app_client() -> TestClient:
    return TestClient(create_app())


def create_main_app_client() -> TestClient:
    return TestClient(main_app)
