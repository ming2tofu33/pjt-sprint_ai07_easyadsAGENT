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
        target = getattr(self._inner, name)
        if name not in {"put", "put_writes", "aput", "aput_writes", "get", "aget", "list"} or not callable(target):
            return target

        def wrapper(*args, **kwargs):
            if not perf_trace_enabled():
                return target(*args, **kwargs)
            metadata = {
                "operation": name,
                "arg_count": len(args),
                "kwarg_keys": sorted(kwargs.keys()),
            }
            if args:
                metadata["checkpoint_size_bytes"] = estimate_json_size_bytes(args[-1])
                metadata["top_channels"] = top_channels(args[-1])
            with perf_span("checkpoint_save", operation=name, metadata=metadata):
                return target(*args, **kwargs)

        return wrapper


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
