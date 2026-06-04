from contextlib import contextmanager

from orchestrator.app.db.repositories import generation_jobs as repo


class FakeCursor:
    def __init__(self):
        self.calls = []
        self.row = {"public_job_id": "job_db", "status": "queued"}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self):
        self.cursor_obj = FakeCursor()

    def cursor(self):
        return self.cursor_obj


@contextmanager
def fake_transaction(connection=None):
    yield connection


def test_create_generation_job_row_inserts_expected_fields(monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr(repo, "db_transaction", fake_transaction)

    row = repo.create_generation_job_row(
        public_job_id="job_db",
        workspace_id="workspace_id",
        thread_id="thread_id",
        requested_by="demo_user",
        status="queued",
        current_stage="queued",
        progress_percent=0,
        selected_reference_template_id="seed_1",
        output_path=None,
        result_payload=None,
        error=None,
        metadata={"requested_run_mode": "queued_only"},
        connection=conn,
    )

    sql, params = conn.cursor_obj.calls[0]
    assert "insert into generation_jobs" in sql
    assert "public_job_id" in sql
    assert "result_payload, error, metadata" in sql
    assert "%s::jsonb" in sql
    assert params[0] == "job_db"
    assert params[1] == "workspace_id"
    assert row["public_job_id"] == "job_db"


def test_get_generation_job_row_selects_by_public_job_id(monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr(repo, "db_transaction", fake_transaction)

    row = repo.get_generation_job_row("job_db", connection=conn)

    sql, params = conn.cursor_obj.calls[0]
    assert "select * from generation_jobs where public_job_id = %s" in sql
    assert params == ("job_db",)
    assert row["public_job_id"] == "job_db"


def test_mark_running_done_failed_update_status(monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr(repo, "db_transaction", fake_transaction)

    repo.mark_generation_job_running_row("job_db", current_stage="t2i_running", connection=conn)
    repo.mark_generation_job_done_row("job_db", {"schema_version": "result_artifact_v1"}, output_path="data/outputs/job/final_0.png", connection=conn)
    repo.mark_generation_job_failed_row("job_db", {"error_code": "x", "message": "failed"}, connection=conn)

    joined = "\n".join(call[0] for call in conn.cursor_obj.calls)
    assert "status = %s" in joined
    assert "progress_percent = %s" in joined
    assert "result_payload = %s::jsonb" in joined
    assert "error = %s::jsonb" in joined
