"""Archive list/detail API 계약 테스트 (Section 8.2 / 11.5 요구사항).

Archive detail endpoint, workspace scope, client URL 무시, 409 등.
"""

from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from orchestrator.app.api.app import create_app
from orchestrator.app.api.schemas.archive import ArchiveItemResponse
from orchestrator.app.api.routers import archive as archive_router
from orchestrator.app.archive.service import ArchivePersistenceUnavailable, ArchiveItemNotFound


def make_client():
    return TestClient(create_app())


# ---------------------------------------------------------------------------
# Archive detail GET /api/v1/archive/items/{id}
# ---------------------------------------------------------------------------

def test_archive_detail_200(monkeypatch):
    """GET /api/v1/archive/items/{id} → 200 및 올바른 필드 반환."""
    item = ArchiveItemResponse(
        ad_id="archive_pub_1",
        job_id="job_pub_1",
        output_id="out_pub_1",
        thread_id="thread_pub_1",
        title="테스트 광고",
        image_url="https://cdn.example.com/image.png",
        status="saved",
        source="generated",
    )
    monkeypatch.setattr(archive_router, "get_archive_item", lambda archive_item_id, workspace_id=None, user_id=None: item)

    resp = make_client().get("/api/v1/archive/items/archive_pub_1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ad_id"] == "archive_pub_1"
    assert data["job_id"] == "job_pub_1"
    assert data["output_id"] == "out_pub_1"
    assert data["image_url"] == "https://cdn.example.com/image.png"


def test_archive_detail_404(monkeypatch):
    """존재하지 않는 archive_item_id → 404."""
    monkeypatch.setattr(
        archive_router, "get_archive_item",
        lambda archive_item_id, workspace_id=None, user_id=None: (_ for _ in ()).throw(ArchiveItemNotFound("not found"))
    )

    resp = make_client().get("/api/v1/archive/items/nonexistent")
    assert resp.status_code == 404
    body = resp.json()
    assert body["detail"]["error_code"] == "archive_item_not_found"


def test_archive_detail_user_isolation(monkeypatch):
    """동일 workspace+user 성공, 동일 workspace+다른 user 404, 다른 workspace 404 검증."""
    import orchestrator.app.archive.service as svc

    # patch helpers
    monkeypatch.setattr(svc, "_ensure_postgres_enabled", lambda: None)
    monkeypatch.setattr(svc, "_resolve_user_id", lambda user_id: user_id or "u1")
    monkeypatch.setattr(svc, "_resolve_workspace_id", lambda wid, user_id=None, **_: wid or "ws1")

    # get_archive_item_row mock
    repo_mock = MagicMock()
    
    def fake_get_row(public_archive_id, workspace_id, created_by=None):
        if workspace_id == "ws1" and created_by == "u1":
            return {"public_archive_id": public_archive_id, "title": "my ad"}
        return None
        
    repo_mock.get_archive_item_row.side_effect = fake_get_row
    monkeypatch.setattr(svc, "archive_item_repo", repo_mock)

    # 1. ws1, u1 -> 성공
    res1 = svc.get_archive_item(archive_item_id="a1", workspace_id="ws1", user_id="u1")
    assert res1.ad_id == "a1"

    # 2. ws1, u2 -> 404
    try:
        svc.get_archive_item(archive_item_id="a1", workspace_id="ws1", user_id="u2")
        assert False, "Should raise ArchiveItemNotFound"
    except ArchiveItemNotFound:
        pass

    # 3. ws2, u1 -> 404
    try:
        svc.get_archive_item(archive_item_id="a1", workspace_id="ws2", user_id="u1")
        assert False, "Should raise ArchiveItemNotFound"
    except ArchiveItemNotFound:
        pass


def test_archive_detail_503_when_db_disabled(monkeypatch):
    """DB 비활성화 시 503."""
    monkeypatch.setattr(
        archive_router, "get_archive_item",
        lambda archive_item_id, workspace_id=None, user_id=None: (_ for _ in ()).throw(ArchivePersistenceUnavailable("DB disabled"))
    )

    resp = make_client().get("/api/v1/archive/items/archive_1?workspace_id=ws1")
    assert resp.status_code == 503
    assert resp.json()["detail"]["error_code"] == "archive_storage_unavailable"


# ---------------------------------------------------------------------------
# Archive create: generated source
# ---------------------------------------------------------------------------

def test_archive_create_returns_409_when_final_output_not_ready(monkeypatch):
    """source=generated 인 경우 final output이 없으면 409 반환."""
    from orchestrator.app.archive.service import ArchiveGenerationOutputNotReady

    monkeypatch.setattr(
        archive_router, "create_archive_item",
        lambda req: (_ for _ in ()).throw(ArchiveGenerationOutputNotReady("Final output not ready"))
    )

    resp = make_client().post(
        "/api/v1/archive/items",
        json={
            "title": "내 광고",
            "public_job_id": "job1",
            "image_url": "https://evil.com/injected.png",
            "source": "generated",
        },
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "generation_output_not_ready"


def test_archive_create_generated_source_ignores_client_urls_on_success(monkeypatch):
    """source=generated 인 경우 성공 응답에서 클라이언트 URL을 무시하고 서버 결정 URL을 반환한다."""
    server_item = ArchiveItemResponse(
        ad_id="archive_1",
        job_id="job1",
        output_id="output1",
        title="광고",
        image_url="https://r2.example.com/server-final.png",
        status="saved",
        source="generated",
    )

    monkeypatch.setattr(
        archive_router,
        "create_archive_item",
        lambda request: server_item,
    )

    response = make_client().post(
        "/api/v1/archive/items",
        json={
            "title": "광고",
            "public_job_id": "job1",
            "image_url": "https://evil.com/injected.png",
            "thumbnail_url": "https://evil.com/thumb.png",
            "source": "generated",
        },
    )

    assert response.status_code == 201
    item = response.json()["item"]
    assert item["image_url"] == "https://r2.example.com/server-final.png"
    assert item["image_url"] != "https://evil.com/injected.png"


# ---------------------------------------------------------------------------
# Archive list: workspace scope 적용
# ---------------------------------------------------------------------------

def test_archive_list_returns_empty_state_when_no_items(monkeypatch):
    """항목 없을 때 empty_state 포함."""
    monkeypatch.setattr(
        archive_router, "list_archive_items",
        lambda workspace_id=None, user_id=None, limit=50, offset=0: ([], 0),
    )
    resp = make_client().get("/api/v1/archive/items?workspace_id=ws1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["empty_state"] is not None
    assert body["empty_state"]["kind"] == "no_archive_items"


def test_archive_list_pagination(monkeypatch):
    """pagination 필드 검증."""
    item = ArchiveItemResponse(ad_id="a1", title="광고", status="saved", source="generated")
    monkeypatch.setattr(
        archive_router, "list_archive_items",
        lambda workspace_id=None, user_id=None, limit=1, offset=0: ([item], 5),
    )
    resp = make_client().get("/api/v1/archive/items?limit=1&offset=0")
    assert resp.status_code == 200
    pg = resp.json()["pagination"]
    assert pg["total"] == 5
    assert pg["limit"] == 1
    assert pg["offset"] == 0
    assert pg["has_more"] is True  # total=5, returned=1 → more items exist


def test_archive_list_can_skip_exact_total(monkeypatch):
    """include_total=false이면 목록 API가 정확한 count 조회를 생략하도록 서비스에 전달."""
    item = ArchiveItemResponse(ad_id="a1", title="광고", status="saved", source="generated")
    calls = {}

    def fake_list_archive_items(workspace_id=None, user_id=None, limit=1, offset=0, include_total=True):
        calls["include_total"] = include_total
        return [item], 2

    monkeypatch.setattr(archive_router, "list_archive_items", fake_list_archive_items)

    resp = make_client().get("/api/v1/archive/items?limit=1&include_total=false")

    assert resp.status_code == 200
    assert calls["include_total"] is False
    pg = resp.json()["pagination"]
    assert pg["total"] == 2
    assert pg["has_more"] is True


def test_archive_list_returns_full_join_fields(monkeypatch):
    """Archive list가 Output/Asset JOIN된 전체 필드를 반환하는지 검증."""
    item = ArchiveItemResponse(
        ad_id="a1",
        job_id="job_public",
        output_id="output_public",
        thread_id="thread_public",
        title="광고",
        image_url="https://cdn.example.com/final.png",
        thumbnail_url="https://cdn.example.com/thumb.png",
        storage_provider="r2",
        mime_type="image/png",
        width=1024,
        height=1024,
        is_final=True,
        status="saved",
        source="generated",
    )
    monkeypatch.setattr(
        archive_router, "list_archive_items",
        lambda workspace_id=None, user_id=None, limit=50, offset=0: ([item], 1),
    )
    resp = make_client().get("/api/v1/archive/items")
    assert resp.status_code == 200
    data = resp.json()["items"][0]
    
    assert data["job_id"] == "job_public"
    assert data["output_id"] == "output_public"
    assert data["thread_id"] == "thread_public"
    assert data["image_url"] == "https://cdn.example.com/final.png"
    assert data["thumbnail_url"] == "https://cdn.example.com/thumb.png"
    assert data["storage_provider"] == "r2"
    assert data["mime_type"] == "image/png"
    assert data["width"] == 1024
    assert data["height"] == 1024
    assert data["is_final"] is True


# ---------------------------------------------------------------------------
# OpenAPI route 등록 확인
# ---------------------------------------------------------------------------

def test_archive_detail_and_delete_routes_registered():
    """GET, DELETE 모두 /archive/items/{id} 경로에 등록돼야 함."""
    schema = create_app().openapi()
    path = schema["paths"].get("/api/v1/archive/items/{archive_item_id}", {})
    assert "get" in path, "GET detail endpoint 미등록"
    assert "delete" in path, "DELETE endpoint 미등록"
