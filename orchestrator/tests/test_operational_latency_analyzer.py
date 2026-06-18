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
