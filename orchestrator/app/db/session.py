"""Lazy Postgres connection helpers."""

from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter_ns
from typing import Any, Iterator

from orchestrator.app.db.errors import DatabaseDependencyError
from orchestrator.app.db.settings import get_database_url, is_postgres_enabled
from orchestrator.app.observability.performance import (
    build_event,
    estimate_json_size_bytes,
    perf_trace_enabled,
    record_perf_event,
    sql_fingerprint,
)


def _sql_operation(sql: object) -> str:
    text = str(sql or "").lstrip()
    return text.split(" ", 1)[0].upper() if text else "UNKNOWN"


def _table_names(sql: object) -> list[str]:
    text = " ".join(str(sql or "").replace("\n", " ").split()).lower()
    tables: list[str] = []
    for token in (" from ", " join ", " update ", " into "):
        if token not in text:
            continue
        tail = text.split(token, 1)[1]
        candidate = tail.split(" ", 1)[0].strip(",;")
        if candidate and candidate not in tables:
            tables.append(candidate)
    return tables


class TransactionMetrics:
    def __init__(self, transaction_id: str, *, connection_reused: bool):
        self.transaction_id = transaction_id
        self.connection_reused = connection_reused
        self.query_count = 0
        self.query_duration_ms = 0.0
        self.row_count = 0


class InstrumentedCursor:
    def __init__(self, inner: Any, *, repository: str = "db", metrics: TransactionMetrics):
        self._inner = inner
        self._repository = repository
        self._metrics = metrics
        self._last_query_metadata: dict[str, Any] | None = None

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def __enter__(self):
        enter = getattr(self._inner, "__enter__", None)
        if callable(enter):
            enter()
        return self

    def __exit__(self, exc_type, exc, tb):
        exit_fn = getattr(self._inner, "__exit__", None)
        if callable(exit_fn):
            return exit_fn(exc_type, exc, tb)
        return None

    def _record_query(self, sql: object, params: object, duration_ms: float, *, status: str, exception_type: str | None = None):
        params_size = estimate_json_size_bytes(params)
        metadata = {
            "repository": self._repository,
            "sql_operation": _sql_operation(sql),
            "query_fingerprint": sql_fingerprint(str(sql)),
            "transaction_id": self._metrics.transaction_id,
            "query_param_size_bytes": params_size,
            "query_param_size_method": "json_estimate" if params_size is not None else "unavailable",
            "table_names": _table_names(sql),
            "row_count": getattr(self._inner, "rowcount", None),
            "exception_type": exception_type,
        }
        self._last_query_metadata = metadata
        self._metrics.query_count += 1
        self._metrics.query_duration_ms += duration_ms
        record_perf_event(
            build_event(
                "db_query",
                operation="query",
                duration_ms=duration_ms,
                status=status,
                metadata=metadata,
            )
        )

    def execute(self, sql, params=None):
        if not perf_trace_enabled():
            return self._inner.execute(sql, params)
        started = perf_counter_ns()
        try:
            result = self._inner.execute(sql, params)
        except Exception as exc:
            self._record_query(sql, params, (perf_counter_ns() - started) / 1_000_000, status="error", exception_type=type(exc).__name__)
            raise
        self._record_query(sql, params, (perf_counter_ns() - started) / 1_000_000, status="ok")
        return result

    def executemany(self, sql, params_seq):
        if not perf_trace_enabled():
            return self._inner.executemany(sql, params_seq)
        started = perf_counter_ns()
        try:
            result = self._inner.executemany(sql, params_seq)
        except Exception as exc:
            self._record_query(sql, params_seq, (perf_counter_ns() - started) / 1_000_000, status="error", exception_type=type(exc).__name__)
            raise
        self._record_query(sql, params_seq, (perf_counter_ns() - started) / 1_000_000, status="ok")
        return result

    def _record_fetch(self, operation: str, rows: Any):
        if not perf_trace_enabled() or self._last_query_metadata is None:
            return
        if isinstance(rows, list):
            row_count = len(rows)
            payload = rows
        elif rows is None:
            row_count = 0
            payload = None
        else:
            row_count = 1
            payload = rows
        self._metrics.row_count += row_count
        payload_size = estimate_json_size_bytes(payload)
        record_perf_event(
            build_event(
                "db_fetch",
                operation=operation,
                duration_ms=0.0,
                metadata={
                    **self._last_query_metadata,
                    "row_count": row_count,
                    "response_size_bytes": payload_size,
                    "response_size_method": "json_estimate" if payload_size is not None else "unavailable",
                },
            )
        )

    def fetchone(self):
        row = self._inner.fetchone()
        self._record_fetch("fetchone", row)
        return row

    def fetchall(self):
        rows = self._inner.fetchall()
        self._record_fetch("fetchall", rows)
        return rows


class InstrumentedConnection:
    def __init__(self, inner: Any, *, metrics: TransactionMetrics):
        self._inner = inner
        self._metrics = metrics

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def cursor(self, *args, **kwargs):
        return InstrumentedCursor(self._inner.cursor(*args, **kwargs), metrics=self._metrics)


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
    transaction_id = f"tx_{perf_counter_ns()}"
    metrics = TransactionMetrics(transaction_id, connection_reused=connection is not None)
    started = perf_counter_ns()
    status = "committed"
    exception_type = None

    def emit():
        if not perf_trace_enabled():
            return
        record_perf_event(
            build_event(
                "db_transaction",
                operation="transaction",
                duration_ms=(perf_counter_ns() - started) / 1_000_000,
                status="ok" if status == "committed" else "error",
                metadata={
                    "transaction_id": metrics.transaction_id,
                    "connection_reused": metrics.connection_reused,
                    "transaction_status": status,
                    "query_count": metrics.query_count,
                    "query_duration_ms": round(metrics.query_duration_ms, 3),
                    "fetched_row_count": metrics.row_count,
                    "exception_type": exception_type,
                },
            )
        )

    try:
        if connection is not None:
            if hasattr(connection, "transaction"):
                with connection.transaction():
                    yield InstrumentedConnection(connection, metrics=metrics) if perf_trace_enabled() else connection
            else:
                yield InstrumentedConnection(connection, metrics=metrics) if perf_trace_enabled() else connection
            return

        with get_db_connection() as new_connection:
            with new_connection.transaction():
                yield InstrumentedConnection(new_connection, metrics=metrics) if perf_trace_enabled() else new_connection
    except Exception as exc:
        status = "rolled_back"
        exception_type = type(exc).__name__
        raise
    finally:
        emit()
