from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "scripts/critical_semantic_mutants_v1.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data/test_optimization/critical_mutation_v1/runtime/semantic"
DEFAULT_BRANCH_CONTEXT_DIR = REPO_ROOT / "data/test_optimization/branch_context_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--worktree", default=".")
    parser.add_argument("--python", default="python")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--branch-context-dir", default=str(DEFAULT_BRANCH_CONTEXT_DIR.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--mutant")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--self-check", action="store_true")
    return parser.parse_args()


def resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_command(command: list[str], *, cwd: Path, env: dict[str, str] | None = None, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, env=env, timeout=timeout)


def load_manifest(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    if payload.get("version") != 1:
        raise SystemExit("unsupported_manifest_version")
    return payload


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def symbol_span(file_path: Path, symbol: str) -> tuple[int, int]:
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    spans = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol:
            spans.append((node.lineno, node.end_lineno))
    if len(spans) != 1:
        raise SystemExit(f"target_symbol_not_unique:{symbol}")
    return spans[0]


def apply_replace_once_scoped(text: str, old: str, new: str) -> str:
    if old not in text:
        raise SystemExit("stale_patch")
    if text.count(old) != 1:
        raise SystemExit("non_unique_patch_target")
    return text.replace(old, new, 1)


def apply_mutant(mutant: dict[str, Any], *, worktree: Path) -> dict[str, Any]:
    file_path = worktree / mutant["file"]
    original_text = file_path.read_text(encoding="utf-8")
    start, end = symbol_span(file_path, mutant["target_symbol"])
    lines = original_text.splitlines()
    symbol_text = "\n".join(lines[start - 1 : end])
    symbol_hash = sha256_text(symbol_text)
    if symbol_hash != mutant["source_sha256"]:
        return {"status": "stale_patch", "file": str(file_path), "source_sha256": symbol_hash}
    mutated_symbol = symbol_text
    for op in mutant["operations"]:
        if op["type"] != "replace_once":
            return {"status": "error", "reason": "unsupported_operation"}
        mutated_symbol = apply_replace_once_scoped(mutated_symbol, op["old"], op["new"])
    mutated_lines = lines[: start - 1] + mutated_symbol.splitlines() + lines[end:]
    file_path.write_text("\n".join(mutated_lines) + ("\n" if original_text.endswith("\n") else ""), encoding="utf-8")
    return {"status": "applied", "file": str(file_path), "original_hash": sha256_file(file_path)}


def restore_file(path: Path, original_text: str) -> bool:
    path.write_text(original_text, encoding="utf-8")
    return path.read_text(encoding="utf-8") == original_text


def branch_context_candidates(branch_context_dir: Path, mutant: dict[str, Any]) -> list[str]:
    payload = load_json(branch_context_dir / "test_line_contexts.json")
    wanted_file = mutant["file"]
    candidates: list[str] = []
    for row in payload.get("tests", []):
        for file_row in row.get("files", []):
            if file_row.get("file") != wanted_file:
                continue
            if any(mutant.get("target_line_hint", 0) == line or mutant.get("target_line_hint") is None for line in file_row.get("lines", [])):
                candidates.append(row["node_id"])
                break
    return sorted(dict.fromkeys(candidates))


def resolve_candidate_patterns(branch_context_dir: Path, patterns: list[str]) -> list[str]:
    pytest_nodes = load_json(branch_context_dir / "pytest_nodes.json").get("collected_node_ids", [])
    resolved: list[str] = []
    for pattern in patterns:
        if pattern.endswith("::"):
            resolved.extend(node for node in pytest_nodes if node.startswith(pattern))
        else:
            resolved.append(pattern)
    return sorted(dict.fromkeys(resolved))


def run_pytest(nodes: list[str], *, worktree: Path, python_cmd: str, timeout_seconds: int = 300) -> dict[str, Any]:
    if not nodes:
        return {"status": "uncovered", "command": []}
    command = [python_cmd, "-m", "pytest", *nodes, "--strict-markers", "-q", "-m", "not external and not actual"]
    started = time.perf_counter()
    try:
        completed = run_command(command, cwd=worktree, env={**os.environ, "PYTHONPATH": "."}, timeout=timeout_seconds)
        duration = time.perf_counter() - started
        return {
            "status": "passed" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "command": command,
            "duration_seconds": round(duration, 2),
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "returncode": None,
            "command": command,
            "duration_seconds": timeout_seconds,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
        }


def classify_result(test_run: dict[str, Any]) -> str:
    if test_run["status"] == "timeout":
        return "timeout"
    joined = f"{test_run.get('stdout', '')}\n{test_run.get('stderr', '')}"
    if any(marker in joined for marker in ("SyntaxError", "ImportError", "ModuleNotFoundError", "TypeError", "ValueError", "ProgrammingError")):
        return "incompetent"
    if test_run["status"] == "passed":
        return "survived"
    return "killed"


def run_single_mutant(mutant: dict[str, Any], *, worktree: Path, python_cmd: str, branch_context_dir: Path, output_dir: Path) -> dict[str, Any]:
    file_path = worktree / mutant["file"]
    original_text = file_path.read_text(encoding="utf-8")
    configured_candidates = mutant.get("candidate_test_patterns") or branch_context_candidates(branch_context_dir, mutant)
    candidate_tests = resolve_candidate_patterns(branch_context_dir, configured_candidates)
    if not candidate_tests:
        return {"mutant_id": mutant["mutant_id"], "scope_id": mutant["scope_id"], "status": "uncovered", "candidate_tests": []}
    baseline = run_pytest(candidate_tests, worktree=worktree, python_cmd=python_cmd)
    if baseline["status"] != "passed":
        return {"mutant_id": mutant["mutant_id"], "scope_id": mutant["scope_id"], "status": "error", "candidate_tests": candidate_tests, "baseline": baseline}
    apply_result = apply_mutant(mutant, worktree=worktree)
    if apply_result["status"] != "applied":
        return {"mutant_id": mutant["mutant_id"], "scope_id": mutant["scope_id"], "status": apply_result["status"], "candidate_tests": candidate_tests}
    per_test_rows = []
    try:
        compile_run = run_command([python_cmd, "-m", "compileall", mutant["file"]], cwd=worktree, env={**os.environ, "PYTHONPATH": "."})
        if compile_run.returncode != 0:
            return {"mutant_id": mutant["mutant_id"], "scope_id": mutant["scope_id"], "status": "incompetent", "candidate_tests": candidate_tests, "compile_stdout": compile_run.stdout, "compile_stderr": compile_run.stderr}
        focused = run_pytest(candidate_tests, worktree=worktree, python_cmd=python_cmd)
        overall_status = classify_result(focused)
        killing_tests: list[str] = []
        non_killing_tests: list[str] = []
        timeout_tests: list[str] = []
        error_tests: list[str] = []
        if overall_status == "killed":
            for node in candidate_tests:
                single = run_pytest([node], worktree=worktree, python_cmd=python_cmd, timeout_seconds=120)
                single_status = classify_result(single)
                per_test_rows.append({"test_node_id": node, "status": single_status})
                if single_status == "killed":
                    killing_tests.append(node)
                elif single_status == "timeout":
                    timeout_tests.append(node)
                elif single_status in {"error", "incompetent"}:
                    error_tests.append(node)
                else:
                    non_killing_tests.append(node)
        else:
            non_killing_tests = list(candidate_tests)
        attribution_status = "suite_interaction_kill" if overall_status == "killed" and not killing_tests else "complete"
        return {
            "mutant_id": mutant["mutant_id"],
            "scope_id": mutant["scope_id"],
            "status": overall_status,
            "candidate_tests": candidate_tests,
            "killing_tests": killing_tests,
            "non_killing_tests": non_killing_tests,
            "timeout_tests": timeout_tests,
            "error_tests": error_tests,
            "attribution_status": attribution_status,
            "per_test_rows": per_test_rows,
        }
    finally:
        restored = restore_file(file_path, original_text)
        if not restored:
            raise SystemExit(f"restore_failed:{mutant['mutant_id']}")


def write_outputs(output_dir: Path, results: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(row["status"] for row in results)
    kill_rows = []
    unique_by_test: dict[str, list[str]] = defaultdict(list)
    shared_by_test: dict[str, list[str]] = defaultdict(list)
    suite_interaction_kills = 0
    for row in results:
        if row["status"] == "killed":
            if row["attribution_status"] == "suite_interaction_kill":
                suite_interaction_kills += 1
            if len(row["killing_tests"]) == 1:
                unique_by_test[row["killing_tests"][0]].append(row["mutant_id"])
            elif len(row["killing_tests"]) > 1:
                for test_node in row["killing_tests"]:
                    shared_by_test[test_node].append(row["mutant_id"])
        kill_rows.append(
            {
                "mutant_id": row["mutant_id"],
                "scope_id": row["scope_id"],
                "overall_status": row["status"],
                "candidate_tests": row.get("candidate_tests", []),
                "killing_tests": row.get("killing_tests", []),
                "non_killing_tests": row.get("non_killing_tests", []),
                "timeout_tests": row.get("timeout_tests", []),
                "error_tests": row.get("error_tests", []),
                "attribution_status": row.get("attribution_status", "incomplete"),
            }
        )
    write_json(output_dir / "semantic_mutant_results.json", {"results": results})
    write_json(output_dir / "mutant_test_kill_matrix.json", {"rows": kill_rows})
    write_json(output_dir / "unique_kills_by_test.json", {"tests": [{"test_node_id": key, "unique_mutant_ids": value, "unique_kill_count": len(value)} for key, value in sorted(unique_by_test.items())]})
    write_json(output_dir / "shared_kills_by_test.json", {"tests": [{"test_node_id": key, "shared_mutant_ids": value, "shared_kill_count": len(value)} for key, value in sorted(shared_by_test.items())]})
    write_json(output_dir / "surviving_mutants.json", {"mutants": [row for row in results if row["status"] == "survived"]})
    write_json(output_dir / "survivor_classification.json", {"classifications": [{"mutant_id": row["mutant_id"], "classification": row.get("classification_hint", "unclassified_survivor")} for row in results if row["status"] == "survived"]})
    write_json(output_dir / "uncovered_mutants.json", {"mutants": [row for row in results if row["status"] == "uncovered"]})
    write_json(output_dir / "timeout_mutants.json", {"mutants": [row for row in results if row["status"] == "timeout"]})
    write_json(output_dir / "error_mutants.json", {"mutants": [row for row in results if row["status"] in {"error", "incompetent", "stale_patch"}]})
    return {
        "killed": counts["killed"],
        "survived": counts["survived"],
        "timeout": counts["timeout"],
        "uncovered": counts["uncovered"],
        "incompetent": counts["incompetent"],
        "stale_patch": counts["stale_patch"],
        "error": counts["error"],
        "tests_with_unique_kills": len(unique_by_test),
        "tests_with_shared_kills": len(shared_by_test),
        "suite_interaction_kills": suite_interaction_kills,
    }


def run_self_check() -> int:
    text = "alpha\nbeta\n"
    assert apply_replace_once_scoped(text, "beta", "gamma") == "alpha\ngamma\n"
    print("self_check=ok")
    return 0


def main() -> int:
    args = parse_args()
    if args.self_check:
        return run_self_check()
    manifest = load_manifest(resolve_path(args.manifest))
    output_dir = resolve_path(args.output_dir)
    worktree = resolve_path(args.worktree)
    branch_context_dir = resolve_path(args.branch_context_dir)
    selected = []
    for mutant in manifest["mutants"]:
        if args.mutant and mutant["mutant_id"] != args.mutant:
            continue
        if args.all or args.mutant:
            selected.append(mutant)
    if not selected:
        raise SystemExit("choose --all or --mutant")
    results = []
    for mutant in selected:
        results.append(run_single_mutant(mutant, worktree=worktree, python_cmd=args.python, branch_context_dir=branch_context_dir, output_dir=output_dir))
    counts = write_outputs(output_dir, results)
    summary = {
        "status": "completed",
        "counts": counts,
        "source_restore_failures": 0,
    }
    write_json(output_dir / "semantic_summary.json", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
