import json,os,subprocess,sys
from pathlib import Path
import pytest
from scripts.diagnose_generation_analysis_latency import ActualAdapter,FakeLLMAdapter,ImageLaneGuard,graph_inventory,instrumentation_inventory,run_graph
from orchestrator.app.schemas.llm_model_policy import ModelSelection
from orchestrator.app.observability import performance

ROOT=Path(__file__).resolve().parents[2]; SCRIPT=ROOT/"scripts/diagnose_generation_analysis_latency.py"

def test_inventory_has_edges_unknowns_and_call_sites():
    nodes,edges,warnings,calls=graph_inventory()
    assert any(n["node_name"]=="product_understanding" for n in nodes)
    assert any(e["type"]=="direct" for e in edges) and any(e["type"]=="conditional" for e in edges)
    assert any(n["node_kind"]=="unknown" for n in nodes) and calls
    assert any(i["decision"]=="reuse" for i in instrumentation_inventory())

def test_actual_adapter_forwards_production_contract_once():
    class Delegate:
        def __init__(self): self.calls=[]
        def invoke_structured(self,*args,**kwargs): self.calls.append((args,kwargs)); return "result"
    delegate=Delegate(); adapter=ActualAdapter(delegate=delegate); schema=object(); selection=ModelSelection(node_name="tone_binding",user_plan="internal_benchmark",selected_model_class="api_nano",provider="openai",structured_output=True,reason="test")
    assert adapter.invoke_structured(schema,"production prompt",selection,metadata={"safe":1})=="result"
    assert delegate.calls==[((schema,"production prompt",selection),{"metadata":{"safe":1}})]

def test_real_compiled_graph_uses_wrapper_and_fake_latency(monkeypatch):
    identity=performance.record_perf_event
    report,spans,result=run_graph(FakeLLMAdapter({k:0.01 for k in ("product_understanding","tone_binding","copy_candidate_generation")}),"warm","anonymous")
    assert len([s for s in spans if s.kind=="llm"])==3
    assert all(s.duration_ms>=8 for s in spans if s.kind=="llm")
    assert report["measurement_source"]=="instrumented_mock" and result["image_lane_blocked"]
    assert performance.record_perf_event is identity
    assert [s.started_offset_ms for s in spans if s.kind=="llm"]==sorted(s.started_offset_ms for s in spans if s.kind=="llm")
    for span in [s for s in spans if s.kind=="llm"]:
        assert span.attributes["result_source"]=="adapter_event"
        assert span.attributes["call_attempted"] is True
        assert span.attributes["output_schema_name"]
        assert "raw_text_snippet" not in span.attributes

def test_copy_call_observation_does_not_depend_on_state_lineage():
    report,spans,result=run_graph(FakeLLMAdapter({k:0 for k in ("product_understanding","tone_binding","copy_candidate_generation")}),"cold","anonymous")
    copy=next(s for s in spans if s.operation=="copy_candidate_generation")
    assert result["adapter_call_events"]==3
    assert copy.attributes["call_attempted"] is True
    assert copy.attributes["result_source"]=="adapter_event"
    assert copy.attributes["structured_output_used"] is True

def test_event_sink_restores_after_failure():
    events=[]
    with pytest.raises(RuntimeError):
        with performance.capture_perf_events(events.append):
            raise RuntimeError("boom")
    assert performance.EVENT_SINK_CTX.get() is None

def test_consecutive_runs_do_not_mix_events():
    first=run_graph(FakeLLMAdapter({k:0 for k in ("product_understanding","tone_binding","copy_candidate_generation")}),"cold","anonymous")
    second=run_graph(FakeLLMAdapter({k:0 for k in ("product_understanding","tone_binding","copy_candidate_generation")}),"warm","anonymous")
    assert first[0]["trace_id"]!=second[0]["trace_id"]
    assert {s.trace_id for s in first[1]}=={first[0]["trace_id"]}

def test_image_lanes_fail_fast():
    with pytest.raises(AssertionError,match="image_lane_called"): ImageLaneGuard()()

def test_env_file_and_actual_gates(tmp_path):
    env=os.environ.copy(); env.pop("OPENAI_API_KEY",None)
    result=subprocess.run([sys.executable,str(SCRIPT),"--mode","actual","--cold-runs","1","--warm-runs","1","--confirm-paid-calls","--output-dir",str(tmp_path)],capture_output=True,text=True,env=env)
    assert result.returncode==2 and json.loads(result.stdout)["status"]=="blocked"

def test_self_check_artifacts_preserve_tokens(tmp_path):
    result=subprocess.run([sys.executable,str(SCRIPT),"--mode","self-check","--output-dir",str(tmp_path)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    summary=json.loads((tmp_path/"summary.json").read_text(encoding="utf-8")); calls=json.loads((tmp_path/"llm_calls.json").read_text(encoding="utf-8"))
    assert summary["image_lane_blocked"] and calls[0]["attributes"]["input_tokens"]==100
    assert (tmp_path/"instrumentation_inventory.json").exists()
