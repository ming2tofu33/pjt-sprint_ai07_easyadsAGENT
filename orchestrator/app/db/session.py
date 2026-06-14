"""Lazy Postgres connection helpers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from orchestrator.app.db.errors import DatabaseDependencyError
from orchestrator.app.db.settings import get_database_url, is_postgres_enabled
from orchestrator.app.observability.performance import perf_trace_enabled, record_perf_event, sql_fingerprint


class InstrumentedCursor:
    def __init__(self, inner, *, repository: str = "db", transaction_id: str | None = None):
        self._inner = inner
        self._repository = repository
        self._transaction_id = transaction_id

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def execute(self, sql, params=None):
        if not perf_trace_enabled():
            return self._inner.execute(sql, params)
        import time

        started = time.perf_counter_ns()
        try:
            result = self._inner.execute(sql, params)
        except Exception as exc:
            duration_ms = (time.perf_counter_ns() - started) / 1_000_000
            record_perf_event(
                {
                    "schema_version": 1,
                    "event_type": "db_query",
                    "trace_id": None,
                    "request_id": None,
                    "scenario_id": None,
                    "run_id": None,
                    "cold_or_warm": None,
                    "component": "orchestrator",
                    "operation": "query",
                    "started_at": None,
                    "duration_ms": round(duration_ms, 3),
                    "status": "error",
                    "metadata": {
                        "repository": self._repository,
                        "sql_operation": str(sql).lstrip().split(" ", 1)[0].upper() if sql else "UNKNOWN",
                        "query_fingerprint": sql_fingerprint(str(sql)),
                        "transaction_id": self._transaction_id,
                        "exception_type": type(exc).__name__,
                    },
                }
            )
            raise
        duration_ms = (time.perf_counter_ns() - started) / 1_000_000
        record_perf_event(
            {
                "schema_version": 1,
                "event_type": "db_query",
                "trace_id": None,
                "request_id": None,
                "scenario_id": None,
                "run_id": None,
                "cold_or_warm": None,
                "component": "orchestrator",
                "operation": "query",
                "started_at": None,
                "duration_ms": round(duration_ms, 3),
                "status": "ok",
                "metadata": {
                    "repository": self._repository,
                    "sql_operation": str(sql).lstrip().split(" ", 1)[0].upper() if sql else "UNKNOWN",
                    "query_fingerprint": sql_fingerprint(str(sql)),
                    "transaction_id": self._transaction_id,
                    "row_count": getattr(self._inner, "rowcount", None),
                },
            }
        )
        return result


class InstrumentedConnection:
    def __init__(self, inner, *, transaction_id: str):
        self._inner = inner
        self._transaction_id = transaction_id

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def cursor(self, *args, **kwargs):
        manager = self._inner.cursor(*args, **kwargs)

        class CursorContext:
            def __enter__(self_nonlocal):
                return InstrumentedCursor(manager.__enter__(), transaction_id=self._transaction_id)

            def __exit__(self_nonlocal, exc_type, exc, tb):
                return manager.__exit__(exc_type, exc, tb)

        return CursorContext()


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
    import time

    transaction_id = f"tx_{time.perf_counter_ns()}"
    started = time.perf_counter_ns()
    if connection is not None:
        if hasattr(connection, "transaction"):
            with connection.transaction():
                yield InstrumentedConnection(connection, transaction_id=transaction_id) if perf_trace_enabled() else connection
        else:
            # For tests with mock connections
            yield InstrumentedConnection(connection, transaction_id=transaction_id) if perf_trace_enabled() else connection
        if perf_trace_enabled():
            duration_ms = (time.perf_counter_ns() - started) / 1_000_000
            record_perf_event(
                {
                    "schema_version": 1,
                    "event_type": "db_transaction",
                    "trace_id": None,
                    "request_id": None,
                    "scenario_id": None,
                    "run_id": None,
                    "cold_or_warm": None,
                    "component": "orchestrator",
                    "operation": "transaction",
                    "started_at": None,
                    "duration_ms": round(duration_ms, 3),
                    "status": "ok",
                    "metadata": {"transaction_id": transaction_id, "connection_reused": True},
                }
            )
        return
    with get_db_connection() as new_connection:
        with new_connection.transaction():
            yield InstrumentedConnection(new_connection, transaction_id=transaction_id) if perf_trace_enabled() else new_connection
        if perf_trace_enabled():
            duration_ms = (time.perf_counter_ns() - started) / 1_000_000
            record_perf_event(
                {
                    "schema_version": 1,
                    "event_type": "db_transaction",
                    "trace_id": None,
                    "request_id": None,
                    "scenario_id": None,
                    "run_id": None,
                    "cold_or_warm": None,
                    "component": "orchestrator",
                    "operation": "transaction",
                    "started_at": None,
                    "duration_ms": round(duration_ms, 3),
                    "status": "ok",
                    "metadata": {"transaction_id": transaction_id, "connection_reused": False},
                }
            )
