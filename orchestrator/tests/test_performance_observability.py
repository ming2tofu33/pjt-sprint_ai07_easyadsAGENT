from __future__ import annotations

import json
import asyncio
from contextlib import nullcontext

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from orchestrator.app.observability import performance
from orchestrator.app.api.app import create_app
from orchestrator.app.db.session import db_transaction
from orchestrator.app.graph.builder import _instrument_node, build_marketing_graph
from orchestrator.app.graph.checkpointer import InstrumentedCheckpointer, get_checkpointer


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

    class FakeInner(BaseCheckpointSaver):
        def __init__(self):
            super().__init__(serde=InMemorySaver().serde)

        @property
        def config_specs(self):
            return []

        def get_tuple(self, config):
            return {"config": config}

        def list(self, config, *, filter=None, before=None, limit=None):
            yield {"config": config}

        def put(self, config, checkpoint, metadata, new_versions):
            return checkpoint

        def put_writes(self, config, writes, task_id, task_path=""):
            return None

        def delete_thread(self, thread_id: str) -> None:
            return None

        def get_next_version(self, current, channel):
            return 1

        async def aget_tuple(self, config):
            return {"config": config}

        async def aput(self, config, checkpoint, metadata, new_versions):
            return {"checkpoint": checkpoint}

        async def aget(self, config):
            return {"config": config}

        async def alist(self, config, *, filter=None, before=None, limit=None):
            yield {"config": config}

        async def aput_writes(self, config, writes, task_id, task_path=""):
            return None

        async def adelete_thread(self, thread_id: str) -> None:
            return None

    wrapped = InstrumentedCheckpointer(FakeInner())
    result = asyncio.run(wrapped.aput({"a": 1}, {"value": 2}, {}, {}))
    assert result == {"checkpoint": {"value": 2}}
    assert events[-1]["event_type"] == "checkpoint_write"


def test_memory_checkpointer_is_valid_base_saver(monkeypatch):
    monkeypatch.delenv("EASYADS_DB_BACKEND", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_checkpointer.cache_clear()
    checkpointer = get_checkpointer()
    assert isinstance(checkpointer, BaseCheckpointSaver)
    assert isinstance(checkpointer._inner, InMemorySaver)


def test_instrumented_checkpointer_compiles_graph_when_perf_disabled(monkeypatch):
    monkeypatch.delenv("EASYADS_PERF_TRACE", raising=False)
    monkeypatch.delenv("EASYADS_DB_BACKEND", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_checkpointer.cache_clear()
    graph = build_marketing_graph(checkpointer=get_checkpointer())
    assert graph is not None


def test_instrumented_checkpointer_compiles_graph_when_perf_enabled(monkeypatch):
    monkeypatch.setenv("EASYADS_PERF_TRACE", "1")
    monkeypatch.delenv("EASYADS_DB_BACKEND", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_checkpointer.cache_clear()
    graph = build_marketing_graph(checkpointer=get_checkpointer())
    assert graph is not None


def test_instrumented_checkpointer_sync_iterator_semantics(monkeypatch):
    monkeypatch.setenv("EASYADS_PERF_TRACE", "1")

    class FakeSaver(BaseCheckpointSaver):
        def __init__(self):
            super().__init__(serde=InMemorySaver().serde)

        @property
        def config_specs(self):
            return ["x"]

        def get_tuple(self, config):
            return ("tuple", config)

        def list(self, config, *, filter=None, before=None, limit=None):
            yield 1
            yield 2

        def put(self, config, checkpoint, metadata, new_versions):
            return checkpoint

        def put_writes(self, config, writes, task_id, task_path=""):
            return writes

        def delete_thread(self, thread_id: str) -> None:
            self.deleted = thread_id

        def get_next_version(self, current, channel):
            return 5

        async def aget_tuple(self, config):
            return None

        async def aput(self, config, checkpoint, metadata, new_versions):
            return checkpoint

        async def alist(self, config, *, filter=None, before=None, limit=None):
            yield 1

        async def aput_writes(self, config, writes, task_id, task_path=""):
            return None

        async def adelete_thread(self, thread_id: str) -> None:
            return None

    saver = InstrumentedCheckpointer(FakeSaver())
    assert saver.config_specs == ["x"]
    assert saver.get_tuple({"t": 1}) == ("tuple", {"t": 1})
    assert list(saver.list({"t": 1})) == [1, 2]
    assert saver.put({}, {"a": 1}, {}, {}) == {"a": 1}
    assert saver.put_writes({}, [("a", 1)], "task") == [("a", 1)]
    saver.delete_thread("thread_1")
    assert saver.get_next_version(None, None) == 5


def test_instrumented_checkpointer_async_iterator_semantics(monkeypatch):
    monkeypatch.setenv("EASYADS_PERF_TRACE", "1")

    class FakeSaver(BaseCheckpointSaver):
        def __init__(self):
            super().__init__(serde=InMemorySaver().serde)

        @property
        def config_specs(self):
            return []

        def get_tuple(self, config):
            return None

        def list(self, config, *, filter=None, before=None, limit=None):
            yield 0

        def put(self, config, checkpoint, metadata, new_versions):
            return checkpoint

        def put_writes(self, config, writes, task_id, task_path=""):
            return None

        def delete_thread(self, thread_id: str) -> None:
            return None

        def get_next_version(self, current, channel):
            return 1

        async def aget_tuple(self, config):
            return ("tuple", config)

        async def aget(self, config):
            return {"config": config}

        async def alist(self, config, *, filter=None, before=None, limit=None):
            yield "a"
            yield "b"

        async def aput(self, config, checkpoint, metadata, new_versions):
            return checkpoint

        async def aput_writes(self, config, writes, task_id, task_path=""):
            return writes

        async def adelete_thread(self, thread_id: str) -> None:
            return None

    async def run():
        saver = InstrumentedCheckpointer(FakeSaver())
        values = []
        async for item in saver.alist({"t": 1}):
            values.append(item)
        return (
            await saver.aget_tuple({"t": 1}),
            await saver.aget({"t": 1}),
            await saver.aput({}, {"a": 1}, {}, {}),
            await saver.aput_writes({}, [("a", 1)], "task"),
            values,
        )

    result = asyncio.run(run())
    assert result == (("tuple", {"t": 1}), {"config": {"t": 1}}, {"a": 1}, [("a", 1)], ["a", "b"])


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
