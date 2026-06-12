"""LangGraph checkpointer factory.

Durable Postgres-backed saver when the existing DB contract is active
(EASYADS_DB_BACKEND=postgres + DATABASE_URL), in-memory saver otherwise.
HITL interrupt/resume (Command(resume=...)) only survives process restarts
in postgres mode; memory mode remains the default for tests and local dev.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any


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
        return _build_postgres_checkpointer()
    try:
        from langgraph.checkpoint.memory import InMemorySaver
    except ImportError:  # pragma: no cover - older langgraph naming
        from langgraph.checkpoint.memory import MemorySaver as InMemorySaver
    return InMemorySaver()
