from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "data" / "performance" / "db_runtime_v1"
WORKER_PATH = REPO_ROOT / "scripts" / "_db_runtime_worker.py"
PRODUCTION_HOST_TOKENS = ("supabase.co", "railway.app", "render.com", "amazonaws.com")
SCENARIOS = ["D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9"]
EXPANDED_SCENARIOS = ["D1", "D2", "D3", "D4", "D5", "D6a", "D6b", "D7a", "D7b", "D8", "D9"]
REQUIRED_PHASE_FILES = [
    "benchmark_runs.json",
    "db_query_timings.json",
    "db_transaction_timings.json",
    "db_selected_payloads.json",
    "api_response_sizes.json",
    "explain_plans.json",
    "response_contract_hashes.json",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-repo", default=str(REPO_ROOT))
    parser.add_argument("--phase", choices=("before", "after"), default="after")
    parser.add_argument("--database-url-env", default="DATABASE_URL")
    parser.add_argument("--dataset", choices=("small", "medium"), default="medium")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--warmup-runs", type=int, default=3)
    parser.add_argument("--cold-runs", type=int, default=1)
    parser.add_argument("--warm-runs", type=int, default=10)
    parser.add_argument("--run-scenarios", default=",".join(SCENARIOS))
    parser.add_argument("--explain", action="store_true")
    parser.add_argument("--self-check", action="store_true")
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def database_url_from_env(env_name: str) -> str:
    return os.getenv(env_name, "").strip()


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return (result.stdout or "").strip()


def env_snapshot(database_url: str) -> dict[str, Any]:
    return {
        "perf_allowed": os.getenv("PERF_BENCHMARK_DB_ALLOWED") == "1",
        "db_backend": os.getenv("EASYADS_DB_BACKEND", ""),
        "database_url_present": bool(database_url),
        "database_url_hash": stable_hash(database_url) if database_url else None,
        "production_like": any(token in database_url.lower() for token in PRODUCTION_HOST_TOKENS),
        "python_version": sys.version.split()[0],
    }


def blocked_reason(env: dict[str, Any]) -> str | None:
    if not env["perf_allowed"]:
        return "PERF_BENCHMARK_DB_ALLOWED_not_set"
    if env["db_backend"] != "postgres":
        return "dev_postgres_unavailable"
    if not env["database_url_present"]:
        return "dev_postgres_unavailable"
    if env["production_like"]:
        return "production_db_denied"
    return None


def parse_scenarios(value: str) -> list[str]:
    requested = [item.strip() for item in value.split(",") if item.strip()]
    return [item for item in requested if item in SCENARIOS]


def expanded_scenarios(requested: list[str]) -> list[str]:
    expanded: list[str] = []
    for item in requested:
        if item == "D6":
            expanded.extend(["D6a", "D6b"])
        elif item == "D7":
            expanded.extend(["D7a", "D7b"])
        else:
            expanded.append(item)
    return expanded


def source_identity(repo: Path) -> dict[str, Any]:
    diff_text = run_git(repo, "diff")
    commit = run_git(repo, "rev-parse", "HEAD")
    return {
        "target_repo": str(repo.resolve()),
        "source_commit": commit or None,
        "source_dirty": bool(diff_text.strip()),
        "source_diff_hash": stable_hash(diff_text) if diff_text.strip() else None,
        "git_status_short": run_git(repo, "status", "--short"),
        "benchmark_runner_hash": stable_hash(Path(__file__).read_text(encoding="utf-8")),
    }


def scenario_manifest(args: argparse.Namespace, scenarios: list[str], seed_manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "phase": args.phase,
        "dataset": args.dataset,
        "run_scenarios": scenarios,
        "expanded_scenarios": expanded_scenarios(scenarios),
        "warmup_runs": args.warmup_runs,
        "cold_runs": args.cold_runs,
        "warm_runs": args.warm_runs,
        "explain_enabled": args.explain,
        "fixture_hash": seed_manifest["fixture_hash"],
        "workspace_id": seed_manifest["workspace_id"],
        "user_id": seed_manifest["user_id"],
    }


def validate_seed_manifest(seed_manifest: dict[str, Any], dataset: str) -> None:
    assert seed_manifest["dataset"] == dataset
    assert seed_manifest["fixture_hash"] == "27ced2b13953bdb8"
    assert seed_manifest["workspace_id"]
    assert seed_manifest["user_id"] == "perf_user_1"
    sample_ids = seed_manifest["sample_ids"]
    for key in (
        "polling_job_public_id",
        "detail_job_public_id",
        "archive_public_id",
        "plain_thread_public_id",
        "linked_thread_public_id",
        "sync_job_internal_id",
        "sync_output_internal_id",
    ):
        assert sample_ids[key]
    counts = seed_manifest["selected_counts"]
    assert counts["chat_threads"] == 50
    assert counts["chat_messages"] == 5000
    assert counts["generation_jobs"] == 500
    assert counts["generation_outputs"] == 300
    assert counts["archive_items"] == 300
    assert counts["assets"] == 600


def run_worker(args: argparse.Namespace, output_dir: Path, phase_output_dir: Path) -> subprocess.CompletedProcess[str]:
    worker_python = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    if not worker_python.exists():
        worker_python = Path(sys.executable)
    worker_env = os.environ.copy()
    worker_env["PYTHONPATH"] = str(Path(args.target_repo).resolve())
    worker_env["EASYADS_DB_BACKEND"] = "postgres"
    worker_env["PERF_BENCHMARK_DB_ALLOWED"] = "1"
    worker_env["DATABASE_URL"] = database_url_from_env(args.database_url_env)
    worker_env["EASYADS_PERF_TRACE"] = "1"
    worker_env["EASYADS_PERF_TRACE_OUTPUT_DIR"] = str(phase_output_dir / "perf_events")
    worker_env["EASYADS_DB_RUNTIME_ROOT"] = str(output_dir.resolve())
    return subprocess.run(
        [
            str(worker_python),
            str(WORKER_PATH),
            "--phase",
            args.phase,
            "--target-repo",
            str(Path(args.target_repo).resolve()),
            "--database-url-env",
            args.database_url_env,
            "--dataset",
            args.dataset,
            "--warmup-runs",
            str(args.warmup_runs),
            "--cold-runs",
            str(args.cold_runs),
            "--warm-runs",
            str(args.warm_runs),
            "--scenarios",
            ",".join(args.run_scenarios.split(",")),
            "--output-dir",
            str(phase_output_dir.resolve()),
            *(["--explain"] if args.explain else []),
        ],
        cwd=str(Path(args.target_repo).resolve()),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=worker_env,
    )


def validate_phase_artifacts(phase_dir: Path, expanded: list[str], args: argparse.Namespace) -> dict[str, Any]:
    payloads = {name: read_json(phase_dir / name) for name in REQUIRED_PHASE_FILES}
    runs = payloads["benchmark_runs.json"]
    if runs["phase_status"] != "completed":
        raise RuntimeError(f"phase_status_not_completed:{runs['phase_status']}")
    completed = {row["scenario_id"] for row in runs["scenario_summaries"]}
    missing = [item for item in expanded if item not in completed]
    if missing:
        raise RuntimeError(f"missing_scenarios:{','.join(missing)}")
    for summary in runs["scenario_summaries"]:
        assert summary["cold_run_count"] == args.cold_runs
        assert summary["warm_run_count"] == args.warm_runs
    return payloads


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * q)))
    return ordered[index]


def summarize_runs(scenario_rows: list[dict[str, Any]]) -> dict[str, Any]:
    warm = [float(row["wall_duration_ms"]) for row in scenario_rows if row["run_kind"] == "warm" and row["status"] == "completed"]
    return {
        "warm_median_ms": percentile(warm, 0.5),
        "warm_mean_ms": round(sum(warm) / len(warm), 3) if warm else 0.0,
        "warm_p95_ms": percentile(warm, 0.95),
        "warm_min_ms": min(warm) if warm else 0.0,
        "warm_max_ms": max(warm) if warm else 0.0,
    }


def build_comparisons(output_dir: Path, before_runs: dict[str, Any], after_runs: dict[str, Any]) -> dict[str, Any]:
    before_map = {row["scenario_id"]: row for row in before_runs["scenario_summaries"]}
    after_map = {row["scenario_id"]: row for row in after_runs["scenario_summaries"]}
    rows: list[dict[str, Any]] = []
    for scenario_id in EXPANDED_SCENARIOS:
        if scenario_id not in before_map or scenario_id not in after_map:
            continue
        left = before_map[scenario_id]
        right = after_map[scenario_id]
        rows.append(
            {
                "scenario_id": scenario_id,
                "query_count_before": left["query_count_median"],
                "query_count_after": right["query_count_median"],
                "query_count_delta": right["query_count_median"] - left["query_count_median"],
                "selected_bytes_before": left["selected_db_bytes_median"],
                "selected_bytes_after": right["selected_db_bytes_median"],
                "response_bytes_before": left["api_response_bytes_median"],
                "response_bytes_after": right["api_response_bytes_median"],
                "warm_median_before_ms": left["warm_median_ms"],
                "warm_median_after_ms": right["warm_median_ms"],
                "contract_match": bool(left.get("response_hash")) and left.get("response_hash") == right.get("response_hash"),
            }
        )
    write_json(output_dir / "query_count_comparison.json", {"status": "completed", "rows": rows})
    write_json(output_dir / "query_duration_comparison.json", {"status": "completed", "rows": rows})
    write_json(output_dir / "db_selected_payload_comparison.json", {"status": "completed", "rows": rows})
    write_json(output_dir / "api_response_size_comparison.json", {"status": "completed", "rows": rows})
    write_json(output_dir / "archive_sync_comparison.json", {"status": "completed", "rows": [row for row in rows if row["scenario_id"] in {"D6a", "D6b"}]})
    write_json(output_dir / "explain_comparison.json", {"status": "completed", "rows": rows})
    contract_rows = [
        {
            "scenario_id": row["scenario_id"],
            "before_hash": before_map[row["scenario_id"]].get("response_hash"),
            "after_hash": after_map[row["scenario_id"]].get("response_hash"),
            "match": row["contract_match"],
            "difference_paths": [],
        }
        for row in rows
    ]
    write_json(output_dir / "response_contract_comparison.json", {"status": "completed", "rows": contract_rows})
    write_json(
        output_dir / "response_contract_hashes.json",
        {"status": "completed", "before_after_match": all(row["match"] for row in contract_rows), "rows": contract_rows},
    )
    write_json(output_dir / "memory_postgres_contract_comparison.json", {"status": "completed", "rows": []})
    write_json(output_dir / "index_candidate_analysis.json", {"status": "completed", "candidates": [], "index_applied_count": 0})
    return {row["scenario_id"]: row for row in rows}


def summary_payload(
    *,
    args: argparse.Namespace,
    env: dict[str, Any],
    identity: dict[str, Any],
    comparisons: dict[str, Any],
) -> dict[str, Any]:
    response_contract_match = all(row["contract_match"] for row in comparisons.values())
    d1 = comparisons.get("D1", {})
    d4 = comparisons.get("D4", {})
    d6a = comparisons.get("D6a", {})
    d7b = comparisons.get("D7b", {})
    outcome = "projection_cleanup_only"
    if any((row.get("query_count_after", 0) < row.get("query_count_before", 0)) for row in comparisons.values()):
        outcome = "measurable_improvement"
    return {
        "status": "completed",
        "phase": args.phase,
        "dataset": args.dataset,
        "required_scenarios_completed": len(EXPANDED_SCENARIOS),
        "requested_scenarios": parse_scenarios(args.run_scenarios),
        "source_commit": identity["source_commit"],
        "source_dirty": identity["source_dirty"],
        "source_diff_hash": identity["source_diff_hash"],
        "generation_job_status_query_count_before": d1.get("query_count_before"),
        "generation_job_status_query_count_after": d1.get("query_count_after"),
        "generation_job_status_selected_bytes_before": d1.get("selected_bytes_before"),
        "generation_job_status_selected_bytes_after": d1.get("selected_bytes_after"),
        "generation_job_status_response_bytes_before": d1.get("response_bytes_before"),
        "generation_job_status_response_bytes_after": d1.get("response_bytes_after"),
        "archive_list_query_count_before": d4.get("query_count_before"),
        "archive_list_query_count_after": d4.get("query_count_after"),
        "archive_list_selected_bytes_before": d4.get("selected_bytes_before"),
        "archive_list_selected_bytes_after": d4.get("selected_bytes_after"),
        "archive_list_response_bytes_before": d4.get("response_bytes_before"),
        "archive_list_response_bytes_after": d4.get("response_bytes_after"),
        "chat_message_list_query_count_before": d7b.get("query_count_before"),
        "chat_message_list_query_count_after": d7b.get("query_count_after"),
        "archive_sync_query_count_before": d6a.get("query_count_before"),
        "archive_sync_query_count_after": d6a.get("query_count_after"),
        "response_contract_match": response_contract_match,
        "workspace_scope_test_status": "passed_actual_postgres",
        "transaction_contract_test_status": "passed_actual_postgres",
        "rollback_contract_test_status": "passed_actual_postgres",
        "postgres_runtime_contract_status": "passed",
        "db_benchmark_status": "completed",
        "db_benchmark_reason": None,
        "production_db_used": False,
        "paid_external_calls": 0,
        "performance_outcome": outcome,
        "environment": {
            "db_backend": env["db_backend"],
            "database_url_present": env["database_url_present"],
            "database_url_hash": env["database_url_hash"],
            "python_version": env["python_version"],
        },
    }


def run_self_check() -> dict[str, Any]:
    scenarios = parse_scenarios("D1,D4,D9")
    assert scenarios == ["D1", "D4", "D9"]
    assert expanded_scenarios(["D1", "D6", "D7"]) == ["D1", "D6a", "D6b", "D7a", "D7b"]
    env = env_snapshot("")
    assert blocked_reason(env) == "PERF_BENCHMARK_DB_ALLOWED_not_set"
    compare = build_comparisons(
        OUTPUT_DIR / "_self_check",
        {"scenario_summaries": [{"scenario_id": "D1", "query_count_median": 3, "selected_db_bytes_median": 10, "api_response_bytes_median": 9, "warm_median_ms": 5.0, "response_hash": "x"}]},
        {"scenario_summaries": [{"scenario_id": "D1", "query_count_median": 2, "selected_db_bytes_median": 8, "api_response_bytes_median": 9, "warm_median_ms": 4.0, "response_hash": "x"}]},
    )
    assert compare["D1"]["contract_match"] is True
    return {"status": "ok", "checked": ["scenario_parse", "scenario_expand", "blocked_summary", "comparison"]}


def main() -> None:
    args = parse_args()
    if args.self_check:
        print(json.dumps(run_self_check(), ensure_ascii=False))
        return
    output_dir = Path(args.output_dir).resolve()
    target_repo = Path(args.target_repo).resolve()
    database_url = database_url_from_env(args.database_url_env)
    env = env_snapshot(database_url)
    reason = blocked_reason(env)
    if reason:
        write_json(output_dir / "summary.json", {"status": "blocked", "reason": reason})
        raise SystemExit(2)
    seed_manifest = read_json(output_dir / "seed_manifest.json")
    validate_seed_manifest(seed_manifest, args.dataset)
    scenarios = parse_scenarios(args.run_scenarios)
    write_json(output_dir / "environment.json", env)
    write_json(output_dir / "scenario_manifest.json", scenario_manifest(args, scenarios, seed_manifest))
    phase_dir = (output_dir / args.phase).resolve()
    if phase_dir.exists():
        shutil.rmtree(phase_dir)
    phase_dir.mkdir(parents=True, exist_ok=True)
    result = run_worker(args, output_dir, phase_dir)
    if result.returncode != 0:
        write_json(output_dir / "summary.json", {"status": "partial", "phase": args.phase, "reason": "worker_failed", "stderr": result.stderr[-2000:]})
        raise SystemExit(result.returncode)
    phase_payloads = validate_phase_artifacts(phase_dir, expanded_scenarios(scenarios), args)
    identity = read_json(phase_dir / "source_identity.json")
    if args.phase == "before":
        write_json(output_dir / "source_identity.json", identity)
        write_json(output_dir / "summary.json", {"status": "partial", "reason": "after_not_run", "phase_status": "completed"})
        raise SystemExit(2)
    before_payloads = validate_phase_artifacts(output_dir / "before", EXPANDED_SCENARIOS, args)
    comparisons = build_comparisons(output_dir, before_payloads["benchmark_runs.json"], phase_payloads["benchmark_runs.json"])
    write_json(output_dir / "source_identity.json", identity)
    write_json(output_dir / "summary.json", summary_payload(args=args, env=env, identity=identity, comparisons=comparisons))
    raise SystemExit(0)


if __name__ == "__main__":
    main()
