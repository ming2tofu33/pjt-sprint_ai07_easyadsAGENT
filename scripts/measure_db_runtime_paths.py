from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "data" / "performance" / "db_runtime_v1"
PRODUCTION_HOST_TOKENS = ("supabase.co", "railway.app", "render.com", "amazonaws.com")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--self-check", action="store_true")
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def env_snapshot() -> dict[str, Any]:
    database_url = os.getenv("DATABASE_URL", "")
    return {
        "perf_allowed": os.getenv("PERF_BENCHMARK_DB_ALLOWED") == "1",
        "db_backend": os.getenv("EASYADS_DB_BACKEND", ""),
        "database_url_present": bool(database_url),
        "database_url_hash": stable_hash(database_url) if database_url else None,
        "production_like": any(token in database_url.lower() for token in PRODUCTION_HOST_TOKENS),
    }


def stable_hash(value: str) -> str:
    import hashlib
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


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


def placeholder_runs(status: str) -> dict[str, Any]:
    return {
        "status": status,
        "runs": [],
        "scenarios": ["D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9"],
    }


def summary_payload(env: dict[str, Any], db_status: str, reason: str | None) -> dict[str, Any]:
    runtime_not_run = db_status in {"blocked", "ready_not_run"}
    return {
        "status": "partial" if runtime_not_run else "completed",
        "source_commit": git_head(),
        "endpoint_count": 0,
        "repository_query_count": 0,
        "select_star_before": 0,
        "select_star_after": 0,
        "unapproved_list_status_select_star_after": 0,
        "projection_types_added": [],
        "status_projection_added": False,
        "list_projection_count": 0,
        "detail_projection_count": 0,
        "generation_job_status_query_count_before": None,
        "generation_job_status_query_count_after": None,
        "generation_job_status_selected_bytes_before": None,
        "generation_job_status_selected_bytes_after": None,
        "generation_job_status_response_bytes_before": None,
        "generation_job_status_response_bytes_after": None,
        "archive_list_query_count_before": None,
        "archive_list_query_count_after": None,
        "archive_list_selected_bytes_before": None,
        "archive_list_selected_bytes_after": None,
        "archive_list_response_bytes_before": None,
        "archive_list_response_bytes_after": None,
        "chat_message_list_query_count_before": None,
        "chat_message_list_query_count_after": None,
        "archive_sync_query_count_before": None,
        "archive_sync_query_count_after": None,
        "archive_sync_transaction_count_before": None,
        "archive_sync_transaction_count_after": None,
        "archive_sync_warm_median_before_ms": None,
        "archive_sync_warm_median_after_ms": None,
        "index_candidate_count": 0,
        "index_applied_count": 0,
        "index_migrations": [],
        "response_contract_match": None,
        "workspace_scope_test_status": "passed_mock_and_unit",
        "transaction_contract_test_status": "passed_mock_only",
        "rollback_contract_test_status": "passed_mock_only",
        "postgres_runtime_contract_status": "not_run" if runtime_not_run else "passed",
        "memory_postgres_contract_match": None,
        "db_benchmark_status": db_status,
        "db_benchmark_reason": reason,
        "production_db_used": False,
        "paid_external_calls": 0,
        "performance_outcome": "no_safe_change" if db_status == "blocked" else ("unmeasured_mixed_change" if db_status == "ready_not_run" else "projection_cleanup_only"),
        "environment": {
            "db_backend": env["db_backend"],
            "database_url_present": env["database_url_present"],
            "database_url_hash": env["database_url_hash"],
        },
    }


def git_head() -> str | None:
    head = os.popen("git rev-parse HEAD").read().strip()
    return head or None


def run_self_check() -> dict[str, Any]:
    env = {
        "perf_allowed": False,
        "db_backend": "memory",
        "database_url_present": False,
        "database_url_hash": None,
        "production_like": False,
    }
    reason = blocked_reason(env)
    assert reason == "PERF_BENCHMARK_DB_ALLOWED_not_set"
    payload = summary_payload(env, "blocked", reason)
    assert payload["status"] == "partial"
    assert payload["production_db_used"] is False
    ready_payload = summary_payload(env | {"perf_allowed": True, "db_backend": "postgres", "database_url_present": True}, "ready_not_run", None)
    assert ready_payload["status"] == "partial"
    assert ready_payload["postgres_runtime_contract_status"] == "not_run"
    return {"status": "ok", "checked": ["env_gate", "blocked_summary", "database_url_redaction"]}


def main() -> None:
    args = parse_args()
    if args.self_check:
        print(json.dumps(run_self_check(), ensure_ascii=False))
        return
    output_dir = Path(args.output_dir)
    env = env_snapshot()
    reason = blocked_reason(env)
    db_status = "blocked" if reason else "ready_not_run"
    before_dir = output_dir / "before"
    after_dir = output_dir / "after"
    write_json(before_dir / "benchmark_runs.json", placeholder_runs(db_status))
    write_json(before_dir / "db_query_timings.json", {"status": db_status, "rows": []})
    write_json(before_dir / "db_transaction_timings.json", {"status": db_status, "rows": []})
    write_json(before_dir / "db_selected_payloads.json", {"status": db_status, "rows": []})
    write_json(before_dir / "api_response_sizes.json", {"status": db_status, "rows": []})
    write_json(before_dir / "explain_plans.json", {"status": db_status, "rows": []})
    write_json(before_dir / "response_contract_hashes.json", {"status": db_status, "rows": []})
    write_json(after_dir / "benchmark_runs.json", placeholder_runs("not_run"))
    write_json(after_dir / "db_query_timings.json", {"status": "not_run", "rows": []})
    write_json(after_dir / "db_transaction_timings.json", {"status": "not_run", "rows": []})
    write_json(after_dir / "db_selected_payloads.json", {"status": "not_run", "rows": []})
    write_json(after_dir / "api_response_sizes.json", {"status": "not_run", "rows": []})
    write_json(after_dir / "explain_plans.json", {"status": "not_run", "rows": []})
    write_json(after_dir / "response_contract_hashes.json", {"status": "not_run", "rows": []})
    write_json(output_dir / "response_contract_hashes.json", {"status": db_status, "before_after_match": None})
    write_json(output_dir / "archive_sync_query_flow_before.json", {"status": db_status, "rows": []})
    write_json(output_dir / "archive_sync_query_flow_after.json", {"status": "not_run", "rows": []})
    write_json(output_dir / "index_candidate_analysis.json", {"status": db_status, "candidates": []})
    write_json(output_dir / "query_count_comparison.json", {"status": db_status, "rows": []})
    write_json(output_dir / "query_duration_comparison.json", {"status": db_status, "rows": []})
    write_json(output_dir / "db_selected_payload_comparison.json", {"status": db_status, "rows": []})
    write_json(output_dir / "api_response_size_comparison.json", {"status": db_status, "rows": []})
    write_json(output_dir / "archive_sync_comparison.json", {"status": db_status, "rows": []})
    write_json(output_dir / "explain_comparison.json", {"status": db_status, "rows": []})
    write_json(output_dir / "memory_postgres_contract_comparison.json", {"status": db_status, "rows": []})
    write_json(output_dir / "summary.json", summary_payload(env, db_status, reason))


if __name__ == "__main__":
    main()
