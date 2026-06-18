import pytest
from orchestrator.app.observability.latency_trace import LatencySpan, build_report, critical_path, interval_union_ms, redact

def s(name,duration,*,deps=None,offset=0,container=False,kind="deterministic",attrs=None,parent=None):
    return LatencySpan(trace_id="t",span_id=name,parent_span_id=parent,layer="x",operation=name,kind=kind,started_offset_ms=offset,ended_offset_ms=offset+duration,duration_ms=duration,is_container_span=container,depends_on_span_ids=deps or [],attributes=attrs or {})

def test_safe_telemetry_token_redaction():
    value=redact({"input_tokens":120,"cached_tokens":80,"access_token":"abc","refresh_token":"abc","nested":{"authorization":"x"},"raw_prompt":"p"})
    assert value=={"input_tokens":120,"cached_tokens":80,"access_token":"[REDACTED]","refresh_token":"[REDACTED]","nested":{"authorization":"[REDACTED]"},"raw_prompt":"[REDACTED]"}

def test_container_not_double_counted():
    duration,_=critical_path([s("graph",470,container=True),s("a",100),s("b",150,deps=["a"]),s("c",200,deps=["b"])])
    assert duration==450

def test_sequential_and_parallel_dag():
    assert critical_path([s("a",100),s("b",150,deps=["a"]),s("c",200,deps=["b"])])[0]==450
    assert critical_path([s("a",150),s("b",200)])[0]==200

def test_provider_child_hierarchy_not_dependency():
    assert critical_path([s("node",200),s("provider",180,parent="node",kind="llm")])[0]==200

def test_overlapping_intervals_union():
    assert interval_union_ms([s("a",150,offset=0),s("b",200,offset=100)])==300

def test_cycle_fails():
    with pytest.raises(ValueError,match="cycle"): critical_path([s("a",1,deps=["b"]),s("b",1,deps=["a"])])

def test_missing_parent_allowed_and_tokens_aggregate():
    spans=[s("a",60,kind="llm",parent="missing",attrs={"input_tokens":10,"cached_tokens":2}),s("b",50,kind="llm",deps=["a"],attrs={"input_tokens":20,"cached_tokens":3})]
    report=build_report("t",spans,total_wall_ms=120,source="instrumented_mock")
    assert (report.input_tokens,report.cached_tokens)==(30,5)
    assert report.dominant_latency_class=="INSUFFICIENT_EVIDENCE"

@pytest.mark.parametrize(("span","expected"),[
    (s("queue_wait",40),"WORKER_QUEUE_OR_COLD_START"),
    (s("checkpoint_write",40,kind="persistence"),"CHECKPOINT_OR_PERSISTENCE_OVERHEAD"),
    (s("workspace_lookup",40,kind="db"),"DB_OR_WORKSPACE_OVERHEAD"),
    (s("polling_visibility",40,kind="ui"),"POLLING_VISIBILITY_DELAY"),
])
def test_actual_non_llm_classifiers(span,expected):
    assert build_report("t",[span],total_wall_ms=100,source="actual").dominant_latency_class==expected
