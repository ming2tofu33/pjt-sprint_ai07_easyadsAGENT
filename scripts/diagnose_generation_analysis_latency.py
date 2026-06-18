from __future__ import annotations

import argparse, ast, json, os, sys, time
from pathlib import Path
from typing import Any
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel
from orchestrator.app.graph.builder import build_text_analysis_latency_graph
from orchestrator.app.graph.state import MarketingState
from orchestrator.app.llm.adapters.openai import OpenAIAdapter
from orchestrator.app.llm.settings import get_llm_settings
from orchestrator.app.llm.node_runner import override_llm_adapter
from orchestrator.app.llm.plan_policy import build_default_plan_policy
from orchestrator.app.observability import performance
from orchestrator.app.observability.latency_trace import LatencySpan, build_report, critical_path, json_safe_dump
from orchestrator.app.schemas.llm_model_policy import LLMCallResult, ModelSelection

LATENCIES = {"product_understanding": 0.10, "tone_binding": 0.15, "copy_candidate_generation": 0.20}

class DiagnosticOutput(BaseModel):
    summary: str

class ImageLaneGuard:
    calls = 0
    def __call__(self, *_args, **_kwargs):
        self.calls += 1
        raise AssertionError("image_lane_called_during_latency_diagnostic")

class FakeLLMAdapter:
    def __init__(self, latencies=None): self.latencies = latencies or LATENCIES
    def invoke_structured(self, schema, prompt, selection, metadata=None):
        started=time.perf_counter(); time.sleep(self.latencies.get(selection.node_name,0))
        return LLMCallResult(success=False,node_name=selection.node_name,model_selection=selection,output=None,error="diagnostic_fallback",
            latency_ms=round((time.perf_counter()-started)*1000),token_usage={"input_tokens":100,"output_tokens":0,"cached_tokens":10,"reasoning_tokens":0},cost_estimate=0,metadata={"diagnostic":True,"provider":"mock","fallback_used":True,"fallback_reason":"diagnostic_fallback"})

def selection_for(node_name: str, provider: str) -> ModelSelection:
    return ModelSelection(node_name=node_name, user_plan="internal_benchmark", selected_model_class="api_nano" if provider == "openai" else "mock",
        provider=provider, structured_output=True, reason="latency diagnostic", latency_budget="interactive")

def parse_args():
    p=argparse.ArgumentParser(); p.add_argument("--mode",choices=("self-check","mock","actual"),required=True); p.add_argument("--scenario",choices=("short","long"),default="short")
    p.add_argument("--auth-mode",choices=("anonymous","authenticated-fixture"),default="anonymous"); p.add_argument("--runs",type=int,default=1); p.add_argument("--cold-runs",type=int,default=0); p.add_argument("--warm-runs",type=int,default=0)
    p.add_argument("--env-file"); p.add_argument("--confirm-paid-calls",action="store_true"); p.add_argument("--max-actual-graph-runs",type=int,default=2); p.add_argument("--max-actual-llm-calls",type=int,default=6)
    p.add_argument("--output-dir",default="data/qa/generation_analysis_latency_v2"); return p.parse_args()

def load_env_file(path: str|None):
    if not path: return
    for line in (REPO_ROOT/path).read_text(encoding="utf-8-sig").splitlines():
        line=line.strip()
        if line and not line.startswith("#") and "=" in line:
            k,v=line.split("=",1); os.environ.setdefault(k.strip(),v.strip().strip('"').strip("'"))

def graph_inventory():
    path=REPO_ROOT/"orchestrator/app/graph/builder.py"; tree=ast.parse(path.read_text(encoding="utf-8-sig")); nodes={}; edges=[]; warnings=[]
    for call in [n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]:
        if call.func.attr=="add_node":
            if call.args and isinstance(call.args[0],ast.Constant):
                name=str(call.args[0].value); callable_name=ast.unparse(call.args[1]) if len(call.args)>1 else None
                nodes[name]={"node_name":name,"registered_callable":callable_name,"module":str(path.relative_to(REPO_ROOT)),"direct_edges":[],"conditional_routes":[],"upstream_nodes":[],"downstream_nodes":[],"start_connected":False,"end_connected":False,"node_kind":"unknown","actual_external_call_sites":[],"possible_parallel_group":None,"dependency_evidence":"builder registration","planned_llm_call_count":None,"call_site_status":"unresolved"}
            else: warnings.append("dynamic_node_registration")
        elif call.func.attr=="add_edge" and len(call.args)>=2:
            src=ast.unparse(call.args[0]); dst=ast.unparse(call.args[1]); edges.append({"source":src.strip("'\""),"target":dst.strip("'\""),"type":"direct"})
        elif call.func.attr=="add_conditional_edges" and call.args:
            src=ast.unparse(call.args[0]).strip("'\""); mapping_node=call.args[2] if len(call.args)>2 and isinstance(call.args[2],ast.Dict) else None
            if mapping_node:
                for route_node,dst_node in zip(mapping_node.keys,mapping_node.values):
                    route=ast.unparse(route_node).strip("'\""); dst=ast.unparse(dst_node).strip("'\"")
                    edges.append({"source":src,"target":dst,"route":route,"type":"conditional"})
            else: warnings.append(f"unresolved_conditional:{src}")
    for edge in edges:
        src,dst=edge["source"],edge["target"]
        if src in nodes: nodes[src]["downstream_nodes"].append(dst); (nodes[src]["direct_edges"] if edge["type"]=="direct" else nodes[src]["conditional_routes"]).append(dst)
        if dst in nodes: nodes[dst]["upstream_nodes"].append(src)
    call_sites=[]
    for file in (REPO_ROOT/"orchestrator/app/llm/nodes").glob("*.py"):
        text=file.read_text(encoding="utf-8-sig")
        if "run_structured_node(" in text:
            call_sites.append(str(file.relative_to(REPO_ROOT)))
            for row in nodes.values():
                if row["node_name"] in file.stem or file.stem in row["node_name"]:
                    row.update(node_kind="llm",actual_external_call_sites=[str(file.relative_to(REPO_ROOT))],planned_llm_call_count=1,call_site_status="mapped")
    return list(nodes.values()),edges,warnings,call_sites

def instrumentation_inventory():
    return [
      {"existing_feature":"trace context/JSONL events","file":"orchestrator/app/observability/performance.py","production_boundary":True,"overlap":"latency_trace is report adapter","decision":"reuse"},
      {"existing_feature":"node timing","file":"orchestrator/app/graph/builder.py::_instrument_node","production_boundary":True,"overlap":"none","decision":"reuse"},
      {"existing_feature":"checkpoint timing","file":"orchestrator/app/graph/checkpointer.py::InstrumentedCheckpointer","production_boundary":True,"overlap":"none","decision":"reuse"},
      {"existing_feature":"API timing/context","file":"orchestrator/app/api/app.py::performance_middleware","production_boundary":True,"overlap":"none","decision":"reuse"},
      {"existing_feature":"BFF/frontend events","file":"apps/web/app/api/_proxy/orchestrator.ts; apps/web/lib/performance.ts","production_boundary":True,"overlap":"none","decision":"reuse"},
    ]

def build_diagnostic_graph(adapter, events):
    return build_text_analysis_latency_graph(checkpointer=InMemorySaver())

def events_to_spans(trace_id,events,state,wall_ms):
    rows=[e for e in events if e.get("event_type")=="graph_node"]; spans=[]; previous=None; offset=0.0
    results=state.get("llm_call_results") or []
    origin=min((e.get("started_at_ns") for e in rows if e.get("started_at_ns") is not None),default=None)
    for i,event in enumerate(rows):
        duration=float(event["duration_ms"]); node=event["operation"]; result=results[i] if i<len(results) else {}; usage=result.get("token_usage") or {}; selection=result.get("model_selection") or {}; metadata=result.get("metadata") or {}
        measured_offset=(event.get("started_at_ns")-origin)/1_000_000 if origin is not None and event.get("started_at_ns") is not None else offset
        success=bool(result.get("success")); sid=f"node_{i}"; attrs={**usage,"call_attempted":True,"call_succeeded":success,"selected_provider":selection.get("provider"),"executed_provider":metadata.get("provider") or selection.get("provider"),"selected_model":selection.get("model_name") or selection.get("selected_model_class"),"executed_model":metadata.get("model") or selection.get("model_name"),"retry_count":metadata.get("retry_count",0),"fallback_used":bool(metadata.get("fallback_used")),"fallback_reason":metadata.get("fallback_reason"),"measurement_source":"instrumented_mock"}
        spans.append(LatencySpan(trace_id=trace_id,span_id=sid,parent_span_id="graph",layer="langgraph",operation=node,kind="llm",started_offset_ms=measured_offset,ended_offset_ms=measured_offset+duration,duration_ms=duration,depends_on_span_ids=[previous] if previous else [],status="ok" if success else "error",attributes=attrs))
        previous=sid; offset=measured_offset+duration
    spans.append(LatencySpan(trace_id=trace_id,span_id="graph",layer="langgraph",operation="graph_execution",kind="deterministic",duration_ms=wall_ms,ended_offset_ms=wall_ms,is_container_span=True,attributes={"measurement_source":"instrumented_mock"}))
    return spans

def run_graph(adapter,run_kind,auth_mode):
    events=[]; graph=build_diagnostic_graph(adapter,events); return execute_compiled_graph(graph,adapter,run_kind,auth_mode,events)

def execute_compiled_graph(graph,adapter,run_kind,auth_mode,events=None):
    events=events if events is not None else []; trace_id=f"trace_{uuid4().hex}"; run_id=f"run_{uuid4().hex}"
    tokens=performance.bind_perf_context(trace_id=trace_id,request_id=f"req_{uuid4().hex}",run_id=run_id,cold_or_warm=run_kind)
    previous_trace_flag=os.environ.get("EASYADS_PERF_TRACE")
    previous_enable=os.environ.get("EASYADS_ENABLE_LLM_CALLS"); previous_provider=os.environ.get("EASYADS_LLM_PROVIDER")
    os.environ["EASYADS_PERF_TRACE"]="1"
    os.environ["EASYADS_ENABLE_LLM_CALLS"]="true"; os.environ["EASYADS_LLM_PROVIDER"]="openai"
    try:
        started=time.perf_counter()
        diagnostic_state={"user_input":"카페 신메뉴 홍보 포스터","status":"queued","user_plan":"internal_benchmark","plan_policy":build_default_plan_policy("internal_benchmark").model_dump(),"input_evidence_bundle":{"input_mode":"text_only","user_text":"카페 신메뉴 홍보 포스터","explicit_product_mentions":["카페 신메뉴"],"explicit_user_facts":[],"overall_confidence":0.8},"context":{"business_type":"cafe","item_or_service":"신메뉴","promotion_goal":"awareness","ad_format":"poster"},"current_brief":{"requested_ad_format":"poster"},"ad_format":"poster","copy_generation_mode":"auto_pilot"}
        with performance.capture_perf_events(events.append), override_llm_adapter(adapter):
            state=graph.invoke(diagnostic_state,{"configurable":{"thread_id":run_id}})
        wall=(time.perf_counter()-started)*1000
    finally:
        performance.reset_perf_context(tokens)
        if previous_trace_flag is None: os.environ.pop("EASYADS_PERF_TRACE",None)
        else: os.environ["EASYADS_PERF_TRACE"]=previous_trace_flag
        if previous_enable is None: os.environ.pop("EASYADS_ENABLE_LLM_CALLS",None)
        else: os.environ["EASYADS_ENABLE_LLM_CALLS"]=previous_enable
        if previous_provider is None: os.environ.pop("EASYADS_LLM_PROVIDER",None)
        else: os.environ["EASYADS_LLM_PROVIDER"]=previous_provider
    spans=events_to_spans(trace_id,events,state,wall); source="actual" if isinstance(adapter,ActualAdapter) else "instrumented_mock"
    return build_report(trace_id,spans,total_wall_ms=wall,source=source).model_dump(),spans,{"run_id":run_id,"run_kind":run_kind,"auth_evidence_level":"fixture" if auth_mode=="authenticated-fixture" else "unavailable","image_lane_blocked":True,"t2i_calls":0,"vlm_calls":0,"measurement_source":source}

class ActualAdapter:
    def __init__(self): self.adapter=OpenAIAdapter(get_llm_settings())
    def invoke(self,node_name): return self.adapter.invoke_structured(DiagnosticOutput,"Return JSON with a concise summary for: 카페 신메뉴 홍보",selection_for(node_name,"openai"),metadata={"diagnostic":True})

def write(path,payload): path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json_safe_dump(payload),encoding="utf-8")
def write_artifacts(out,runs):
    nodes,edges,warnings,calls=graph_inventory(); reports=[x[0] for x in runs]; spans=[s.model_dump() for _,ss,_ in runs for s in ss]; results=[x[2] for x in runs]
    write(out/"instrumentation_inventory.json",instrumentation_inventory()); write(out/"summary.json",{"measurement_source":reports[0]["measurement_source"] if reports else "unavailable","runs":len(runs),"reports":reports,"actual_llm_calls":sum(r["llm_call_count"] for r in reports if r["measurement_source"]=="actual"),"t2i_calls":0,"vlm_calls":0,"image_lane_blocked":True})
    write(out/"run_matrix.json",results); write(out/"graph_topology.json",{"nodes":[n["node_name"] for n in nodes],"edges":edges,"warnings":warnings}); write(out/"node_inventory.json",nodes); write(out/"span_tree.json",spans); write(out/"llm_calls.json",[s for s in spans if s["kind"]=="llm"])
    cps=[]
    for report,ss,result in runs:
        ms,path=critical_path(ss); cps.append({"trace_id":report["trace_id"],"duration_ms":ms,"operations":[s.operation for s in path],"measurement_source":report["measurement_source"]}); d=out/"runs"/result["run_id"]
        write(d/"trace.json",report); write(d/"spans.json",[s.model_dump() for s in ss]); write(d/"llm_calls.json",[s.model_dump() for s in ss if s.kind=="llm"]); write(d/"result.json",result)
    cold=[r[0]["total_wall_ms"] for r in runs if r[2].get("run_kind")=="cold"] or ([reports[0]["total_wall_ms"]] if reports else [])
    warm=[r[0]["total_wall_ms"] for r in runs[1:]]; warm_median=sorted(warm)[len(warm)//2] if warm else None
    comparison={"cold_ms":cold[0] if cold else None,"warm_runs_ms":warm,"warm_median_ms":warm_median,"cold_minus_warm_median_ms":cold[0]-warm_median if cold and warm_median is not None else None,"auth_contract":"authenticated persistence fixture; Google/BFF auth unavailable","measurement_source":reports[0]["measurement_source"] if reports else "unavailable"}
    write(out/"critical_path.json",cps); write(out/"comparison.json",comparison)
    top=sorted([s for s in spans if not s["is_container_span"]],key=lambda s:s["duration_ms"],reverse=True)[:3]; first=reports[0] if reports else {}
    lines=["# AI 분석 구간 Latency Root Cause Baseline v2","",f"Total wall: {first.get('total_wall_ms','unavailable')}ms","","## Top spans",""]
    lines += [f"{i}. {row['operation']}: {row['duration_ms']:.3f}ms" for i,row in enumerate(top,1)]
    lines += ["","## Critical path","", " → ".join(cps[0]["operations"]) if cps else "unavailable","",f"LLM calls: {first.get('llm_call_count','unavailable')}",f"LLM critical path: {first.get('llm_critical_path_ms','unavailable')}ms",f"Dominant cause: {first.get('dominant_latency_class','INSUFFICIENT_EVIDENCE')}",f"Confidence: {first.get('confidence',0)}",f"Cold/warm delta: {comparison['cold_minus_warm_median_ms'] if comparison['cold_minus_warm_median_ms'] is not None else 'unavailable'}ms","","Mock 측정만으로 실제 제품 병목을 확정하지 않습니다. 실제 Google/BFF 인증 지연은 운영 trace 없이는 unavailable입니다. T2I/VLM 경계는 fail-fast로 차단했습니다."]
    (out/"report.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    (out/"railway_checklist.md").write_text("# Railway 확인 목록\n\n- deployment SHA, replica ID, trace_id\n- 요청 시작·종료 시각\n- CPU/Memory spike 및 process restart 여부\n- trace_id structured log\n\nSecret 또는 환경 변수 값은 공유하지 않습니다.\n",encoding="utf-8")

def preflight_actual(args):
    planned_runs=args.cold_runs+args.warm_runs; per_run=len(LATENCIES); total=planned_runs*per_run
    reasons=[]
    if not args.confirm_paid_calls: reasons.append("confirm_paid_calls_required")
    if os.getenv("EASYADS_ENABLE_LLM_CALLS","").lower()!="true": reasons.append("EASYADS_ENABLE_LLM_CALLS_not_true")
    if os.getenv("EASYADS_LLM_PROVIDER")!="openai": reasons.append("EASYADS_LLM_PROVIDER_not_openai")
    if not os.getenv("OPENAI_API_KEY"): reasons.append("OPENAI_API_KEY_missing")
    if planned_runs>args.max_actual_graph_runs or total>args.max_actual_llm_calls: reasons.append("actual_call_budget_exceeded")
    return {"planned_graph_runs":planned_runs,"planned_llm_calls_per_run":per_run,"planned_total_llm_calls":total,"blocked_reasons":reasons}

def main():
    args=parse_args(); load_env_file(args.env_file); out=Path(args.output_dir); out=out if out.is_absolute() else REPO_ROOT/out
    ImageLaneGuard() # construction verifies fail-fast guard is available
    if args.mode=="actual":
        plan=preflight_actual(args)
        if plan["blocked_reasons"]: print(json.dumps({"status":"blocked",**plan})); return 2
        specs=["cold"]*args.cold_runs+["warm"]*args.warm_runs; runs=[]; adapter=ActualAdapter(); graph=build_diagnostic_graph(adapter,[])
        for kind in specs:
            item=execute_compiled_graph(graph,adapter,kind,args.auth_mode); runs.append(item)
            if not item[0]["llm_call_count"] or any(s.status!="ok" for s in item[1]): break
    else:
        count=1 if args.mode=="self-check" else args.runs; adapter=FakeLLMAdapter(); graph=build_diagnostic_graph(adapter,[])
        runs=[execute_compiled_graph(graph,adapter,"cold" if i==0 else "warm",args.auth_mode) for i in range(count)]
    write_artifacts(out,runs); print(json.dumps({"status":"ok","mode":args.mode,"runs":len(runs),"output_dir":str(out),"t2i_calls":0,"vlm_calls":0})); return 0
if __name__=="__main__": raise SystemExit(main())
