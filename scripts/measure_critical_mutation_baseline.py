from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data/test_optimization/critical_mutation_v1"
DEFAULT_SCOPE_MANIFEST = REPO_ROOT / "scripts/critical_mutation_scope_v1.json"
DEFAULT_SEMANTIC_MANIFEST = REPO_ROOT / "scripts/critical_semantic_mutants_v1.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--scope-manifest", default=str(DEFAULT_SCOPE_MANIFEST.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--semantic-manifest", default=str(DEFAULT_SEMANTIC_MANIFEST.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--self-check", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any] | list[Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def normalize_status(value: str | None) -> str:
    mapping = {
        None: "error",
        "killed": "killed",
        "survived": "survived",
        "timeout": "timeout",
        "uncovered": "uncovered",
        "error": "error",
        "incompetent": "error",
        "suspicious": "error",
    }
    return mapping.get(value, "error")


def compute_scores(counts: Counter[str]) -> dict[str, float]:
    executable = counts["killed"] + counts["survived"]
    strict = executable + counts["timeout"] + counts["error"]
    return {
        "executable_mutation_score": 0.0 if executable == 0 else counts["killed"] / executable,
        "strict_mutation_score": 0.0 if strict == 0 else counts["killed"] / strict,
    }


def classify_survivor(mutant: dict[str, Any]) -> str:
    hint = mutant.get("classification_hint")
    return hint or "unclassified_survivor"


def unique_kill_summary(kill_matrix: list[dict[str, Any]]) -> dict[str, int]:
    killed_by_test: dict[str, set[str]] = defaultdict(set)
    shared_tests: set[str] = set()
    for row in kill_matrix:
        tests = row.get("killing_tests", [])
        if len(tests) == 1:
            killed_by_test[tests[0]].add(row["mutant_id"])
        elif len(tests) > 1:
            shared_tests.update(tests)
    return {
        "tests_with_unique_kills": sum(1 for kills in killed_by_test.values() if kills),
        "tests_with_shared_kills": len(shared_tests),
    }


def run_command(command: list[str]) -> tuple[int, str, str]:
    completed = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True)
    return completed.returncode, completed.stdout, completed.stderr


def runtime_info() -> dict[str, Any]:
    info: dict[str, Any] = {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "execution_platform": "WSL2" if "microsoft" in platform.release().lower() else platform.system(),
        "cpu_count": os.cpu_count(),
        "uv_available": shutil.which("uv") is not None,
        "mutmut_available": shutil.which("mutmut") is not None,
    }
    for label, command in (
        ("pytest_version", [sys.executable, "-m", "pytest", "--version"]),
        ("coverage_version", [sys.executable, "-m", "coverage", "--version"]),
        ("mutmut_version", ["mutmut", "--version"]),
    ):
        try:
            code, stdout, stderr = run_command(command)
        except FileNotFoundError:
            info[label] = None
            continue
        info[label] = stdout.strip() or stderr.strip() or (None if code != 0 else "")
    return info


def resolve_scope_manifest(scope_manifest: dict[str, Any], contract_matrix: list[dict[str, Any]], critical_gaps: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    contracts_by_id = {item["contract_id"]: item for item in contract_matrix}
    gap_files = {item["file"] for item in critical_gaps.get("files", [])}
    resolved = []
    source_files = set()
    target_functions = 0
    for scope in scope_manifest["scopes"]:
        contract_details = [contracts_by_id[contract_id] for contract_id in scope["contracts"] if contract_id in contracts_by_id]
        resolved_scope = {
            **scope,
            "contract_details": contract_details,
            "critical_gap_files": sorted(path for path in scope["source_files"] if path in gap_files),
            "source_file_count": len(scope["source_files"]),
            "target_function_count": len(scope["functions"]),
        }
        resolved.append(resolved_scope)
        source_files.update(scope["source_files"])
        target_functions += len(scope["functions"])
    summary = {
        "scope_count": len(resolved),
        "source_file_count": len(source_files),
        "target_function_count": target_functions,
    }
    return resolved, summary


def build_blocked_payload(output_dir: Path, reason: str, env_info: dict[str, Any], scope_summary: dict[str, Any]) -> int:
    summary = {
        "status": "blocked",
        "reason": reason,
        "source_commit": git_head(),
        "python_version": env_info.get("python_version"),
        "mutation_tool": "mutmut",
        "mutation_tool_version": env_info.get("mutmut_version"),
        "execution_platform": env_info.get("execution_platform"),
        "baseline_collected_nodes": 0,
        "baseline_passed": 0,
        "baseline_skipped": 0,
        **scope_summary,
        "automated_generated": 0,
        "automated_killed": 0,
        "automated_survived": 0,
        "automated_timeout": 0,
        "automated_uncovered": 0,
        "automated_error": 0,
        "executable_mutation_score": 0.0,
        "strict_mutation_score": 0.0,
        "semantic_mutant_count": 0,
        "semantic_killed": 0,
        "semantic_survived": 0,
        "tests_with_unique_kills": 0,
        "tests_with_shared_kills": 0,
        "covered_but_survived": 0,
        "uncovered_mutant_count": 0,
        "removal_candidates_protected_by_unique_kill": 0,
        "automatic_deletions": 0,
    }
    write_json(output_dir / "summary.json", summary)
    return 0


def git_head() -> str:
    code, stdout, _ = run_command(["git", "rev-parse", "HEAD"])
    if code != 0:
        return "unknown"
    return stdout.strip()


def capture_tool_help(output_dir: Path) -> None:
    help_dir = output_dir / "tool_help"
    help_dir.mkdir(parents=True, exist_ok=True)
    for name, command in (
        ("mutmut_version.txt", ["mutmut", "--version"]),
        ("mutmut_help.txt", ["mutmut", "--help"]),
        ("mutmut_run_help.txt", ["mutmut", "run", "--help"]),
    ):
        try:
            code, stdout, stderr = run_command(command)
            payload = stdout + (("\n[stderr]\n" + stderr) if stderr else "")
        except FileNotFoundError:
            code = 127
            payload = "command not found\n"
        (help_dir / name).write_text(f"exit_code={code}\n{payload}", encoding="utf-8")


def run_self_check() -> int:
    assert normalize_status("incompetent") == "error"
    assert normalize_status("killed") == "killed"
    counts = Counter({"killed": 3, "survived": 1, "timeout": 1, "error": 1})
    scores = compute_scores(counts)
    assert round(scores["executable_mutation_score"], 4) == 0.75
    assert round(scores["strict_mutation_score"], 4) == 0.5
    summary = unique_kill_summary(
        [
            {"mutant_id": "m1", "killing_tests": ["t1"]},
            {"mutant_id": "m2", "killing_tests": ["t1", "t2"]},
            {"mutant_id": "m3", "killing_tests": ["t3"]},
        ]
    )
    assert summary["tests_with_unique_kills"] == 2
    assert summary["tests_with_shared_kills"] == 2
    assert classify_survivor({"classification_hint": "workspace_scope_removed"}) == "workspace_scope_removed"
    print("self_check=ok")
    return 0


def main() -> int:
    args = parse_args()
    if args.self_check:
        return run_self_check()

    output_dir = resolve_path(args.output_dir)
    scope_manifest = load_json(resolve_path(args.scope_manifest))
    semantic_manifest = load_json(resolve_path(args.semantic_manifest))
    contract_matrix = load_json(REPO_ROOT / "data/test_optimization/layer_contract_dedup_v1/contract_matrix.json")
    critical_gaps = load_json(REPO_ROOT / "data/test_optimization/branch_context_v1/critical_branch_gaps.json")
    removal_candidates = load_json(REPO_ROOT / "data/test_optimization/assertion_quality_v1/removal_candidates.json")
    marker_summary = load_json(REPO_ROOT / "data/test_optimization/marker_taxonomy/marker_summary.json")
    branch_summary = load_json(REPO_ROOT / "data/test_optimization/branch_context_v1/summary.json")

    resolved_scopes, scope_summary = resolve_scope_manifest(scope_manifest, contract_matrix, critical_gaps)
    env_info = runtime_info()
    capture_tool_help(output_dir)

    write_json(output_dir / "environment.json", env_info)
    write_json(output_dir / "scope_manifest_resolved.json", {"version": 1, "scopes": resolved_scopes})
    write_json(
        output_dir / "tool_configuration.json",
        {
            "mutation_tool": "mutmut",
            "selection": ["-m", "not external and not actual", "--strict-markers", "-q"],
            "source_paths": sorted({path for scope in resolved_scopes for path in scope["source_files"]}),
        },
    )
    write_json(
        output_dir / "baseline_results.json",
        {
            "marker_summary": marker_summary,
            "branch_context_summary": branch_summary,
            "baseline_collected_nodes": branch_summary.get("baseline_collected_nodes"),
        },
    )
    write_json(output_dir / "semantic_mutants.json", semantic_manifest)
    write_json(
        output_dir / "branch_context_mutation_join.json",
        {
            "status": "pending_runtime",
            "critical_gap_files": critical_gaps.get("files", []),
            "scope_ids": [scope["scope_id"] for scope in resolved_scopes],
        },
    )
    write_json(
        output_dir / "removal_candidates_with_mutation.json",
        {
            "findings": [
                {**finding, "mutation_status": "pending_runtime", "mutation_protected": False}
                for finding in removal_candidates["findings"]
            ]
        },
    )
    write_json(output_dir / "critical_gaps_after_mutation.json", {"status": "pending_runtime", "files": critical_gaps.get("files", [])})
    write_json(output_dir / "automated_mutants.json", {"mutants": []})
    write_json(output_dir / "automated_scope_summary.json", {"scopes": [], "status": "pending_runtime"})
    write_json(output_dir / "mutation_scores.json", {"status": "pending_runtime", **compute_scores(Counter())})
    write_json(output_dir / "semantic_mutant_results.json", {"results": []})
    write_json(output_dir / "mutant_test_kill_matrix.json", {"rows": []})
    write_json(output_dir / "unique_kills_by_test.json", {"tests": []})
    write_json(output_dir / "surviving_mutants.json", {"mutants": []})
    write_json(output_dir / "survivor_classification.json", {"classifications": []})
    write_json(output_dir / "uncovered_mutants.json", {"mutants": []})
    write_json(output_dir / "timeout_mutants.json", {"mutants": []})
    write_json(output_dir / "error_mutants.json", {"mutants": []})
    (output_dir / "report.md").write_text("# Critical Mutation Baseline v1\n\n- status: `blocked`\n", encoding="utf-8")

    if not env_info.get("mutmut_available"):
        return build_blocked_payload(output_dir, "mutation_runtime_unavailable", env_info, scope_summary)
    return build_blocked_payload(output_dir, "automated_execution_not_started", env_info, scope_summary)


if __name__ == "__main__":
    raise SystemExit(main())
