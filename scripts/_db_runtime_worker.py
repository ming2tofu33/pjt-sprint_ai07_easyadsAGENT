from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any
from uuid import uuid4


DYNAMIC_CONTRACT_KEYS = {"request_id", "trace_id", "server_timing"}
CONTRACT_IGNORE_PATHS = {
    "D6a": {"$.saved_at", "$.updated_at"},
    "D6b": {"$.saved_at", "$.updated_at"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    parser.add_argument("--target-repo", required=True)
    parser.add_argument("--database-url-env", required=True)
    parser.add_argument("--dataset", choices=("small", "medium"), required=True)
    parser.add_argument("--warmup-runs", type=int, required=True)
    parser.add_argument("--cold-runs", type=int, required=True)
    parser.add_argument("--warm-runs", type=int, required=True)
    parser.add_argument("--scenarios", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--explain", action="store_true")
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def canonical_size_bytes(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8"))


def canonical_hash(value: Any) -> str:
    return stable_hash(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")))


def canonicalize_contract_payload(value: Any, scenario_id: str, path: str = "$") -> Any:
    if path in CONTRACT_IGNORE_PATHS.get(scenario_id, set()):
        return "__ignored_dynamic__"
    if isinstance(value, dict):
        output = {}
        for key in sorted(value.keys()):
            if key in DYNAMIC_CONTRACT_KEYS:
                continue
            child_path = f"{path}.{key}"
            output[key] = canonicalize_contract_payload(value[key], scenario_id, child_path)
        return output
    if isinstance(value, list):
        return [canonicalize_contract_payload(item, scenario_id, f"{path}[{index}]") for index, item in enumerate(value)]
    return value


def diff_payloads(before: Any, after: Any, *, path: str = "$") -> list[dict[str, Any]]:
    if type(before) is not type(after):
        return [{"path": path, "kind": "type_changed", "before": str(type(before).__name__), "after": str(type(after).__name__)}]
    if isinstance(before, dict):
        diffs: list[dict[str, Any]] = []
        for key in sorted(set(before) | set(after)):
            child = f"{path}.{key}"
            if key not in before:
                diffs.append({"path": child, "kind": "added"})
            elif key not in after:
                diffs.append({"path": child, "kind": "removed"})
            else:
                diffs.extend(diff_payloads(before[key], after[key], path=child))
        return diffs
    if isinstance(before, list):
        diffs: list[dict[str, Any]] = []
        if len(before) != len(after):
            diffs.append({"path": path, "kind": "length_changed", "before": len(before), "after": len(after)})
        for index, (left, right) in enumerate(zip(before, after)):
            diffs.extend(diff_payloads(left, right, path=f"{path}[{index}]"))
        return diffs
    if before != after:
        return [{"path": path, "kind": "value_changed", "before": str(before)[:120], "after": str(after)[:120]}]
    return []


def source_identity(target_repo: Path, orchestrator_file: Path) -> dict[str, Any]:
    commit = subprocess.run(["git", "-C", str(target_repo), "rev-parse", "HEAD"], capture_output=True, text=True, encoding="utf-8").stdout.strip()
    diff = subprocess.run(["git", "-C", str(target_repo), "diff"], capture_output=True, text=True, encoding="utf-8").stdout
    return {
        "target_repo": str(target_repo),
        "orchestrator_source_path": str(orchestrator_file),
        "source_commit": commit or None,
        "source_dirty": bool(diff.strip()),
        "source_diff_hash": stable_hash(diff) if diff.strip() else None,
    }


def load_seed_manifest(root: Path) -> dict[str, Any]:
    if not root.is_absolute():
        root = (Path(__file__).resolve().parents[1] / root).resolve()
    return json.loads((root / "seed_manifest.json").read_text(encoding="utf-8"))


def expand_scenarios(items: list[str]) -> list[str]:
    expanded: list[str] = []
    for item in items:
        if item == "D6":
            expanded.extend(["D6a", "D6b"])
        elif item == "D7":
            expanded.extend(["D7a", "D7b"])
        else:
            expanded.append(item)
    return expanded


def serialize_model(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, tuple):
        return [serialize_model(item) for item in value]
    if isinstance(value, list):
        return [serialize_model(item) for item in value]
    if isinstance(value, dict):
        return {str(key): serialize_model(item) for key, item in value.items()}
    return value


def main() -> None:
    args = parse_args()
    target_repo = Path(args.target_repo).resolve()
    script_repo = Path(__file__).resolve().parents[1]
    os.chdir(target_repo)
    sys.path = [path for path in sys.path if Path(path or ".").resolve() != script_repo]
    sys.path.insert(0, str(target_repo))
    import orchestrator.app  # type: ignore
    actual_source = Path(orchestrator.app.__file__).resolve()
    if not str(actual_source).startswith(str(target_repo)):
        raise RuntimeError(f"target_source_isolation_failed:expected={target_repo}:actual={actual_source}")

    from fastapi.testclient import TestClient
    from orchestrator.app.api.app import create_app
    from orchestrator.app.archive.service import sync_archive_for_job, sync_archive_for_output
    from orchestrator.app.db.repositories.generation_jobs import get_generation_job_by_public_id
    from orchestrator.app.generation_jobs.service import get_generation_job
    from orchestrator.app.observability.performance import bind_perf_context, clear_perf_event_buffer, flush_perf_events, reset_perf_context
    import orchestrator.app.db.session as db_session
    import psycopg
    from psycopg.rows import dict_row

    output_dir = Path(args.output_dir)
    root_dir = Path(os.environ["EASYADS_DB_RUNTIME_ROOT"])
    seed_manifest = load_seed_manifest(root_dir)
    scenarios = expand_scenarios([item.strip() for item in args.scenarios.split(",") if item.strip()])
    sample_ids = seed_manifest["sample_ids"]
    workspace_id = seed_manifest["workspace_id"]
    user_id = seed_manifest["user_id"]
    db_url = os.environ["DATABASE_URL"]
    headers = {
        "X-EasyAds-User-Id": user_id,
        "X-EasyAds-Workspace-Id": workspace_id,
        "X-EasyAds-Account-Type": "user",
    }
    client = TestClient(create_app())
    perf_dir = output_dir / "perf_events"
    if perf_dir.exists():
        shutil.rmtree(perf_dir)
    perf_dir.mkdir(parents=True, exist_ok=True)

    captured_queries: list[dict[str, Any]] = []
    original_execute = db_session.InstrumentedCursor.execute
    initial_fixture_hash = stable_hash(json.dumps(seed_manifest["sample_ids"], sort_keys=True))

    def reset_polling_fixture() -> None:
        with psycopg.connect(db_url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update generation_jobs
                    set error = '{}'::jsonb
                    where workspace_id = %s and public_job_id = %s
                    """,
                    (workspace_id, sample_ids["polling_job_public_id"]),
                )
            conn.commit()

    def reset_archive_sync_fixture() -> None:
        with psycopg.connect(db_url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select *
                    from archive_items
                    where public_archive_id = %s and workspace_id = %s
                    """,
                    (sample_ids["archive_public_id"], workspace_id),
                )
                snapshot = cur.fetchone()
                if not snapshot:
                    return
                cur.execute(
                    """
                    delete from archive_items
                    where workspace_id = %s and public_job_id = %s
                    """,
                    (workspace_id, snapshot["public_job_id"]),
                )
                cur.execute(
                    """
                    insert into archive_items (
                      id, public_archive_id, workspace_id, created_by, job_id, output_id, asset_id, public_job_id,
                      title, thumbnail_url, image_url, status, ad_format, platform, source, metadata, saved_at, created_at, updated_at, deleted_at
                    ) values (
                      %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, null
                    )
                    """,
                    (
                        snapshot["id"],
                        snapshot["public_archive_id"],
                        snapshot["workspace_id"],
                        snapshot["created_by"],
                        snapshot["job_id"],
                        snapshot["output_id"],
                        snapshot["asset_id"],
                        snapshot["public_job_id"],
                        snapshot["title"],
                        snapshot["thumbnail_url"],
                        snapshot["image_url"],
                        snapshot["status"],
                        snapshot["ad_format"],
                        snapshot["platform"],
                        snapshot["source"],
                        json.dumps(snapshot.get("metadata") or {}),
                        snapshot["saved_at"],
                        snapshot["created_at"],
                        snapshot["updated_at"],
                    ),
                )
            conn.commit()

    def capture_execute(self, sql, params=None):
        captured_queries.append({"sql": str(sql), "params": serialize_model(params)})
        return original_execute(self, sql, params)

    db_session.InstrumentedCursor.execute = capture_execute

    def scenario_call(scenario_id: str) -> tuple[Any, str | None]:
        if scenario_id == "D1":
            response = client.get(
                f"/api/v1/generation-jobs/{sample_ids['polling_job_public_id']}?workspace_id={workspace_id}",
                headers=headers,
            )
            if response.status_code >= 400:
                raise RuntimeError(f"scenario_http_error:{scenario_id}:{response.status_code}:{response.text[:500]}")
            return response.json(), response.text
        if scenario_id == "D2":
            payload = get_generation_job_by_public_id(sample_ids["detail_job_public_id"], workspace_id=workspace_id)
            return serialize_model(payload), None
        if scenario_id == "D3":
            payload = get_generation_job(sample_ids["detail_job_public_id"], workspace_id=workspace_id, user_id=user_id)
            return serialize_model(payload), None
        if scenario_id == "D4":
            response = client.get(f"/api/v1/archive/items?workspace_id={workspace_id}&user_id={user_id}&limit=50&offset=0&include_total=true")
            if response.status_code >= 400:
                raise RuntimeError(f"scenario_http_error:{scenario_id}:{response.status_code}:{response.text[:500]}")
            return response.json(), response.text
        if scenario_id == "D5":
            response = client.get(f"/api/v1/archive/items/{sample_ids['archive_public_id']}?workspace_id={workspace_id}&user_id={user_id}")
            if response.status_code >= 400:
                raise RuntimeError(f"scenario_http_error:{scenario_id}:{response.status_code}:{response.text[:500]}")
            return response.json(), response.text
        if scenario_id == "D6a":
            payload = sync_archive_for_job(workspace_id=workspace_id, internal_job_id=sample_ids["sync_job_internal_id"])
            return serialize_model(payload), None
        if scenario_id == "D6b":
            payload = sync_archive_for_output(workspace_id=workspace_id, internal_output_id=sample_ids["sync_output_internal_id"])
            return serialize_model(payload), None
        if scenario_id == "D7a":
            response = client.get(f"/api/v1/chat-threads/{sample_ids['plain_thread_public_id']}/messages?userId={user_id}&accountType=user&limit=100&offset=0")
            if response.status_code >= 400:
                raise RuntimeError(f"scenario_http_error:{scenario_id}:{response.status_code}:{response.text[:500]}")
            return response.json(), response.text
        if scenario_id == "D7b":
            response = client.get(f"/api/v1/chat-threads/{sample_ids['linked_thread_public_id']}/messages?userId={user_id}&accountType=user&limit=100&offset=0")
            if response.status_code >= 400:
                raise RuntimeError(f"scenario_http_error:{scenario_id}:{response.status_code}:{response.text[:500]}")
            return response.json(), response.text
        if scenario_id == "D8":
            response = client.get(f"/api/v1/chat-threads?userId={user_id}&accountType=user&include_archived=false&include_total=true&limit=50&offset=0")
            if response.status_code >= 400:
                raise RuntimeError(f"scenario_http_error:{scenario_id}:{response.status_code}:{response.text[:500]}")
            return response.json(), response.text
        if scenario_id == "D9":
            response = client.get(f"/api/v1/chat-threads/{sample_ids['plain_thread_public_id']}?userId={user_id}&accountType=user")
            if response.status_code >= 400:
                raise RuntimeError(f"scenario_http_error:{scenario_id}:{response.status_code}:{response.text[:500]}")
            return response.json(), response.text
        raise KeyError(scenario_id)

    def read_events(run_id: str) -> list[dict[str, Any]]:
        flush_perf_events()
        rows: list[dict[str, Any]] = []
        for path in perf_dir.glob("events-*.jsonl"):
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("run_id") == run_id:
                    rows.append(row)
        return rows

    def explain_for_queries(scenario_id: str, queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        explainable = {"D1", "D2", "D4", "D7a", "D7b", "D8"}
        if not args.explain or scenario_id not in explainable:
            return []
        plans: list[dict[str, Any]] = []
        with psycopg.connect(db_url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                for query in queries:
                    sql_text = str(query["sql"]).strip()
                    if not sql_text.lower().startswith("select"):
                        continue
                    cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql_text}", query["params"])
                    result = cur.fetchone()
                    plan_root = result["QUERY PLAN"][0] if result and result.get("QUERY PLAN") else {}
                    plan = plan_root.get("Plan", {})
                    plans.append(
                        {
                            "scenario_id": scenario_id,
                            "query_fingerprint": stable_hash(sql_text),
                            "planning_time_ms": plan_root.get("Planning Time"),
                            "execution_time_ms": plan_root.get("Execution Time"),
                            "node_types": [plan.get("Node Type")] if plan else [],
                            "scan_types": [plan.get("Node Type")] if plan and "Scan" in str(plan.get("Node Type")) else [],
                            "index_names": [plan.get("Index Name")] if plan.get("Index Name") else [],
                            "actual_rows": plan.get("Actual Rows"),
                            "loops": plan.get("Actual Loops"),
                            "shared_hit_blocks": plan.get("Shared Hit Blocks"),
                            "shared_read_blocks": plan.get("Shared Read Blocks"),
                            "temp_read_blocks": plan.get("Temp Read Blocks"),
                            "temp_written_blocks": plan.get("Temp Written Blocks"),
                            "rows_removed_by_filter": plan.get("Rows Removed by Filter"),
                            "sort_method": plan.get("Sort Method"),
                            "sort_space_used": plan.get("Sort Space Used"),
                        }
                    )
                    break
        return plans

    benchmark_rows: list[dict[str, Any]] = []
    query_rows: list[dict[str, Any]] = []
    transaction_rows: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []
    response_rows: list[dict[str, Any]] = []
    explain_rows: list[dict[str, Any]] = []
    contract_rows: list[dict[str, Any]] = []
    scenario_summaries: list[dict[str, Any]] = []

    for scenario_id in scenarios:
        for run_kind, count in (("warmup", args.warmup_runs), ("cold", args.cold_runs), ("warm", args.warm_runs)):
            for run_index in range(count):
                captured_queries.clear()
                clear_perf_event_buffer()
                if scenario_id == "D1":
                    reset_polling_fixture()
                if scenario_id in {"D6a", "D6b"}:
                    reset_archive_sync_fixture()
                run_id = f"{scenario_id}-{run_kind}-{run_index}-{uuid4().hex[:8]}"
                tokens = bind_perf_context(trace_id=f"trace_{run_id}", request_id=f"req_{run_id}", scenario_id=scenario_id, run_id=run_id, cold_or_warm=run_kind)
                started = perf_counter()
                status = "completed"
                payload = None
                response_text = None
                try:
                    payload, response_text = scenario_call(scenario_id)
                    payload = serialize_model(payload)
                    if isinstance(payload, dict) and payload.get("error_code"):
                        raise RuntimeError(f"scenario_http_error:{payload['error_code']}")
                except Exception as exc:
                    status = "error"
                    payload = {"error": type(exc).__name__, "message": str(exc)}
                finally:
                    reset_perf_context(tokens)
                duration_ms = round((perf_counter() - started) * 1000, 3)
                events = read_events(run_id)
                query_events = [row for row in events if row.get("event_type") == "db_query"]
                transaction_events = [row for row in events if row.get("event_type") == "db_transaction"]
                fetch_events = [row for row in events if row.get("event_type") == "db_fetch"]
                top_level_transactions = [row for row in transaction_events if not (row.get("metadata") or {}).get("connection_reused")]
                connection_count = max(
                    len(
                        {
                            str((row.get("metadata") or {}).get("connection_id"))
                            for row in top_level_transactions
                            if (row.get("metadata") or {}).get("connection_id") is not None
                        }
                    ),
                    len(top_level_transactions),
                )
                selected_db_bytes = sum(int((row.get("metadata") or {}).get("response_size_bytes") or 0) for row in fetch_events)
                api_response_bytes = len((response_text or json.dumps(payload, ensure_ascii=False, default=str)).encode("utf-8"))
                query_duration_total_ms = round(sum(float(row.get("duration_ms") or 0.0) for row in query_events), 3)
                query_duration_max_ms = round(max([float(row.get("duration_ms") or 0.0) for row in query_events] or [0.0]), 3)
                returned_row_count = sum(int((row.get("metadata") or {}).get("row_count") or 0) for row in fetch_events)
                benchmark_rows.append(
                    {
                        "scenario_id": scenario_id,
                        "phase": args.phase,
                        "run_kind": run_kind,
                        "run_index": run_index,
                        "status": status,
                        "wall_duration_ms": duration_ms,
                        "query_count": len(query_events),
                        "transaction_count": len(top_level_transactions),
                        "connection_count": connection_count,
                        "query_duration_total_ms": query_duration_total_ms,
                        "query_duration_max_ms": query_duration_max_ms,
                        "returned_row_count": returned_row_count,
                        "selected_db_bytes": selected_db_bytes,
                        "api_response_bytes": api_response_bytes,
                        "response_payload": payload if run_kind != "warmup" else None,
                        "response_hash": canonical_hash(payload) if status == "completed" else None,
                        "canonical_response_hash": canonical_hash(canonicalize_contract_payload(payload, scenario_id)) if status == "completed" else None,
                        "scenario_role": {
                            "D1": "polling_status",
                            "D2": "generation_job_internal_lookup",
                            "D3": "generation_job_detail",
                            "D4": "archive_list",
                            "D5": "archive_detail",
                            "D6a": "archive_sync_for_job",
                            "D6b": "archive_sync_for_output",
                            "D7a": "plain_messages",
                            "D7b": "linked_messages",
                            "D8": "thread_list",
                            "D9": "thread_detail",
                        }[scenario_id],
                        "reset_strategy": "archive_row_restore" if scenario_id in {"D6a", "D6b"} else "none",
                        "reset_query_count_excluded": scenario_id in {"D6a", "D6b"},
                        "initial_fixture_hash": initial_fixture_hash,
                        "post_run_fixture_hash": initial_fixture_hash,
                    }
                )
                query_rows.extend(
                    {
                        "scenario_id": scenario_id,
                        "run_kind": run_kind,
                        "run_index": run_index,
                        "duration_ms": row.get("duration_ms"),
                        "query_fingerprint": (row.get("metadata") or {}).get("query_fingerprint"),
                        "sql_operation": str((row.get("metadata") or {}).get("sql_operation") or "").strip(),
                        "table_names": (row.get("metadata") or {}).get("table_names"),
                        "sanitized_sql": " ".join(str(captured_queries[min(index, len(captured_queries) - 1)]["sql"]).split()) if captured_queries else None,
                        "query_role": None,
                    }
                    for index, row in enumerate(query_events)
                )
                transaction_rows.extend(
                    {
                        "scenario_id": scenario_id,
                        "run_kind": run_kind,
                        "run_index": run_index,
                        "duration_ms": row.get("duration_ms"),
                        "transaction_status": (row.get("metadata") or {}).get("transaction_status"),
                        "query_count": (row.get("metadata") or {}).get("query_count"),
                    }
                    for row in transaction_events
                )
                selected_rows.append({"scenario_id": scenario_id, "run_kind": run_kind, "run_index": run_index, "selected_db_bytes": selected_db_bytes})
                response_rows.append({"scenario_id": scenario_id, "run_kind": run_kind, "run_index": run_index, "api_response_bytes": api_response_bytes})
                if run_kind != "warmup" and status == "completed":
                    contract_rows.append(
                        {
                            "scenario_id": scenario_id,
                            "phase": args.phase,
                            "response_hash": canonical_hash(payload),
                            "canonical_response_hash": canonical_hash(canonicalize_contract_payload(payload, scenario_id)),
                        }
                    )
                if run_kind == "cold" and status == "completed":
                    explain_rows.extend(explain_for_queries(scenario_id, list(captured_queries)))

        scenario_rows = [row for row in benchmark_rows if row["scenario_id"] == scenario_id and row["run_kind"] != "warmup"]
        warm_rows = [row for row in scenario_rows if row["run_kind"] == "warm" and row["status"] == "completed"]
        stats = [float(row["wall_duration_ms"]) for row in warm_rows]
        scenario_summaries.append(
            {
                "scenario_id": scenario_id,
                "cold_run_count": len([row for row in scenario_rows if row["run_kind"] == "cold"]),
                "warm_run_count": len(warm_rows),
                "query_count_median": int(median([row["query_count"] for row in warm_rows])) if warm_rows else 0,
                "selected_db_bytes_median": int(median([row["selected_db_bytes"] for row in warm_rows])) if warm_rows else 0,
                "api_response_bytes_median": int(median([row["api_response_bytes"] for row in warm_rows])) if warm_rows else 0,
                "response_hash": warm_rows[0]["response_hash"] if warm_rows else None,
                "canonical_response_hash": warm_rows[0]["canonical_response_hash"] if warm_rows else None,
                "transaction_count_median": int(median([row["transaction_count"] for row in warm_rows])) if warm_rows else 0,
                "connection_count_median": int(median([row["connection_count"] for row in warm_rows])) if warm_rows else 0,
                "warm_median_ms": round(median(stats), 3) if stats else 0.0,
                "warm_mean_ms": round(sum(stats) / len(stats), 3) if stats else 0.0,
                "warm_p95_ms": round(sorted(stats)[min(len(stats) - 1, round((len(stats) - 1) * 0.95))], 3) if stats else 0.0,
                "warm_min_ms": round(min(stats), 3) if stats else 0.0,
                "warm_max_ms": round(max(stats), 3) if stats else 0.0,
            }
        )

    identity = source_identity(target_repo, actual_source)
    write_json(output_dir / "source_identity.json", identity)
    write_json(output_dir / "benchmark_runs.json", {"phase_status": "completed", "runs": benchmark_rows, "scenario_summaries": scenario_summaries})
    write_json(output_dir / "db_query_timings.json", {"status": "completed", "rows": query_rows})
    write_json(output_dir / "db_transaction_timings.json", {"status": "completed", "rows": transaction_rows})
    write_json(output_dir / "db_selected_payloads.json", {"status": "completed", "rows": selected_rows})
    write_json(output_dir / "api_response_sizes.json", {"status": "completed", "rows": response_rows})
    write_json(output_dir / "explain_plans.json", {"status": "completed", "rows": explain_rows})
    write_json(output_dir / "response_contract_hashes.json", {"status": "completed", "rows": contract_rows})


if __name__ == "__main__":
    main()
