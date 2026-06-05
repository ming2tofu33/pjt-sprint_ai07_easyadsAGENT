"""Lazy Postgres connection helpers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from orchestrator.app.db.errors import DatabaseDependencyError
from orchestrator.app.db.settings import get_database_url, is_postgres_enabled


@contextmanager
def get_db_connection() -> Iterator[object]:
    if not is_postgres_enabled():
        raise RuntimeError("Postgres DB backend is not enabled.")
    try:
        import psycopg  # type: ignore
        from psycopg.rows import dict_row  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise DatabaseDependencyError("psycopg is required for EASYADS_DB_BACKEND=postgres.") from exc

    connection = psycopg.connect(get_database_url(required=True), row_factory=dict_row)
    try:
        yield connection
    finally:
        connection.close()


@contextmanager
def db_transaction(connection: object | None = None) -> Iterator[object]:
    if connection is not None:
        if hasattr(connection, "transaction"):
            with connection.transaction():
                yield connection
        else:
            # For tests with mock connections
            yield connection
        return
    with get_db_connection() as new_connection:
        with new_connection.transaction():
            yield new_connection
