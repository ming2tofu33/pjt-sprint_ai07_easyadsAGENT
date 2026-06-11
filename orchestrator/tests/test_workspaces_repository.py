from contextlib import contextmanager

from orchestrator.app.db.repositories import workspaces as repo


class FakeCursor:
    def __init__(self, rows):
        self.calls = []
        self.rows = list(rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


class FakeConnection:
    def __init__(self, rows):
        self.cursor_obj = FakeCursor(rows)

    def cursor(self):
        return self.cursor_obj


@contextmanager
def fake_transaction(connection=None):
    yield connection


def test_ensure_user_workspace_promotes_legacy_fallback_workspace(monkeypatch):
    legacy_row = {"id": "workspace_legacy", "metadata": {"source": "demo_fallback"}}
    normalized_row = {"id": "workspace_legacy", "metadata": {"source": "supabase_auth"}}
    conn = FakeConnection([legacy_row, normalized_row])
    monkeypatch.setattr(repo, "db_transaction", fake_transaction)

    workspace = repo.ensure_user_workspace("user_uuid_1", connection=conn)

    select_sql, select_params = conn.cursor_obj.calls[0]
    update_sql, update_params = conn.cursor_obj.calls[1]
    assert "left join chat_threads" in select_sql
    assert "left join generation_jobs" in select_sql
    assert "count(distinct ct.id) + count(distinct gj.id) > 0" in select_sql
    assert "w.metadata->>'source' = 'supabase_auth'" in select_sql
    assert select_params == ("user_uuid_1",)
    assert "update workspaces set name = %s" in update_sql
    assert update_params[0] == "User Workspace"
    assert update_params[2] == "workspace_legacy"
    assert workspace == normalized_row


def test_ensure_user_workspace_reuses_existing_supabase_workspace(monkeypatch):
    existing_row = {"id": "workspace_user", "metadata": {"source": "supabase_auth"}}
    conn = FakeConnection([existing_row])
    monkeypatch.setattr(repo, "db_transaction", fake_transaction)

    workspace = repo.ensure_user_workspace("user_uuid_1", connection=conn)

    assert len(conn.cursor_obj.calls) == 1
    assert workspace == existing_row
