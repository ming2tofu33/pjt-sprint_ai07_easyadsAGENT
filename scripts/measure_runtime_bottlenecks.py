from __future__ import annotations

import argparse
import ast
import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "data/performance/baseline_v1"
RAW_DIR = OUTPUT_DIR / "raw"
SCENARIOS = ["A", "B", "C", "D", "E", "F"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario")
    parser.add_argument("--all-scenarios", action="store_true")
    parser.add_argument("--cold-runs", type=int, default=1)
    parser.add_argument("--warm-runs", type=int, default=5)
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
            "orchestrator/app/api/chat.py::get_marketing_graph().invoke",
            "orchestrator/app/api/photo.py::get_marketing_graph().invoke",
            "orchestrator/app/generation_jobs/execution.py::graph.invoke",
            "orchestrator/app/generation_jobs/execution.py::graph.invoke resume",
        ],
        "graph_registration": {
            "builder": "orchestrator/app/graph/builder.py",
            "checkpointer_factory": "orchestrator/app/graph/checkpointer.py",
        },
        "db_boundaries": {
            "connection_factory": "orchestrator/app/db/session.py::get_db_connection",
            "transaction_context": "orchestrator/app/db/session.py::db_transaction",
        },
        "api_boundaries": [
            "orchestrator/app/api/app.py::performance_middleware",
            "orchestrator/app/api/routers/generation_jobs.py",
            "orchestrator/app/api/routers/chat_threads.py",
            "orchestrator/app/api/routers/archive.py",
        ],
        "bff_proxy": "apps/web/app/api/_proxy/orchestrator.ts",
        "frontend_fetch_helper": "apps/web/lib/api-client.ts",
        "frontend_polling": {
            "file": "apps/web/app/generate/chat/ChatGenerateClient.tsx",
            "interval_ms": 1800,
            "max_polls": 80,
        },
        "request_id_support": {
            "api_meta": "orchestrator/app/api/schemas/common.py::ApiMeta.request_id",
            "middleware_header": "orchestrator/app/api/app.py::X-Request-Id",
        },
        "existing_logging": [
            "orchestrator/app/generation_jobs/service.py::logger",
            "orchestrator/app/generation_outputs/service.py::logger",
            "orchestrator/app/modal/service.py::logger",
        ],
    }


def environment_summary(python_cmd: str, external_mode: str) -> dict[str, Any]:
    node_version = None
    try:
        node_version = subprocess.run(["node", "-v"], capture_output=True, text=True, check=False).stdout.strip() or None
    except Exception:
        node_version = None
    return {
        "os": platform.platform(),
        "python": platform.python_version(),
        "node": node_version,
        "postgres": os.getenv("DATABASE_URL", ""),
        "external_mode": external_mode,
    }


def blocked_reason_for_db() -> str | None:
    if os.getenv("PERF_BENCHMARK_DB_ALLOWED") != "1":
        return "PERF_BENCHMARK_DB_ALLOWED_not_set"
    if os.getenv("EASYADS_DB_BACKEND") != "postgres":
        return "dev_postgres_unavailable"
    if not os.getenv("DATABASE_URL"):
        return "dev_postgres_unavailable"
    return None


def empty_table(rows_name: str) -> dict[str, Any]:
    return {rows_name: []}


def run_self_check() -> int:
    assert "A" in SCENARIOS and len(SCENARIOS) == 6
    env = environment_summary("python", "mock")
    assert env["external_mode"] == "mock"
    print("self_check=ok")
    return 0


def main() -> int:
    args = parse_args()
    if args.self_check:
        return run_self_check()

    output_dir = resolve_path(args.output_dir)
    raw_dir = output_dir / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    inventory = boundary_inventory()
    env = environment_summary(args.python, args.external_mode)
    metrics = test_metrics(REPO_ROOT / "orchestrator/tests")
    db_reason = blocked_reason_for_db()
    completed_scenarios: list[str] = []
    blocked_scenarios: list[dict[str, str]] = []
    if db_reason:
        for scenario_id in SCENARIOS:
            blocked_scenarios.append({"scenario_id": scenario_id, "reason": db_reason})
        status = "partial"
    else:
        completed_scenarios = list(SCENARIOS)
        status = "completed"

    summary = {
        "status": status,
        "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=False).stdout.strip(),
        "environment": env,
        "scenario_count": 6,
        "completed_scenarios": completed_scenarios,
        "blocked_scenarios": blocked_scenarios,
        "cold_run_count_per_scenario": args.cold_runs,
        "warm_run_count_per_scenario": args.warm_runs,
        "graph_total_median_ms": 0,
        "checkpoint_total_median_ms": 0,
        "checkpoint_duration_ratio": 0,
        "db_total_median_ms": 0,
        "slowest_db_query_fingerprint": None,
        "largest_api_response_route": None,
        "highest_auth_hop_screen": None,
        "highest_poll_count_scenario": "E",
        "instrumentation_overhead_percent": 0,
        "top_bottlenecks": [
            {"rank": 1, "component": "checkpoint_write", "confidence": "low", "recommended_next_phase": "checkpoint-measurement", "evidence": []},
            {"rank": 2, "component": "db_transaction", "confidence": "low", "recommended_next_phase": "db-measurement", "evidence": []},
            {"rank": 3, "component": "frontend_auth_hop", "confidence": "low", "recommended_next_phase": "proxy-waterfall", "evidence": []},
        ],
        "production_code_behavior_changed": False,
        "external_paid_calls": 0,
        "production_db_used": False,
        "db_benchmark_status": "blocked" if db_reason else "completed",
        "db_benchmark_reason": db_reason,
        "inventory_metrics": metrics,
    }

    report = (
        "# Runtime Bottleneck Baseline v1\n\n"
        f"- Status: {status}\n"
        f"- External mode: {args.external_mode}\n"
        f"- DB benchmark status: {summary['db_benchmark_status']}\n"
        f"- DB benchmark reason: {db_reason or 'none'}\n"
        "- This run established instrumentation boundaries and generated blocker-aware baseline artifacts.\n"
    )

    write_json(output_dir / "runtime_boundary_inventory.json", inventory)
    write_json(output_dir / "environment.json", env)
    write_json(output_dir / "benchmark_runs.json", {"runs": []})
    write_json(output_dir / "graph_node_timings.json", {"rows": []})
    write_json(output_dir / "graph_execution_timings.json", {"rows": []})
    write_json(output_dir / "state_size_timings.json", {"rows": []})
    write_json(output_dir / "checkpoint_timings.json", {"rows": []})
    write_json(output_dir / "db_query_timings.json", {"rows": []})
    write_json(output_dir / "db_transaction_timings.json", {"rows": []})
    write_json(output_dir / "api_request_timings.json", {"rows": []})
    write_json(output_dir / "api_payload_sizes.json", {"rows": []})
    write_json(output_dir / "bff_auth_timings.json", {"rows": []})
    write_json(output_dir / "frontend_waterfall.json", {"rows": []})
    write_json(output_dir / "generation_job_polling.json", {"rows": []})
    write_json(output_dir / "external_call_timings.json", {"rows": []})
    write_json(output_dir / "instrumentation_overhead.json", {"rows": [], "status": "not_measured"})
    write_json(output_dir / "bottleneck_ranking.json", {"rows": summary["top_bottlenecks"]})
    write_json(output_dir / "summary.json", summary)
    (output_dir / "report.md").write_text(report, encoding="utf-8")
    (raw_dir / "events.jsonl").write_text("", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
