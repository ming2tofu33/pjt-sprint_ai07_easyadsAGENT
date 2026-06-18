from __future__ import annotations

import argparse, json
from datetime import datetime
from pathlib import Path

SEGMENTS=["browser_to_bff","bff_auth","bff_total","bff_to_orchestrator","workspace_lookup","thread_lookup","generation_job_create","graph_queue_wait","graph_execution","checkpoint_write","result_persist","terminal_to_poll","poll_to_reducer","reducer_to_dom"]

def load(path):
    p=Path(path); text=p.read_text(encoding="utf-8-sig")
    if p.suffix==".jsonl": return [json.loads(line) for line in text.splitlines() if line.strip()]
    value=json.loads(text); return value if isinstance(value,list) else value.get("events",[value])

def _wall_ms(left,right):
    try: return max(0,(datetime.fromisoformat(str(right).replace("Z","+00:00"))-datetime.fromisoformat(str(left).replace("Z","+00:00"))).total_seconds()*1000)
    except (TypeError,ValueError): return None

def analyze(browser,bff,orch,mode="unknown"):
    events=[*browser,*bff,*orch]; traces={e.get("trace_id") for e in events if e.get("trace_id")}
    if len(traces)!=1: raise ValueError("trace_id mismatch")
    shas={e.get("git_commit_sha") for e in [*bff,*orch] if e.get("git_commit_sha")}; warnings=[] if len(shas)<=1 else ["deployment SHA mismatch"]
    values={name:None for name in SEGMENTS}; sources={name:"unavailable" for name in SEGMENTS}
    mapping={"bff_auth":"bff_auth","bff_request_total":"bff_total","bff_orchestrator_upstream":"bff_to_orchestrator","workspace_lookup":"workspace_lookup","thread_lookup":"thread_lookup","generation_job_create":"generation_job_create","graph_queue_wait":"graph_queue_wait","graph_execution":"graph_execution","checkpoint_write":"checkpoint_write","result_persist":"result_persist","terminal_to_poll":"terminal_to_poll","poll_to_reducer":"poll_to_reducer","reducer_to_dom":"reducer_to_dom"}
    for event in events:
        operation=str(event.get("operation") or ""); segment=mapping.get(operation)
        if event.get("event_type")=="frontend_request" and operation.startswith("POST ") and "generation-jobs" in operation: segment="browser_to_bff"
        if segment and isinstance(event.get("duration_ms"),(int,float)): values[segment]=event["duration_ms"]; sources[segment]=event.get("measurement_source","actual")
    browser_sorted=sorted(browser,key=lambda e:str(e.get("started_at") or ""))
    def event(name): return next((e for e in reversed(browser_sorted) if e.get("operation")==name),None)
    terminal_poll=next((e for e in reversed(browser_sorted) if e.get("event_type")=="frontend_request" and str(e.get("operation","")).startswith("GET ") and "generation-jobs" in str(e.get("operation"))),None)
    reducer=event("reducer_applied"); dom=event("terminal_result_visible") or event("context_summary_visible")
    if terminal_poll and reducer:
        value=_wall_ms(terminal_poll.get("started_at"),reducer.get("started_at")); values["poll_to_reducer"]=value; sources["poll_to_reducer"]="actual" if value is not None else "unavailable"
    if reducer and dom:
        value=_wall_ms(reducer.get("started_at"),dom.get("started_at")); values["reducer_to_dom"]=value; sources["reducer_to_dom"]="actual" if value is not None else "unavailable"
    missing=[name for name,value in values.items() if value is None]
    return {"mode":mode,"trace_id":next(iter(traces)),"segments":values,"measurement_sources":sources,"warnings":warnings,"missing":missing,"classification":"INSUFFICIENT_EVIDENCE" if missing else "EXPLORATORY_COMPARISON","confidence":0.4,"additional_measurement_needed":["repeat anonymous/authenticated runs"]}

def compare(anonymous,authenticated):
    def total(result): return sum(v for v in result["segments"].values() if isinstance(v,(int,float)))
    def delta(name):
        a,b=anonymous["segments"].get(name),authenticated["segments"].get(name)
        return b-a if isinstance(a,(int,float)) and isinstance(b,(int,float)) else None
    return {"status":"exploratory","anonymous_total":total(anonymous),"authenticated_total":total(authenticated),"auth_delta":total(authenticated)-total(anonymous),"bff_auth_delta":delta("bff_auth"),"graph_delta":delta("graph_execution"),"polling_delta":delta("terminal_to_poll"),"missing_by_mode":{"anonymous":anonymous["missing"],"authenticated":authenticated["missing"]},"additional_runs_required":True}

def _args():
    p=argparse.ArgumentParser(); p.add_argument("--browser-trace"); p.add_argument("--bff-logs"); p.add_argument("--orchestrator-logs")
    for mode in ("anonymous","authenticated"):
        p.add_argument(f"--browser-{mode}"); p.add_argument(f"--bff-logs-{mode}"); p.add_argument(f"--orchestrator-logs-{mode}")
    p.add_argument("--output-dir",required=True); return p.parse_args()

def main():
    a=_args(); out=Path(a.output_dir); out.mkdir(parents=True,exist_ok=True)
    if a.browser_anonymous and a.browser_authenticated:
        anon=analyze(load(a.browser_anonymous),load(a.bff_logs_anonymous),load(a.orchestrator_logs_anonymous),"anonymous"); auth=analyze(load(a.browser_authenticated),load(a.bff_logs_authenticated),load(a.orchestrator_logs_authenticated),"authenticated"); result={"anonymous":anon,"authenticated":auth}; comparison=compare(anon,auth)
    else:
        if not all((a.browser_trace,a.bff_logs,a.orchestrator_logs)): raise SystemExit("single mode requires --browser-trace, --bff-logs, --orchestrator-logs")
        single=analyze(load(a.browser_trace),load(a.bff_logs),load(a.orchestrator_logs)); result=single; comparison={"status":"single_trace_only","additional_runs_required":True}
    payloads={"summary.json":result,"segment_breakdown.json":result,"critical_path.json":{"status":"unavailable","reason":"cross-process monotonic clocks are not subtracted"},"anonymous_vs_authenticated.json":comparison,"missing_evidence.json":result.get("missing",{})}
    for name,value in payloads.items(): (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (out/"report.md").write_text("# Operational E2E Latency\n\nExploratory comparison only. Additional repeated anonymous/authenticated measurements are required.\n",encoding="utf-8")
if __name__=="__main__": main()
