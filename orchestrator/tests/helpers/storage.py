from fastapi.testclient import TestClient
from pathlib import Path

from orchestrator.app.api.app import create_app
from PIL import Image


def make_api_client() -> TestClient:
    return TestClient(create_app())


def write_test_png(path: Path, *, size: tuple[int, int] = (64, 32), color=(255, 0, 0)) -> Path:
    Image.new("RGB", size, color=color).save(path)
    return path
