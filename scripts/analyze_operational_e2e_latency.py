from __future__ import annotations

import argparse, json
from pathlib import Path

SEGMENTS = ["browser_to_bff","bff_auth","bff_to_orchestrator","workspace_lookup","thread_lookup","generation_job_create","graph_queue_wait","graph_execution","checkpoint_write","result_persist","terminal_to_poll","poll_to_reducer","reducer_to_dom"]

def load(path: str):
    p=Path(path); text=p.read_text(encoding="utf-8-sig")
    if p.suffix==".jsonl": return [json.loads(line) for line in text.splitlines() if line.strip()]
    value=json.loads(text); return value if isinstance(value,list) else value.get("events",[value])

def analyze(browser,bff,orch):
    events=[*browser,*bff,*orch]; traces={e.get("trace_id") for e in events if e.get("trace_id")}
    if len(traces)!=1: raise ValueError("trace_id mismatch")
    shas={e.get("git_commit_sha") for e in [*bff,*orch] if e.get("git_commit_sha")}
    warnings=[] if len(shas)<=1 else ["deployment SHA mismatch"]
    values={name:None for name in SEGMENTS}; sources={name:"unavailable" for name in SEGMENTS}
    mapping={"bff_auth":"bff_auth","workspace_lookup":"workspace_lookup","thread_lookup":"thread_lookup","generation_job_create":"generation_job_create","graph_execution":"graph_execution","checkpoint_write":"checkpoint_write","result_persist":"result_persist","terminal_to_poll":"terminal_to_poll","poll_to_reducer":"poll_to_reducer","reducer_to_dom":"reducer_to_dom"}
    for event in events:
        segment=mapping.get(event.get("operation"))
        if segment and isinstance(event.get("duration_ms"),(int,float)):
            values[segment]=event["duration_ms"]; sources[segment]=event.get("measurement_source","actual")
    missing=[name for name,value in values.items() if value is None]
    return {"trace_id":next(iter(traces)),"segments":values,"measurement_sources":sources,"warnings":warnings,"missing":missing,"classification":"INSUFFICIENT_EVIDENCE" if missing else "EXPLORATORY_COMPARISON","confidence":0.4,"additional_measurement_needed":["repeat anonymous/authenticated runs"]}

def main():
    p=argparse.ArgumentParser(); p.add_argument("--browser-trace",required=True); p.add_argument("--bff-logs",required=True); p.add_argument("--orchestrator-logs",required=True); p.add_argument("--output-dir",required=True); a=p.parse_args()
    result=analyze(load(a.browser_trace),load(a.bff_logs),load(a.orchestrator_logs)); out=Path(a.output_dir); out.mkdir(parents=True,exist_ok=True)
    payloads={"summary.json":result,"segment_breakdown.json":{"segments":result["segments"],"sources":result["measurement_sources"]},"critical_path.json":{"status":"unavailable","reason":"cross-process monotonic clocks are not subtracted"},"anonymous_vs_authenticated.json":{"status":"exploratory","additional_runs_required":True},"missing_evidence.json":result["missing"]}
    for name,value in payloads.items(): (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (out/"report.md").write_text("# Operational E2E Latency\n\nExploratory comparison only. Additional repeated anonymous/authenticated measurements are required.\n",encoding="utf-8")
if __name__=="__main__": main()
