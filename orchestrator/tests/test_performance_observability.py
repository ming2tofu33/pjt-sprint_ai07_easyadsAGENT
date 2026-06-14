from __future__ import annotations

import json
import asyncio
from contextlib import nullcontext

from orchestrator.app.observability import performance
from orchestrator.app.api.app import create_app
from orchestrator.app.db.session import db_transaction
from orchestrator.app.graph.builder import _instrument_node
from orchestrator.app.graph.checkpointer import InstrumentedCheckpointer


def test_perf_trace_disabled_by_default(monkeypatch):
    monkeypatch.delenv("EASYADS_PERF_TRACE", raising=False)
    assert performance.perf_trace_enabled() is False


def test_sql_fingerprint_redacts_literals():
    left = performance.sql_fingerprint("select * from jobs where id = 123 and name = 'abc'")
    right = performance.sql_fingerprint("select * from jobs where id = 456 and name = 'xyz'")
    assert left == right


def test_estimate_json_size_bytes_handles_unserializable():
    class X:
        pass

    assert performance.estimate_json_size_bytes({"x": X()}) is not None


def test_record_perf_event_writes_jsonl(monkeypatch, tmp_path):
    monkeypatch.setenv("EASYADS_PERF_TRACE", "1")
    monkeypatch.setenv("EASYADS_PERF_TRACE_OUTPUT_DIR", str(tmp_path))
    performance.record_perf_event(
        performance.build_event(
            "benchmark_marker",
            operation="self-check",
            duration_ms=1.2,
            metadata={"status": "ok"},
        )
    )
    performance.flush_perf_events()
    rows = list(tmp_path.glob("events-*.jsonl"))
    assert len(rows) == 1
    payload = json.loads(rows[0].read_text(encoding="utf-8").splitlines()[0])
    assert payload["event_type"] == "benchmark_marker"


def test_builder_wrapper_skips_size_estimate_when_flag_off(monkeypatch):
    monkeypatch.delenv("EASYADS_PERF_TRACE", raising=False)

    def explode(_value):
        raise AssertionError("should not run")

    monkeypatch.setattr("orchestrator.app.graph.builder.estimate_json_size_bytes", explode)
    wrapped = _instrument_node("node", lambda state: {"ok": state["ok"]})
    assert wrapped({"ok": 1}) == {"ok": 1}


def test_builder_wrapper_supports_async(monkeypatch):
    monkeypatch.setenv("EASYADS_PERF_TRACE", "1")
    events = []
    monkeypatch.setattr("orchestrator.app.observability.performance.record_perf_event", lambda event: events.append(event))

    async def node(state):
        return {"done": state["value"]}

    wrapped = _instrument_node("async_node", node)
    assert asyncio.run(wrapped({"value": 7})) == {"done": 7}
    assert events[-1]["event_type"] == "graph_node"


def test_checkpointer_aput_waits_for_coroutine(monkeypatch):
    monkeypatch.setenv("EASYADS_PERF_TRACE", "1")
    events = []
    monkeypatch.setattr("orchestrator.app.observability.performance.record_perf_event", lambda event: events.append(event))

    class FakeInner:
        async def aput(self, config, checkpoint, metadata, new_versions):
            return {"checkpoint": checkpoint}

    wrapped = InstrumentedCheckpointer(FakeInner())
    result = asyncio.run(wrapped.aput({"a": 1}, {"value": 2}, {}, {}))
    assert result == {"checkpoint": {"value": 2}}
    assert events[-1]["event_type"] == "checkpoint_write"


def test_db_transaction_records_contextual_events(monkeypatch):
    monkeypatch.setenv("EASYADS_PERF_TRACE", "1")
    events = []
    monkeypatch.setattr("orchestrator.app.observability.performance.record_perf_event", lambda event: events.append(event))

    class FakeCursor:
        rowcount = 1

        def execute(self, sql, params=None):
            return {"sql": sql, "params": params}

        def fetchall(self):
            return [{"id": 1}]

    class FakeConnection:
        def transaction(self):
            return nullcontext()

        def cursor(self, *args, **kwargs):
            return FakeCursor()

    tokens = performance.bind_perf_context(trace_id="trace_x", request_id="req_x", scenario_id="A", run_id="run_1", cold_or_warm="cold")
    monkeypatch.setattr("orchestrator.app.db.session.record_perf_event", lambda event: events.append(event))
    try:
        with db_transaction(FakeConnection()) as conn:
            rows = conn.cursor().execute("select * from jobs where id = %s", [1])
            assert rows["sql"].startswith("select")
            conn.cursor().fetchall()
    finally:
        performance.reset_perf_context(tokens)

    assert any(event["event_type"] == "db_transaction" for event in events)
    assert any(event["event_type"] == "db_query" and event["trace_id"] == "trace_x" for event in events)


def test_perf_middleware_preserves_original_exception(monkeypatch):
    app = create_app()

    @app.get("/boom")
    def boom():
        raise RuntimeError("boom")

    from fastapi.testclient import TestClient

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/boom")
    assert response.status_code == 500
