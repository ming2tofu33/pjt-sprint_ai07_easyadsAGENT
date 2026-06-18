from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from atexit import register as atexit_register
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter_ns
from typing import Any, Iterator
from uuid import uuid4


logger = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data/performance/baseline_v1/raw"
TRACE_ID_CTX: ContextVar[str | None] = ContextVar("easyads_perf_trace_id", default=None)
REQUEST_ID_CTX: ContextVar[str | None] = ContextVar("easyads_perf_request_id", default=None)
SCENARIO_ID_CTX: ContextVar[str | None] = ContextVar("easyads_perf_scenario_id", default=None)
RUN_ID_CTX: ContextVar[str | None] = ContextVar("easyads_perf_run_id", default=None)
COLD_WARM_CTX: ContextVar[str | None] = ContextVar("easyads_perf_cold_or_warm", default=None)
EVENT_SINK_CTX: ContextVar[Any | None] = ContextVar("easyads_perf_event_sink", default=None)
_WRITE_LOCK = threading.Lock()
_EVENT_BUFFER: list[str] = []
_BUFFER_LIMIT = 100


def perf_trace_enabled() -> bool:
    return os.getenv("EASYADS_PERF_TRACE", "0") == "1"


def frontend_perf_trace_enabled() -> bool:
    return os.getenv("NEXT_PUBLIC_EASYADS_PERF_TRACE", "0") == "1"


def perf_output_dir() -> Path:
    value = os.getenv("EASYADS_PERF_TRACE_OUTPUT_DIR")
    if not value:
        return DEFAULT_OUTPUT_DIR
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _process_events_path() -> Path:
    return perf_output_dir() / f"events-{os.getpid()}.jsonl"


def new_trace_id() -> str:
    return f"trace_{uuid4().hex}"


def new_request_id() -> str:
    return f"req_{uuid4().hex}"


def stable_hash(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def normalize_sql(sql: str) -> str:
    compact = " ".join(sql.split()).lower()
    out: list[str] = []
    in_string = False
    quote = ""
    for ch in compact:
        if in_string:
            if ch == quote:
                in_string = False
                out.append("?")
            continue
        if ch in {"'", '"'}:
            in_string = True
            quote = ch
            continue
        if ch.isdigit():
            if not out or out[-1] != "?":
                out.append("?")
            continue
        out.append(ch)
    return "".join(out)


def sql_fingerprint(sql: str) -> str:
    return hashlib.sha256(normalize_sql(sql).encode("utf-8")).hexdigest()[:16]


def estimate_json_size_bytes(value: Any) -> int | None:
    try:
        return len(json.dumps(value, ensure_ascii=False, default=str).encode("utf-8"))
    except Exception:
        return None


def top_channels(value: Any, *, limit: int | None = None) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    top_limit = limit or int(os.getenv("EASYADS_PERF_TRACE_TOP_CHANNELS", "10") or "10")
    rows: list[dict[str, Any]] = []
    for key, item in value.items():
        size = estimate_json_size_bytes(item)
        rows.append(
            {
                "channel_name": str(key),
                "estimated_size_bytes": size,
                "value_type": type(item).__name__,
                "list_length": len(item) if isinstance(item, list) else None,
                "dict_key_count": len(item) if isinstance(item, dict) else None,
            }
        )
    rows.sort(key=lambda row: row.get("estimated_size_bytes") or -1, reverse=True)
    return rows[:top_limit]


def bind_perf_context(
    *,
    trace_id: str | None = None,
    request_id: str | None = None,
    scenario_id: str | None = None,
    run_id: str | None = None,
    cold_or_warm: str | None = None,
) -> dict[str, object]:
    tokens: dict[str, object] = {}
    if trace_id is not None:
        tokens["trace_id"] = TRACE_ID_CTX.set(trace_id)
    if request_id is not None:
        tokens["request_id"] = REQUEST_ID_CTX.set(request_id)
    if scenario_id is not None:
        tokens["scenario_id"] = SCENARIO_ID_CTX.set(scenario_id)
    if run_id is not None:
        tokens["run_id"] = RUN_ID_CTX.set(run_id)
    if cold_or_warm is not None:
        tokens["cold_or_warm"] = COLD_WARM_CTX.set(cold_or_warm)
    return tokens


def reset_perf_context(tokens: dict[str, object]) -> None:
    for key, token in tokens.items():
        if key == "trace_id":
            TRACE_ID_CTX.reset(token)  # type: ignore[arg-type]
        elif key == "request_id":
            REQUEST_ID_CTX.reset(token)  # type: ignore[arg-type]
        elif key == "scenario_id":
            SCENARIO_ID_CTX.reset(token)  # type: ignore[arg-type]
        elif key == "run_id":
            RUN_ID_CTX.reset(token)  # type: ignore[arg-type]
        elif key == "cold_or_warm":
            COLD_WARM_CTX.reset(token)  # type: ignore[arg-type]


def current_perf_context() -> dict[str, str | None]:
    return {
        "trace_id": TRACE_ID_CTX.get(),
        "request_id": REQUEST_ID_CTX.get(),
        "scenario_id": SCENARIO_ID_CTX.get(),
        "run_id": RUN_ID_CTX.get(),
        "cold_or_warm": COLD_WARM_CTX.get(),
    }


def ensure_trace_id() -> str:
    trace_id = TRACE_ID_CTX.get()
    if trace_id:
        return trace_id
    trace_id = new_trace_id()
    TRACE_ID_CTX.set(trace_id)
    return trace_id


def ensure_request_id() -> str:
    request_id = REQUEST_ID_CTX.get()
    if request_id:
        return request_id
    request_id = new_request_id()
    REQUEST_ID_CTX.set(request_id)
    return request_id


def build_event(
    event_type: str,
    *,
    operation: str,
    duration_ms: float,
    status: str = "ok",
    component: str = "orchestrator",
    metadata: dict[str, Any] | None = None,
    started_at: str | None = None,
) -> dict[str, Any]:
    context = current_perf_context()
    return {
        "schema_version": 1,
        "event_type": event_type,
        "trace_id": context["trace_id"],
        "request_id": context["request_id"],
        "scenario_id": context["scenario_id"],
        "run_id": context["run_id"],
        "cold_or_warm": context["cold_or_warm"],
        "component": component,
        "operation": operation,
        "started_at": started_at or now_iso(),
        "duration_ms": round(max(duration_ms, 0.0), 3),
        "status": status,
        "metadata": metadata or {},
    }


def record_perf_event(event: dict[str, Any]) -> None:
    if not perf_trace_enabled():
        return
    sink = EVENT_SINK_CTX.get()
    if sink is not None:
        sink(event)
        return
    try:
        path = _process_events_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False, default=str) + "\n"
        with _WRITE_LOCK:
            _EVENT_BUFFER.append(line)
            if len(_EVENT_BUFFER) >= _BUFFER_LIMIT:
                _flush_locked(path)
    except Exception:
        logger.debug("performance instrumentation failed", exc_info=True)


def _flush_locked(path: Path | None = None) -> None:
    if not _EVENT_BUFFER:
        return
    target = path or _process_events_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.writelines(_EVENT_BUFFER)
    _EVENT_BUFFER.clear()


def flush_perf_events() -> None:
    if not perf_trace_enabled():
        return
    try:
        with _WRITE_LOCK:
            _flush_locked()
    except Exception:
        logger.debug("performance flush failed", exc_info=True)


def clear_perf_event_buffer() -> None:
    with _WRITE_LOCK:
        _EVENT_BUFFER.clear()


@dataclass
class PerfTimer:
    event_type: str
    operation: str
    component: str = "orchestrator"
    metadata: dict[str, Any] | None = None
    started_at: str | None = None
    _start_ns: int | None = None
    _end_ns: int | None = None

    def start(self) -> "PerfTimer":
        self.started_at = now_iso()
        self._start_ns = perf_counter_ns()
        return self

    def finish(self, *, status: str = "ok", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        end_ns = perf_counter_ns()
        self._end_ns = end_ns
        duration_ms = 0.0 if self._start_ns is None else (end_ns - self._start_ns) / 1_000_000
        payload = build_event(
            self.event_type,
            operation=self.operation,
            duration_ms=duration_ms,
            status=status,
            component=self.component,
            metadata={**(self.metadata or {}), **(metadata or {})},
            started_at=self.started_at,
        )
        payload["started_at_ns"] = self._start_ns
        payload["ended_at_ns"] = end_ns
        record_perf_event(payload)
        return payload


@contextmanager
def capture_perf_events(sink) -> Iterator[None]:
    """Context-local event capture; safe across failures and concurrent contexts."""
    token = EVENT_SINK_CTX.set(sink)
    try:
        yield
    finally:
        EVENT_SINK_CTX.reset(token)


@contextmanager
def perf_span(
    event_type: str,
    *,
    operation: str,
    component: str = "orchestrator",
    metadata: dict[str, Any] | None = None,
) -> Iterator[PerfTimer]:
    timer = PerfTimer(event_type=event_type, operation=operation, component=component, metadata=metadata).start()
    try:
        yield timer
    except Exception as exc:
        timer.finish(status="error", metadata={"exception_type": type(exc).__name__})
        raise
    else:
        timer.finish()


atexit_register(flush_perf_events)
