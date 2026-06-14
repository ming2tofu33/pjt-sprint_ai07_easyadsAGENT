from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data/test_optimization/pruning_inventory_v1"
DEFAULT_TESTS_ROOT = REPO_ROOT / "orchestrator/tests"
DEFAULT_BRANCH_CONTEXT_DIR = REPO_ROOT / "data/test_optimization/branch_context_v1"
DEFAULT_ASSERTION_QUALITY_DIR = REPO_ROOT / "data/test_optimization/assertion_quality_v1"
DEFAULT_MUTATION_DIR = REPO_ROOT / "data/test_optimization/critical_mutation_v1"
DEFAULT_CONTRACT_MATRIX_DIR = REPO_ROOT / "data/test_optimization/layer_contract_dedup_v1"
DEFAULT_MARKER_INVENTORY_DIR = REPO_ROOT / "data/test_optimization/marker_inventory_v1"
DEFAULT_MARKER_FALLBACK_DIR = REPO_ROOT / "data/test_optimization/marker_taxonomy"
DEFAULT_BASELINE_DIR = REPO_ROOT / "data/test_optimization/baseline_v1"
DEFAULT_BASELINE_FALLBACK_DIR = REPO_ROOT / "data/test_optimization"
MUTATION_SOURCE_COMMIT = "2e8586bc94d46b55a0b639248f31200f22c1bdbd"
MUTATION_TOOLING_COMMIT = "2a5bbc1eef9fd9f0d771842152b04d8845cf9dab"
PROTECTED_MARKERS = {"critical", "security", "transaction", "regression", "external", "actual", "e2e"}
HIGH_RISK_MARKERS = {"graph"}
PROTECTED_CONTRACT_TERMS = (
    "workspace",
    "tenant",
    "transaction",
    "rollback",
    "migration",
    "snapshot",
    "resume",
    "interrupt",
    "stale",
    "idempotency",
    "final-output-selection-transaction",
    "provider",
    "r2",
    "usage",
    "dedup",
    "quality",
    "compliance",
    "actual",
)
LOW_RISK_CATEGORY_HINTS = (
    "mock_passthrough",
    "getter",
    "constructor",
    "library_default",
    "serialization_duplicate",
    "schema_default_duplicate",
)
LAYER_MARKERS = {"unit", "integration", "contract", "e2e"}
DOMAIN_HINTS = {
    "archive": ("archive",),
    "copy": ("copy", "native", "typography", "prompt"),
    "graph": ("graph", "router", "chat_thread", "chat_threads", "resume", "interrupt"),
    "storage": ("storage", "asset", "r2"),
    "api": ("api", "router"),
    "validation": ("validation", "quality", "compliance", "ocr"),
    "generation": ("generation", "final_selection"),
    "reference": ("reference", "brand_kit"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tests-root", default="orchestrator/tests")
    parser.add_argument("--output-dir", default="data/test_optimization/pruning_inventory_v1")
    parser.add_argument("--branch-context-dir", default="data/test_optimization/branch_context_v1")
    parser.add_argument("--assertion-quality-dir", default="data/test_optimization/assertion_quality_v1")
    parser.add_argument("--mutation-dir", default="data/test_optimization/critical_mutation_v1")
    parser.add_argument("--contract-matrix-dir", default="data/test_optimization/layer_contract_dedup_v1")
    parser.add_argument("--marker-inventory-dir", default="data/test_optimization/marker_inventory_v1")
    parser.add_argument("--baseline-dir", default="data/test_optimization/baseline_v1")
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


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_command(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, env=env)


def git_head() -> str:
    return run_command(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT).stdout.strip()


def git_changed_files(base: str, head: str, paths: list[str]) -> list[str]:
    completed = run_command(["git", "diff", "--name-only", f"{base}..{head}", "--", *paths], cwd=REPO_ROOT)
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def resolve_optional_dir(requested: Path, fallback: Path) -> tuple[Path, bool]:
    if requested.exists():
        return requested, False
    if fallback.exists():
        return fallback, True
    return requested, False


def resolve_baseline_dir(requested: Path) -> tuple[Path, bool]:
    if requested.exists():
        return requested, False
    if (DEFAULT_BASELINE_FALLBACK_DIR / "baseline_summary.json").exists():
        return DEFAULT_BASELINE_FALLBACK_DIR, True
    return requested, False


def classify_domain(file_path: str) -> str:
    lower = file_path.lower()
    for domain, hints in DOMAIN_HINTS.items():
        if any(hint in lower for hint in hints):
            return domain
    return "unknown"


def split_node_id(node_id: str) -> tuple[str, str, str | None]:
    file_part, rest = node_id.split("::", 1)
    if "[" in rest and rest.endswith("]"):
        function, param = rest.split("[", 1)
        return file_part, function, param[:-1]
    return file_part, rest, None


def normalize_marker_payload(marker_nodes: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["node_id"]: row for row in marker_nodes.get("nodes", [])}


def normalize_unique_branch_payload(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["node_id"]: row for row in payload.get("tests", [])}


def normalize_branch_context_payload(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["node_id"]: row for row in payload.get("tests", [])}


def normalize_assertion_payload(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in payload.get("findings", []):
        grouped[row["node_id"]].append(row)
    return grouped


def normalize_duration_payload(payload: dict[str, Any]) -> dict[str, float]:
    result: dict[str, float] = {}
    for row in payload.get("top_slow_tests", []):
        result[row["node_id"]] = float(row["total_seconds"])
    return result


def load_warning_total(path: Path) -> int | None:
    if not path.exists():
        return None
    return int(load_json(path).get("total_warning_events", 0))


def normalize_contract_payload(payload: list[dict[str, Any]]) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    node_to_contract: dict[str, str] = {}
    contracts: dict[str, dict[str, Any]] = {}
    for row in payload:
        contract_id = row["contract_id"]
        contracts[contract_id] = row
        for nodes in row.get("layers", {}).values():
            for node_id in nodes:
                node_to_contract[node_id] = contract_id
    return node_to_contract, contracts


def load_duplicate_candidates(path: Path) -> dict[str, dict[str, Any]]:
    rows = load_json(path, default=[])
    return {row["node_id"]: row for row in rows}


def load_semantic_maps(mutation_dir: Path) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, list[str]], dict[str, list[str]], dict[str, list[str]]]:
    results = load_json(mutation_dir / "runtime/semantic/semantic_mutant_results.json")["results"]
    unique_rows = load_json(mutation_dir / "runtime/semantic/unique_kills_by_test.json")["tests"]
    shared_rows = load_json(mutation_dir / "runtime/semantic/shared_kills_by_test.json")["tests"]
    unique_map = {row["test_node_id"]: row.get("unique_mutant_ids", row.get("mutant_ids", [])) for row in unique_rows}
    shared_map = {row["test_node_id"]: row.get("shared_mutant_ids", row.get("mutant_ids", [])) for row in shared_rows}
    candidate_map: dict[str, list[str]] = defaultdict(list)
    survivor_map: dict[str, list[str]] = defaultdict(list)
    suite_interaction_nodes: dict[str, list[str]] = defaultdict(list)
    non_killing_map: dict[str, list[str]] = defaultdict(list)
    for row in results:
        for node_id in row.get("candidate_tests", []):
            candidate_map[node_id].append(row["mutant_id"])
            if row["status"] == "survived":
                survivor_map[node_id].append(row["mutant_id"])
        for node_id in row.get("non_killing_tests", []):
            non_killing_map[node_id].append(row["mutant_id"])
        if row.get("attribution_status") == "suite_interaction_kill":
            for node_id in row.get("candidate_tests", []):
                suite_interaction_nodes[node_id].append(row["mutant_id"])
    return unique_map, shared_map, candidate_map, survivor_map, suite_interaction_nodes | non_killing_map


@dataclass
class AstTestInfo:
    function: str
    body_hash: str
    assertion_fingerprints: list[str]
    weak_assertion_patterns: list[str]


def extract_ast_test_info(test_file: Path) -> dict[str, AstTestInfo]:
    source = test_file.read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    lines = source.splitlines()
    result: dict[str, AstTestInfo] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            start = node.lineno - 1
            end = node.end_lineno or node.lineno
            body = "\n".join(lines[start:end])
            assert_fps: list[str] = []
            for child in ast.walk(node):
                if isinstance(child, ast.Assert):
                    snippet = ast.get_source_segment(source, child) or ast.dump(child, include_attributes=False)
                    assert_fps.append(sha256_text(snippet)[:12])
            result[node.name] = AstTestInfo(
                function=node.name,
                body_hash=sha256_text(body),
                assertion_fingerprints=sorted(dict.fromkeys(assert_fps)),
                weak_assertion_patterns=[],
            )
    return result


def collect_live_nodes(python_cmd: str, tests_root: Path) -> list[str]:
    completed = run_command(
        [python_cmd, "-m", "pytest", str(tests_root.relative_to(REPO_ROOT)).replace("\\", "/"), "--collect-only", "--strict-markers", "-q"],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": "."},
    )
    if completed.returncode != 0:
        raise SystemExit(completed.stderr[-4000:] or completed.stdout[-4000:] or "live_collect_failed")
    return [line.strip() for line in completed.stdout.splitlines() if line.strip().startswith("orchestrator/tests/")]


def load_automated_scope_rows(mutation_dir: Path) -> list[dict[str, Any]]:
    return load_json(mutation_dir / "automated_scope_summary.json")["scopes"]


def find_automated_scope_memberships(scope_rows: list[dict[str, Any]], node_id: str) -> tuple[list[str], int, int]:
    memberships: list[str] = []
    survivor_count = 0
    uncovered_count = 0
    for row in scope_rows:
        runtime_nodes = load_json(REPO_ROOT / "data/test_optimization/critical_mutation_v1" / "runtime" / row["scope_id"] / "resolved_test_nodes.json", default={"resolved_test_nodes": []})
        if node_id in runtime_nodes.get("resolved_test_nodes", []):
            memberships.append(row["scope_id"])
            survivor_count += int(row.get("survived", 0))
            uncovered_count += int(row.get("uncovered", 0))
    return memberships, survivor_count, uncovered_count


def score_candidate(item: dict[str, Any]) -> int:
    score = 0
    reason = item["reason"].lower()
    category = item["category"]
    if "candidate_for_removal" in category or "candidate" in reason:
        score += 4
    if item["replacement_test"]:
        score += 4
    if item["contract_id"]:
        score += 3
    if item["branch_signature"] not in {None, "empty"}:
        score += 3
    if item["assertion_fingerprints"]:
        score += 2
    if "mock" in category or "mock" in reason:
        score += 2
    if any(hint in category for hint in LOW_RISK_CATEGORY_HINTS):
        score += 1
    if item["duration_seconds"] is not None and item["duration_seconds"] >= 0.5:
        score += 1
    if item["automated_scope_survivor_count"] > 200:
        score -= 3
    if item["automated_scope_uncovered_count"] > 0:
        score -= 4
    if item["layer"] in {"integration", "e2e"} or "graph" in item["markers"]:
        score -= 5
    return score


def choose_replacement(node_id: str, contract_id: str | None, contracts: dict[str, dict[str, Any]]) -> tuple[str | None, str | None]:
    if not contract_id or contract_id not in contracts:
        return None, None
    row = contracts[contract_id]
    owner_tests: list[str] = []
    for layer_name in ("api", "service", "repository", "graph", "policy", "schema"):
        owner_tests.extend(row.get("layers", {}).get(layer_name, []))
    for owner in owner_tests:
        if owner != node_id:
            return owner, contract_id
    return None, contract_id


def build_report(summary: dict[str, Any], compatibility: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Test Deletion Candidate Inventory v1",
        "",
        f"- status: `{summary['status']}`",
        f"- live collected nodes: `{summary['live_collected_nodes']}`",
        f"- protected nodes: `{summary['protected_node_count']}`",
        f"- candidate nodes: `{summary['low_risk_candidate_count'] + summary['manual_review_candidate_count']}`",
        f"- stale evidence nodes: `{summary['stale_evidence_count']}`",
        f"- duplicate clusters: `{summary['duplicate_cluster_count']}`",
        f"- evidence compatibility: `{compatibility['status']}`",
        "",
        "이번 작업은 테스트 삭제 후보 inventory만 생성합니다.",
        "실제 테스트 삭제, full mutation 재실행, branch-context 재실행은 포함하지 않습니다.",
    ]
    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_self_check() -> int:
    protected = classify_candidate_status(
        markers=["critical"],
        contract_id=None,
        unique_branch_count=0,
        semantic_unique_kill_count=0,
        semantic_survivors=[],
        suite_interaction=False,
        critical_gap=False,
        stale=False,
        automated_uncovered=False,
        replacement_test=None,
        duplicate_hint=None,
    )
    assert protected == "protected"
    unique_branch = classify_candidate_status(
        markers=[],
        contract_id=None,
        unique_branch_count=1,
        semantic_unique_kill_count=0,
        semantic_survivors=[],
        suite_interaction=False,
        critical_gap=False,
        stale=False,
        automated_uncovered=False,
        replacement_test="x",
        duplicate_hint="duplicate_candidate",
    )
    assert unique_branch == "protected"
    low_risk = classify_candidate_status(
        markers=[],
        contract_id=None,
        unique_branch_count=0,
        semantic_unique_kill_count=0,
        semantic_survivors=[],
        suite_interaction=False,
        critical_gap=False,
        stale=False,
        automated_uncovered=False,
        replacement_test="x",
        duplicate_hint="duplicate_candidate",
    )
    assert low_risk == "low_risk_candidate"
    review = classify_candidate_status(
        markers=[],
        contract_id=None,
        unique_branch_count=0,
        semantic_unique_kill_count=0,
        semantic_survivors=[],
        suite_interaction=False,
        critical_gap=False,
        stale=False,
        automated_uncovered=False,
        replacement_test=None,
        duplicate_hint=None,
    )
    assert review == "review"
    print("self_check=ok")
    return 0


def classify_candidate_status(
    *,
    markers: list[str],
    contract_id: str | None,
    unique_branch_count: int,
    semantic_unique_kill_count: int,
    semantic_survivors: list[str],
    suite_interaction: bool,
    critical_gap: bool,
    stale: bool,
    automated_uncovered: bool,
    replacement_test: str | None,
    duplicate_hint: str | None,
) -> str:
    if stale:
        return "stale"
    if any(marker in PROTECTED_MARKERS for marker in markers):
        return "protected"
    if unique_branch_count > 0 or semantic_unique_kill_count > 0 or semantic_survivors or suite_interaction:
        return "protected"
    if contract_id and any(term in contract_id for term in PROTECTED_CONTRACT_TERMS):
        return "protected"
    if critical_gap or automated_uncovered:
        return "protected"
    if replacement_test and duplicate_hint == "duplicate_candidate":
        return "low_risk_candidate"
    return "review"


def main() -> int:
    args = parse_args()
    if args.self_check:
        return run_self_check()

    tests_root = resolve_path(args.tests_root)
    output_dir = resolve_path(args.output_dir)
    branch_context_dir = resolve_path(args.branch_context_dir)
    assertion_quality_dir = resolve_path(args.assertion_quality_dir)
    mutation_dir = resolve_path(args.mutation_dir)
    contract_dir = resolve_path(args.contract_matrix_dir)
    marker_dir, marker_fallback_used = resolve_optional_dir(resolve_path(args.marker_inventory_dir), DEFAULT_MARKER_FALLBACK_DIR)
    baseline_dir, baseline_fallback_used = resolve_baseline_dir(resolve_path(args.baseline_dir))

    summary = load_json(mutation_dir / "summary.json")
    expected_pairs = {
        "status": "completed",
        "scope_count": 6,
        "automated_generated": 2579,
        "automated_killed": 1405,
        "automated_survived": 1148,
        "automated_uncovered": 26,
        "automated_timeout": 0,
        "automated_error": 0,
        "semantic_mutant_count": 6,
        "semantic_killed": 2,
        "semantic_survived": 4,
        "semantic_timeout": 0,
        "semantic_uncovered": 0,
        "semantic_stale_patch": 0,
        "semantic_error": 0,
        "source_restore_failures": 0,
        "cleanup_failures": 0,
        "weak_assertion_stale_node_count": 0,
        "automatic_deletions": 0,
    }
    mismatches = {key: {"expected": value, "actual": summary.get(key)} for key, value in expected_pairs.items() if summary.get(key) != value}
    if summary.get("completed_scopes") is None or len(summary.get("completed_scopes", [])) != 6 or summary.get("pending_scopes") != [] or summary.get("blocked_scopes") != []:
        mismatches["scope_lists"] = {
            "completed_scopes": summary.get("completed_scopes"),
            "pending_scopes": summary.get("pending_scopes"),
            "blocked_scopes": summary.get("blocked_scopes"),
        }
    if mismatches:
        raise SystemExit(json.dumps({"status": "artifact_mismatch", "mismatches": mismatches}, ensure_ascii=False))

    output_dir.mkdir(parents=True, exist_ok=True)
    current_commit = git_head()
    production_diff_files = git_changed_files(summary["source_commit"], current_commit, ["orchestrator/app"])
    test_diff_files = git_changed_files(summary["source_commit"], current_commit, ["orchestrator/tests"])
    automated_scope_rows = load_automated_scope_rows(mutation_dir)
    reusable_scopes: list[str] = []
    stale_scopes: list[str] = []
    current_hashes: dict[str, str] = {}
    for row in automated_scope_rows:
        stale = False
        for file_path, expected_hash in row.get("source_file_hashes", {}).items():
            actual_hash = sha256_text((REPO_ROOT / file_path).read_text(encoding="utf-8")) if (REPO_ROOT / file_path).exists() else "missing"
            current_hashes[file_path] = actual_hash
            if actual_hash != expected_hash:
                stale = True
        (stale_scopes if stale else reusable_scopes).append(row["scope_id"])

    live_nodes = collect_live_nodes(args.python, tests_root)
    live_node_set = set(live_nodes)
    branch_nodes = load_json(branch_context_dir / "pytest_nodes.json").get("collected_node_ids", [])
    stale_branch_nodes = [node for node in branch_nodes if node not in live_node_set]
    weak_candidates = load_json(assertion_quality_dir / "removal_candidates.json").get("findings", [])
    stale_weak_assertion_nodes = sorted({row["node_id"] for row in weak_candidates if row["node_id"] not in live_node_set})

    compatibility = {
        "status": "compatible",
        "current_commit": current_commit,
        "mutation_source_commit": summary["source_commit"],
        "production_diff_files": production_diff_files,
        "test_diff_files": test_diff_files,
        "reusable_scopes": reusable_scopes,
        "stale_scopes": stale_scopes,
        "live_collected_nodes": len(live_nodes),
        "stale_branch_nodes": stale_branch_nodes,
        "stale_weak_assertion_nodes": stale_weak_assertion_nodes,
        "marker_inventory_dir": str(marker_dir.relative_to(REPO_ROOT)).replace("\\", "/"),
        "marker_inventory_fallback_used": marker_fallback_used,
        "baseline_dir": str(baseline_dir.relative_to(REPO_ROOT)).replace("\\", "/"),
        "baseline_fallback_used": baseline_fallback_used,
    }
    write_json(output_dir / "evidence_compatibility.json", compatibility)
    write_json(output_dir / "live_pytest_nodes.json", {"collected_node_ids": live_nodes, "count": len(live_nodes)})

    marker_nodes = normalize_marker_payload(load_json(marker_dir / "marker_nodes.json", default={"nodes": []}))
    unique_branches = normalize_unique_branch_payload(load_json(branch_context_dir / "unique_branches_by_test.json", default={"tests": []}))
    branch_contexts = normalize_branch_context_payload(load_json(branch_context_dir / "test_branch_contexts.json", default={"tests": []}))
    assertion_findings = normalize_assertion_payload(load_json(assertion_quality_dir / "weak_assertion_scan.json", default={"findings": []}))
    removal_candidates = normalize_assertion_payload(load_json(assertion_quality_dir / "removal_candidates.json", default={"findings": []}))
    duration_map = normalize_duration_payload(load_json(baseline_dir / "duration_report.json", default={}))
    warning_total = load_warning_total(baseline_dir / "warning_report.json")
    node_to_contract, contracts = normalize_contract_payload(load_json(contract_dir / "contract_matrix.json", default=[]))
    duplicate_candidates = load_duplicate_candidates(contract_dir / "duplicate_contract_candidates.json")
    critical_gap_files = set(load_json(mutation_dir / "critical_gaps_after_mutation.json", default={}).get("critical_branch_gap_files", []))
    mutation_join = load_json(mutation_dir / "branch_context_mutation_join.json", default={"rows": []}).get("rows", [])
    removal_with_mutation = {row["node_id"]: row for row in load_json(mutation_dir / "removal_candidates_with_mutation.json", default={"findings": []}).get("findings", [])}
    semantic_unique_map, semantic_shared_map, semantic_candidate_map, semantic_survivor_map, semantic_mixed_map = load_semantic_maps(mutation_dir)
    semantic_results = load_json(mutation_dir / "runtime/semantic/semantic_mutant_results.json")["results"]

    test_files = sorted({Path(split_node_id(node_id)[0]) for node_id in live_nodes})
    ast_cache = {file_path.as_posix(): extract_ast_test_info(REPO_ROOT / file_path) for file_path in test_files}
    for node_id, findings in assertion_findings.items():
        file_path, function_name, _ = split_node_id(node_id)
        info = ast_cache.get(file_path, {}).get(function_name)
        if info:
            info.weak_assertion_patterns.extend(row["pattern"] for row in findings)

    duplicate_groups: dict[tuple[str | None, str | None, tuple[str, ...], str, str], list[str]] = defaultdict(list)
    inventory: list[dict[str, Any]] = []
    protected_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    stale_rows: list[dict[str, Any]] = []

    for node_id in live_nodes:
        file_path, function_name, parameter_id = split_node_id(node_id)
        markers_row = marker_nodes.get(node_id, {})
        markers = sorted(markers_row.get("all_markers", []))
        layer = next((marker for marker in markers if marker in LAYER_MARKERS), "unknown")
        contract_id = node_to_contract.get(node_id)
        branch_row = branch_contexts.get(node_id, {})
        unique_row = unique_branches.get(node_id, {})
        ast_info = ast_cache.get(file_path, {}).get(function_name)
        weak_rows = assertion_findings.get(node_id, [])
        removal_rows = removal_candidates.get(node_id, [])
        duplicate_hint = duplicate_candidates.get(node_id, {})
        automated_scope_ids, automated_scope_survivor_count, automated_scope_uncovered_count = find_automated_scope_memberships(automated_scope_rows, node_id)
        semantic_unique = semantic_unique_map.get(node_id, [])
        semantic_shared = semantic_shared_map.get(node_id, [])
        semantic_survivors = semantic_survivor_map.get(node_id, [])
        semantic_candidates = semantic_candidate_map.get(node_id, [])
        suite_interaction = any(mutant_id in semantic_mixed_map.get(node_id, []) for mutant_id in semantic_candidates if mutant_id not in semantic_shared and mutant_id not in semantic_unique)
        related_files = {row["target_file"] for row in mutation_join if node_id in row.get("candidate_tests", []) or node_id in row.get("branch_context_owner_tests", [])}
        critical_gap = any(path in critical_gap_files for path in related_files)
        stale = node_id in stale_branch_nodes or node_id in stale_weak_assertion_nodes or any(scope in stale_scopes for scope in automated_scope_ids)
        replacement_test, replacement_contract_id = choose_replacement(node_id, contract_id, contracts)
        candidate_status = classify_candidate_status(
            markers=markers,
            contract_id=contract_id,
            unique_branch_count=int(unique_row.get("unique_branch_count", 0)),
            semantic_unique_kill_count=len(semantic_unique),
            semantic_survivors=semantic_survivors,
            suite_interaction=suite_interaction,
            critical_gap=critical_gap,
            stale=stale,
            automated_uncovered=automated_scope_uncovered_count > 0,
            replacement_test=replacement_test,
            duplicate_hint=duplicate_hint.get("classification"),
        )
        protected_traits = sorted(
            set(markers).intersection(PROTECTED_MARKERS)
            | set(markers).intersection(HIGH_RISK_MARKERS)
            | set((contracts.get(contract_id, {}) or {}).get("protected_traits", []))
            | {"stale_evidence"} if stale else set()
        )
        category = duplicate_hint.get("classification") or (removal_rows[0]["decision"] if removal_rows else "not_candidate")
        reason = duplicate_hint.get("reason") or (removal_rows[0]["reason"] if removal_rows else "no_removal_signal")
        evidence_status = "stale" if stale else ("partial" if not markers_row or not branch_row else "complete")
        duration_value = duration_map.get(node_id)
        item = {
            "node_id": node_id,
            "file": file_path,
            "function": function_name,
            "parameter_id": parameter_id,
            "is_parameterized": parameter_id is not None,
            "markers": markers,
            "layer": layer,
            "domain": classify_domain(file_path),
            "contract_id": contract_id,
            "test_body_sha256": ast_info.body_hash if ast_info else None,
            "assertion_fingerprints": ast_info.assertion_fingerprints if ast_info else [],
            "weak_assertion_patterns": sorted(dict.fromkeys((ast_info.weak_assertion_patterns if ast_info else []) + [row["pattern"] for row in weak_rows])),
            "branch_signature": branch_row.get("branch_signature"),
            "executed_branch_count": int(branch_row.get("executed_branch_count", 0)),
            "unique_branch_count": int(unique_row.get("unique_branch_count", 0)),
            "shared_branch_count": max(int(branch_row.get("executed_branch_count", 0)) - int(unique_row.get("unique_branch_count", 0)), 0),
            "no_source_execution": bool(branch_row.get("no_measured_source_execution", False)),
            "semantic_unique_kill_count": len(semantic_unique),
            "semantic_shared_kill_count": len(semantic_shared),
            "related_semantic_survivors": semantic_survivors,
            "semantic_candidate_mutants": semantic_candidates,
            "automated_scope_ids": automated_scope_ids,
            "automated_scope_survivor_count": automated_scope_survivor_count,
            "automated_scope_uncovered_count": automated_scope_uncovered_count,
            "automated_evidence_level": "scope_only",
            "automated_unique_kill_known": False,
            "duration_seconds": duration_value,
            "warning_count": warning_total,
            "protected_traits": sorted(dict.fromkeys(protected_traits)),
            "evidence_status": evidence_status,
            "candidate_status": candidate_status if candidate_status != "stale" else "not_candidate",
        }
        inventory.append(item)
        duplicate_groups[(contract_id, item["branch_signature"], tuple(item["assertion_fingerprints"]), layer, ",".join(markers))].append(node_id)

        if stale:
            stale_rows.append({**item, "stale_reasons": ["stale_node_or_scope"]})
            continue
        if candidate_status == "protected":
            protected_rows.append(item)
            continue

        deletion_action = "remove_parameter_case" if parameter_id else ("manual_review" if candidate_status == "review" else "remove_test_function")
        candidate = {
            "candidate_id": f"candidate-{len(candidate_rows) + 1:03d}",
            "node_id": node_id,
            "deletion_action": deletion_action,
            "target_parameter_id": parameter_id,
            "category": category,
            "reason": reason,
            "replacement_test": replacement_test,
            "replacement_contract_id": replacement_contract_id,
            "unique_branch_count": item["unique_branch_count"],
            "shared_branch_count": item["shared_branch_count"],
            "semantic_unique_kill_count": item["semantic_unique_kill_count"],
            "semantic_shared_kill_count": item["semantic_shared_kill_count"],
            "related_semantic_survivors": item["related_semantic_survivors"],
            "automated_scope_ids": item["automated_scope_ids"],
            "automated_scope_survivor_count": item["automated_scope_survivor_count"],
            "automated_evidence_level": item["automated_evidence_level"],
            "risk": "low" if candidate_status == "low_risk_candidate" else "medium",
            "priority_score": 0,
            "evidence_status": evidence_status,
            "approved_for_deletion": False,
            "review_required": True,
        }
        candidate["priority_score"] = score_candidate({**item, **candidate})
        candidate_rows.append(candidate)

    candidate_node_ids = {row["node_id"] for row in candidate_rows}
    protected_node_ids = {row["node_id"] for row in protected_rows}
    for item in inventory:
        if item["node_id"] in candidate_node_ids or item["node_id"] in protected_node_ids or any(row["node_id"] == item["node_id"] for row in stale_rows):
            continue
        rejected_rows.append({**item, "approved_for_deletion": False, "review_required": False})

    duplicate_clusters = []
    for index, (key, node_ids) in enumerate(sorted(duplicate_groups.items(), key=lambda item: (len(item[1]) * -1, item[0][0] or "")), start=1):
        contract_id, branch_signature, assertion_set, layer, marker_class = key
        if len(node_ids) < 2 or branch_signature in {None, "empty"} or not assertion_set:
            continue
        recommended_owner = sorted(
            node_ids,
            key=lambda node: (
                node not in protected_node_ids,
                "regression" not in marker_nodes.get(node, {}).get("all_markers", []),
                len(node),
            ),
        )[0]
        redundant_candidates = [node for node in node_ids if node != recommended_owner and node in candidate_node_ids]
        duplicate_clusters.append(
            {
                "cluster_id": f"cluster-{index:03d}",
                "contract_id": contract_id,
                "node_ids": node_ids,
                "recommended_owner_test": recommended_owner,
                "redundant_candidates": redundant_candidates,
                "branch_signature_match": True,
                "assertion_match": True,
                "risk": "low" if not any(node in protected_node_ids for node in node_ids) else "high",
                "review_reason": "protected_member_present" if any(node in protected_node_ids for node in node_ids) else "duplicate_contract_branch_assertion_signature",
            }
        )

    followups = []
    for row in semantic_results:
        if row["status"] != "survived":
            continue
        followups.append(
            {
                "mutant_id": row["mutant_id"],
                "scope_id": row["scope_id"],
                "target_file": row["file"],
                "target_symbol": row["target_symbol"],
                "candidate_tests": row.get("candidate_tests", []),
                "non_killing_tests": row.get("non_killing_tests", []),
                "current_contracts": sorted({node_to_contract.get(node) for node in row.get("candidate_tests", []) if node_to_contract.get(node)}),
                "current_evidence": "semantic_survivor",
                "recommended_assertion_strengthening": f"Add stronger observable assertions around {row['target_symbol']}",
                "excluded_from_deletion_candidates": True,
            }
        )

    candidate_rows.sort(key=lambda row: (row["risk"], -row["priority_score"], row["node_id"]))
    low_risk = [row for row in candidate_rows if row["risk"] == "low"]
    manual_review = [row for row in candidate_rows if row["risk"] != "low"]
    batches_dir = output_dir / "batches"
    batches_dir.mkdir(parents=True, exist_ok=True)
    batch_specs = [
        ("batch-01.json", "low_value_mock_passthrough", lambda row: any(hint in row["category"] or hint in row["reason"].lower() for hint in ("mock", "getter", "constructor", "library")), 30),
        ("batch-02.json", "schema_serialization_duplicates", lambda row: any(hint in row["category"] or hint in row["reason"].lower() for hint in ("schema", "serialization", "alias")), 30),
        ("batch-03.json", "compliance_copy_validation_duplicates", lambda row: classify_domain(row["node_id"]) in {"copy", "validation"}, 30),
        ("batch-04.json", "api_service_repository_duplicates", lambda row: classify_domain(row["node_id"]) in {"api", "generation", "archive"}, 30),
        ("batch-05.json", "graph_integration_review", lambda row: classify_domain(row["node_id"]) == "graph", 30),
        ("batch-06-optional.json", "overflow_optional", lambda row: True, 30),
    ]
    batch_plan_rows = []
    assigned: set[str] = set()
    for filename, label, predicate, limit in batch_specs:
        selected = [row for row in candidate_rows if row["node_id"] not in assigned and predicate(row)]
        if filename != "batch-06-optional.json":
            selected = selected[:limit]
        for row in selected:
            assigned.add(row["node_id"])
        payload = {"batch_id": filename.removesuffix(".json"), "label": label, "candidates": selected, "approved_for_deletion": False}
        write_json(batches_dir / filename, payload)
        if filename != "batch-06-optional.json" or selected:
            batch_plan_rows.append({"batch_id": payload["batch_id"], "candidate_count": len(selected), "optional": filename == "batch-06-optional.json"})

    batch_validation_plan = {
        "full_mutation_rerun": False,
        "branch_context_rerun": False,
        "test_deletions": 0,
        "common_steps": ["live collect", "focused tests", "full orchestrator suite once", "warning compare", "git diff check"],
        "semantic_mutation_policy": "rerun only related semantic mutant ids when affected",
        "automated_mutation_policy": "rerun only affected critical scope when semantic/branch evidence is insufficient",
    }

    inventory_payload = {"tests": inventory}
    write_json(output_dir / "test_node_inventory.json", inventory_payload)
    write_json(output_dir / "protected_test_inventory.json", {"tests": protected_rows})
    write_json(output_dir / "deletion_candidate_inventory.json", {"candidates": candidate_rows})
    write_json(output_dir / "rejected_candidate_inventory.json", {"tests": rejected_rows})
    write_json(output_dir / "stale_evidence_inventory.json", {"tests": stale_rows})
    write_json(output_dir / "duplicate_clusters.json", {"clusters": duplicate_clusters})
    write_json(output_dir / "mutation_gap_followups.json", {"followups": followups})
    write_json(output_dir / "batch_plan.json", {"batches": batch_plan_rows})
    write_json(output_dir / "batch_validation_plan.json", batch_validation_plan)

    final_summary = {
        "status": "completed",
        "source_commit": current_commit,
        "live_collected_nodes": len(live_nodes),
        "inventory_node_count": len(inventory),
        "protected_node_count": len(protected_rows),
        "low_risk_candidate_count": len(low_risk),
        "manual_review_candidate_count": len(manual_review),
        "stale_evidence_count": len(stale_rows),
        "duplicate_cluster_count": len(duplicate_clusters),
        "semantic_survivor_count": len(followups),
        "semantic_unique_kill_test_count": sum(1 for item in inventory if item["semantic_unique_kill_count"] > 0),
        "proposed_batch_count": len(batch_plan_rows),
        "proposed_candidate_count": len(candidate_rows),
        "approved_for_deletion_count": 0,
        "full_mutation_rerun": False,
        "branch_context_rerun": False,
        "test_deletions": 0,
    }
    write_json(output_dir / "summary.json", final_summary)
    build_report(final_summary, compatibility, output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
