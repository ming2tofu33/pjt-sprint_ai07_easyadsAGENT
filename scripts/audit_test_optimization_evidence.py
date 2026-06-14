from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data/test_optimization/evidence_recalibration_v1"
DEFAULT_TESTS_ROOT = REPO_ROOT / "orchestrator/tests"
DEFAULT_BRANCH_CONTEXT_DIR = REPO_ROOT / "data/test_optimization/branch_context_v1"
DEFAULT_MUTATION_DIR = REPO_ROOT / "data/test_optimization/critical_mutation_v1"
DEFAULT_ASSERTION_DIR = REPO_ROOT / "data/test_optimization/assertion_quality_v1"
DEFAULT_CONTRACT_DIR = REPO_ROOT / "data/test_optimization/layer_contract_dedup_v1"
DEFAULT_INVENTORY_DIR = REPO_ROOT / "data/test_optimization/pruning_inventory_v1"
DEFAULT_BATCH_DIRS = [
    REPO_ROOT / "data/test_optimization/pruning_batch_03_v1",
    REPO_ROOT / "data/test_optimization/pruning_batch_04_v1",
    REPO_ROOT / "data/test_optimization/pruning_batch_05_v1",
]
PROTECTED_MARKERS = {"critical", "security", "transaction", "regression", "external", "actual", "e2e", "graph"}
CRITICAL_SCOPE_IDS = {
    "graph-routing-state",
    "quality-ocr",
    "workspace-scope",
    "final-selection-transaction",
    "compliance",
    "native-copy-policy",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tests-root", default="orchestrator/tests")
    parser.add_argument("--branch-context-dir", default="data/test_optimization/branch_context_v1")
    parser.add_argument("--mutation-dir", default="data/test_optimization/critical_mutation_v1")
    parser.add_argument("--assertion-quality-dir", default="data/test_optimization/assertion_quality_v1")
    parser.add_argument("--contract-matrix-dir", default="data/test_optimization/layer_contract_dedup_v1")
    parser.add_argument("--inventory-dir", default="data/test_optimization/pruning_inventory_v1")
    parser.add_argument("--batch-dirs", nargs="*", default=[str(path.relative_to(REPO_ROOT)).replace("\\", "/") for path in DEFAULT_BATCH_DIRS])
    parser.add_argument("--output-dir", default="data/test_optimization/evidence_recalibration_v1")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--self-check", action="store_true")
    return parser.parse_args()


def resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def load_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_command(command: list[str], *, cwd: Path, env: dict[str, str] | None = None, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, env=env, timeout=timeout)


def collect_live_nodes(python_cmd: str, tests_root: Path) -> list[str]:
    completed = run_command(
        [python_cmd, "-m", "pytest", str(tests_root.relative_to(REPO_ROOT)).replace("\\", "/"), "--collect-only", "--strict-markers", "-q"],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": "."},
        timeout=600,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.stderr[-4000:] or completed.stdout[-4000:] or "live_collect_failed")
    return [line.strip() for line in completed.stdout.splitlines() if line.strip().startswith("orchestrator/tests/")]


def normalize_rejection_reason(reason: str) -> list[str]:
    lowered = reason.lower()
    buckets: list[str] = []
    mapping = {
        "no live same-contract replacement": "no_live_replacement",
        "no live replacement": "no_live_replacement",
        "replacement": "no_live_replacement",
        "contract": "different_contract",
        "branch": "different_branch",
        "assertion": "different_assertion",
        "unique branch": "unique_branch",
        "semantic": "semantic_protected",
        "critical_graph_mutation_scope_member": "automated_scope_protected",
        "automated": "automated_scope_protected",
        "protected marker": "protected_marker",
        "protected contract": "protected_contract",
        "regression": "regression",
        "state transition": "different_state_transition",
        "error boundary": "different_error_boundary",
        "insufficient": "insufficient_evidence",
        "no measured source execution": "no_source_execution",
    }
    for needle, bucket in mapping.items():
        if needle in lowered:
            buckets.append(bucket)
    if not buckets:
        if "no removal signal" in lowered:
            buckets.append("insufficient_evidence")
        else:
            buckets.append("insufficient_evidence")
    return sorted(dict.fromkeys(buckets))


def review_survivor(mutant: dict[str, Any]) -> tuple[str, str]:
    mutant_id = mutant["mutant_id"]
    candidates = set(mutant.get("candidate_tests", []))
    if mutant_id.startswith("workspace-scope-remove-"):
        direct_present = any("workspace_isolation" in node or "get_by_public_id" in node for node in candidates)
        if direct_present:
            return "candidate_resolution_gap", "configured candidates rely on service/repository mocks rather than asserting mutated repository behavior"
        return "candidate_resolution_gap", "direct workspace isolation owner test was not selected as an effective killing test"
    if mutant_id == "quality-gate-allow-reject":
        return "candidate_resolution_gap", "candidate set contains integration flows but not a direct unit assertion for reject-to-status mapping"
    if mutant_id == "native-copy-remove-request-leak-guard":
        return "candidate_resolution_gap", "candidate set lacks a direct observable assertion on request-intent rejection outcome"
    return "out_of_contract_mutant", "survived mutant falls outside current direct observable assertions"


def build_branch_evidence_coverage(branch_context_dir: Path, live_nodes: list[str]) -> dict[str, Any]:
    branch_nodes = load_json(branch_context_dir / "pytest_nodes.json", default={"collected_node_ids": []}).get("collected_node_ids", [])
    contexts = {
        row["node_id"]: row
        for row in load_json(branch_context_dir / "test_branch_contexts.json", default={"tests": []}).get("tests", [])
    }
    unique_rows = {
        row["node_id"]: row
        for row in load_json(branch_context_dir / "unique_branches_by_test.json", default={"tests": []}).get("tests", [])
    }
    live_set = set(live_nodes)
    stale_nodes = sorted(node for node in branch_nodes if node not in live_set)
    exact_matched = [node for node in live_nodes if node in contexts]
    nonempty = 0
    empty = 0
    no_source = 0
    unique_positive = 0
    unique_zero = 0
    for node in live_nodes:
        row = contexts.get(node)
        if not row:
            continue
        if row.get("no_measured_source_execution", False):
            no_source += 1
        if row.get("branch_signature") in {None, "empty"}:
            empty += 1
        else:
            nonempty += 1
        if int(unique_rows.get(node, {}).get("unique_branch_count", 0)) > 0:
            unique_positive += 1
        else:
            unique_zero += 1
    return {
        "live_node_count": len(live_nodes),
        "branch_artifact_node_count": len(contexts),
        "exact_matched_node_count": len(exact_matched),
        "nonempty_branch_signature_count": nonempty,
        "empty_branch_signature_count": empty,
        "no_source_execution_count": no_source,
        "unique_branch_test_count": unique_positive,
        "unique_branch_zero_test_count": unique_zero,
        "stale_branch_node_count": len(stale_nodes),
        "branch_deletion_evidence": "insufficient",
    }


def build_automated_coverage(mutation_dir: Path, live_nodes: list[str]) -> dict[str, Any]:
    summary = load_json(mutation_dir / "summary.json")
    scopes = load_json(mutation_dir / "automated_scope_summary.json")["scopes"]
    scope_rows = []
    focused_live_total = 0
    for scope in scopes:
        resolved_path = mutation_dir / "runtime" / scope["scope_id"] / "resolved_test_nodes.json"
        resolved = load_json(resolved_path, default={"resolved_test_nodes": []}).get("resolved_test_nodes", [])
        live_hits = sorted(set(resolved).intersection(live_nodes))
        focused_live_total += len(live_hits)
        scope_rows.append(
            {
                "scope_id": scope["scope_id"],
                "source_files": sorted(scope.get("source_file_hashes", {}).keys()),
                "focused_tests": resolved,
                "generated": int(scope.get("generated", 0)),
                "killed": int(scope.get("killed", 0)),
                "survived": int(scope.get("survived", 0)),
                "uncovered": int(scope.get("uncovered", 0)),
                "focused_scope_live_node_count": len(live_hits),
            }
        )
    return {
        "automated_generated": int(summary["automated_generated"]),
        "automated_killed": int(summary["automated_killed"]),
        "automated_survived": int(summary["automated_survived"]),
        "automated_uncovered": int(summary["automated_uncovered"]),
        "scope_count": len(scope_rows),
        "focused_scope_live_node_count": focused_live_total,
        "test_level_attribution_available": False,
        "scopes": scope_rows,
    }


def build_semantic_coverage(mutation_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    results = load_json(mutation_dir / "runtime/semantic/semantic_mutant_results.json")["results"]
    unique_rows = load_json(mutation_dir / "runtime/semantic/unique_kills_by_test.json")["tests"]
    shared_rows = load_json(mutation_dir / "runtime/semantic/shared_kills_by_test.json")["tests"]
    rows = []
    for row in results:
        rows.append(
            {
                "mutant_id": row["mutant_id"],
                "status": row["status"],
                "target_file": row["file"],
                "target_symbol": row["target_symbol"],
                "candidate_tests": row.get("candidate_tests", []),
                "killing_tests": row.get("killing_tests", []),
                "non_killing_tests": row.get("non_killing_tests", []),
                "attribution_status": row.get("attribution_status"),
                "classification_hint": row.get("classification_hint"),
            }
        )
    coverage = {
        "semantic_mutant_count": len(rows),
        "semantic_survivor_count": sum(1 for row in rows if row["status"] == "survived"),
        "semantic_killed_count": sum(1 for row in rows if row["status"] == "killed"),
        "unique_kill_test_count": len(unique_rows),
        "shared_kill_test_count": len(shared_rows),
        "candidate_test_coverage_count": sum(1 for row in rows if row["candidate_tests"]),
        "mutants": rows,
    }
    return coverage, rows


def build_batch_breakdown(batch_dirs: list[Path]) -> tuple[dict[str, Any], int, int]:
    by_batch = []
    reviewed_total = 0
    approved_total = 0
    reason_counter: Counter[str] = Counter()
    combined_counter: Counter[str] = Counter()
    replacement_missing = 0
    contract_like = 0
    evidence_like = 0
    for batch_dir in batch_dirs:
        rows = load_json(batch_dir / "candidate_review.json")["candidates"]
        reviewed_total += len(rows)
        approved_total += sum(1 for row in rows if row["decision"] == "approved")
        local_counter: Counter[str] = Counter()
        for row in rows:
            buckets = normalize_rejection_reason(row.get("reason", row.get("decision_reason", "")))
            if not row.get("replacement_test"):
                replacement_missing += 1
            if any(bucket in {"different_state_transition", "different_error_boundary", "different_contract"} for bucket in buckets):
                contract_like += 1
            if any(bucket in {"insufficient_evidence", "no_live_replacement", "different_branch", "different_assertion", "no_source_execution"} for bucket in buckets):
                evidence_like += 1
            for bucket in buckets:
                reason_counter[bucket] += 1
                local_counter[bucket] += 1
            combined_counter["+".join(buckets)] += 1
        by_batch.append({"batch_id": batch_dir.name, "candidate_count": len(rows), "reason_counts": dict(sorted(local_counter.items()))})
    denominator = reviewed_total or 1
    payload = {
        "batches": by_batch,
        "reason_counts": dict(sorted(reason_counter.items())),
        "combined_reason_counts": dict(sorted(combined_counter.items(), key=lambda item: (-item[1], item[0]))),
        "replacement_missing_ratio": round(replacement_missing / denominator, 4),
        "unique_contract_ratio": round(contract_like / denominator, 4),
        "evidence_gap_ratio": round(evidence_like / denominator, 4),
    }
    return payload, reviewed_total, approved_total


def build_empirical_candidate_plan(inventory_dir: Path) -> dict[str, Any]:
    duplicate_clusters = load_json(inventory_dir / "duplicate_clusters.json")["clusters"]
    node_inventory = {
        row["node_id"]: row
        for row in load_json(inventory_dir / "test_node_inventory.json")["tests"]
    }
    plan_rows = []
    order = 0
    for cluster in duplicate_clusters:
        if cluster.get("risk") != "low":
            continue
        if not cluster.get("branch_signature_match") or not cluster.get("assertion_match"):
            continue
        for node_id in cluster.get("redundant_candidates", []):
            item = node_inventory.get(node_id)
            if not item:
                continue
            if item.get("parameter_id") is not None:
                continue
            if item.get("unique_branch_count", 0) != 0:
                continue
            if item.get("semantic_unique_kill_count", 0) != 0 or item.get("related_semantic_survivors"):
                continue
            if set(item.get("markers", [])).intersection(PROTECTED_MARKERS):
                continue
            if set(item.get("automated_scope_ids", [])).intersection(CRITICAL_SCOPE_IDS):
                continue
            order += 1
            plan_rows.append(
                {
                    "node_id": node_id,
                    "candidate_type": "duplicate_cluster",
                    "cluster_id": cluster["cluster_id"],
                    "proposed_owner": cluster["recommended_owner_test"],
                    "why_not_selected_before": "inventory_required_live_replacement_and manual review batches stayed protection-biased",
                    "risk": "medium",
                    "experiment_order": order,
                }
            )
            if len(plan_rows) >= 10:
                break
        if len(plan_rows) >= 10:
            break
    return {"candidates": plan_rows}


def build_evidence_value_assessment() -> dict[str, str]:
    return {
        "branch_context_v1": "useful_for_protection",
        "branch_context_v1_for_direct_pruning": "insufficient_for_direct_pruning",
        "critical_mutation_automated_v1": "useful_for_gap_detection",
        "critical_mutation_semantic_v1": "useful_for_gap_detection",
        "critical_mutation_v1_for_direct_pruning": "insufficient_for_direct_pruning",
    }


def build_automated_uncovered_review(mutation_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    uncovered = load_json(mutation_dir / "runtime/semantic/uncovered_mutants.json", default={"mutants": []}).get("mutants", [])
    review_rows = []
    followups = []
    for row in uncovered:
        classification = "insufficient_mutant_detail"
        if "workspace" in row.get("mutant_id", "") or "transaction" in row.get("mutant_id", ""):
            classification = "scope_test_selection_gap"
        review_rows.append(
            {
                "mutant_id": row.get("mutant_id"),
                "scope_id": row.get("scope_id"),
                "file": row.get("file"),
                "target_symbol": row.get("target_symbol"),
                "mutant_expression": row.get("description"),
                "focused_tests": row.get("candidate_tests", []),
                "classification": classification,
            }
        )
        if len(followups) < 5 and classification in {"scope_test_selection_gap", "missing_test"}:
            followups.append(
                {
                    "mutant_id": row.get("mutant_id"),
                    "scope_id": row.get("scope_id"),
                    "priority": "high",
                    "reason": classification,
                }
            )
    return review_rows, followups


def run_self_check() -> int:
    assert normalize_rejection_reason("no live replacement evidence under the stricter layer/strength guard") == ["no_live_replacement"]
    assert "no_live_replacement" in normalize_rejection_reason("graph_or_integration_contract_has_no_removal_signal_and_no_live_replacement")
    klass, _ = review_survivor({"mutant_id": "quality-gate-allow-reject", "candidate_tests": []})
    assert klass == "candidate_resolution_gap"
    assessment = build_evidence_value_assessment()
    assert assessment["branch_context_v1_for_direct_pruning"] == "insufficient_for_direct_pruning"
    print("self_check=ok")
    return 0


def main() -> int:
    args = parse_args()
    if args.self_check:
        return run_self_check()

    tests_root = resolve_path(args.tests_root)
    branch_context_dir = resolve_path(args.branch_context_dir)
    mutation_dir = resolve_path(args.mutation_dir)
    inventory_dir = resolve_path(args.inventory_dir)
    output_dir = resolve_path(args.output_dir)
    batch_dirs = [resolve_path(path) for path in args.batch_dirs]

    live_nodes = collect_live_nodes(args.python, tests_root)
    branch_coverage = build_branch_evidence_coverage(branch_context_dir, live_nodes)
    automated_coverage = build_automated_coverage(mutation_dir, live_nodes)
    semantic_coverage, semantic_rows = build_semantic_coverage(mutation_dir)
    batch_breakdown, reviewed_total, approved_total = build_batch_breakdown(batch_dirs)

    survivor_reviews = []
    classification_counter: Counter[str] = Counter()
    for row in semantic_rows:
        if row["status"] != "survived":
            continue
        classification, reason = review_survivor(row)
        classification_counter[classification] += 1
        survivor_reviews.append(
            {
                "mutant_id": row["mutant_id"],
                "classification": classification,
                "reason": reason,
                "target_file": row["target_file"],
                "target_symbol": row["target_symbol"],
                "candidate_tests": row["candidate_tests"],
                "killing_tests": row["killing_tests"],
                "non_killing_tests": row["non_killing_tests"],
            }
        )

    uncovered_review, uncovered_followups = build_automated_uncovered_review(mutation_dir)
    empirical_plan = build_empirical_candidate_plan(inventory_dir)
    summary = {
        "status": "completed",
        "live_node_count": len(live_nodes),
        "batch_03_05_reviewed_count": reviewed_total,
        "batch_03_05_approved_count": approved_total,
        "branch_evidence_complete_count": branch_coverage["exact_matched_node_count"],
        "branch_unique_test_count": branch_coverage["unique_branch_test_count"],
        "branch_zero_unique_test_count": branch_coverage["unique_branch_zero_test_count"],
        "automated_mutant_count": automated_coverage["automated_generated"],
        "automated_survivor_count": automated_coverage["automated_survived"],
        "automated_uncovered_count": automated_coverage["automated_uncovered"],
        "automated_test_attribution_available": False,
        "semantic_mutant_count": semantic_coverage["semantic_mutant_count"],
        "semantic_survivor_count": semantic_coverage["semantic_survivor_count"],
        "semantic_real_gap_count": classification_counter["real_test_gap"],
        "semantic_equivalent_count": classification_counter["equivalent_mutant"],
        "semantic_candidate_resolution_gap_count": classification_counter["candidate_resolution_gap"],
        "semantic_mutants_killed_after_fix": 0,
        "empirical_candidate_count": len(empirical_plan["candidates"]),
        "leave_one_out_executed_count": 0,
        "empirically_redundant_count": 0,
        "actual_deleted_node_count": 0,
        "modified_test_count": 0,
        "full_automated_mutation_rerun": False,
        "full_branch_context_rerun": False,
        "production_code_changed": False,
    }

    write_json(output_dir / "branch_evidence_coverage.json", branch_coverage)
    write_json(output_dir / "automated_mutation_evidence_coverage.json", automated_coverage)
    write_json(output_dir / "semantic_mutation_evidence_coverage.json", semantic_coverage)
    write_json(output_dir / "batch_rejection_reason_breakdown.json", batch_breakdown)
    write_json(output_dir / "evidence_value_assessment.json", build_evidence_value_assessment())
    write_json(output_dir / "semantic_survivor_review.json", {"survivors": survivor_reviews})
    write_json(output_dir / "automated_uncovered_review.json", {"rows": uncovered_review})
    write_json(output_dir / "automated_gap_followups.json", {"followups": uncovered_followups})
    write_json(output_dir / "empirical_candidate_plan.json", empirical_plan)
    write_json(output_dir / "summary.json", summary)
    (output_dir / "report.md").write_text(
        "\n".join(
            [
                "# Evidence Recalibration v1",
                "",
                f"- live nodes: {len(live_nodes)}",
                f"- reviewed batch candidates: {reviewed_total}",
                f"- semantic survivors: {semantic_coverage['semantic_survivor_count']}",
                f"- empirical candidates: {len(empirical_plan['candidates'])}",
                "- branch context and mutation artifacts were assessed as protection/gap-detection evidence, not direct pruning proof.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
