from __future__ import annotations

import argparse
import ast
import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TESTS_ROOT = REPO_ROOT / "orchestrator/tests"
DEFAULT_INVENTORY_DIR = REPO_ROOT / "data/test_optimization/pruning_inventory_v1"
DEFAULT_BRANCH_CONTEXT_DIR = REPO_ROOT / "data/test_optimization/branch_context_v1"
DEFAULT_MUTATION_DIR = REPO_ROOT / "data/test_optimization/critical_mutation_v1"
DEFAULT_CONTRACT_MATRIX_DIR = REPO_ROOT / "data/test_optimization/layer_contract_dedup_v1"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data/test_optimization/pruning_batch_06_v1"
PROTECTED_REASONS = {"protected_member_present"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tests-root", default=str(DEFAULT_TESTS_ROOT.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--inventory-dir", default=str(DEFAULT_INVENTORY_DIR.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--branch-context-dir", default=str(DEFAULT_BRANCH_CONTEXT_DIR.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--mutation-dir", default=str(DEFAULT_MUTATION_DIR.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--contract-matrix-dir", default=str(DEFAULT_CONTRACT_MATRIX_DIR.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--python", default="python")
    parser.add_argument("--self-check", action="store_true")
    return parser.parse_args()


def resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def test_metrics(tests_root: Path) -> dict[str, int]:
    file_count = 0
    loc = 0
    function_count = 0
    parameterized_function_count = 0
    for path in sorted(tests_root.rglob("test_*.py")):
        file_count += 1
        text = path.read_text(encoding="utf-8-sig")
        loc += sum(1 for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#"))
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                function_count += 1
                if any(
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == "parametrize"
                    for decorator in node.decorator_list
                ):
                    parameterized_function_count += 1
    return {
        "test_file_count": file_count,
        "test_loc_nonblank_noncomment": loc,
        "test_function_count": function_count,
        "parameterized_function_count": parameterized_function_count,
    }


def node_base(node_id: str) -> str:
    head, _, tail = node_id.partition("[")
    return head if tail else node_id


def infer_action_type(cluster: dict[str, Any]) -> str:
    nodes = cluster.get("node_ids", [])
    bases = {node_base(node) for node in nodes}
    if len(nodes) >= 2 and len(bases) == 1 and any("[" in node for node in nodes):
        return "remove_parameter_rows"
    return "defer_structural_review"


def review_decision(cluster: dict[str, Any], action_type: str) -> tuple[str, str]:
    if cluster.get("review_reason") in PROTECTED_REASONS or cluster.get("risk") == "high":
        return ("rejected", "protected_or_high_risk_cluster")
    if action_type == "remove_parameter_rows":
        return ("deferred", "parameter_rows_need_boundary_manual_review")
    return ("deferred", "structural_similarity_without_safe_auto_apply")


def build_structural_clusters(duplicate_clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cluster in duplicate_clusters:
        action_type = infer_action_type(cluster)
        decision, reason = review_decision(cluster, action_type)
        rows.append(
            {
                "cluster_id": cluster["cluster_id"],
                "action_type": action_type,
                "risk": cluster.get("risk", "unknown"),
                "review_reason": cluster.get("review_reason"),
                "recommended_owner_test": cluster.get("recommended_owner_test"),
                "node_count": len(cluster.get("node_ids", [])),
                "candidate_count": len(cluster.get("redundant_candidates", [])),
                "approved_for_application": False,
                "decision": decision,
                "decision_reason": reason,
                "node_ids": cluster.get("node_ids", []),
                "redundant_candidates": cluster.get("redundant_candidates", []),
            }
        )
    return rows


def build_plan_rows(rows: list[dict[str, Any]], action_type: str) -> list[dict[str, Any]]:
    plan = []
    for index, row in enumerate([item for item in rows if item["action_type"] == action_type], start=1):
        plan.append(
            {
                "action_id": f"{action_type}-{index:03d}",
                "action_type": action_type,
                "owner_node": row.get("recommended_owner_test"),
                "target_nodes": row.get("redundant_candidates", []),
                "affected_file": (row.get("recommended_owner_test") or "").split("::", 1)[0] or None,
                "normalized_body_match": True,
                "call_fingerprint_match": True,
                "assertion_fingerprint_match": True,
                "branch_signature_match": True,
                "contract_id": None,
                "markers": [],
                "risk": row.get("risk", "unknown"),
                "approved_for_application": False,
                "review_status": row["decision"],
                "review_reason": row["decision_reason"],
                "cluster_id": row["cluster_id"],
            }
        )
    return plan


def run_self_check() -> int:
    exact = {"node_ids": ["a::test_one", "a::test_two"], "redundant_candidates": ["a::test_two"], "risk": "high", "review_reason": "protected_member_present", "cluster_id": "c1"}
    param = {"node_ids": ["a::test_same[x]", "a::test_same[y]"], "redundant_candidates": ["a::test_same[y]"], "risk": "low", "review_reason": "duplicate_contract_branch_assertion_signature", "cluster_id": "c2"}
    rows = build_structural_clusters([exact, param])
    assert rows[0]["decision"] == "rejected"
    assert rows[1]["action_type"] == "remove_parameter_rows"
    assert rows[1]["decision"] == "deferred"
    print("self_check=ok")
    return 0


def main() -> int:
    args = parse_args()
    if args.self_check:
        return run_self_check()

    tests_root = resolve_path(args.tests_root)
    inventory_dir = resolve_path(args.inventory_dir)
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manual_review_inventory = load_json(inventory_dir / "manual_review_inventory.json")
    duplicate_clusters = load_json(inventory_dir / "duplicate_clusters.json").get("clusters", [])
    test_node_inventory = load_json(inventory_dir / "test_node_inventory.json").get("tests", [])

    structural_clusters = build_structural_clusters(duplicate_clusters)
    exact_duplicate_plan: list[dict[str, Any]] = []
    parametrization_plan: list[dict[str, Any]] = []
    parameter_row_plan = build_plan_rows(structural_clusters, "remove_parameter_rows")
    setup_consolidation_plan: list[dict[str, Any]] = []
    approved_plan: list[dict[str, Any]] = []
    rejected_clusters = [row for row in structural_clusters if row["decision"] == "rejected"]
    deferred_clusters = [row for row in structural_clusters if row["decision"] == "deferred"]
    protected_clusters = [row for row in structural_clusters if row.get("review_reason") in PROTECTED_REASONS]

    metrics = test_metrics(tests_root)
    before_metrics = {
        "manual_review_input_count": len(manual_review_inventory.get("candidates", [])),
        "collected_node_count": len(test_node_inventory),
        **metrics,
    }
    summary = {
        "status": "planned",
        "batch_id": "batch-06-final",
        "manual_review_input_count": before_metrics["manual_review_input_count"],
        "structural_cluster_count": len(structural_clusters),
        "exact_duplicate_cluster_count": len(exact_duplicate_plan),
        "parametrization_cluster_count": len(parametrization_plan),
        "redundant_parameter_row_count": len(parameter_row_plan),
        "setup_consolidation_count": len(setup_consolidation_plan),
        "approved_action_count": 0,
        "rejected_action_count": len(rejected_clusters),
        "deferred_action_count": len(deferred_clusters),
        "before_collected_nodes": before_metrics["collected_node_count"],
        "before_test_loc": before_metrics["test_loc_nonblank_noncomment"],
        "before_test_function_count": before_metrics["test_function_count"],
        "before_parameterized_function_count": before_metrics["parameterized_function_count"],
    }

    write_json(output_dir / "structural_clusters.json", {"clusters": structural_clusters})
    write_json(output_dir / "exact_duplicate_plan.json", {"actions": exact_duplicate_plan})
    write_json(output_dir / "parametrization_plan.json", {"actions": parametrization_plan})
    write_json(output_dir / "parameter_row_plan.json", {"actions": parameter_row_plan})
    write_json(output_dir / "setup_consolidation_plan.json", {"actions": setup_consolidation_plan})
    write_json(output_dir / "approved_consolidation_plan.json", {"actions": approved_plan})
    write_json(output_dir / "rejected_clusters.json", {"clusters": rejected_clusters})
    write_json(output_dir / "deferred_clusters.json", {"clusters": deferred_clusters})
    write_json(output_dir / "protected_clusters.json", {"clusters": protected_clusters})
    write_json(output_dir / "before_metrics.json", before_metrics)
    write_json(output_dir / "planner_summary.json", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
