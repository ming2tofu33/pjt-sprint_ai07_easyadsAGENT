import pytest
from scripts.analyze_operational_e2e_latency import analyze

def event(trace,operation,duration=None,sha="abc"):
    return {"trace_id":trace,"operation":operation,"duration_ms":duration,"git_commit_sha":sha,"measurement_source":"actual"}

def test_analyzer_rejects_trace_mismatch():
    with pytest.raises(ValueError,match="trace_id mismatch"): analyze([event("a","x")],[event("b","x")],[])

def test_analyzer_preserves_unavailable_and_sha_warning():
    result=analyze([event("a","poll_to_reducer",2,"a")],[event("a","bff_auth",4,"a")],[event("a","graph_execution",10,"b")])
    assert result["segments"]["workspace_lookup"] is None
    assert result["segments"]["bff_auth"]==4
    assert result["warnings"]==["deployment SHA mismatch"]
