from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app
from orchestrator.app.api.routers import archive as archive_router
from orchestrator.app.api.routers import assets as assets_router
from orchestrator.app.api.routers import chat_threads as chat_threads_router
from orchestrator.app.api.schemas.archive import ArchiveItemResponse
from orchestrator.app.api.schemas.assets import AssetInfo, AssetPresignResponse, UploadInstruction


def test_resolve_workspace_scope_forwards_guest_account_type(monkeypatch):
    from orchestrator.app.db import workspace_scope

    captured = {}

    def fake_ensure_user_workspace(user_id, account_type=None, connection=None):
        captured.update({"user_id": user_id, "account_type": account_type, "connection": connection})
        return {"id": "workspace_guest"}

    monkeypatch.setattr(workspace_scope.workspace_repo, "ensure_user_workspace", fake_ensure_user_workspace)
    monkeypatch.setattr(workspace_scope.db_settings, "get_demo_user_id", lambda: None)

    workspace_id = workspace_scope.resolve_workspace_scope(user_id="guest_uuid_1", account_type="guest")

    assert workspace_id == "workspace_guest"
    assert captured == {"user_id": "guest_uuid_1", "account_type": "guest", "connection": None}


def test_archive_routes_pass_account_type_to_service(monkeypatch):
    item = ArchiveItemResponse(
        ad_id="archive_1",
        job_id="job_1",
        title="Guest archive",
        status="saved",
        source="generated",
    )
    captured = {}

    def fake_create_archive_item(request):
        captured["create_account_type"] = getattr(request, "account_type", None)
        return item

    def fake_list_archive_items(workspace_id=None, user_id=None, account_type=None, limit=50, offset=0):
        captured["list_account_type"] = account_type
        return [item], 1

    monkeypatch.setattr(archive_router, "create_archive_item", fake_create_archive_item)
    monkeypatch.setattr(archive_router, "list_archive_items", fake_list_archive_items)

    http = TestClient(create_app())
    created = http.post(
        "/api/v1/archive/items",
        json={"title": "Guest archive", "public_job_id": "job_1", "accountType": "guest"},
    )
    listed = http.get("/api/v1/archive/items", params={"user_id": "guest_uuid_1", "account_type": "guest"})

    assert created.status_code == 201
    assert listed.status_code == 200
    assert captured == {"create_account_type": "guest", "list_account_type": "guest"}


def test_asset_presign_route_passes_account_type_to_service(monkeypatch):
    captured = {}

    def fake_presign_asset_upload(req, *, user_id=None, account_type=None):
        captured.update({"user_id": user_id, "account_type": account_type})
        return AssetPresignResponse(
            asset=AssetInfo(asset_id="asset_123", kind=req.kind, status="pending"),
            upload=UploadInstruction(method="PUT", url="https://r2.example.com/upload", expires_at="2026-06-11T00:00:00+00:00"),
        )

    monkeypatch.setattr(assets_router.service, "presign_asset_upload", fake_presign_asset_upload)

    response = TestClient(create_app()).post(
        "/api/v1/assets/uploads/presign",
        params={"user_id": "guest_uuid_1", "account_type": "guest"},
        json={"kind": "source", "filename": "source.png", "mimeType": "image/png", "sizeBytes": 1024},
    )

    assert response.status_code == 200
    assert captured == {"user_id": "guest_uuid_1", "account_type": "guest"}


def test_chat_thread_route_passes_account_type_to_service(monkeypatch):
    captured = {}

    def fake_list_chat_threads(user_id=None, account_type=None, include_archived=False, limit=50, offset=0, include_total=True):
        captured.update({
            "user_id": user_id,
            "account_type": account_type,
            "include_archived": include_archived,
            "include_total": include_total,
        })
        return [], 0

    monkeypatch.setattr(chat_threads_router.chat_service, "list_chat_threads", fake_list_chat_threads)

    response = TestClient(create_app()).get(
        "/api/v1/chat-threads",
        params={"userId": "guest_uuid_1", "accountType": "guest", "include_archived": "true", "include_total": "false"},
    )

    assert response.status_code == 200
    assert captured == {
        "user_id": "guest_uuid_1",
        "account_type": "guest",
        "include_archived": True,
        "include_total": False,
    }
