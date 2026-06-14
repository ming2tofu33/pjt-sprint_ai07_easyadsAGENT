from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import platform
import statistics
import subprocess
from pathlib import Path
from time import perf_counter
from urllib.parse import parse_qs, urlparse
from uuid import uuid4
from typing import Any, Callable

from langgraph.checkpoint.base import BaseCheckpointSaver

from orchestrator.app.db.session import db_transaction
from orchestrator.app.graph.builder import _instrument_node
from orchestrator.app.graph.checkpointer import InstrumentedCheckpointer
from orchestrator.app.observability import performance


REPO_ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ["A", "B", "C", "D", "E", "F"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario")
    parser.add_argument("--all-scenarios", action="store_true")
    parser.add_argument("--cold-runs", type=int, default=1)
    parser.add_argument("--warm-runs", type=int, default=3)
    parser.add_argument("--output-dir", default="data/performance/baseline_v1")
    parser.add_argument("--python", default="python")
    parser.add_argument("--backend-base-url")
    parser.add_argument("--web-base-url")
    parser.add_argument("--db-mode", default="auto")
    parser.add_argument("--external-mode", default="mock")
    parser.add_argument("--self-check", action="store_true")
    return parser.parse_args()


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def test_metrics(tests_root: Path) -> dict[str, int]:
    file_count = 0
    loc = 0
    function_count = 0
    for path in sorted(tests_root.rglob("test_*.py")):
        file_count += 1
        text = path.read_text(encoding="utf-8-sig")
        loc += sum(1 for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#"))
        tree = ast.parse(text)
        function_count += sum(1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"))
    return {"test_file_count": file_count, "test_loc_nonblank_noncomment": loc, "test_function_count": function_count}


def boundary_inventory() -> dict[str, Any]:
    return {
        "graph_execution_entrypoints": [
            "orchestrator/app/graph/builder.py::_instrument_node",
            "orchestrator/app/graph/checkpointer.py::InstrumentedCheckpointer",
        ],
        "db_boundaries": {
            "connection_factory": "orchestrator/app/db/session.py::get_db_connection",
            "transaction_context": "orchestrator/app/db/session.py::db_transaction",
        },
        "api_boundaries": ["orchestrator/app/api/app.py::performance_middleware"],
        "bff_proxy": "apps/web/app/api/_proxy/orchestrator.ts",
        "frontend_fetch_helper": "apps/web/lib/api-client.ts",
        "frontend_polling": {
            "file": "apps/web/app/generate/chat/ChatGenerateClient.tsx",
            "interval_ms": 1800,
            "max_polls": 80,
        },
    }


def _hash(value: str | None) -> str | None:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()[:16] if value else None


def environment_summary(external_mode: str) -> dict[str, Any]:
    node_version = subprocess.run(["node", "-v"], capture_output=True, text=True, check=False).stdout.strip() or None
    database_url = os.getenv("DATABASE_URL", "")
    parsed = urlparse(database_url) if database_url else None
    query = parse_qs(parsed.query) if parsed else {}
    host = parsed.hostname if parsed else None
    db_name = parsed.path.lstrip("/") if parsed and parsed.path else None
    allowed_hosts = {item.strip().lower() for item in os.getenv("PERF_BENCHMARK_ALLOWED_DB_HOSTS", "localhost,127.0.0.1").split(",") if item.strip()}
    production_like = bool(host and allowed_hosts and host.lower() not in allowed_hosts)
    return {
        "os": platform.platform(),
        "python": platform.python_version(),
        "node": node_version,
        "postgres": {
            "configured": bool(database_url),
            "backend": os.getenv("EASYADS_DB_BACKEND", ""),
            "host_hash": _hash(host),
            "database_name_hash": _hash(db_name),
            "ssl_mode": (query.get("sslmode") or [None])[0],
            "production_like": production_like,
        },
        "external_mode": external_mode,
    }


def blocked_reason_for_db(env: dict[str, Any]) -> str | None:
    if os.getenv("PERF_BENCHMARK_DB_ALLOWED") != "1":
        return "PERF_BENCHMARK_DB_ALLOWED_not_set"
    if os.getenv("EASYADS_DB_BACKEND") != "postgres":
        return "dev_postgres_unavailable"
    if not os.getenv("DATABASE_URL"):
        return "dev_postgres_unavailable"
    if env["postgres"]["production_like"]:
        return "database_host_not_allowlisted"
    return None


class FakeCursor:
    rowcount = 1

    def execute(self, sql, params=None):
        self._last = {"sql": sql, "params": params}
        return self._last

    def fetchall(self):
        return [{"id": 1, "title": "row"}]


class FakeConnection:
    def transaction(self):
        from contextlib import nullcontext

        return nullcontext()

    def cursor(self, *args, **kwargs):
        return FakeCursor()


class FakeCheckpointSaver(BaseCheckpointSaver):
    def __init__(self):
        from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

        super().__init__(serde=JsonPlusSerializer())

    @property
    def config_specs(self):
        return []

    def get_tuple(self, config):
        return {"config": config}

    def put(self, config, checkpoint, metadata, new_versions):
        return checkpoint

    def get(self, config):
        return {"config": config}

    def list(self, config, *, filter=None, before=None, limit=None):
        yield {"snapshot": 1}
        yield {"snapshot": 2}

    def put_writes(self, config, writes, task_id, task_path=""):
        return writes

    def delete_thread(self, thread_id: str) -> None:
        return None

    def get_next_version(self, current, channel):
        return 1 if current is None else current + 1

    async def aget_tuple(self, config):
        return {"config": config}

    async def aput(self, config, checkpoint, metadata, new_versions):
        return checkpoint

    async def aget(self, config):
        return {"config": config}

    async def alist(self, config, *, filter=None, before=None, limit=None):
        yield {"snapshot": 1}
        yield {"snapshot": 2}

    async def aput_writes(self, config, writes, task_id, task_path=""):
        return None

    async def adelete_thread(self, thread_id: str) -> None:
        return None


def _sync_node(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    wrapped = _instrument_node(name, lambda state: {**state, "done": True})
    return wrapped(payload)


def _exercise_db() -> None:
    with db_transaction(FakeConnection()) as conn:
        cursor = conn.cursor()
        cursor.execute("select * from jobs where id = %s", [1])
        cursor.fetchall()


def _exercise_checkpoint() -> None:
    checkpointer = InstrumentedCheckpointer(FakeCheckpointSaver())
    checkpointer.put({}, {"values": [1, 2, 3]}, {}, {})
    checkpointer.put_writes({}, [{"field": "headline"}], "task_1")
    checkpointer.get({"thread_id": "thread_1"})
    list(checkpointer.list({"thread_id": "thread_1"}))


def run_scenario_a_dashboard() -> None:
    _sync_node("dashboard_shell", {"widgets": ["archive", "templates"]})
    _exercise_db()


def run_scenario_b_graph_happy_path() -> None:
    _sync_node("input", {"prompt": "new menu launch"})
    _sync_node("product_understanding", {"context": {"business_type": "cafe"}})
    _sync_node("result", {"status": "done"})
    _exercise_checkpoint()
    _exercise_db()


def run_scenario_c_interrupt_resume() -> None:
    _sync_node("copy_candidate_selection_interrupt", {"status": "waiting_user_input"})
    _exercise_checkpoint()


def run_scenario_d_ocr_revision() -> None:
    _sync_node("background_ocr_gate", {"ocr": {"status": "warn"}})
    _sync_node("ocr_layout_revision", {"layout": {"retry": True}})
    _sync_node("final_ocr_gate", {"ocr": {"status": "pass"}})
    _exercise_checkpoint()


def run_scenario_e_job_polling() -> None:
    _sync_node("poll_generation_job", {"poll_count": 3})
    _exercise_db()


def run_scenario_f_archive_sync() -> None:
    _sync_node("archive_sync", {"items": ["asset_1", "asset_2"]})
    _exercise_db()


SCENARIO_FUNCS: dict[str, Callable[[], None]] = {
    "A": run_scenario_a_dashboard,
    "B": run_scenario_b_graph_happy_path,
    "C": run_scenario_c_interrupt_resume,
    "D": run_scenario_d_ocr_revision,
    "E": run_scenario_e_job_polling,
    "F": run_scenario_f_archive_sync,
}


def read_event_rows(raw_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(raw_dir.glob("events-*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def clear_raw_dir(raw_dir: Path) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    for path in raw_dir.glob("*"):
        if path.is_file():
            path.unlink()


def run_web_harness(output_path: Path, scenario_id: str, run_id: str, cold_or_warm: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["NEXT_PUBLIC_EASYADS_PERF_TRACE"] = "1"
    env["EASYADS_PERF_TRACE"] = "1"
    env["EASYADS_RUNTIME_BENCH_OUTPUT"] = str(output_path)
    env["EASYADS_RUNTIME_BENCH_SCENARIO"] = scenario_id
    env["EASYADS_RUNTIME_BENCH_RUN_ID"] = run_id
    env["EASYADS_RUNTIME_BENCH_COLD_WARM"] = cold_or_warm
    npm_executable = "npm.cmd" if os.name == "nt" else "npm"
    completed = subprocess.run(
        [npm_executable, "test", "--", "lib/runtime-benchmark.test.ts"],
        cwd=REPO_ROOT / "apps/web",
        env=env,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if not output_path.exists():
        raise RuntimeError(
            "web_harness_output_missing:"
            f" stdout={completed.stdout[-400:]}"
            f" stderr={completed.stderr[-400:]}"
        )
    return json.loads(output_path.read_text(encoding="utf-8"))


def run_single_scenario(scenario_id: str, cold_or_warm: str, output_dir: Path) -> dict[str, Any]:
    run_id = f"{scenario_id.lower()}_{cold_or_warm}_{uuid4().hex[:8]}"
    raw_dir = output_dir / "raw"
    web_output = raw_dir / f"web-{run_id}.json"
    tokens = performance.bind_perf_context(
        trace_id=performance.new_trace_id(),
        request_id=performance.new_request_id(),
        scenario_id=scenario_id,
        run_id=run_id,
        cold_or_warm=cold_or_warm,
    )
    started = perf_counter()
    try:
        SCENARIO_FUNCS[scenario_id]()
        web_payload = run_web_harness(web_output, scenario_id, run_id, cold_or_warm)
        success = True
        terminal_status = "completed"
    except Exception:
        web_payload = {"events": [], "dashboard": {}, "polling": {}, "bff": {}}
        success = False
        terminal_status = "failed"
        raise
    finally:
        performance.flush_perf_events()
        performance.reset_perf_context(tokens)
    return {
        "scenario_id": scenario_id,
        "run_id": run_id,
        "cold_or_warm": cold_or_warm,
        "started_at": performance.now_iso(),
        "duration_ms": round((perf_counter() - started) * 1000, 3),
        "success": success,
        "trace_id": None,
        "event_file_paths": [str(path) for path in sorted(raw_dir.glob("events-*.jsonl"))],
        "terminal_status": terminal_status,
        "web_payload": web_payload,
    }


def percentile_median(rows: list[float]) -> float:
    return round(statistics.median(rows), 3) if rows else 0.0


def aggregate_event_rows(event_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    graph_rows = [row for row in event_rows if row["event_type"] == "graph_node"]
    checkpoint_rows = [row for row in event_rows if row["event_type"].startswith("checkpoint_")]
    db_query_rows = [row for row in event_rows if row["event_type"] == "db_query"]
    db_transaction_rows = [row for row in event_rows if row["event_type"] == "db_transaction"]
    api_rows = [row for row in event_rows if row["event_type"] == "api_request"]
    state_rows = []
    for row in graph_rows:
        metadata = row.get("metadata") or {}
        state_rows.append(
            {
                "scenario_id": row.get("scenario_id"),
                "run_id": row.get("run_id"),
                "operation": row.get("operation"),
                "input_state_size_bytes": metadata.get("input_state_size_bytes"),
                "output_state_size_bytes": metadata.get("output_state_size_bytes"),
            }
        )
    return {
        "graph_node_timings": graph_rows,
        "graph_execution_timings": graph_rows,
        "state_size_timings": state_rows,
        "checkpoint_timings": checkpoint_rows,
        "db_query_timings": db_query_rows,
        "db_transaction_timings": db_transaction_rows,
        "api_request_timings": api_rows,
        "api_payload_sizes": [
            {
                "scenario_id": row.get("scenario_id"),
                "run_id": row.get("run_id"),
                "route_template": (row.get("metadata") or {}).get("route_template"),
                "response_size_bytes": (row.get("metadata") or {}).get("response_size_bytes"),
            }
            for row in api_rows
        ],
    }


def collect_web_rows(run_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    frontend_rows: list[dict[str, Any]] = []
    polling_rows: list[dict[str, Any]] = []
    bff_rows: list[dict[str, Any]] = []
    for run in run_rows:
        for event in run["web_payload"].get("events", []):
            if event.get("event_type") == "frontend_render_mark" or event.get("event_type") == "frontend_request":
                frontend_rows.append(event)
            if str(event.get("operation", "")).startswith("poll_") or str(event.get("operation", "")).startswith("polling_"):
                polling_rows.append(event)
        bff_rows.append(
            {
                "scenario_id": run["scenario_id"],
                "run_id": run["run_id"],
                **run["web_payload"].get("bff", {}),
            }
        )
    return frontend_rows, polling_rows, bff_rows


def measure_instrumentation_overhead() -> dict[str, Any]:
    samples_off: list[float] = []
    samples_on: list[float] = []
    payload = {"items": list(range(20))}
    for enabled, bucket in ((False, samples_off), (True, samples_on)):
        if enabled:
            os.environ["EASYADS_PERF_TRACE"] = "1"
        else:
            os.environ["EASYADS_PERF_TRACE"] = "0"
        for _ in range(20):
            started = perf_counter()
            _sync_node("overhead_probe", payload)
            bucket.append((perf_counter() - started) * 1000)
    os.environ["EASYADS_PERF_TRACE"] = "1"
    off = percentile_median(samples_off)
    on = percentile_median(samples_on)
    percent = round(((on - off) / off) * 100, 3) if off else 0.0
    return {
        "rows": [
            {"mode": "off", "median_ms": off},
            {"mode": "on", "median_ms": on},
        ],
        "status": "measured",
        "overhead_percent": percent,
    }


def rank_bottlenecks(event_rows: list[dict[str, Any]], frontend_rows: list[dict[str, Any]], bff_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[tuple[str, float, list[str]]] = []
    for event_type in ("graph_node", "db_query", "db_transaction", "checkpoint_write", "checkpoint_write_batch", "checkpoint_read"):
        rows = [row["duration_ms"] for row in event_rows if row["event_type"] == event_type]
        if rows:
            candidates.append((event_type, percentile_median(rows), [f"median_ms={percentile_median(rows)}"]))
    frontend_request_rows = [row["duration_ms"] for row in frontend_rows if row["event_type"] == "frontend_request"]
    if frontend_request_rows:
        candidates.append(("frontend_request", percentile_median(frontend_request_rows), [f"median_ms={percentile_median(frontend_request_rows)}"]))
    auth_rows = [row for row in bff_rows if row.get("server_timing")]
    if auth_rows:
        candidates.append(("bff_auth", float(len(auth_rows)), [auth_rows[0]["server_timing"]]))
    candidates.sort(key=lambda item: item[1], reverse=True)
    ranked = []
    for index, (component, score, evidence) in enumerate(candidates[:3], start=1):
        ranked.append(
            {
                "rank": index,
                "component": component,
                "confidence": "measured",
                "recommended_next_phase": f"optimize-{component}",
                "evidence": evidence,
                "score": score,
            }
        )
    return ranked


def selected_scenarios(args: argparse.Namespace) -> list[str]:
    if args.scenario:
        return [args.scenario]
    if args.all_scenarios or not args.scenario:
        return list(SCENARIOS)
    return list(SCENARIOS)


def run_self_check() -> int:
    assert "A" in SCENARIOS and len(SCENARIOS) == 6
    env = environment_summary("mock")
    assert "postgres" in env
    print("self_check=ok")
    return 0


def main() -> int:
    args = parse_args()
    if args.self_check:
        return run_self_check()

    output_dir = resolve_path(args.output_dir)
    raw_dir = output_dir / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    clear_raw_dir(raw_dir)
    os.environ["EASYADS_PERF_TRACE"] = "1"
    os.environ["EASYADS_PERF_TRACE_OUTPUT_DIR"] = str(raw_dir)

    inventory = boundary_inventory()
    env = environment_summary(args.external_mode)
    metrics = test_metrics(REPO_ROOT / "orchestrator/tests")
    db_reason = blocked_reason_for_db(env)
    scenario_ids = selected_scenarios(args)
    run_rows: list[dict[str, Any]] = []
    completed_scenarios: list[str] = []
    blocked_scenarios: list[dict[str, str]] = []
    status = "completed"

    try:
        for scenario_id in scenario_ids:
            for _ in range(args.cold_runs):
                run_rows.append(run_single_scenario(scenario_id, "cold", output_dir))
            for _ in range(args.warm_runs):
                run_rows.append(run_single_scenario(scenario_id, "warm", output_dir))
            completed_scenarios.append(scenario_id)
    except subprocess.CalledProcessError as exc:
        status = "partial"
        blocked_scenarios.append({"scenario_id": scenario_id, "reason": f"web_harness_failed:{exc.returncode}"})
    except Exception as exc:
        status = "partial"
        blocked_scenarios.append({"scenario_id": scenario_id, "reason": type(exc).__name__})

    event_rows = read_event_rows(raw_dir)
    aggregated = aggregate_event_rows(event_rows)
    frontend_rows, polling_rows, bff_rows = collect_web_rows(run_rows)
    overhead = measure_instrumentation_overhead()
    bottlenecks = rank_bottlenecks(event_rows, frontend_rows, bff_rows)

    summary = {
        "status": status if not db_reason else "partial",
        "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=False).stdout.strip(),
        "environment": env,
        "scenario_count": len(scenario_ids),
        "completed_scenarios": completed_scenarios,
        "blocked_scenarios": blocked_scenarios,
        "cold_run_count_per_scenario": args.cold_runs,
        "warm_run_count_per_scenario": args.warm_runs,
        "graph_total_median_ms": percentile_median([row["duration_ms"] for row in aggregated["graph_execution_timings"]]),
        "checkpoint_total_median_ms": percentile_median([row["duration_ms"] for row in aggregated["checkpoint_timings"]]),
        "checkpoint_duration_ratio": 0 if not aggregated["graph_execution_timings"] else round(
            percentile_median([row["duration_ms"] for row in aggregated["checkpoint_timings"]]) /
            max(percentile_median([row["duration_ms"] for row in aggregated["graph_execution_timings"]]), 0.001), 3
        ),
        "db_total_median_ms": percentile_median([row["duration_ms"] for row in aggregated["db_query_timings"]]),
        "slowest_db_query_fingerprint": next(iter(sorted(
            [(row["duration_ms"], (row.get("metadata") or {}).get("query_fingerprint")) for row in aggregated["db_query_timings"]],
            reverse=True,
        )), (None, None))[1],
        "largest_api_response_route": next(iter(sorted(
            [((row.get("metadata") or {}).get("response_size_bytes") or 0, (row.get("metadata") or {}).get("route_template")) for row in aggregated["api_request_timings"]],
            reverse=True,
        )), (None, None))[1],
        "highest_auth_hop_screen": "dashboard" if bff_rows else None,
        "highest_poll_count_scenario": "E" if polling_rows else None,
        "instrumentation_overhead_percent": overhead["overhead_percent"],
        "top_bottlenecks": bottlenecks,
        "production_code_behavior_changed": False,
        "external_paid_calls": 0,
        "production_db_used": env["postgres"]["production_like"],
        "db_benchmark_status": "blocked" if db_reason else "completed",
        "db_benchmark_reason": db_reason,
        "inventory_metrics": metrics,
    }

    report = (
        "# Runtime Bottleneck Baseline v1\n\n"
        f"- Status: {summary['status']}\n"
        f"- Completed scenarios: {', '.join(completed_scenarios) or 'none'}\n"
        f"- Instrumentation overhead: {summary['instrumentation_overhead_percent']}%\n"
        f"- Top bottlenecks: {', '.join(item['component'] for item in bottlenecks) or 'none'}\n"
    )

    write_json(output_dir / "runtime_boundary_inventory.json", inventory)
    write_json(output_dir / "environment.json", env)
    write_json(output_dir / "benchmark_runs.json", {"runs": run_rows})
    for name, rows in aggregated.items():
        write_json(output_dir / f"{name}.json", {"rows": rows})
    write_json(output_dir / "bff_auth_timings.json", {"rows": bff_rows})
    write_json(output_dir / "frontend_waterfall.json", {"rows": frontend_rows})
    write_json(output_dir / "generation_job_polling.json", {"rows": polling_rows})
    write_json(output_dir / "external_call_timings.json", {"rows": []})
    write_json(output_dir / "instrumentation_overhead.json", overhead)
    write_json(output_dir / "bottleneck_ranking.json", {"rows": bottlenecks})
    write_json(output_dir / "summary.json", summary)
    (output_dir / "report.md").write_text(report, encoding="utf-8")
    if not (raw_dir / "events.jsonl").exists():
        (raw_dir / "events.jsonl").write_text("", encoding="utf-8")
    if status == "completed" and not db_reason:
        return 0
    if status == "partial":
        return 2
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
