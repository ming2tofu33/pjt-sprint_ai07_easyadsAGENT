from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from statistics import median


SEGMENTS = [
    "browser_to_bff", "bff_auth", "bff_total", "bff_to_orchestrator",
    "workspace_lookup", "thread_lookup", "generation_job_create", "graph_queue_wait",
    "graph_execution", "llm_critical_path", "checkpoint_write", "result_persist",
    "terminal_to_poll", "poll_to_reducer", "reducer_to_dom",
]


def load(path):
    target = Path(path)
    text = target.read_text(encoding="utf-8-sig")
    if target.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    value = json.loads(text)
    return value if isinstance(value, list) else value.get("events", [value])


def _wall_ms(left, right):
    try:
        start = datetime.fromisoformat(str(left).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(right).replace("Z", "+00:00"))
        return max(0.0, (end - start).total_seconds() * 1000)
    except (TypeError, ValueError):
        return None


def _percentile(values, percentile):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percentile)))
    return ordered[index]


def _duration_sum(events):
    values = [event.get("duration_ms") for event in events]
    numeric = [value for value in values if isinstance(value, (int, float))]
    return round(sum(numeric), 3) if numeric else None


def analyze(browser, bff, orch, mode="unknown"):
    events = [*browser, *bff, *orch]
    traces = {event.get("trace_id") for event in events if event.get("trace_id")}
    if len(traces) != 1:
        raise ValueError("trace_id mismatch")

    shas = {event.get("git_commit_sha") for event in [*bff, *orch] if event.get("git_commit_sha")}
    deployment_changed = len(shas) > 1 or any(
        event.get("event_type") in {"deployment", "restart", "crash"} for event in events
    )
    warnings = ["deployment SHA mismatch"] if len(shas) > 1 else []
    values = {name: None for name in SEGMENTS}
    sources = {name: "unavailable" for name in SEGMENTS}
    mapping = {
        "bff_auth": "bff_auth", "bff_request_total": "bff_total",
        "bff_orchestrator_upstream": "bff_to_orchestrator", "workspace_lookup": "workspace_lookup",
        "thread_lookup": "thread_lookup", "generation_job_create": "generation_job_create",
        "graph_queue_wait": "graph_queue_wait", "graph_execution": "graph_execution",
        "checkpoint_write": "checkpoint_write", "result_persist": "result_persist",
        "terminal_to_poll": "terminal_to_poll",
        "poll_to_reducer": "poll_to_reducer", "reducer_to_dom": "reducer_to_dom",
    }
    for item in events:
        operation = str(item.get("operation") or "")
        segment = mapping.get(operation)
        if item.get("event_type") == "frontend_request" and operation.startswith("POST ") and "generation-jobs" in operation:
            segment = "browser_to_bff"
        if segment and isinstance(item.get("duration_ms"), (int, float)):
            values[segment] = item["duration_ms"]
            sources[segment] = item.get("measurement_source", "actual")

    event_groups = {
        "graph_execution": [item for item in orch if item.get("event_type") == "graph_execution"],
        "llm_critical_path": [item for item in orch if item.get("event_type") in {"llm_call", "llm_call_finished"}],
        "checkpoint_write": [item for item in orch if str(item.get("event_type", "")).startswith("checkpoint_write")],
        "result_persist": [item for item in orch if item.get("event_type") == "result_persist" or item.get("operation") == "result_persist"],
    }
    for segment, group in event_groups.items():
        value = _duration_sum(group)
        if value is not None:
            values[segment], sources[segment] = value, "actual"

    browser_sorted = sorted(browser, key=lambda item: str(item.get("started_at") or ""))
    mark = lambda name: next((item for item in browser_sorted if item.get("operation") == name), None)
    last_mark = lambda name: next((item for item in reversed(browser_sorted) if item.get("operation") == name), None)
    posts = [item for item in browser_sorted if item.get("event_type") == "frontend_request" and str(item.get("operation", "")).startswith("POST ") and "generation-jobs" in str(item.get("operation"))]
    polls = [item for item in browser_sorted if item.get("event_type") == "frontend_request" and str(item.get("operation", "")).startswith("GET ") and "generation-jobs" in str(item.get("operation"))]
    reducer = last_mark("reducer_applied")
    waiting_visible = mark("context_summary_visible")
    terminal_visible = last_mark("terminal_result_visible") or last_mark("final_result_visible")
    terminal_poll = polls[-1] if polls else None

    if terminal_poll and reducer:
        values["poll_to_reducer"] = _wall_ms(terminal_poll.get("started_at"), reducer.get("started_at"))
        sources["poll_to_reducer"] = "actual" if values["poll_to_reducer"] is not None else "unavailable"
    if reducer and terminal_visible:
        values["reducer_to_dom"] = _wall_ms(reducer.get("started_at"), terminal_visible.get("started_at"))
        sources["reducer_to_dom"] = "actual" if values["reducer_to_dom"] is not None else "unavailable"

    initial_start = posts[0].get("started_at") if posts else None
    answer_start = posts[1].get("started_at") if len(posts) > 1 else None
    metrics = {
        "browser_total_ms": _wall_ms(initial_start, terminal_visible.get("started_at") if terminal_visible else None),
        "initial_post_duration_ms": posts[0].get("duration_ms") if posts else None,
        "answer_post_duration_ms": posts[1].get("duration_ms") if len(posts) > 1 else None,
        "start_to_waiting_user_input_ms": _wall_ms(initial_start, waiting_visible.get("started_at") if waiting_visible else None),
        "answer_to_done_ms": _wall_ms(answer_start, terminal_visible.get("started_at") if terminal_visible else None),
        "done_poll_duration_ms": terminal_poll.get("duration_ms") if terminal_poll else None,
        "poll_count": len(polls),
    }
    http_durations = [item.get("duration_ms") for item in orch if item.get("event_type") == "api_request" and isinstance(item.get("duration_ms"), (int, float))]
    metrics["orchestrator_http_p50_ms"] = median(http_durations) if http_durations else None
    metrics["orchestrator_http_p95_ms"] = _percentile(http_durations, 0.95)

    structured = {
        "graph_spans_present": bool(event_groups["graph_execution"] or any(item.get("event_type") == "graph_node" for item in orch)),
        "llm_spans_present": bool(event_groups["llm_critical_path"]),
        "persistence_spans_present": bool(event_groups["checkpoint_write"] or event_groups["result_persist"]),
    }
    missing = [name for name, value in values.items() if value is None]
    required_missing = [name for name in ("graph_execution", "llm_critical_path", "checkpoint_write", "result_persist") if values[name] is None]
    measurement_quality = "degraded" if deployment_changed or required_missing else "usable"
    browser_uses_vercel_api = any(str(item.get("operation", "")).startswith(("POST /api/", "GET /api/")) for item in browser)
    railway_bff_critical = bool(bff) and not browser_uses_vercel_api

    total = metrics["browser_total_ms"]
    answer_to_done = metrics["answer_to_done_ms"]
    primary_class = "INSUFFICIENT_EVIDENCE"
    primary_suspect = "GENERATION_OR_POLLING_PATH"
    confidence = 0.25
    if measurement_quality == "usable" and isinstance(total, (int, float)) and total > 0:
        if isinstance(values["llm_critical_path"], (int, float)) and values["llm_critical_path"] / total >= 0.5:
            primary_class, primary_suspect, confidence = "GRAPH_SERIAL_LLM_ACCUMULATION", "GRAPH_OR_LLM_PATH", 0.82
        elif isinstance(values["graph_execution"], (int, float)) and values["graph_execution"] / total >= 0.5:
            primary_class, primary_suspect, confidence = "GRAPH_OR_LLM_DOMINANT", "GRAPH_EXECUTION", 0.72
        elif isinstance(answer_to_done, (int, float)) and answer_to_done / total >= 0.5:
            primary_class, primary_suspect, confidence = "FINAL_GENERATION_PATH_DOMINANT", "GENERATION_OR_POLLING_PATH", 0.65

    blocked_reasons = []
    if deployment_changed:
        blocked_reasons.append("DEPLOYMENT_OR_RESTART_NEAR_RUN")
    if required_missing:
        blocked_reasons.append("STRUCTURED_GRAPH_LLM_PERSISTENCE_SPANS_MISSING")
    return {
        "mode": mode,
        "trace_id": next(iter(traces)),
        "active_shas": sorted(shas),
        "deployment_changed_near_run": deployment_changed,
        "metrics": metrics,
        "segments": values,
        "measurement_sources": sources,
        "structured_evidence": structured,
        "production_path": {
            "bff_layer": "vercel_api_route" if browser_uses_vercel_api else "railway_bff_or_unknown",
            "railway_bff_in_critical_path": railway_bff_critical,
            "railway_bff_metrics": "critical_path" if railway_bff_critical else "auxiliary_only",
        },
        "warnings": warnings,
        "missing": missing,
        "missing_evidence": required_missing,
        "measurement_quality": measurement_quality,
        "classification": primary_class,
        "primary_class": primary_class,
        "primary_suspect": primary_suspect,
        "confidence": confidence,
        "blocked_reasons": blocked_reasons,
        "next_action": "restore structured graph spans and rerun stable anonymous" if blocked_reasons else "review classified critical path",
    }


def compare(anonymous, authenticated):
    def total(result):
        measured = result.get("metrics", {}).get("browser_total_ms")
        return measured if isinstance(measured, (int, float)) else sum(value for value in result["segments"].values() if isinstance(value, (int, float)))

    def delta(name):
        left, right = anonymous["segments"].get(name), authenticated["segments"].get(name)
        return right - left if isinstance(left, (int, float)) and isinstance(right, (int, float)) else None

    return {
        "status": "exploratory", "anonymous_total": total(anonymous), "authenticated_total": total(authenticated),
        "auth_delta": total(authenticated) - total(anonymous), "bff_auth_delta": delta("bff_auth"),
        "graph_delta": delta("graph_execution"), "polling_delta": delta("terminal_to_poll"),
        "missing_by_mode": {"anonymous": anonymous["missing"], "authenticated": authenticated["missing"]},
        "additional_runs_required": True,
    }


def _args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser-trace"); parser.add_argument("--bff-logs"); parser.add_argument("--orchestrator-logs")
    for mode in ("anonymous", "authenticated"):
        parser.add_argument(f"--browser-{mode}"); parser.add_argument(f"--bff-logs-{mode}"); parser.add_argument(f"--orchestrator-logs-{mode}")
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main():
    args = _args(); output = Path(args.output_dir); output.mkdir(parents=True, exist_ok=True)
    if args.browser_anonymous and args.browser_authenticated:
        anonymous = analyze(load(args.browser_anonymous), load(args.bff_logs_anonymous), load(args.orchestrator_logs_anonymous), "anonymous")
        authenticated = analyze(load(args.browser_authenticated), load(args.bff_logs_authenticated), load(args.orchestrator_logs_authenticated), "authenticated")
        result = {"anonymous": anonymous, "authenticated": authenticated}; comparison = compare(anonymous, authenticated)
    else:
        if not all((args.browser_trace, args.bff_logs, args.orchestrator_logs)):
            raise SystemExit("single mode requires --browser-trace, --bff-logs, --orchestrator-logs")
        result = analyze(load(args.browser_trace), load(args.bff_logs), load(args.orchestrator_logs)); comparison = {"status": "single_trace_only", "additional_runs_required": True}
    payloads = {
        "summary.json": result, "segment_breakdown.json": result,
        "critical_path.json": {"primary_class": result.get("primary_class"), "confidence": result.get("confidence")} if "primary_class" in result else comparison,
        "anonymous_vs_authenticated.json": comparison, "missing_evidence.json": result.get("missing_evidence", {}),
    }
    for name, value in payloads.items():
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "report.md").write_text("# Operational E2E Latency\n\nAnalyzer output. Review `summary.json` for evidence quality and blocked reasons.\n", encoding="utf-8")


if __name__ == "__main__":
    main()
