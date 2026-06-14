"""LangGraph checkpointer factory.

Durable Postgres-backed saver when the existing DB contract is active
(EASYADS_DB_BACKEND=postgres + DATABASE_URL), in-memory saver otherwise.
HITL interrupt/resume (Command(resume=...)) only survives process restarts
in postgres mode; memory mode remains the default for tests and local dev.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver

from orchestrator.app.observability.performance import estimate_json_size_bytes, perf_span, perf_trace_enabled, top_channels


class InstrumentedCheckpointer(BaseCheckpointSaver):
    def __init__(self, inner: BaseCheckpointSaver):
        super().__init__(serde=inner.serde)
        self._inner = inner

    @property
    def config_specs(self):
        return self._inner.config_specs

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

    def get_tuple(self, config):
        if not perf_trace_enabled():
            return self._inner.get_tuple(config)
        with perf_span("checkpoint_read", operation="get_tuple", metadata={"operation": "get_tuple"}):
            return self._inner.get_tuple(config)

    def get(self, config):
        if not perf_trace_enabled():
            return self._inner.get(config)
        with perf_span("checkpoint_read", operation="get", metadata={"operation": "get"}):
            return self._inner.get(config)

    def list(self, config, *, filter=None, before=None, limit=None):
        iterator = self._inner.list(config, filter=filter, before=before, limit=limit)
        if not perf_trace_enabled():
            yield from iterator
            return
        with perf_span("checkpoint_list", operation="list", metadata={"operation": "list"}):
            yield from iterator

    def put(self, config, checkpoint, metadata, new_versions):
        if not perf_trace_enabled():
            return self._inner.put(config, checkpoint, metadata, new_versions)
        with perf_span(
            "checkpoint_write",
            operation="put",
            metadata=self._metadata("put", checkpoint, size_field="checkpoint_size_bytes"),
        ):
            return self._inner.put(config, checkpoint, metadata, new_versions)

    def put_writes(self, config, writes, task_id, task_path=""):
        if not perf_trace_enabled():
            return self._inner.put_writes(config, writes, task_id, task_path=task_path)
        with perf_span(
            "checkpoint_write_batch",
            operation="put_writes",
            metadata=self._metadata("put_writes", writes, size_field="writes_size_bytes"),
        ):
            return self._inner.put_writes(config, writes, task_id, task_path=task_path)

    def delete_thread(self, thread_id: str) -> None:
        return self._inner.delete_thread(thread_id)

    def get_next_version(self, current, channel):
        return self._inner.get_next_version(current, channel)

    async def aget_tuple(self, config):
        if not perf_trace_enabled():
            return await self._inner.aget_tuple(config)
        with perf_span("checkpoint_read", operation="aget_tuple", metadata={"operation": "aget_tuple"}):
            return await self._inner.aget_tuple(config)

    async def aget(self, config):
        if not perf_trace_enabled():
            return await self._inner.aget(config)
        with perf_span("checkpoint_read", operation="aget", metadata={"operation": "aget"}):
            return await self._inner.aget(config)

    async def alist(self, config, *, filter=None, before=None, limit=None):
        iterator = self._inner.alist(config, filter=filter, before=before, limit=limit)
        if not perf_trace_enabled():
            async for item in iterator:
                yield item
            return
        with perf_span("checkpoint_list", operation="alist", metadata={"operation": "alist"}):
            async for item in iterator:
                yield item

    async def aput(self, config, checkpoint, metadata, new_versions):
        if not perf_trace_enabled():
            return await self._inner.aput(config, checkpoint, metadata, new_versions)
        with perf_span(
            "checkpoint_write",
            operation="aput",
            metadata=self._metadata("aput", checkpoint, size_field="checkpoint_size_bytes"),
        ):
            return await self._inner.aput(config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=""):
        if not perf_trace_enabled():
            return await self._inner.aput_writes(config, writes, task_id, task_path=task_path)
        with perf_span(
            "checkpoint_write_batch",
            operation="aput_writes",
            metadata=self._metadata("aput_writes", writes, size_field="writes_size_bytes"),
        ):
            return await self._inner.aput_writes(config, writes, task_id, task_path=task_path)

    async def adelete_thread(self, thread_id: str) -> None:
        return await self._inner.adelete_thread(thread_id)


def _build_postgres_checkpointer() -> BaseCheckpointSaver:
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    from orchestrator.app.db.settings import get_database_url

    pool = ConnectionPool(
        get_database_url(required=True),
        max_size=4,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    checkpointer = PostgresSaver(pool)
    checkpointer.setup()
    return checkpointer


@lru_cache(maxsize=1)
def get_checkpointer() -> BaseCheckpointSaver:
    from orchestrator.app.db.settings import is_postgres_enabled

    if is_postgres_enabled():
        return InstrumentedCheckpointer(_build_postgres_checkpointer())
    try:
        from langgraph.checkpoint.memory import InMemorySaver
    except ImportError:  # pragma: no cover - older langgraph naming
        from langgraph.checkpoint.memory import MemorySaver as InMemorySaver
    return InstrumentedCheckpointer(InMemorySaver())
