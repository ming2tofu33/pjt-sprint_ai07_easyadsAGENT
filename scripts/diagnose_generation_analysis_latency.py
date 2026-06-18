from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator.app.observability.latency_trace import LatencySpan, build_report, critical_path, json_safe_dump


MOCK_LATENCIES = {"brief_interpreter": 100.0, "product_understanding": 150.0, "copy_generation": 200.0}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generation analysis latency baseline (never invokes T2I/VLM).")
    parser.add_argument("--mode", choices=("self-check", "mock", "actual"), required=True)
    parser.add_argument("--scenario", choices=("short", "long"), default="short")
    parser.add_argument("--auth-mode", choices=("anonymous", "authenticated-fixture"), default="anonymous")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--cold-runs", type=int, default=0)
    parser.add_argument("--warm-runs", type=int, default=0)
    parser.add_argument("--confirm-paid-calls", action="store_true")
    parser.add_argument("--max-actual-graph-runs", type=int, default=2)
    parser.add_argument("--max-actual-llm-calls", type=int, default=8)
    parser.add_argument("--env-file")
    parser.add_argument("--output-dir", default="data/qa/generation_analysis_latency_v1")
    return parser.parse_args()


def graph_inventory() -> tuple[list[dict], list[dict]]:
    path = REPO_ROOT / "orchestrator/app/graph/builder.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    nodes: list[dict] = []
    edges: list[dict] = []
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
        name = call.func.attr
        if name == "add_node" and call.args and isinstance(call.args[0], ast.Constant):
            node_name = str(call.args[0].value)
            kind = "interrupt" if "interrupt" in node_name else "llm" if node_name in MOCK_LATENCIES else "deterministic"
            nodes.append({"node_name": node_name, "module": str(path.relative_to(REPO_ROOT)), "node_kind": kind,
                          "upstream_dependencies": [], "downstream_nodes": [], "can_run_without_previous_output": False,
                          "possible_parallel_candidate": False, "actual_llm_call_count": 1 if kind == "llm" else 0})
        elif name in {"add_edge", "add_conditional_edges"} and call.args and isinstance(call.args[0], ast.Constant):
            target = call.args[1].value if name == "add_edge" and len(call.args) > 1 and isinstance(call.args[1], ast.Constant) else None
            edges.append({"source": call.args[0].value, "target": target, "type": "direct" if name == "add_edge" else "conditional"})
    unique_nodes = {row["node_name"]: row for row in nodes}
    return list(unique_nodes.values()), edges


def mock_run(index: int, auth_mode: str) -> tuple[dict, list[LatencySpan]]:
    trace_id = f"trace_{uuid4().hex}"
    root = LatencySpan(trace_id=trace_id, span_id="graph", layer="langgraph", operation="graph_execution", kind="deterministic", duration_ms=470, started_offset_ms=15)
    spans = [root]
    offset = 15.0
    previous = "graph"
    for node, duration in MOCK_LATENCIES.items():
        span_id = f"{node}_{index}"
        spans.append(LatencySpan(trace_id=trace_id, span_id=span_id, parent_span_id=previous, layer="llm", operation=node,
                                 kind="llm", duration_ms=duration, started_offset_ms=offset,
                                 attributes={"input_tokens": 100, "output_tokens": 30, "cached_tokens": 0, "token_source": "estimated", "retry_count": 0}))
        previous, offset = span_id, offset + duration
    auth_ms = 12.0 if auth_mode == "authenticated-fixture" else 2.0
    spans.append(LatencySpan(trace_id=trace_id, layer="bff", operation="auth", kind="db", duration_ms=auth_ms, started_offset_ms=0))
    spans.append(LatencySpan(trace_id=trace_id, layer="frontend", operation="polling_visibility", kind="ui", duration_ms=1800, started_offset_ms=485))
    report = build_report(trace_id, spans, total_wall_ms=2285)
    report.bff_auth_ms = auth_ms
    report.graph_execution_ms = 470
    report.terminal_to_ui_ms = 1800
    return report.model_dump(), spans


def write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_safe_dump(payload), encoding="utf-8")


def write_artifacts(output: Path, runs: list[tuple[dict, list[LatencySpan]]]) -> None:
    nodes, edges = graph_inventory()
    reports = [report for report, _ in runs]
    all_spans = [span.model_dump() for _, spans in runs for span in spans]
    llm_calls = [span for span in all_spans if span["kind"] == "llm"]
    write(output / "summary.json", {"schema_version": 1, "runs": len(runs), "reports": reports,
          "actual_graph_runs": 0, "actual_llm_calls": 0, "t2i_calls": 0, "vlm_calls": 0})
    write(output / "run_matrix.json", reports)
    write(output / "graph_topology.json", {"nodes": [n["node_name"] for n in nodes], "edges": edges})
    write(output / "node_inventory.json", nodes)
    write(output / "span_tree.json", all_spans)
    write(output / "llm_calls.json", llm_calls)
    critical = []
    for report, spans in runs:
        duration, path = critical_path(spans)
        critical.append({"trace_id": report["trace_id"], "duration_ms": duration, "operations": [s.operation for s in path]})
        run_dir = output / "runs" / report["trace_id"]
        write(run_dir / "trace.json", report)
        write(run_dir / "spans.json", [s.model_dump() for s in spans])
        write(run_dir / "llm_calls.json", [s.model_dump() for s in spans if s.kind == "llm"])
        write(run_dir / "result.json", {"status": "mock_complete", "t2i_call_attempted": False, "vlm_call_attempted": False})
    write(output / "critical_path.json", critical)
    write(output / "comparison.json", {"anonymous_vs_authenticated_fixture_ms": "run both auth modes to compare", "actual_available": False})
    (output / "report.md").write_text("# AI 분석 구간 Latency Root Cause Baseline\n\n이 진단은 성능 최적화를 적용하지 않고 구간별 측정 기준선만 생성합니다.\n\n실제 LLM 호출은 수행하지 않았으며 T2I/VLM 호출 수는 0입니다. Mock 기준에서는 직렬 LLM 누적보다 1.8초 polling visibility 지연이 더 큽니다. 실제 병목 판정에는 승인된 actual 측정이 추가로 필요합니다.\n", encoding="utf-8")
    (output / "railway_checklist.md").write_text("# Railway 확인 목록\n\n- deployment SHA\n- replica ID\n- request trace_id\n- 요청 시작·종료 시각\n- CPU/Memory spike 여부\n- process restart 여부\n- 해당 trace_id structured log\n\nSecret 또는 환경 변수 값은 공유하지 않습니다.\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output = Path(args.output_dir)
    if not output.is_absolute(): output = REPO_ROOT / output
    if args.mode == "actual":
        planned_runs = args.cold_runs + args.warm_runs
        planned_calls = planned_runs * len(MOCK_LATENCIES)
        if not args.confirm_paid_calls:
            raise SystemExit("actual mode blocked: --confirm-paid-calls required")
        if planned_runs > args.max_actual_graph_runs or planned_calls > args.max_actual_llm_calls:
            raise SystemExit(f"actual mode blocked by budget: runs={planned_runs}, planned_llm_calls={planned_calls}")
        raise SystemExit("actual mode preflight passed, but execution is intentionally unavailable until an explicit production-safe graph fixture is configured")
    runs = [mock_run(i, args.auth_mode) for i in range(max(1, args.runs))]
    if args.mode == "self-check": runs = runs[:1]
    write_artifacts(output, runs)
    print(json.dumps({"status": "ok", "mode": args.mode, "output_dir": str(output), "actual_llm_calls": 0, "t2i_calls": 0, "vlm_calls": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
