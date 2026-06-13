"""Consolidated archive tests.

Merged from:
- orchestrator/tests/test_archive_api_detail.py
- orchestrator/tests/test_archive_generation_output_integration.py
- orchestrator/tests/test_archive_generation_outputs.py
- orchestrator/tests/test_archive_items_repository.py
- orchestrator/tests/test_archive_service_performance.py
"""



# ===== from test_archive_api_detail.py =====
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


# ===== from test_archive_generation_output_integration.py =====
import pytest
from unittest.mock import MagicMock
from orchestrator.app.archive.service import (
    create_archive_item,
    ArchiveInvalidGeneratedSource,
    ArchiveGenerationOutputNotReady,
    ArchiveItemNotFound,
)
from orchestrator.app.api.schemas.archive import ArchiveItemCreateRequest

def test_archive_invalid_generated_source(monkeypatch):
    monkeypatch.setattr("orchestrator.app.archive.service._ensure_postgres_enabled", lambda: None)
    monkeypatch.setattr("orchestrator.app.archive.service._resolve_workspace_id", lambda *a, **k: "ws1")

    req = ArchiveItemCreateRequest(
        title="test",
        source="generated",
        public_job_id=None,
    )

    with pytest.raises(ArchiveInvalidGeneratedSource):
        create_archive_item(req)

def test_archive_generation_job_not_found(monkeypatch):
    monkeypatch.setattr("orchestrator.app.archive.service._ensure_postgres_enabled", lambda: None)
    monkeypatch.setattr("orchestrator.app.archive.service._resolve_workspace_id", lambda *a, **k: "ws1")

    mock_job_repo = MagicMock()
    mock_job_repo.get_generation_job_db.return_value = None
    monkeypatch.setattr("orchestrator.app.archive.service.job_repo", mock_job_repo)

    req = ArchiveItemCreateRequest(
        title="test",
        source="generated",
        public_job_id="job1",
    )

    with pytest.raises(ArchiveItemNotFound):
        create_archive_item(req)

def test_archive_generation_output_not_ready(monkeypatch):
    monkeypatch.setattr("orchestrator.app.archive.service._ensure_postgres_enabled", lambda: None)
    monkeypatch.setattr("orchestrator.app.archive.service._resolve_workspace_id", lambda *a, **k: "ws1")

    mock_job_repo = MagicMock()
    mock_job_repo.get_generation_job_db.return_value = {
        "id": "job_uuid",
        "public_job_id": "job1",
    }
    monkeypatch.setattr("orchestrator.app.archive.service.job_repo", mock_job_repo)

    monkeypatch.setattr(
        "orchestrator.app.archive.service.sync_archive_for_job",
        lambda *a, **k: (_ for _ in ()).throw(
            ArchiveGenerationOutputNotReady("Final output not ready")
        ),
    )

    req = ArchiveItemCreateRequest(
        title="test",
        source="generated",
        public_job_id="job1",
    )

    with pytest.raises(ArchiveGenerationOutputNotReady):
        create_archive_item(req)

def test_done_does_not_ignore_archive_sync_failure(monkeypatch):
    """Archive sync 실패 시 _create_output_records_for_done_job_db가 예외를 전파해야 함."""
    from orchestrator.app.generation_jobs.service import _create_output_records_for_done_job_db

    # R2 업로드 비활성화 (local asset 경로로 진행)
    monkeypatch.setattr("orchestrator.app.generation_jobs.service._should_attempt_r2_upload", lambda: False)
    monkeypatch.setattr(
        "orchestrator.app.generation_jobs.service.asset_repo.create_asset",
        lambda *args, **kwargs: {"id": "asset1", "storage_provider": "local_dev"},
    )
    monkeypatch.setattr(
        "orchestrator.app.generation_jobs.service.generation_output_repo.create_generation_output",
        lambda *args, **kwargs: {"id": "out1", "public_output_id": "public_out1"},
    )
    monkeypatch.setattr(
        "orchestrator.app.generation_jobs.service.generation_output_repo.mark_output_final",
        lambda *args, **kwargs: {"id": "out1"},
    )
    monkeypatch.setattr(
        "orchestrator.app.generation_jobs.service.generation_job_repo.update_generation_job_row",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "orchestrator.app.generation_jobs.service._record_generation_job_event_db",
        MagicMock(),
    )
    monkeypatch.setattr(
        "orchestrator.app.artifacts.service.merge_final_asset_into_result_payload",
        lambda **kwargs: kwargs.get("result_payload", {}),
    )

    def mock_sync(*args, **kwargs):
        raise RuntimeError("Archive sync failed")

    # archive_service 모듈 attribute로 참조하므로, 해당 경로로 patch
    monkeypatch.setattr("orchestrator.app.generation_jobs.service.archive_service.sync_archive_for_output", mock_sync)

    row = {"id": "1", "workspace_id": "ws1", "public_job_id": "pub1", "thread_id": "th1", "requested_by": "u1"}
    result_payload = {"final_image_path": "data/outputs/pub1/final.png"}

    with pytest.raises(RuntimeError, match="Archive sync failed"):
        _create_output_records_for_done_job_db(row, result_payload, "data/outputs/pub1/final.png", connection=MagicMock())


# ===== from test_archive_generation_outputs.py =====
import pytest
from unittest.mock import MagicMock
from orchestrator.app.archive.service import sync_archive_for_job

def test_sync_archive_for_job_success(monkeypatch):
    mock_job = {
        "id": "job_uuid",
        "thread_id": "thread_uuid",
        "public_job_id": "job_public",
        "requested_by": "user1",
        "brief": {"item_or_service": "Cool product"},
    }

    mock_thread = {
        "id": "thread_uuid",
        "title": "Thread Title",
    }

    mock_outputs = [{
        "id": "output_uuid",
        "asset_id": "asset_uuid",
        "image_url": "local/image.png",
        "thumbnail_url": "local/thumb.png",
    }]

    mock_archive_row = {
        "public_archive_id": "archive_public",
        "id": "archive_uuid"
    }

    job_repo_mock = MagicMock()
    job_repo_mock.get_generation_job_db_by_id.return_value = mock_job
    monkeypatch.setattr("orchestrator.app.archive.service.job_repo", job_repo_mock)

    thread_repo_mock = MagicMock()
    thread_repo_mock.get_chat_thread.return_value = mock_thread
    monkeypatch.setattr("orchestrator.app.archive.service.thread_repo", thread_repo_mock)

    output_repo_mock = MagicMock()
    output_repo_mock.list_generation_outputs.return_value = mock_outputs
    monkeypatch.setattr("orchestrator.app.archive.service.output_repo", output_repo_mock)

    archive_repo_mock = MagicMock()
    archive_repo_mock.upsert_generated_archive_item_row.return_value = mock_archive_row

    archive_repo_mock.get_archive_item_row.return_value = {
        **mock_archive_row,
        "workspace_id": "ws1",
        "title": "Thread Title",
        "j_public_job_id": "job_public",
        "public_output_id": "out_public",
        "public_thread_id": "thread_public",
    }
    monkeypatch.setattr("orchestrator.app.archive.service.archive_item_repo", archive_repo_mock)

    monkeypatch.setattr("orchestrator.app.archive.service._ensure_postgres_enabled", lambda: None)

    res = sync_archive_for_job(workspace_id="ws1", internal_job_id="job_uuid")

    assert res is not None
    assert res.title == "Thread Title"
    assert res.job_id == "job_public"

    archive_repo_mock.upsert_generated_archive_item_row.assert_called_once()
    called_kwargs = archive_repo_mock.upsert_generated_archive_item_row.call_args[1]
    assert called_kwargs["title"] == "Thread Title"
    assert called_kwargs["source"] == "generated"
    assert called_kwargs["output_id"] == "output_uuid"


# ===== from test_archive_items_repository.py =====
from contextlib import contextmanager

from orchestrator.app.db.repositories import archive_items as repo


class FakeCursor:
    def __init__(self):
        self.calls = []
        self.row = {
            "id": "archive_uuid",
            "workspace_id": "workspace_uuid",
            "public_job_id": "job_1",
            "title": "봄을 닮은 한 잔",
            "image_url": "/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal.png",
            "status": "saved",
            "source": "generated",
            "metadata": {"tags": ["카페"]},
        }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), params))

    def fetchone(self):
        if "count(*) as total" in self.calls[-1][0]:
            return {"total": 1}
        return self.row

    def fetchall(self):
        return [self.row]


class FakeConnection:
    def __init__(self):
        self.cursor_obj = FakeCursor()

    def cursor(self):
        return self.cursor_obj


@contextmanager
def fake_transaction(connection=None):
    yield connection


def test_create_archive_item_row_inserts_generated_result(monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr(repo, "db_transaction", fake_transaction)

    row = repo.create_archive_item_row(
        workspace_id="workspace_uuid",
        created_by="user_1",
        title="봄을 닮은 한 잔",
        public_job_id="job_1",
        image_url="/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal.png",
        thumbnail_url="/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal.png",
        ad_format="1:1",
        platform="인스타 피드",
        metadata={"tags": ["카페"]},
        connection=conn,
    )

    sql, params = conn.cursor_obj.calls[0]
    assert "insert into archive_items" in sql
    assert "public_job_id" in sql
    assert "%s::jsonb" in sql
    assert params[0] == "workspace_uuid"
    assert params[5] == "job_1"
    assert row["id"] == "archive_uuid"


def test_list_count_and_soft_delete_archive_items(monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr(repo, "db_transaction", fake_transaction)

    rows = repo.list_archive_item_rows(workspace_id="workspace_uuid", limit=20, offset=0, connection=conn)
    total = repo.count_archive_item_rows(workspace_id="workspace_uuid", connection=conn)
    updated = repo.update_archive_item_status_row(archive_item_id="archive_uuid", workspace_id="workspace_uuid", status="favorite", connection=conn)
    deleted = repo.soft_delete_archive_item_row(archive_item_id="archive_uuid", workspace_id="workspace_uuid", connection=conn)

    joined = "\n".join(call[0] for call in conn.cursor_obj.calls)
    assert "i.workspace_id = %s and i.deleted_at is null order by i.saved_at desc" in joined
    assert "select count(*) as total from archive_items" in joined
    assert "set status = %s, updated_at = now()" in joined
    assert "set deleted_at = now(), updated_at = now()" in joined
    assert rows[0]["id"] == "archive_uuid"
    assert total == 1
    assert updated["id"] == "archive_uuid"
    assert deleted["id"] == "archive_uuid"


def test_archive_list_query_omits_output_payload_by_default(monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr(repo, "db_transaction", fake_transaction)

    repo.list_archive_item_rows(workspace_id="workspace_uuid", limit=20, offset=0, connection=conn)

    sql = conn.cursor_obj.calls[0][0]
    assert "o.result_payload as output_result_payload" not in sql


def test_archive_item_queries_can_filter_by_creator(monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr(repo, "db_transaction", fake_transaction)

    repo.list_archive_item_rows(workspace_id="workspace_uuid", created_by="user_1", limit=20, offset=0, connection=conn)
    repo.count_archive_item_rows(workspace_id="workspace_uuid", created_by="user_1", connection=conn)
    repo.update_archive_item_status_row(archive_item_id="archive_uuid", workspace_id="workspace_uuid", created_by="user_1", status="favorite", connection=conn)
    repo.soft_delete_archive_item_row(archive_item_id="archive_uuid", workspace_id="workspace_uuid", created_by="user_1", connection=conn)

    joined = "\n".join(call[0] for call in conn.cursor_obj.calls)
    params = [call[1] for call in conn.cursor_obj.calls]
    assert "i.created_by = %s" in joined
    assert params[0] == ("workspace_uuid", "user_1", 20, 0)
    assert params[1] == ("workspace_uuid", "user_1")
    assert params[2] == ("favorite", "archive_uuid", "workspace_uuid", "user_1")
    assert params[3] == ("archive_uuid", "workspace_uuid", "user_1")


def test_archive_item_get_queries_can_filter_by_creator(monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr(repo, "db_transaction", fake_transaction)

    repo.get_archive_item_row(
        public_archive_id="archive_1",
        workspace_id="ws1",
        created_by="user1",
        connection=conn,
    )

    sql, params = conn.cursor_obj.calls[0]
    assert "i.created_by = %s" in sql
    assert params == ("archive_1", "ws1", "user1")


# ===== from test_archive_service_performance.py =====
from orchestrator.app.archive import service as archive_service


def test_list_archive_items_can_skip_exact_count(monkeypatch):
    calls = {}

    monkeypatch.setattr(archive_service, "_ensure_postgres_enabled", lambda: None)
    monkeypatch.setattr(archive_service, "_resolve_user_id", lambda user_id=None: user_id)
    monkeypatch.setattr(archive_service, "_resolve_workspace_id", lambda workspace_id=None, **_: workspace_id or "workspace_uuid")

    def fake_list_archive_item_rows(*, workspace_id, created_by=None, limit=50, offset=0):
        calls["list"] = {
            "workspace_id": workspace_id,
            "created_by": created_by,
            "limit": limit,
            "offset": offset,
        }
        return [
            {
                "public_archive_id": "archive_1",
                "title": "첫 번째 광고",
                "thumbnail_public_url": "https://cdn.example.com/thumb-1.png",
                "status": "saved",
                "source": "generated",
            },
            {
                "public_archive_id": "archive_2",
                "title": "두 번째 광고",
                "thumbnail_public_url": "https://cdn.example.com/thumb-2.png",
                "status": "saved",
                "source": "generated",
            },
        ]

    def fail_count_archive_item_rows(**_kwargs):
        raise AssertionError("count query should be skipped")

    monkeypatch.setattr(archive_service.archive_item_repo, "list_archive_item_rows", fake_list_archive_item_rows)
    monkeypatch.setattr(archive_service.archive_item_repo, "count_archive_item_rows", fail_count_archive_item_rows)

    items, total = archive_service.list_archive_items(
        workspace_id="workspace_uuid",
        user_id="user_1",
        limit=1,
        offset=0,
        include_total=False,
    )

    assert [item.ad_id for item in items] == ["archive_1"]
    assert total == 2
    assert calls["list"] == {
        "workspace_id": "workspace_uuid",
        "created_by": "user_1",
        "limit": 2,
        "offset": 0,
    }
