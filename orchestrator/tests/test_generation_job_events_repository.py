from contextlib import contextmanager

from orchestrator.app.db.repositories import generation_job_events as repo


class FakeCursor:
    def __init__(self):
        self.calls = []
        self.row = {"id": "event_uuid", "event_type": "queued"}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), params))

    def fetchone(self):
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


def test_record_generation_job_event_uses_jsonb_payload(monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr(repo, "db_transaction", fake_transaction)

    row = repo.record_generation_job_event(
        workspace_id="workspace_uuid",
        thread_id="thread_uuid",
        job_id="job_uuid",
        event_type="running",
        message="t2i_running",
        payload={"current_stage": "t2i_running"},
        connection=conn,
    )

    sql, params = conn.cursor_obj.calls[0]
    assert "insert into generation_job_events" in sql
    assert "%s::jsonb" in sql
    assert params[0] == "workspace_uuid"
    assert params[3] == "running"
    assert '"current_stage": "t2i_running"' in params[5]
    assert row["id"] == "event_uuid"


def test_list_generation_job_events_orders_by_created(monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr(repo, "db_transaction", fake_transaction)

    rows = repo.list_generation_job_events("job_uuid", limit=10, connection=conn)

    sql, params = conn.cursor_obj.calls[0]
    assert "where job_id = %s" in sql
    assert "order by created_at desc" in sql
    assert params == ("job_uuid", 10)
    assert rows[0]["event_type"] == "queued"

def test_list_generation_job_events_by_public_job_id_joins_generation_jobs(monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr(repo, "db_transaction", fake_transaction)

    rows = repo.list_generation_job_events_by_public_job_id("job_db", limit=10, connection=conn)

    sql, params = conn.cursor_obj.calls[0]
    assert "join generation_jobs j on j.id = e.job_id" in sql
    assert "where j.public_job_id = %s" in sql
    assert "order by e.created_at desc" in sql
    assert params == ("job_db", 10)
    assert rows[0]["event_type"] == "queued"