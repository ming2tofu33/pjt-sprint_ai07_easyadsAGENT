"""LangGraph checkpointer factory.

Durable Postgres-backed saver when the existing DB contract is active
(EASYADS_DB_BACKEND=postgres + DATABASE_URL), in-memory saver otherwise.
HITL interrupt/resume (Command(resume=...)) only survives process restarts
in postgres mode; memory mode remains the default for tests and local dev.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from orchestrator.app.observability.performance import estimate_json_size_bytes, perf_span, perf_trace_enabled, top_channels


class InstrumentedCheckpointer:
    def __init__(self, inner: Any):
        self._inner = inner

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def _metadata(self, operation: str, payload: Any, *, size_field: str) -> dict[str, Any]:
        size = estimate_json_size_bytes(payload)
        return {
            "operation": operation,
            size_field: size,
            "size_method": "json_estimate" if size is not None else "unavailable",
            "top_channels": top_channels(payload),
        }

    def put(self, config, checkpoint, metadata, new_versions):
        target = self._inner.put
        if not perf_trace_enabled():
            return target(config, checkpoint, metadata, new_versions)
        with perf_span("checkpoint_write", operation="put", metadata=self._metadata("put", checkpoint, size_field="checkpoint_size_bytes")):
            return target(config, checkpoint, metadata, new_versions)

    def put_writes(self, config, writes, task_id, task_path=""):
        target = self._inner.put_writes
        if not perf_trace_enabled():
            return target(config, writes, task_id, task_path=task_path)
        with perf_span("checkpoint_write_batch", operation="put_writes", metadata=self._metadata("put_writes", writes, size_field="writes_size_bytes")):
            return target(config, writes, task_id, task_path=task_path)

    async def aput(self, config, checkpoint, metadata, new_versions):
        target = self._inner.aput
        if not perf_trace_enabled():
            return await target(config, checkpoint, metadata, new_versions)
        with perf_span("checkpoint_write", operation="aput", metadata=self._metadata("aput", checkpoint, size_field="checkpoint_size_bytes")):
            return await target(config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=""):
        target = self._inner.aput_writes
        if not perf_trace_enabled():
            return await target(config, writes, task_id, task_path=task_path)
        with perf_span("checkpoint_write_batch", operation="aput_writes", metadata=self._metadata("aput_writes", writes, size_field="writes_size_bytes")):
            return await target(config, writes, task_id, task_path=task_path)

    def get(self, config):
        target = self._inner.get
        if not perf_trace_enabled():
            return target(config)
        with perf_span("checkpoint_read", operation="get", metadata={"operation": "get"}):
            return target(config)

    async def aget(self, config):
        target = self._inner.aget
        if not perf_trace_enabled():
            return await target(config)
        with perf_span("checkpoint_read", operation="aget", metadata={"operation": "aget"}):
            return await target(config)

    def list(self, *args, **kwargs):
        target = self._inner.list
        if not perf_trace_enabled():
            return target(*args, **kwargs)
        with perf_span("checkpoint_list", operation="list", metadata={"operation": "list"}):
            return list(target(*args, **kwargs))


def _build_postgres_checkpointer() -> Any:
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    from orchestrator.app.db.settings import get_database_url

    # PostgresSaver requires autocommit connections with dict_row factory.
    # The pool lives for the process lifetime (singleton via get_checkpointer).
    pool = ConnectionPool(
        get_database_url(required=True),
        max_size=4,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    checkpointer = PostgresSaver(pool)
    # Idempotent: creates checkpoints/checkpoint_blobs/checkpoint_writes tables
    # and runs the library's own schema migrations on first call.
    checkpointer.setup()
    return checkpointer


@lru_cache(maxsize=1)
def get_checkpointer() -> Any:
    from orchestrator.app.db.settings import is_postgres_enabled

    if is_postgres_enabled():
        return InstrumentedCheckpointer(_build_postgres_checkpointer())
    try:
        from langgraph.checkpoint.memory import InMemorySaver
    except ImportError:  # pragma: no cover - older langgraph naming
        from langgraph.checkpoint.memory import MemorySaver as InMemorySaver
    return InstrumentedCheckpointer(InMemorySaver())
