from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


JSONSafeValue = str | int | float | bool | None | list["JSONSafeValue"] | dict[str, "JSONSafeValue"]
_SENSITIVE = {"authorization", "cookie", "access_token", "api_key", "prompt", "raw_prompt", "raw_response", "email"}


class LatencySpan(BaseModel):
    trace_id: str
    span_id: str = Field(default_factory=lambda: f"span_{uuid4().hex}")
    parent_span_id: str | None = None
    layer: str
    operation: str
    kind: Literal["deterministic", "llm", "db", "external_io", "interrupt", "persistence", "network", "ui"]
    duration_ms: float = Field(ge=0)
    status: str = "ok"
    started_offset_ms: float = Field(default=0, ge=0)
    attributes: dict[str, Any] = Field(default_factory=dict)


class GenerationLatencyReport(BaseModel):
    trace_id: str
    total_wall_ms: float
    browser_to_bff_ms: float | None = None
    bff_auth_ms: float | None = None
    bff_to_orchestrator_ms: float | None = None
    job_create_ms: float | None = None
    graph_queue_wait_ms: float | None = None
    graph_execution_ms: float | None = None
    graph_persist_ms: float | None = None
    terminal_to_ui_ms: float | None = None
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
    cold_start_suspected: bool = False
    dominant_latency_class: str = "INSUFFICIENT_EVIDENCE"
    confidence: float = 0
    evidence_codes: list[str] = Field(default_factory=list)


def safe_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def redact(value: Any, key: str = "") -> JSONSafeValue:
    if key.lower() in _SENSITIVE or any(part in key.lower() for part in ("secret", "token", "password")):
        return "[REDACTED]"
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return str(value)


def critical_path(spans: list[LatencySpan]) -> tuple[float, list[LatencySpan]]:
    """Return longest parent/child path. Siblings are treated as parallel."""
    by_parent: dict[str | None, list[LatencySpan]] = defaultdict(list)
    ids = {span.span_id for span in spans}
    for span in spans:
        by_parent[span.parent_span_id if span.parent_span_id in ids else None].append(span)

    def visit(span: LatencySpan, seen: frozenset[str]) -> tuple[float, list[LatencySpan]]:
        if span.span_id in seen:
            return 0, []
        children = [visit(child, seen | {span.span_id}) for child in by_parent[span.span_id]]
        child_ms, child_path = max(children, key=lambda item: item[0], default=(0, []))
        return span.duration_ms + child_ms, [span, *child_path]

    return max((visit(root, frozenset()) for root in by_parent[None]), key=lambda item: item[0], default=(0, []))


def build_report(trace_id: str, spans: list[LatencySpan], *, total_wall_ms: float | None = None) -> GenerationLatencyReport:
    wall = total_wall_ms if total_wall_ms is not None else max((s.started_offset_ms + s.duration_ms for s in spans), default=0)
    _, path = critical_path(spans)
    llm = [s for s in spans if s.kind == "llm"]
    llm_path = [s for s in path if s.kind == "llm"]
    tokens = lambda name: sum(int(s.attributes.get(name) or 0) for s in llm)
    evidence: list[str] = []
    dominant = "INSUFFICIENT_EVIDENCE"
    confidence = 0.35 if spans else 0
    llm_critical = sum(s.duration_ms for s in llm_path)
    if len(llm_path) >= 2 and wall and llm_critical / wall >= 0.5:
        dominant, confidence = "GRAPH_SERIAL_LLM_ACCUMULATION", min(0.95, 0.65 + llm_critical / wall * 0.25)
        evidence.append("GRAPH_SERIAL_LLM_ACCUMULATION")
    elif len(llm) == 1 and wall and llm[0].duration_ms / wall >= 0.5:
        dominant, confidence = "SINGLE_LLM_PROVIDER_DOMINANT", 0.85
        evidence.append("SINGLE_LLM_PROVIDER_DOMINANT")
    elif any(s.operation in {"polling_visibility", "terminal_to_ui"} and wall and s.duration_ms / wall >= 0.25 for s in spans):
        dominant, confidence = "POLLING_VISIBILITY_DELAY", 0.8
        evidence.append("POLLING_VISIBILITY_DELAY")
    return GenerationLatencyReport(
        trace_id=trace_id, total_wall_ms=round(wall, 3), llm_call_count=len(llm),
        llm_sequential_call_count=len(llm_path), llm_total_sum_ms=sum(s.duration_ms for s in llm),
        llm_critical_path_ms=llm_critical,
        deterministic_node_sum_ms=sum(s.duration_ms for s in spans if s.kind == "deterministic"),
        db_sum_ms=sum(s.duration_ms for s in spans if s.kind == "db"),
        external_io_sum_ms=sum(s.duration_ms for s in spans if s.kind == "external_io"),
        input_tokens=tokens("input_tokens") if any("input_tokens" in s.attributes for s in llm) else None,
        output_tokens=tokens("output_tokens") if any("output_tokens" in s.attributes for s in llm) else None,
        cached_tokens=tokens("cached_tokens") if any("cached_tokens" in s.attributes for s in llm) else None,
        dominant_latency_class=dominant, confidence=round(confidence, 3), evidence_codes=evidence,
    )


def json_safe_dump(payload: Any) -> str:
    return json.dumps(redact(payload), ensure_ascii=False, indent=2) + "\n"
