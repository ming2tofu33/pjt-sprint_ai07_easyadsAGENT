from orchestrator.app.observability.latency_trace import LatencySpan, build_report, critical_path, redact


def span(name, duration, *, parent=None, kind="deterministic", offset=0, attributes=None):
    return LatencySpan(trace_id="trace_1", span_id=name, parent_span_id=parent, layer="test", operation=name,
                       kind=kind, duration_ms=duration, started_offset_ms=offset, attributes=attributes or {})


def test_span_duration_and_nested_critical_path():
    spans = [span("root", 10), span("a", 100, parent="root"), span("b", 30, parent="a")]
    duration, path = critical_path(spans)
    assert duration == 140
    assert [item.operation for item in path] == ["root", "a", "b"]


def test_parallel_siblings_are_not_summed_on_critical_path():
    spans = [span("root", 5), span("slow", 100, parent="root"), span("fast", 20, parent="root")]
    duration, path = critical_path(spans)
    assert duration == 105
    assert [item.operation for item in path] == ["root", "slow"]


def test_token_usage_and_serial_llm_classification():
    spans = [span("root", 10), span("llm1", 60, parent="root", kind="llm", attributes={"input_tokens": 10, "cached_tokens": 2}),
             span("llm2", 50, parent="llm1", kind="llm", attributes={"input_tokens": 20, "cached_tokens": 0})]
    report = build_report("trace_1", spans, total_wall_ms=120)
    assert report.llm_call_count == 2
    assert report.input_tokens == 30
    assert report.cached_tokens == 2
    assert report.dominant_latency_class == "GRAPH_SERIAL_LLM_ACCUMULATION"


def test_redaction_blocks_secrets_and_raw_prompts():
    value = redact({"authorization": "Bearer secret", "raw_prompt": "private", "safe": {"count": 2}})
    assert value == {"authorization": "[REDACTED]", "raw_prompt": "[REDACTED]", "safe": {"count": 2}}

