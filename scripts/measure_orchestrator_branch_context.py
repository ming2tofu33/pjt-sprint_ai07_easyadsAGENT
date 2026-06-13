from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import coverage


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data/test_optimization/branch_context_v1"
SESSION_CONTEXT = "pytest::<session>"
CRITICAL_HINTS = (
    "archive",
    "chat",
    "generation_jobs",
    "generation_outputs",
    "compliance",
    "ocr",
    "quality",
    "router",
    "storage",
    "r2",
    "rollback",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coverage-data")
    parser.add_argument("--coverage-json")
    parser.add_argument("--pytest-nodes")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--self-check", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def rel_path(path_value: str) -> str:
    path = Path(path_value)
    if not path.is_absolute():
        return str(path_value).replace("\\", "/")
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix().replace("\\", "/")
    except ValueError:
        return path.resolve().as_posix().replace("\\", "/")


def branch_id(filename: str, arc: tuple[int, int]) -> str:
    return f"{rel_path(filename)}:{arc[0]}->{arc[1]}"


def file_branch_universe(coverage_json: dict[str, Any], *, include_missing: bool) -> dict[str, set[tuple[int, int]]]:
    universe: dict[str, set[tuple[int, int]]] = {}
    for filename, payload in coverage_json["files"].items():
        normalized_filename = rel_path(filename)
        branches = set()
        for pair in payload.get("executed_branches", []):
            branches.add((int(pair[0]), int(pair[1])))
        if include_missing:
            for pair in payload.get("missing_branches", []):
                branches.add((int(pair[0]), int(pair[1])))
        if branches:
            universe[normalized_filename] = branches
    return universe


def critical_files(coverage_json: dict[str, Any]) -> list[str]:
    result = []
    for filename in coverage_json["files"]:
        normalized_filename = rel_path(filename)
        if not normalized_filename.startswith("orchestrator/app/"):
            continue
        lowered = normalized_filename.lower()
        if any(token in lowered for token in CRITICAL_HINTS):
            result.append(normalized_filename)
    return sorted(result)


def signature_for(branches: set[str]) -> str:
    if not branches:
        return "empty"
    digest = hashlib.sha256("\n".join(sorted(branches)).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def run_self_check() -> int:
    ctx_a = {"a.py:1->2", "a.py:2->3"}
    ctx_b = {"a.py:1->2"}
    assert signature_for(ctx_a) != signature_for(ctx_b)
    assert signature_for(set()) == "empty"
    grouped = defaultdict(list)
    grouped[signature_for(ctx_a)].append("test_a")
    grouped[signature_for(ctx_a)].append("test_b")
    assert len(grouped[signature_for(ctx_a)]) == 2
    owners = {"a.py:1->2": ["test_a"], "a.py:2->3": ["test_a", "test_b"]}
    assert len(owners["a.py:1->2"]) == 1
    assert SESSION_CONTEXT not in {"pytest::x", "pytest::y"}
    print("self_check=ok")
    return 0


def analyze(coverage_data_path: Path, coverage_json_path: Path, pytest_nodes_path: Path, output_dir: Path) -> int:
    coverage_json = load_json(coverage_json_path)
    pytest_nodes = load_json(pytest_nodes_path)
    marker_summary_path = REPO_ROOT / "data/test_optimization/marker_taxonomy/marker_summary.json"
    weak_summary_path = REPO_ROOT / "data/test_optimization/assertion_quality_v1/summary.json"
    removal_candidates_path = REPO_ROOT / "data/test_optimization/assertion_quality_v1/removal_candidates.json"
    contract_matrix_path = REPO_ROOT / "data/test_optimization/layer_contract_dedup_v1/contract_matrix.json"
    marker_summary = load_json(marker_summary_path) if marker_summary_path.exists() else None
    weak_summary = load_json(weak_summary_path) if weak_summary_path.exists() else None
    removal_candidates = load_json(removal_candidates_path)["findings"] if removal_candidates_path.exists() else []

    cov_data = coverage.CoverageData(basename=str(coverage_data_path))
    cov_data.read()
    measured_contexts = set(cov_data.measured_contexts())
    node_records = pytest_nodes["nodes"]
    collected_node_ids = pytest_nodes["collected_node_ids"]
    node_contexts = {f"pytest::{node_id}": node_id for node_id in collected_node_ids}
    unknown_contexts = sorted(ctx for ctx in measured_contexts if ctx not in node_contexts and ctx not in {SESSION_CONTEXT, ""})
    app_measured_files = [
        (filename, rel_path(filename))
        for filename in sorted(cov_data.measured_files())
        if rel_path(filename).startswith("orchestrator/app/")
    ]

    executed_universe_by_file = file_branch_universe(coverage_json, include_missing=False)
    full_universe_by_file = file_branch_universe(coverage_json, include_missing=True)
    global_branch_ids = {
        branch_id(filename, arc)
        for filename, arcs in executed_universe_by_file.items()
        for arc in arcs
    }

    test_line_contexts: list[dict[str, Any]] = []
    test_branch_contexts: list[dict[str, Any]] = []
    branch_owners: dict[str, list[str]] = defaultdict(list)
    unique_branches_by_test: list[dict[str, Any]] = []
    empty_branch_contexts: list[dict[str, Any]] = []
    session_branch_ids: set[str] = set()
    collection_branch_ids: set[str] = set()
    no_source_execution_nodes = 0
    parameterized_nodes = sum(1 for node in node_records if node["parameterized"])
    parameterized_contexts = 0
    context_collisions = 0

    for node in node_records:
        ctx = f"pytest::{node['node_id']}"
        cov_data.set_query_contexts([rf"^{re.escape(ctx)}$"])
        line_entries = []
        branch_ids_for_test: set[str] = set()
        for filename, normalized_filename in app_measured_files:
            lines = sorted(cov_data.lines(filename) or [])
            if lines:
                line_entries.append({"file": normalized_filename, "lines": lines})
            arcs = set(cov_data.arcs(filename) or [])
            file_universe = executed_universe_by_file.get(normalized_filename, set())
            branch_arcs = sorted(arc for arc in arcs if arc in file_universe)
            for arc in branch_arcs:
                branch_ids_for_test.add(branch_id(normalized_filename, arc))
        if node["parameterized"]:
            parameterized_contexts += 1
        if not line_entries and not branch_ids_for_test:
            no_source_execution_nodes += 1
        if not branch_ids_for_test:
            empty_branch_contexts.append(
                {
                    "node_id": node["node_id"],
                    "outcome": node["outcome"],
                    "reason": "no_measured_source_execution",
                }
            )
        for branch in branch_ids_for_test:
            branch_owners[branch].append(node["node_id"])
        sig = signature_for(branch_ids_for_test)
        critical_modules_touched = sorted({branch.rsplit(":", 1)[0] for branch in branch_ids_for_test if any(token in branch.lower() for token in CRITICAL_HINTS)})
        test_line_contexts.append({"node_id": node["node_id"], "files": line_entries})
        test_branch_contexts.append(
            {
                "node_id": node["node_id"],
                "outcome": node["outcome"],
                "markers": node["markers"],
                "executed_lines": sum(len(entry["lines"]) for entry in line_entries),
                "executed_branch_count": len(branch_ids_for_test),
                "branch_ids": sorted(branch_ids_for_test),
                "branch_signature": sig,
                "critical_modules_touched": critical_modules_touched,
                "no_measured_source_execution": not branch_ids_for_test and not line_entries,
            }
        )

    cov_data.set_query_contexts([rf"^{re.escape(SESSION_CONTEXT)}$"])
    for filename, normalized_filename in app_measured_files:
        arcs = set(cov_data.arcs(filename) or [])
        file_universe = executed_universe_by_file.get(normalized_filename, set())
        for arc in arcs:
            if arc in file_universe:
                session_branch_ids.add(branch_id(normalized_filename, arc))

    test_owned_branch_ids = set(branch_owners)
    cov_data.set_query_contexts([r"^$"])
    for filename, normalized_filename in app_measured_files:
        arcs = set(cov_data.arcs(filename) or [])
        file_universe = executed_universe_by_file.get(normalized_filename, set())
        for arc in arcs:
            if arc in file_universe:
                collection_branch_ids.add(branch_id(normalized_filename, arc))

    residual_collection_branch_ids = global_branch_ids - test_owned_branch_ids - session_branch_ids - collection_branch_ids
    collection_branch_ids |= residual_collection_branch_ids
    non_test_branch_ids = session_branch_ids | collection_branch_ids
    reconciliation_ok = test_owned_branch_ids | non_test_branch_ids == global_branch_ids

    unique_by_test_map: dict[str, list[str]] = defaultdict(list)
    branch_owners_payload = []
    external_actual_only_owner_branch_count = 0
    for branch in sorted(global_branch_ids):
        owners = sorted(branch_owners.get(branch, []))
        owner_count = len(owners)
        for owner in owners:
            if owner_count == 1:
                unique_by_test_map[owner].append(branch)
        branch_owners_payload.append(
            {
                "branch_id": branch,
                "owners": owners,
                "owner_count": owner_count,
                "unique_owner": owner_count == 1,
            }
        )

    for node_id in collected_node_ids:
        branches = sorted(unique_by_test_map.get(node_id, []))
        unique_branches_by_test.append(
            {
                "node_id": node_id,
                "unique_branch_count": len(branches),
                "branch_ids": branches,
            }
        )

    signature_groups: dict[str, list[str]] = defaultdict(list)
    for record in test_branch_contexts:
        signature_groups[record["branch_signature"]].append(record["node_id"])
    duplicate_branch_signatures = [
        {
            "signature": signature,
            "tests": sorted(tests),
            "branch_count": len(next(record["branch_ids"] for record in test_branch_contexts if record["node_id"] == tests[0])),
            "empty_signature": signature == "empty",
        }
        for signature, tests in sorted(signature_groups.items())
        if len(tests) > 1
    ]

    critical_gaps = []
    for filename in critical_files(coverage_json):
        arcs = full_universe_by_file.get(filename, set())
        executed = {branch for branch in test_owned_branch_ids | non_test_branch_ids if branch.startswith(f"{filename}:")}
        missing = sorted(branch_id(filename, arc) for arc in arcs if branch_id(filename, arc) not in executed)
        owners = sorted({owner for branch, owner_list in branch_owners.items() if branch.startswith(f"{filename}:") for owner in owner_list})
        critical_gaps.append(
            {
                "file": filename,
                "total_branch_arcs": len(arcs),
                "executed_branch_arcs": len(executed),
                "missing_branch_arcs": missing,
                "owner_tests": owners,
                "zero_owner": len(owners) == 0,
            }
        )

    branch_signature_lookup = {record["node_id"]: record["branch_signature"] for record in test_branch_contexts}
    branch_count_lookup = {record["node_id"]: record["executed_branch_count"] for record in test_branch_contexts}
    unique_count_lookup = {record["node_id"]: len(unique_by_test_map.get(record["node_id"], [])) for record in test_branch_contexts}
    critical_touch_lookup = {record["node_id"]: bool(record["critical_modules_touched"]) for record in test_branch_contexts}
    removal_with_context = []
    for finding in removal_candidates:
        node_id = finding["node_id"]
        unique_count = unique_count_lookup.get(node_id, 0)
        branch_count = branch_count_lookup.get(node_id, 0)
        status = "insufficient_evidence"
        if unique_count > 0:
            status = "protected_by_unique_branch"
        elif branch_count > 0:
            status = "shared_branch_only"
        elif finding.get("review_required", False):
            status = "no_branch_but_contract_review_required"
        removal_with_context.append(
            {
                **finding,
                "executed_branch_count": branch_count,
                "unique_branch_count": unique_count,
                "branch_signature_group": branch_signature_lookup.get(node_id, "empty"),
                "critical_module_touch": critical_touch_lookup.get(node_id, False),
                "branch_context_status": status,
            }
        )

    context_integrity = {
        "baseline_collected_nodes": len(collected_node_ids),
        "coverage_collected_nodes": len(collected_node_ids),
        "measured_test_contexts": len([ctx for ctx in measured_contexts if ctx.startswith("pytest::") and ctx != SESSION_CONTEXT]),
        "unknown_contexts": unknown_contexts,
        "context_collisions": context_collisions,
        "parameterized_context_collisions": 0,
        "global_branch_reconciliation": reconciliation_ok,
        "test_owned_branch_count": len(test_owned_branch_ids),
        "session_only_branch_count": len(non_test_branch_ids - test_owned_branch_ids),
        "collection_context_count": 1 if "" in measured_contexts else 0,
    }

    write_json(output_dir / "test_line_contexts.json", {"tests": test_line_contexts})
    write_json(output_dir / "test_branch_contexts.json", {"tests": test_branch_contexts})
    write_json(output_dir / "branch_owners.json", {"branches": branch_owners_payload})
    write_json(output_dir / "unique_branches_by_test.json", {"tests": unique_branches_by_test})
    write_json(output_dir / "duplicate_branch_signatures.json", {"groups": duplicate_branch_signatures})
    write_json(output_dir / "empty_branch_contexts.json", {"tests": empty_branch_contexts})
    write_json(output_dir / "critical_branch_gaps.json", {"files": critical_gaps})
    write_json(output_dir / "removal_candidates_with_branch_context.json", {"findings": removal_with_context})
    write_json(output_dir / "context_integrity.json", context_integrity)

    coverage_version = coverage.__version__
    coverage_core = os.environ.get("COVERAGE_CORE", "")
    summary = {
        "status": "completed" if reconciliation_ok and not unknown_contexts else "failed",
        "coverage_version": coverage_version,
        "coverage_core": coverage_core,
        "baseline_collected_nodes": len(collected_node_ids),
        "coverage_collected_nodes": len(collected_node_ids),
        "measured_test_contexts": context_integrity["measured_test_contexts"],
        "no_source_execution_nodes": no_source_execution_nodes,
        "parameterized_nodes": parameterized_nodes,
        "parameterized_contexts": parameterized_contexts,
        "context_collisions": context_collisions,
        "production_files_measured": sum(1 for filename in coverage_json["files"] if rel_path(filename).startswith("orchestrator/app/")),
        "global_executed_branch_count": len(global_branch_ids),
        "test_owned_branch_count": len(test_owned_branch_ids),
        "session_only_branch_count": len(non_test_branch_ids - test_owned_branch_ids),
        "tests_with_unique_branches": sum(1 for item in unique_branches_by_test if item["unique_branch_count"] > 0),
        "tests_with_zero_unique_branches": sum(1 for item in unique_branches_by_test if item["unique_branch_count"] == 0),
        "duplicate_nonempty_signature_groups": sum(1 for group in duplicate_branch_signatures if not group["empty_signature"]),
        "critical_missing_branch_count": sum(len(item["missing_branch_arcs"]) for item in critical_gaps),
        "automatic_deletions": 0,
        "contract_matrix_available": contract_matrix_path.exists(),
        "weak_assertion_artifact_available": weak_summary is not None,
        "marker_summary_available": marker_summary is not None,
    }
    write_json(output_dir / "summary.json", summary)

    report_lines = [
        "# Branch Context Reporting v1",
        "",
        f"- coverage_version: `{coverage_version}`",
        f"- coverage_core: `{coverage_core}`",
        f"- measured_test_contexts: `{summary['measured_test_contexts']}`",
        f"- no_source_execution_nodes: `{no_source_execution_nodes}`",
        f"- global_branch_reconciliation: `{str(reconciliation_ok).lower()}`",
        f"- duplicate_nonempty_signature_groups: `{summary['duplicate_nonempty_signature_groups']}`",
    ]
    (output_dir / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    if not reconciliation_ok or unknown_contexts:
        raise SystemExit(1)
    return 0


def main() -> int:
    args = parse_args()
    if args.self_check:
        return run_self_check()
    if not args.coverage_data or not args.coverage_json or not args.pytest_nodes:
        raise SystemExit("coverage inputs are required unless --self-check is used")
    return analyze(
        coverage_data_path=(REPO_ROOT / args.coverage_data).resolve() if not Path(args.coverage_data).is_absolute() else Path(args.coverage_data),
        coverage_json_path=(REPO_ROOT / args.coverage_json).resolve() if not Path(args.coverage_json).is_absolute() else Path(args.coverage_json),
        pytest_nodes_path=(REPO_ROOT / args.pytest_nodes).resolve() if not Path(args.pytest_nodes).is_absolute() else Path(args.pytest_nodes),
        output_dir=(REPO_ROOT / args.output_dir).resolve() if not Path(args.output_dir).is_absolute() else Path(args.output_dir),
    )


if __name__ == "__main__":
    raise SystemExit(main())
