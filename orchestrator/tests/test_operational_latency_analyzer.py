import pytest
from scripts.analyze_operational_e2e_latency import analyze, compare

def event(trace,operation,duration=None,sha="abc"):
    return {"trace_id":trace,"operation":operation,"duration_ms":duration,"git_commit_sha":sha,"measurement_source":"actual"}

def test_analyzer_rejects_trace_mismatch():
    with pytest.raises(ValueError,match="trace_id mismatch"): analyze([event("a","x")],[event("b","x")],[])

def test_analyzer_preserves_unavailable_and_sha_warning():
    result=analyze([event("a","poll_to_reducer",2,"a")],[event("a","bff_auth",4,"a")],[event("a","graph_execution",10,"b")])
    assert result["segments"]["workspace_lookup"] is None
    assert result["segments"]["bff_auth"]==4
    assert result["warnings"]==["deployment SHA mismatch"]

def test_analyzer_maps_real_bff_and_browser_operations():
    browser=[event("a","POST /api/generation-jobs",120) | {"event_type":"frontend_request"}]
    bff=[event("a","bff_request_total",100),event("a","bff_orchestrator_upstream",80),event("a","bff_auth",10)]
    result=analyze(browser,bff,[event("a","graph_execution",50)],"anonymous")
    assert result["segments"]["browser_to_bff"]==120
    assert result["segments"]["bff_total"]==100
    assert result["segments"]["bff_to_orchestrator"]==80

def test_analyzer_compares_anonymous_and_authenticated():
    anon=analyze([event("a","poll_to_reducer",2)],[event("a","bff_auth",4)],[event("a","graph_execution",10)],"anonymous")
    auth=analyze([event("b","poll_to_reducer",3)],[event("b","bff_auth",9)],[event("b","graph_execution",12)],"authenticated")
    result=compare(anon,auth)
    assert result["bff_auth_delta"]==5
    assert result["graph_delta"]==2
    assert "anonymous" in result["missing_by_mode"]


def test_analyzer_aggregates_structured_graph_llm_and_persistence_spans():
    browser = [
        event("a", "POST /api/generation-jobs", 100) | {"event_type": "frontend_request", "started_at": "2026-01-01T00:00:00Z"},
        event("a", "context_summary_visible", 0) | {"event_type": "render_mark", "started_at": "2026-01-01T00:00:02Z"},
        event("a", "POST /api/generation-jobs/job/answer", 90) | {"event_type": "frontend_request", "started_at": "2026-01-01T00:00:03Z"},
        event("a", "GET /api/generation-jobs/job", 40) | {"event_type": "frontend_request", "started_at": "2026-01-01T00:00:05Z"},
        event("a", "reducer_applied", 0) | {"event_type": "render_mark", "started_at": "2026-01-01T00:00:05.050Z"},
        event("a", "terminal_result_visible", 0) | {"event_type": "render_mark", "started_at": "2026-01-01T00:00:06Z"},
    ]
    orch = [
        event("a", "generation_job_create", 1800) | {"event_type": "graph_execution"},
        event("a", "product_understanding", 900) | {"event_type": "llm_call_finished"},
        event("a", "put", 100) | {"event_type": "checkpoint_write"},
        event("a", "result_persist", 200) | {"event_type": "result_persist"},
    ]

    result = analyze(browser, [], orch, "anonymous")

    assert result["segments"]["graph_execution"] == 1800
    assert result["segments"]["llm_critical_path"] == 900
    assert result["segments"]["checkpoint_write"] == 100
    assert result["segments"]["result_persist"] == 200
    assert result["metrics"]["browser_total_ms"] == 6000
    assert result["metrics"]["answer_to_done_ms"] == 3000
    assert result["production_path"]["railway_bff_in_critical_path"] is False


def test_analyzer_degrades_changed_deployment_and_missing_spans():
    result = analyze(
        [event("a", "POST /api/generation-jobs", 100, "one") | {"event_type": "frontend_request"}],
        [event("a", "bff_auth", 5, "one")],
        [event("a", "GET /api/v1/generation-jobs/job", 10, "two") | {"event_type": "api_request"}],
    )

    assert result["measurement_quality"] == "degraded"
    assert result["primary_class"] == "INSUFFICIENT_EVIDENCE"
    assert "DEPLOYMENT_OR_RESTART_NEAR_RUN" in result["blocked_reasons"]
    assert "graph_execution" in result["missing_evidence"]
