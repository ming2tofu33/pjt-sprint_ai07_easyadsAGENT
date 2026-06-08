from orchestrator.app.db.repositories import usage_events


class FakeCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.executed = []

    def execute(self, sql, params=()):
        self.executed.append((sql, params))

    def fetchone(self):
        if self.rows:
            return self.rows.pop(0)
        return None

    def fetchall(self):
        if self.rows:
            row = self.rows.pop(0)
            return row if isinstance(row, list) else [row]
        return []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self, rows):
        self.cursor_obj = FakeCursor(rows)

    def cursor(self):
        return self.cursor_obj

    def transaction(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_record_usage_event_once_uses_jsonb_and_idempotent_conflict():
    conn = FakeConnection(rows=[{"id": "usage_uuid", "event_type": "llm_call"}])

    row = usage_events.record_usage_event_once(
        workspace_id="ws1",
        event_type="llm_call",
        quantity=1,
        unit="call",
        idempotency_key="usage-key",
        metadata={"input_tokens": 1},
        connection=conn,
    )

    sql, params = conn.cursor_obj.executed[0]
    assert row["id"] == "usage_uuid"
    assert "on conflict (workspace_id, idempotency_key)" in sql
    assert "%s::jsonb" in sql
    assert params[-1] == '{"input_tokens": 1}'


def test_record_usage_event_once_fetches_existing_duplicate():
    conn = FakeConnection(rows=[None, {"id": "existing_usage"}])

    row = usage_events.record_usage_event_once(
        workspace_id="ws1",
        event_type="r2_upload",
        quantity=10,
        unit="byte",
        idempotency_key="duplicate",
        connection=conn,
    )

    assert row["id"] == "existing_usage"
    assert len(conn.cursor_obj.executed) == 2


def test_aggregate_usage_summary_returns_breakdowns():
    conn = FakeConnection(
        rows=[
            {
                "llm_calls": 1,
                "llm_input_tokens": 10,
                "llm_output_tokens": 5,
                "llm_total_tokens": 15,
                "t2i_images": 2,
                "r2_upload_bytes": 3,
                "r2_storage_bytes_added": 3,
                "r2_storage_bytes_removed": 1,
                "modal_gpu_seconds": 4,
                "estimated_cost_usd": 0,
                "unpriced_event_count": 1,
            },
            [{"key": "llm_call", "quantity": 1, "estimated_cost_usd": 0}],
            [{"key": "openai", "quantity": 1, "estimated_cost_usd": 0}],
            [{"key": "gpt", "quantity": 1, "estimated_cost_usd": 0}],
            [{"key": "premium", "quantity": 1, "estimated_cost_usd": 0}],
        ]
    )

    totals = usage_events.aggregate_usage_summary(workspace_id="ws1", connection=conn)

    assert totals["estimated_net_storage_bytes"] == 2
    assert totals["by_event_type"][0]["key"] == "llm_call"
    assert "group by event_type, unit" in conn.cursor_obj.executed[1][0]
    assert len(conn.cursor_obj.executed) == 5
