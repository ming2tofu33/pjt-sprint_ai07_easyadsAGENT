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

    workspace = repo.ensure_user_workspace("user_uuid_1", account_type="user", connection=conn)

    lock_sql, lock_params = conn.cursor_obj.calls[0]
    select_sql, select_params = conn.cursor_obj.calls[1]
    update_sql, update_params = conn.cursor_obj.calls[2]
    assert "pg_advisory_xact_lock" in lock_sql
    assert lock_params == ("workspace_owner:user_uuid_1",)
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

    assert len(conn.cursor_obj.calls) == 2
    assert workspace == existing_row


def test_ensure_user_workspace_preserves_existing_guest_when_account_type_omitted(monkeypatch):
    guest_row = {"id": "workspace_guest", "metadata": {"source": "supabase_guest", "account_type": "guest"}}
    conn = FakeConnection([guest_row])
    monkeypatch.setattr(repo, "db_transaction", fake_transaction)

    workspace = repo.ensure_user_workspace("guest_uuid_1", connection=conn)

    assert len(conn.cursor_obj.calls) == 2
    assert workspace == guest_row


def test_ensure_user_workspace_creates_guest_workspace(monkeypatch):
    guest_row = {"id": "workspace_guest", "metadata": {"source": "supabase_guest", "account_type": "guest"}}
    conn = FakeConnection([None, guest_row])
    monkeypatch.setattr(repo, "db_transaction", fake_transaction)

    workspace = repo.ensure_user_workspace("guest_uuid_1", account_type="guest", connection=conn)

    lock_sql, lock_params = conn.cursor_obj.calls[0]
    select_sql, select_params = conn.cursor_obj.calls[1]
    insert_sql, insert_params = conn.cursor_obj.calls[2]
    assert "pg_advisory_xact_lock" in lock_sql
    assert lock_params == ("workspace_owner:guest_uuid_1",)
    assert "where w.owner_user_id = %s" in select_sql
    assert select_params == ("guest_uuid_1",)
    assert "insert into workspaces" in insert_sql
    assert insert_params[0] == "Guest Workspace"
    assert insert_params[1] == "guest_uuid_1"
    assert workspace == guest_row


def test_ensure_user_workspace_promotes_guest_workspace_to_user(monkeypatch):
    guest_row = {"id": "workspace_guest", "metadata": {"source": "supabase_guest", "account_type": "guest"}}
    promoted_row = {"id": "workspace_guest", "metadata": {"source": "supabase_auth", "account_type": "user"}}
    conn = FakeConnection([guest_row, promoted_row])
    monkeypatch.setattr(repo, "db_transaction", fake_transaction)

    workspace = repo.ensure_user_workspace("guest_uuid_1", account_type="user", connection=conn)

    update_sql, update_params = conn.cursor_obj.calls[2]
    assert "update workspaces set name = %s" in update_sql
    assert update_params[0] == "User Workspace"
    assert update_params[2] == "workspace_guest"
    assert workspace == promoted_row


def test_ensure_user_workspace_guest_account_does_not_downgrade_user_workspace(monkeypatch):
    user_row = {"id": "workspace_user", "metadata": {"source": "supabase_auth", "account_type": "user"}}
    conn = FakeConnection([user_row])
    monkeypatch.setattr(repo, "db_transaction", fake_transaction)

    workspace = repo.ensure_user_workspace("user_uuid_1", account_type="guest", connection=conn)

    assert len(conn.cursor_obj.calls) == 2
    assert workspace == user_row
