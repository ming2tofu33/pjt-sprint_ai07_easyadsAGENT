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
