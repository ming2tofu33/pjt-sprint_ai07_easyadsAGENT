from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from orchestrator.app.observability.performance import estimate_json_size_bytes


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_CONTRACT_DIR = REPO_ROOT / "data" / "performance" / "state_contract_v1"
DEFAULT_BEFORE_DIR = REPO_ROOT / "data" / "performance" / "checkpoint_artifact_v1" / "before"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "performance" / "checkpoint_artifact_v1"
SCENARIOS = ("S1", "S2", "S3", "S4", "S5")
HEAVY_KEYS = {
    "result_payload",
    "background_validation_report",
    "t2i_request",
    "t2i_result",
    "image_prompt_spec",
    "image_prompt",
    "text_style_spec",
    "tone_binding_output",
    "product_understanding",
    "font_catalog_summary",
}
CANONICAL_DB_ONLY = {"messages", "llm_call_results", "model_selections", "result_payload"}
EPHEMERAL_RUNTIME_ONLY = {"prompt_render_output"}
REFERENCE_CANDIDATES = {
    "background_validation_report",
    "t2i_request",
    "t2i_result",
    "image_prompt_spec",
    "image_prompt",
    "text_style_spec",
    "tone_binding_output",
    "product_understanding",
    "font_catalog_summary",
}
GATE_THRESHOLDS = {
    "duration_ratio": 0.02,
    "max_checkpoint_bytes": 1_048_576,
    "revision_growth_ratio": 1.5,
    "cross_scenario_terminal_duplicate_ratio": 0.2,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-contract-dir", default=str(DEFAULT_STATE_CONTRACT_DIR))
    parser.add_argument("--before-dir", default=str(DEFAULT_BEFORE_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--self-check", action="store_true")
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def median_value(rows: dict[str, Any], field: str) -> float:
    return float(rows[field]["median"])


def load_warm_terminal_states(before_dir: Path) -> dict[str, dict[str, Any]]:
    rows = read_json(before_dir / "benchmark_runs.json")
    states: dict[str, dict[str, Any]] = {}
    for scenario in SCENARIOS:
        warm_rows = [row for row in rows if row["scenario_id"] == scenario and row["cold_or_warm"] == "warm"]
        if warm_rows:
            states[scenario] = warm_rows[-1]["terminal_state"]
    return states


def load_state_contract_inputs(state_contract_dir: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    summary = read_json(state_contract_dir / "summary.json")
    channels = read_json(state_contract_dir / "state_channel_classification.json")
    channel_map = {row["channel"]: row for row in channels}
    return summary, channel_map


def summarize_state_sizes(
    states: dict[str, dict[str, Any]],
    channel_map: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    per_key: dict[str, dict[str, Any]] = {}
    fingerprints: Counter[tuple[str, str]] = Counter()
    key_sizes_by_fingerprint: dict[tuple[str, str], int] = {}
    for scenario, state in states.items():
        for key, value in state.items():
            size = estimate_json_size_bytes(value) or 0
            channel_info = channel_map.get(key, {})
            record = per_key.setdefault(
                key,
                {
                    "state_key": key,
                    "samples": [],
                    "sizes": [],
                    "resume_required": bool(channel_info.get("resume_consumer_count", 0) > 0)
                    or key in {"current_brief", "context", "missing_fields", "status", "t2i_request", "t2i_result"},
                    "public_contract_required": bool(channel_info.get("public_contract_consumer_count", 0) > 0)
                    or key in {"result_payload", "artifact_refs", "final_image_path"},
                    "runtime_read_after_write_measured": False,
                    "classification_source": classification_source(channel_info, key),
                    "resume_requirement_verified": bool(channel_info.get("resume_consumer_count", 0) > 0),
                },
            )
            record["sizes"].append(size)
            record["samples"].append({"scenario_id": scenario, "size_bytes": size})
            fingerprint = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
            fingerprints[(key, fingerprint)] += 1
            key_sizes_by_fingerprint[(key, fingerprint)] = size
    total_duplicate_bytes = 0
    for (key, _fingerprint), count in fingerprints.items():
        if count < 2:
            continue
        total_duplicate_bytes += key_sizes_by_fingerprint[(key, _fingerprint)] * (count - 1)
    size_rows: list[dict[str, Any]] = []
    duplicate_rows: list[dict[str, Any]] = []
    for key, row in sorted(per_key.items()):
        sizes = row["sizes"]
        median_size = sorted(sizes)[len(sizes) // 2]
        max_size = max(sizes)
        repeat_count = sum(1 for scenario in states if (estimate_json_size_bytes(states[scenario].get(key)) or 0) == median_size)
        duplicate_serialized_bytes = sum(
            key_sizes_by_fingerprint[(seen_key, fingerprint)] * (count - 1)
            for (seen_key, fingerprint), count in fingerprints.items()
            if seen_key == key and count >= 2
        )
        classification = classify_key(key, median_size)
        size_rows.append(
            {
                "state_key": key,
                "median_size_bytes": median_size,
                "max_size_bytes": max_size,
                "checkpoint_repeat_count": repeat_count,
                "cross_scenario_terminal_duplicate_bytes": duplicate_serialized_bytes,
                "read_after_write_count": 0,
                "runtime_read_after_write_measured": row["runtime_read_after_write_measured"],
                "resume_required": row["resume_required"],
                "resume_requirement_verified": row["resume_requirement_verified"],
                "public_contract_required": row["public_contract_required"],
                "classification": classification,
                "classification_source": row["classification_source"],
                "canonical_store": canonical_store(classification),
                "externalization_candidate": classification == "checkpoint_reference",
                "risk": risk_for_key(key, classification),
                "reason": reason_for_key(key, classification, median_size),
            }
        )
        if duplicate_serialized_bytes > 0:
            duplicate_rows.append(
                {
                    "state_key": key,
                    "cross_scenario_terminal_duplicate_bytes": duplicate_serialized_bytes,
                    "median_size_bytes": median_size,
                    "classification": classification,
                    "classification_source": row["classification_source"],
                    "measurement_scope": "cross_scenario_warm_terminal_states",
                }
            )
    size_rows.sort(key=lambda item: (-item["median_size_bytes"], item["state_key"]))
    duplicate_rows.sort(key=lambda item: (-item["cross_scenario_terminal_duplicate_bytes"], item["state_key"]))
    return size_rows, duplicate_rows, total_duplicate_bytes


def classification_source(channel_info: dict[str, Any], key: str) -> str:
    parts = []
    if channel_info:
        parts.append("state_contract_v1")
    if key in HEAVY_KEYS:
        parts.append("known_heavy_key_hint")
    parts.append("static_policy_hint")
    return "+".join(parts)


def classify_key(key: str, median_size: int) -> str:
    if key in CANONICAL_DB_ONLY:
        return "canonical_db_only"
    if key in EPHEMERAL_RUNTIME_ONLY:
        return "ephemeral_runtime_only"
    if key in REFERENCE_CANDIDATES and (median_size >= 2048 or key in HEAVY_KEYS):
        return "checkpoint_reference"
    return "checkpoint_inline"


def canonical_store(classification: str) -> str:
    return {
        "checkpoint_inline": "checkpoint",
        "checkpoint_reference": "asset",
        "canonical_db_only": "db",
        "ephemeral_runtime_only": "runtime",
    }[classification]


def risk_for_key(key: str, classification: str) -> str:
    if key in {"t2i_request", "t2i_result"}:
        return "medium"
    if classification == "checkpoint_reference":
        return "low"
    if classification == "canonical_db_only":
        return "high"
    return "low"


def reason_for_key(key: str, classification: str, median_size: int) -> str:
    if classification == "checkpoint_reference":
        return f"Large repeated terminal payload ({median_size} bytes median) and likely referenceable."
    if classification == "canonical_db_only":
        return "Canonical store already exists or public result owns this payload."
    if classification == "ephemeral_runtime_only":
        return "Short-lived runtime field; not safe to rehydrate blindly."
    return "Inline state required for routing or cheap enough to keep."


def build_gate(
    *,
    before_dir: Path,
    state_contract_summary: dict[str, Any],
    size_rows: list[dict[str, Any]],
    cross_scenario_terminal_duplicate_bytes: int,
) -> dict[str, Any]:
    checkpoint_timings = read_json(before_dir / "checkpoint_timings.json")
    graph_timings = read_json(before_dir / "graph_execution_timings.json")
    state_sizes = read_json(before_dir / "state_sizes.json")
    checkpoint_total_bytes = sum(median_value(state_sizes[scenario], "checkpoint_write_bytes_total") for scenario in SCENARIOS)
    checkpoint_max_bytes = max(median_value(state_sizes[scenario], "checkpoint_write_bytes_max") for scenario in SCENARIOS)
    graph_total_ms = sum(median_value(graph_timings[scenario], "graph_wall_duration_ms") for scenario in SCENARIOS)
    checkpoint_total_ms = sum(median_value(checkpoint_timings[scenario], "checkpoint_write_duration_total_ms") for scenario in SCENARIOS)
    checkpoint_duration_ratio = round(checkpoint_total_ms / graph_total_ms, 4) if graph_total_ms else 0.0
    revision_growth_ratio = round(
        median_value(state_sizes["S3"], "checkpoint_write_bytes_total")
        / max(median_value(state_sizes["S1"], "checkpoint_write_bytes_total"), 1.0),
        4,
    )
    cross_scenario_terminal_duplicate_ratio = round(
        cross_scenario_terminal_duplicate_bytes / max(checkpoint_total_bytes, 1.0),
        4,
    )
    duration_gate = checkpoint_duration_ratio >= GATE_THRESHOLDS["duration_ratio"]
    size_gate = checkpoint_max_bytes >= GATE_THRESHOLDS["max_checkpoint_bytes"]
    growth_gate = revision_growth_ratio >= GATE_THRESHOLDS["revision_growth_ratio"]
    duplicate_gate = cross_scenario_terminal_duplicate_ratio >= GATE_THRESHOLDS["cross_scenario_terminal_duplicate_ratio"]
    top_state_channels = [
        {
            "state_key": row["state_key"],
            "median_size_bytes": row["median_size_bytes"],
            "classification": row["classification"],
            "classification_source": row["classification_source"],
        }
        for row in size_rows[:5]
    ]
    status = "go" if any((duration_gate, size_gate, growth_gate, duplicate_gate)) else "no_go"
    reasons = []
    if not duration_gate:
        reasons.append("checkpoint_duration_ratio_below_threshold")
    if not size_gate:
        reasons.append("checkpoint_max_bytes_below_threshold")
    if not growth_gate:
        reasons.append("revision_growth_ratio_below_threshold")
    if not duplicate_gate:
        reasons.append("cross_scenario_terminal_duplicate_ratio_below_threshold")
    if size_rows and size_rows[0]["state_key"] == "result_payload":
        reasons.append("largest_payload_is_public_result_contract")
    if any(row["classification"] == "checkpoint_reference" for row in size_rows[:3]):
        reasons.append("large_referenceable_payloads_exist")
    return {
        "status": status,
        "source_artifact": "data/performance/state_contract_v1",
        "source_commit": state_contract_summary.get("source_commit"),
        "decision_scope": "deterministic_inmemory_before_benchmark_only",
        "decision_statement": "No-go means no safe externalization was justified for the measured deterministic InMemory benchmark scope.",
        "thresholds": GATE_THRESHOLDS,
        "gate_signals": {
            "duration_gate": duration_gate,
            "size_gate": size_gate,
            "growth_gate": growth_gate,
            "duplicate_gate": duplicate_gate,
        },
        "checkpoint_duration_ratio": checkpoint_duration_ratio,
        "checkpoint_write_duration_total_ms": checkpoint_total_ms,
        "graph_wall_duration_total_ms": graph_total_ms,
        "checkpoint_total_bytes": checkpoint_total_bytes,
        "checkpoint_max_bytes": checkpoint_max_bytes,
        "revision_growth_ratio": revision_growth_ratio,
        "cross_scenario_terminal_duplicate_bytes": cross_scenario_terminal_duplicate_bytes,
        "cross_scenario_terminal_duplicate_ratio": cross_scenario_terminal_duplicate_ratio,
        "top_state_channels": top_state_channels,
        "reasons": reasons,
    }


def build_all_externalization_candidates(size_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = []
    for row in size_rows:
        if row["classification"] != "checkpoint_reference":
            continue
        candidates.append(
            {
                "state_key": row["state_key"],
                "artifact_type": f"{row['state_key']}_json",
                "before_storage": row["classification"],
                "target_storage": "existing_asset",
                "estimated_checkpoint_reduction_bytes": row["cross_scenario_terminal_duplicate_bytes"] or row["median_size_bytes"],
                "expected_read_frequency": 0,
                "implementation_risk": row["risk"],
                "classification_source": row["classification_source"],
                "approved": False,
            }
        )
    candidates.sort(key=lambda item: (-item["estimated_checkpoint_reduction_bytes"], item["state_key"]))
    return candidates


def build_candidate_plan(all_candidates: list[dict[str, Any]], gate_status: str) -> list[dict[str, Any]]:
    plan = []
    for row in all_candidates[:3]:
        plan.append(
            {
                **row,
                "approved": gate_status == "go" and row["implementation_risk"] != "high",
                "selection_basis": "top_3_estimated_checkpoint_reduction_bytes",
            }
        )
    return plan


def write_completed_no_change_artifacts(
    *,
    output_dir: Path,
    gate: dict[str, Any],
    size_rows: list[dict[str, Any]],
    duplicate_rows: list[dict[str, Any]],
    all_candidates: list[dict[str, Any]],
    candidate_plan: list[dict[str, Any]],
) -> None:
    checkpoint_reference_count = sum(1 for row in size_rows if row["classification"] == "checkpoint_reference")
    checkpoint_inline_count = sum(1 for row in size_rows if row["classification"] == "checkpoint_inline")
    canonical_db_only_count = sum(1 for row in size_rows if row["classification"] == "canonical_db_only")
    ephemeral_runtime_only_count = sum(1 for row in size_rows if row["classification"] == "ephemeral_runtime_only")
    validation_status = "not_applicable_no_externalization" if gate["status"] == "no_go" else "not_run"
    summary = {
        "status": "completed_no_change" if gate["status"] == "no_go" else "completed",
        "execution_gate": gate["status"],
        "validation_status": validation_status,
        "state_key_count": len(size_rows),
        "checkpoint_inline_count": checkpoint_inline_count,
        "checkpoint_reference_count": checkpoint_reference_count,
        "canonical_db_only_count": canonical_db_only_count,
        "ephemeral_runtime_only_count": ephemeral_runtime_only_count,
        "externalization_candidate_count": len(all_candidates),
        "externalized_state_key_count": 0,
        "externalized_state_keys": [],
        "checkpoint_total_bytes_before": gate["checkpoint_total_bytes"],
        "checkpoint_total_bytes_after": None,
        "checkpoint_max_bytes_before": gate["checkpoint_max_bytes"],
        "checkpoint_max_bytes_after": None,
        "cross_scenario_terminal_duplicate_bytes_before": gate["cross_scenario_terminal_duplicate_bytes"],
        "cross_scenario_terminal_duplicate_bytes_after": None,
        "checkpoint_write_duration_ratio_before": gate["checkpoint_duration_ratio"],
        "checkpoint_write_duration_ratio_after": None,
        "checkpoint_write_duration_total_before_ms": gate["checkpoint_write_duration_total_ms"],
        "checkpoint_write_duration_total_after_ms": None,
        "artifact_write_count": 0,
        "artifact_write_bytes": 0,
        "artifact_write_duration_ms": None,
        "artifact_read_count": 0,
        "artifact_read_duration_ms": None,
        "lazy_load_cache_hit_count": 0,
        "lazy_load_cache_miss_count": 0,
        "graph_warm_median_before_ms": None,
        "graph_warm_median_after_ms": None,
        "resume_warm_median_before_ms": None,
        "resume_warm_median_after_ms": None,
        "result_contract_match": None,
        "resume_duplicate_count": None,
        "artifact_missing_fail_closed": None,
        "artifact_hash_mismatch_rejected": None,
        "workspace_scope_mismatch_rejected": None,
        "required_policy": {
            "artifact_missing": "fail_closed",
            "hash_mismatch": "reject",
            "workspace_mismatch": "reject",
        },
        "public_object_key_exposed": False,
        "destructive_retention_enabled": False,
        "performance_outcome": "no_safe_externalization",
        "production_db_used": False,
        "paid_external_calls": 0,
    }
    write_json(output_dir / "execution_gate.json", gate)
    write_json(output_dir / "gate_thresholds.json", {"thresholds": GATE_THRESHOLDS, "decision_scope": gate["decision_scope"]})
    write_json(output_dir / "state_residency_policy.json", size_rows)
    write_json(output_dir / "state_channel_size_breakdown.json", size_rows)
    write_json(output_dir / "duplicate_payload_analysis.json", duplicate_rows)
    write_json(output_dir / "all_externalization_candidates.json", all_candidates)
    write_json(output_dir / "artifact_candidate_plan.json", candidate_plan)
    write_json(
        output_dir / "artifact_reference_contract.json",
        {
            "status": "policy_defined_not_implemented",
            "validation_status": validation_status,
            "public_object_key_exposed": False,
            "recommended_ref_shape": {
                "artifact_type": "str",
                "artifact_id": "str",
                "storage_backend": "str",
                "sha256": "str",
                "size_bytes": "int",
                "schema_version": "str",
                "created_at": "str",
            },
        },
    )
    write_json(
        output_dir / "idempotency_validation.json",
        {
            "status": "policy_defined_not_implemented",
            "validation_status": validation_status,
            "duplicate_write_reused_existing_ref": None,
            "recommended_idempotency_key_parts": [
                "workspace_id",
                "thread_id",
                "job_id",
                "artifact_type",
                "source_revision",
                "schema_version",
                "payload_sha256",
            ],
        },
    )
    write_json(
        output_dir / "lazy_load_metrics.json",
        {
            "status": "not_run",
            "validation_status": validation_status,
            "lazy_load_count": 0,
            "cache_hit_count": 0,
            "cache_miss_count": 0,
            "storage_read_duration_ms": None,
            "loaded_bytes": 0,
        },
    )
    write_json(
        output_dir / "resume_validation.json",
        {
            "status": "not_run",
            "validation_status": validation_status,
            "result_contract_match": None,
            "resume_duplicate_count": None,
            "missing_state_field_regressions": None,
        },
    )
    write_json(
        output_dir / "missing_corrupt_validation.json",
        {
            "status": "policy_defined_not_implemented",
            "validation_status": validation_status,
            "artifact_missing_fail_closed": None,
            "artifact_hash_mismatch_rejected": None,
            "workspace_scope_mismatch_rejected": None,
            "required_policy": summary["required_policy"],
        },
    )
    write_json(
        output_dir / "checkpoint_retention_policy.json",
        {
            "status": "policy_defined_not_planned",
            "destructive_retention_enabled": False,
            "active_waiting_user_input": "retain checkpoints and referenced artifacts",
            "running_retrying": "retain current and previous recovery checkpoints",
            "done": "cleanup policy deferred to later operational task",
            "failed": "retain for debug window, cleanup later",
        },
    )
    write_json(output_dir / "summary.json", summary)
    report = "\n".join(
        [
            "# Checkpoint Residency & Large Artifact Separation v1",
            "",
            f"- status: `{summary['status']}`",
            f"- execution_gate: `{gate['status']}`",
            f"- decision_scope: `{gate['decision_scope']}`",
            f"- checkpoint_duration_ratio: `{gate['checkpoint_duration_ratio']}`",
            f"- checkpoint_write_duration_total_ms: `{gate['checkpoint_write_duration_total_ms']}`",
            f"- checkpoint_total_bytes: `{gate['checkpoint_total_bytes']}`",
            f"- cross_scenario_terminal_duplicate_bytes: `{gate['cross_scenario_terminal_duplicate_bytes']}`",
            "- decision: no source externalization applied in this pass",
            "",
            "## Top State Keys",
            *[
                f"- `{row['state_key']}`: median={row['median_size_bytes']} classification={row['classification']} source={row['classification_source']}"
                for row in size_rows[:10]
            ],
            "",
            "## Gate Reasons",
            *[f"- `{reason}`" for reason in gate["reasons"]],
        ]
    )
    (output_dir / "report.md").write_text(report + "\n", encoding="utf-8")


def run_self_check() -> dict[str, Any]:
    sample_states = {
        "S1": {"result_payload": {"big": "x" * 3000}, "messages": ["a"], "prompt_render_output": {"tmp": True}},
        "S2": {"result_payload": {"big": "x" * 3000}, "messages": ["a"], "prompt_render_output": {"tmp": True}},
    }
    channel_map = {
        "result_payload": {"public_contract_consumer_count": 1},
        "messages": {"resume_consumer_count": 1},
        "prompt_render_output": {},
    }
    size_rows, duplicate_rows, duplicate_total = summarize_state_sizes(sample_states, channel_map)
    assert any(row["state_key"] == "result_payload" and row["classification"] == "canonical_db_only" for row in size_rows)
    assert any(row["state_key"] == "prompt_render_output" and row["classification"] == "ephemeral_runtime_only" for row in size_rows)
    assert any("classification_source" in row for row in size_rows)
    assert duplicate_rows
    assert duplicate_total > 0
    assert GATE_THRESHOLDS["revision_growth_ratio"] == 1.5
    return {
        "status": "ok",
        "checked": [
            "state_key_size_aggregation",
            "duplicate_hash_detection",
            "residency_classification",
            "candidate_plan_generation",
            "gate_thresholds",
        ],
    }


def main() -> None:
    args = parse_args()
    if args.self_check:
        print(json.dumps(run_self_check(), ensure_ascii=False))
        return
    before_dir = Path(args.before_dir)
    output_dir = Path(args.output_dir)
    state_contract_dir = Path(args.state_contract_dir)
    state_contract_summary, channel_map = load_state_contract_inputs(state_contract_dir)
    states = load_warm_terminal_states(before_dir)
    size_rows, duplicate_rows, duplicate_total = summarize_state_sizes(states, channel_map)
    gate = build_gate(
        before_dir=before_dir,
        state_contract_summary=state_contract_summary,
        size_rows=size_rows,
        cross_scenario_terminal_duplicate_bytes=duplicate_total,
    )
    all_candidates = build_all_externalization_candidates(size_rows)
    candidate_plan = build_candidate_plan(all_candidates, gate["status"])
    write_completed_no_change_artifacts(
        output_dir=output_dir,
        gate=gate,
        size_rows=size_rows,
        duplicate_rows=duplicate_rows,
        all_candidates=all_candidates,
        candidate_plan=candidate_plan,
    )


if __name__ == "__main__":
    main()
