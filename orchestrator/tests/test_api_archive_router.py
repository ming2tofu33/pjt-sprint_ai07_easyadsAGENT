from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app
from orchestrator.app.api.routers import archive as archive_router
from orchestrator.app.api.schemas.archive import ArchiveItemResponse


def client() -> TestClient:
    return TestClient(create_app())


def test_openapi_registers_archive_routes():
    schema = create_app().openapi()

    assert "/api/v1/archive/items" in schema["paths"]
    assert "/api/v1/archive/items/{archive_item_id}" in schema["paths"]


def test_archive_save_returns_503_when_persistence_is_disabled(monkeypatch):
    monkeypatch.delenv("EASYADS_DB_BACKEND", raising=False)

    response = client().post(
        "/api/v1/archive/items",
        json={"title": "봄을 닮은 한 잔", "public_job_id": "job_1", "image_url": "/api/generated-assets?path=x"},
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["success"] is False
    assert detail["error_code"] == "archive_storage_unavailable"


def test_archive_save_list_update_and_delete_routes(monkeypatch):
    item = ArchiveItemResponse(
        ad_id="archive_1",
        job_id="job_1",
        title="봄을 닮은 한 잔",
        image_url="/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal.png",
        status="saved",
        source="generated",
    )
    captured = {}

    def fake_create_archive_item(request):
        captured["request"] = request
        return item

    monkeypatch.setattr(archive_router, "create_archive_item", fake_create_archive_item)
    monkeypatch.setattr(archive_router, "list_archive_items", lambda workspace_id=None, user_id=None, limit=50, offset=0: ([item], 1))
    monkeypatch.setattr(archive_router, "update_archive_item", lambda archive_item_id, request: item.model_copy(update={"status": request.status}))
    monkeypatch.setattr(archive_router, "delete_archive_item", lambda archive_item_id, workspace_id=None, user_id=None: item)

    http = client()
    created = http.post(
        "/api/v1/archive/items",
        json={
            "title": "봄을 닮은 한 잔",
            "public_job_id": "job_1",
            "image_url": "/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal.png",
            "ad_format": "1:1",
            "platform": "인스타 피드",
            "source": "generated",
            "metadata": {"tags": ["카페"]},
        },
    )
    listed = http.get("/api/v1/archive/items", params={"limit": 20})
    updated = http.patch("/api/v1/archive/items/archive_1", json={"status": "favorite"})
    deleted = http.delete("/api/v1/archive/items/archive_1")

    assert created.status_code == 201
    assert created.json()["item"]["ad_id"] == "archive_1"
    assert captured["request"].public_job_id == "job_1"
    assert listed.status_code == 200
    assert listed.json()["pagination"]["total"] == 1
    assert updated.status_code == 200
    assert updated.json()["item"]["status"] == "favorite"
    assert deleted.status_code == 200
    assert deleted.json()["item"]["job_id"] == "job_1"


def test_archive_list_update_and_delete_pass_user_id(monkeypatch):
    item = ArchiveItemResponse(
        ad_id="archive_1",
        job_id="job_1",
        title="봄을 닮은 한 잔",
        status="saved",
        source="generated",
    )
    captured = {}

    def fake_list_archive_items(workspace_id=None, user_id=None, limit=50, offset=0):
        captured["list_user_id"] = user_id
        return [item], 1

    def fake_update_archive_item(archive_item_id, request):
        captured["update_user_id"] = request.user_id
        return item.model_copy(update={"status": request.status})

    def fake_delete_archive_item(archive_item_id, workspace_id=None, user_id=None):
        captured["delete_user_id"] = user_id
        return item

    monkeypatch.setattr(archive_router, "list_archive_items", fake_list_archive_items)
    monkeypatch.setattr(archive_router, "update_archive_item", fake_update_archive_item)
    monkeypatch.setattr(archive_router, "delete_archive_item", fake_delete_archive_item)

    http = client()
    listed = http.get("/api/v1/archive/items", params={"user_id": "user_uuid_1"})
    updated = http.patch("/api/v1/archive/items/archive_1", json={"status": "favorite", "user_id": "user_uuid_1"})
    deleted = http.delete("/api/v1/archive/items/archive_1", params={"user_id": "user_uuid_1"})

    assert listed.status_code == 200
    assert updated.status_code == 200
    assert deleted.status_code == 200
    assert captured == {"list_user_id": "user_uuid_1", "update_user_id": "user_uuid_1", "delete_user_id": "user_uuid_1"}
