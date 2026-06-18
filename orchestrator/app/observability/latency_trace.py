from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

SAFE_TELEMETRY_TOKEN_KEYS = {"input_tokens", "output_tokens", "cached_tokens", "reasoning_tokens", "token_source"}
SENSITIVE_EXACT_KEYS = {"access_token", "refresh_token", "authorization", "cookie", "api_key", "secret", "password", "raw_prompt", "raw_response", "email"}
SENSITIVE_SUFFIX_KEYS = ("_access_token", "_refresh_token", "_api_key", "_secret", "_password")


class LatencySpan(BaseModel):
    trace_id: str
    span_id: str = Field(default_factory=lambda: f"span_{uuid4().hex}")
    parent_span_id: str | None = None
    layer: str
    operation: str
    kind: Literal["deterministic", "llm", "db", "external_io", "interrupt", "persistence", "network", "ui", "unknown"]
    started_offset_ms: float = Field(default=0, ge=0)
    ended_offset_ms: float | None = Field(default=None, ge=0)
    duration_ms: float = Field(ge=0)
    is_container_span: bool = False
    depends_on_span_ids: list[str] = Field(default_factory=list)
    parallel_group_id: str | None = None
    status: str = "ok"
    attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_timing(self):
        if self.ended_offset_ms is None:
            self.ended_offset_ms = self.started_offset_ms + self.duration_ms
        if self.ended_offset_ms < self.started_offset_ms:
            raise ValueError("ended_offset_ms must be >= started_offset_ms")
        if abs((self.ended_offset_ms - self.started_offset_ms) - self.duration_ms) > 1.0:
            raise ValueError("duration_ms must match ended_offset_ms - started_offset_ms")
        return self


class GenerationLatencyReport(BaseModel):
    trace_id: str
    total_wall_ms: float
    llm_call_count: int = 0
    llm_sequential_call_count: int = 0
    llm_total_sum_ms: float = 0
    llm_critical_path_ms: float = 0
    deterministic_node_sum_ms: float = 0
    db_sum_ms: float = 0
    external_io_sum_ms: float = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    reasoning_tokens: int | None = None
    dominant_latency_class: str = "INSUFFICIENT_EVIDENCE"
    confidence: float = 0
    evidence: list[str] = Field(default_factory=list)
    counter_evidence: list[str] = Field(default_factory=list)
    measurement_source: str = "unavailable"
    additional_measurement_needed: list[str] = Field(default_factory=list)


def safe_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def redact(value: Any, key: str = "") -> Any:
    normalized = key.lower()
    sensitive = normalized in SENSITIVE_EXACT_KEYS or normalized.endswith(SENSITIVE_SUFFIX_KEYS)
    if normalized not in SAFE_TELEMETRY_TOKEN_KEYS and sensitive:
        return "[REDACTED]"
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return str(value)


def _execution_spans(spans: list[LatencySpan]) -> list[LatencySpan]:
    return [span for span in spans if not span.is_container_span]


def critical_path(spans: list[LatencySpan]) -> tuple[float, list[LatencySpan]]:
    """Longest execution-dependency DAG path; hierarchy never implies dependency."""
    execution = _execution_spans(spans)
    by_id = {span.span_id: span for span in execution}
    state: dict[str, int] = {}
    memo: dict[str, tuple[float, list[LatencySpan]]] = {}

    def visit(span_id: str) -> tuple[float, list[LatencySpan]]:
        if state.get(span_id) == 1:
            raise ValueError(f"dependency cycle detected at {span_id}")
        if span_id in memo:
            return memo[span_id]
        state[span_id] = 1
        span = by_id[span_id]
        dependencies = [visit(dep) for dep in span.depends_on_span_ids if dep in by_id]
        previous_ms, previous_path = max(dependencies, key=lambda item: item[0], default=(0.0, []))
        result = previous_ms + span.duration_ms, [*previous_path, span]
        state[span_id] = 2
        memo[span_id] = result
        return result

    return max((visit(span_id) for span_id in by_id), key=lambda item: item[0], default=(0.0, []))


def interval_union_ms(spans: list[LatencySpan]) -> float:
    intervals = sorted((s.started_offset_ms, s.ended_offset_ms or s.started_offset_ms) for s in _execution_spans(spans))
    total = 0.0
    start = end = None
    for left, right in intervals:
        if start is None:
            start, end = left, right
        elif left <= end:
            end = max(end, right)
        else:
            total += end - start
            start, end = left, right
    return total + (end - start if start is not None else 0)


def build_report(trace_id: str, spans: list[LatencySpan], *, total_wall_ms: float | None = None, source: str = "unavailable") -> GenerationLatencyReport:
    wall = total_wall_ms if total_wall_ms is not None else max((s.ended_offset_ms or 0 for s in spans), default=0)
    _, path = critical_path(spans)
    llm = [s for s in _execution_spans(spans) if s.kind == "llm"]
    llm_path = [s for s in path if s.kind == "llm"]
    def token_total(name: str) -> int | None:
        values = [int(s.attributes[name]) for s in llm if isinstance(s.attributes.get(name), int)]
        return sum(values) if values else None
    llm_critical = sum(s.duration_ms for s in llm_path)
    dominant, confidence, evidence = "INSUFFICIENT_EVIDENCE", 0.3 if spans else 0.0, []
    if source == "actual" and len(llm_path) >= 2 and wall and llm_critical / wall >= 0.5:
        dominant, confidence, evidence = "GRAPH_SERIAL_LLM_ACCUMULATION", 0.9, ["multiple_llm_calls_on_dependency_path"]
    elif source == "actual" and len(llm) == 1 and wall and llm[0].duration_ms / wall >= 0.5:
        dominant, confidence, evidence = "SINGLE_LLM_PROVIDER_DOMINANT", 0.85, ["single_llm_over_half_wall_time"]
    return GenerationLatencyReport(
        trace_id=trace_id, total_wall_ms=round(wall, 3), llm_call_count=len(llm), llm_sequential_call_count=len(llm_path),
        llm_total_sum_ms=round(sum(s.duration_ms for s in llm), 3), llm_critical_path_ms=round(llm_critical, 3),
        deterministic_node_sum_ms=round(sum(s.duration_ms for s in _execution_spans(spans) if s.kind == "deterministic"), 3),
        db_sum_ms=round(sum(s.duration_ms for s in _execution_spans(spans) if s.kind == "db"), 3),
        external_io_sum_ms=round(sum(s.duration_ms for s in _execution_spans(spans) if s.kind == "external_io"), 3),
        input_tokens=token_total("input_tokens"), output_tokens=token_total("output_tokens"), cached_tokens=token_total("cached_tokens"),
        reasoning_tokens=token_total("reasoning_tokens"), dominant_latency_class=dominant, confidence=confidence, evidence=evidence,
        measurement_source=source, additional_measurement_needed=[] if source == "actual" else ["approved actual cold/warm trace"],
    )


def json_safe_dump(payload: Any) -> str:
    return json.dumps(redact(payload), ensure_ascii=False, indent=2) + "\n"
