"""chat_threads repository fake connection 테스트."""
from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# fake DB 인프라
# ---------------------------------------------------------------------------


class FakeCursor:
    def __init__(self):
        self._rows = []
        self._executed = []

    def execute(self, sql, params=None):
        self._executed.append((sql, params))

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


class FakeConn:
    def __init__(self, rows=None):
        self._cursor = FakeCursor()
        if rows:
            self._cursor._rows = rows

    def cursor(self):
        return self._cursor

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


# ---------------------------------------------------------------------------
# repository 함수 monkeypatch 헬퍼
# ---------------------------------------------------------------------------

from orchestrator.app.db.repositories import chat_threads as repo


def _patch_transaction(monkeypatch, conn):
    """db_transaction을 fake conn으로 교체."""
    from contextlib import contextmanager

    @contextmanager
    def _fake_tx(given_conn=None):
        yield conn

    monkeypatch.setattr("orchestrator.app.db.repositories.chat_threads.db_transaction", _fake_tx)


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


def test_create_returns_public_thread_id(monkeypatch):
    row = {
        "id": "uuid-1",
        "public_thread_id": "thread_abc",
        "workspace_id": "ws-1",
        "title": "Test",
        "status": "draft",
        "brand_kit_id": None,
        "project_id": None,
        "final_brief": {},
        "active_job_id": None,
        "final_output_id": None,
        "last_message_at": "2026-01-01T00:00:00+00:00",
        "archived_at": None,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        # The pre-insert guard counts existing threads via the same cursor;
        # a low total keeps us under the limit so the insert proceeds.
        "total": 0,
    }
    conn = FakeConn(rows=[row])
    _patch_transaction(monkeypatch, conn)

    result = repo.create_chat_thread(
        workspace_id="ws-1", created_by="user-1", title="Test"
    )
    assert result["public_thread_id"] == "thread_abc"
    executed_sql = " ".join(sql.lower() for sql, _ in conn._cursor._executed)
    assert "insert into chat_threads" in executed_sql
    # Guard ran the per-workspace advisory lock before inserting.
    assert "pg_advisory_xact_lock" in executed_sql


def test_create_raises_when_thread_limit_reached(monkeypatch):
    from orchestrator.app.chat_threads.errors import ChatThreadLimitReachedError

    # count_chat_threads (via the guard) reads "total" from fetchone → at the
    # default limit of 3, creation must raise and never reach the insert.
    conn = FakeConn(rows=[{"total": 3}])
    _patch_transaction(monkeypatch, conn)

    with pytest.raises(ChatThreadLimitReachedError) as exc_info:
        repo.create_chat_thread(workspace_id="ws-1", created_by="user-1", title="Test")

    assert exc_info.value.error_code == "thread_limit_reached"
    executed_sql = " ".join(sql.lower() for sql, _ in conn._cursor._executed)
    assert "insert into chat_threads" not in executed_sql


def test_create_respects_configurable_limit(monkeypatch):
    # With the limit raised to 5, a workspace at 4 threads can still create.
    monkeypatch.setattr(
        "orchestrator.app.db.repositories.chat_threads.db_settings.get_max_threads_per_workspace",
        lambda: 5,
    )
    row = {"public_thread_id": "thread_ok", "total": 4}
    conn = FakeConn(rows=[row])
    _patch_transaction(monkeypatch, conn)

    result = repo.create_chat_thread(workspace_id="ws-1", created_by="user-1")
    assert result["public_thread_id"] == "thread_ok"


# ---------------------------------------------------------------------------
# get_chat_thread_by_public_id
# ---------------------------------------------------------------------------


def test_get_by_public_id(monkeypatch):
    row = {"id": "uuid-1", "public_thread_id": "thread_abc", "active_public_job_id": None}
    conn = FakeConn(rows=[row])
    _patch_transaction(monkeypatch, conn)

    result = repo.get_chat_thread_by_public_id("thread_abc")
    assert result["public_thread_id"] == "thread_abc"
    sql, params = conn._cursor._executed[0]
    assert "left join generation_jobs" in sql.lower()
    assert params == ("thread_abc",)


def test_get_by_public_id_not_found(monkeypatch):
    conn = FakeConn(rows=[])
    _patch_transaction(monkeypatch, conn)
    result = repo.get_chat_thread_by_public_id("nonexistent")
    assert result is None


# ---------------------------------------------------------------------------
# list_chat_threads
# ---------------------------------------------------------------------------


def test_list_excludes_archived_by_default(monkeypatch):
    conn = FakeConn(rows=[])
    _patch_transaction(monkeypatch, conn)
    repo.list_chat_threads(workspace_id="ws-1", include_archived=False)
    sql, _ = conn._cursor._executed[0]
    assert "archived_at is null" in sql.lower()


def test_list_includes_archived_when_requested(monkeypatch):
    conn = FakeConn(rows=[])
    _patch_transaction(monkeypatch, conn)
    repo.list_chat_threads(workspace_id="ws-1", include_archived=True)
    sql, _ = conn._cursor._executed[0]
    assert "archived_at is null" not in sql.lower()


def test_list_order_uses_last_message_at(monkeypatch):
    conn = FakeConn(rows=[])
    _patch_transaction(monkeypatch, conn)
    repo.list_chat_threads(workspace_id="ws-1")
    sql, _ = conn._cursor._executed[0]
    assert "last_message_at desc" in sql.lower()


# ---------------------------------------------------------------------------
# update_chat_thread (allowlist)
# ---------------------------------------------------------------------------


def test_update_allowlist_only(monkeypatch):
    row = {"id": "uuid-1", "public_thread_id": "thread_abc", "title": "New", "status": "draft"}
    conn = FakeConn(rows=[row])
    _patch_transaction(monkeypatch, conn)

    repo.update_chat_thread("thread_abc", title="New")
    sql, _ = conn._cursor._executed[0]
    assert "update chat_threads" in sql.lower()
    assert "title" in sql.lower()
    # 금지 필드 미포함
    assert "status" not in sql.lower()
    assert "workspace_id" not in sql.lower()


def test_update_final_brief_uses_jsonb(monkeypatch):
    row = {"id": "uuid-1", "public_thread_id": "thread_abc", "final_brief": {"k": "v"}}
    conn = FakeConn(rows=[row])
    _patch_transaction(monkeypatch, conn)

    repo.update_chat_thread("thread_abc", final_brief={"k": "v"})
    sql, _ = conn._cursor._executed[0]
    assert "jsonb" in sql.lower()


# ---------------------------------------------------------------------------
# archive
# ---------------------------------------------------------------------------


def test_archive_sets_status_and_archived_at(monkeypatch):
    row = {"id": "uuid-1", "public_thread_id": "thread_abc", "status": "archived", "archived_at": "2026-01-02", "active_job_id": None}
    conn = FakeConn(rows=[row])
    _patch_transaction(monkeypatch, conn)

    result = repo.archive_chat_thread("thread_abc")
    assert result["status"] == "archived"
    sql, _ = conn._cursor._executed[0]
    assert "archived_at = now()" in sql.lower()
    assert "active_job_id = null" in sql.lower()


# ---------------------------------------------------------------------------
# set/clear active_job_id
# ---------------------------------------------------------------------------


def test_set_active_job_id(monkeypatch):
    row = {"id": "uuid-1", "public_thread_id": "thread_abc", "active_job_id": "job-uuid", "status": "generating"}
    conn = FakeConn(rows=[row])
    _patch_transaction(monkeypatch, conn)

    result = repo.set_chat_thread_active_job("thread_abc", "job-uuid", status="generating")
    assert result["active_job_id"] == "job-uuid"
    sql, _ = conn._cursor._executed[0]
    assert "active_job_id" in sql.lower()


def test_clear_active_job_id(monkeypatch):
    row = {"id": "uuid-1", "public_thread_id": "thread_abc", "active_job_id": None, "status": "completed"}
    conn = FakeConn(rows=[row])
    _patch_transaction(monkeypatch, conn)

    result = repo.clear_chat_thread_active_job("thread_abc", status="completed")
    assert result["active_job_id"] is None
    sql, _ = conn._cursor._executed[0]
    assert "active_job_id = null" in sql.lower()


# ---------------------------------------------------------------------------
# set final_output_id
# ---------------------------------------------------------------------------


def test_set_final_output_id(monkeypatch):
    row = {"id": "uuid-1", "public_thread_id": "thread_abc", "final_output_id": "out-uuid"}
    conn = FakeConn(rows=[row])
    _patch_transaction(monkeypatch, conn)

    result = repo.set_chat_thread_final_output("thread_abc", "out-uuid")
    assert result["final_output_id"] == "out-uuid"
    sql, _ = conn._cursor._executed[0]
    assert "final_output_id" in sql.lower()


def test_complete_generation_guards_workspace_and_expected_active_job(monkeypatch):
    row = {"id": "uuid-1", "public_thread_id": "thread_abc", "active_job_id": None, "status": "completed"}
    conn = FakeConn(rows=[row])
    _patch_transaction(monkeypatch, conn)

    repo.complete_chat_thread_generation(
        public_thread_id="thread_abc",
        workspace_id="workspace_uuid",
        expected_active_job_id="job_uuid",
        final_output_id="output_uuid",
        final_brief={"safe": "brief"},
    )

    sql, params = conn._cursor._executed[0]
    normalized = sql.lower()
    assert "workspace_id = %s::uuid" in normalized
    assert "active_job_id = %s::uuid" in normalized
    assert params[-3:] == ("thread_abc", "workspace_uuid", "job_uuid")


def test_fail_generation_guards_workspace_and_expected_active_job(monkeypatch):
    row = {"id": "uuid-1", "public_thread_id": "thread_abc", "active_job_id": None, "status": "failed"}
    conn = FakeConn(rows=[row])
    _patch_transaction(monkeypatch, conn)

    repo.fail_chat_thread_generation(
        public_thread_id="thread_abc",
        workspace_id="workspace_uuid",
        expected_active_job_id="job_uuid",
    )

    sql, params = conn._cursor._executed[0]
    normalized = sql.lower()
    assert "workspace_id = %s::uuid" in normalized
    assert "active_job_id = %s::uuid" in normalized
    assert params == ("thread_abc", "workspace_uuid", "job_uuid")
