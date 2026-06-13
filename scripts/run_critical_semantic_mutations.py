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


def git_status_lines(cwd: Path) -> list[str]:
    completed = run_command(["git", "status", "--short"], cwd=cwd)
    if completed.returncode != 0:
        return ["git_status_failed"]
    return [line for line in completed.stdout.splitlines() if line.strip()]


def load_manifest(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    if payload.get("version") != 1 or not isinstance(payload.get("mutants"), list):
        raise SystemExit("unsupported_manifest")
    return payload


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def symbol_span(file_path: Path, symbol: str) -> tuple[int, int]:
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    matches = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol:
            matches.append((node.lineno, node.end_lineno))
    if len(matches) != 1:
        raise SystemExit(f"target_symbol_not_unique:{symbol}")
    return matches[0]


def symbol_text(file_path: Path, symbol: str) -> tuple[str, tuple[int, int]]:
    start, end = symbol_span(file_path, symbol)
    lines = file_path.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[start - 1 : end]), (start, end)


def apply_replace_once_scoped(text: str, old: str, new: str) -> str:
    if old not in text:
        raise SystemExit("stale_patch")
    if text.count(old) != 1:
        raise SystemExit("non_unique_patch_target")
    return text.replace(old, new, 1)


def resolve_candidate_patterns(branch_context_dir: Path, patterns: list[str]) -> list[str]:
    pytest_nodes = load_json(branch_context_dir / "pytest_nodes.json").get("collected_node_ids", [])
    resolved: list[str] = []
    for pattern in patterns:
        if pattern.endswith("::"):
            resolved.extend(node for node in pytest_nodes if node.startswith(pattern))
        else:
            resolved.append(pattern)
    return sorted(dict.fromkeys(resolved))


def live_collect_nodes(patterns: list[str], *, worktree: Path, python_cmd: str) -> list[str]:
    files = sorted({pattern.split("::", 1)[0] for pattern in patterns})
    if not files:
        return []
    command = [python_cmd, "-m", "pytest", *files, "--collect-only", "-q"]
    completed = run_command(command, cwd=worktree, env={**os.environ, "PYTHONPATH": "."}, timeout=300)
    if completed.returncode != 0:
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip().startswith("orchestrator/tests/")]


def filter_to_live_nodes(patterns: list[str], live_nodes: list[str]) -> list[str]:
    resolved: list[str] = []
    for pattern in patterns:
        if pattern.endswith("::"):
            resolved.extend(node for node in live_nodes if node.startswith(pattern))
        elif pattern in live_nodes:
            resolved.append(pattern)
    return sorted(dict.fromkeys(resolved))


def branch_context_candidates(branch_context_dir: Path, mutant: dict[str, Any]) -> list[str]:
    payload = load_json(branch_context_dir / "test_line_contexts.json")
    wanted_file = mutant["file"]
    file_path = resolve_path(mutant["file"])
    _, (start, end) = symbol_text(file_path, mutant["target_symbol"])
    candidates: list[str] = []
    for row in payload.get("tests", []):
        for file_row in row.get("files", []):
            if file_row.get("file") != wanted_file:
                continue
            if any(start <= line <= end for line in file_row.get("lines", [])):
                candidates.append(row["node_id"])
                break
    return sorted(dict.fromkeys(candidates))


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


def apply_mutant(mutant: dict[str, Any], *, worktree: Path) -> dict[str, Any]:
    file_path = worktree / mutant["file"]
    original_text = file_path.read_text(encoding="utf-8")
    current_symbol_text, (start, end) = symbol_text(file_path, mutant["target_symbol"])
    current_file_hash = sha256_file(file_path)
    current_symbol_hash = sha256_text(current_symbol_text)
    if mutant.get("source_file_sha256") and current_file_hash != mutant["source_file_sha256"]:
        return {"status": "stale_patch", "reason": "source_file_hash_mismatch", "current_file_hash": current_file_hash}
    expected_symbol_hash = mutant.get("target_symbol_sha256") or mutant.get("source_sha256")
    if current_symbol_hash != expected_symbol_hash:
        return {"status": "stale_patch", "reason": "target_symbol_hash_mismatch", "current_symbol_hash": current_symbol_hash}
    mutated_symbol = current_symbol_text
    for op in mutant["operations"]:
        if op["type"] != "replace_once":
            return {"status": "error", "reason": "unsupported_operation"}
        mutated_symbol = apply_replace_once_scoped(mutated_symbol, op["old"], op["new"])
    original_lines = original_text.splitlines()
    mutated_lines = original_lines[: start - 1] + mutated_symbol.splitlines() + original_lines[end:]
    mutated_text = "\n".join(mutated_lines) + ("\n" if original_text.endswith("\n") else "")
    file_path.write_text(mutated_text, encoding="utf-8")
    return {
        "status": "applied",
        "file": str(file_path),
        "line_span": [start, end],
        "original_file_hash": current_file_hash,
        "original_symbol_hash": current_symbol_hash,
        "mutated_file_hash": sha256_file(file_path),
        "mutated_symbol_hash": sha256_text(symbol_text(file_path, mutant["target_symbol"])[0]),
        "original_text": original_text,
    }


def restore_file(path: Path, original_text: str) -> bool:
    path.write_text(original_text, encoding="utf-8")
    return path.read_text(encoding="utf-8") == original_text


def run_single_mutant(mutant: dict[str, Any], *, worktree: Path, python_cmd: str, branch_context_dir: Path) -> dict[str, Any]:
    file_path = worktree / mutant["file"]
    branch_candidates = branch_context_candidates(branch_context_dir, mutant)
    configured_candidates = resolve_candidate_patterns(branch_context_dir, mutant.get("candidate_test_patterns", []))
    live_nodes = live_collect_nodes(sorted(dict.fromkeys(configured_candidates + branch_candidates)), worktree=worktree, python_cmd=python_cmd)
    configured_candidates = filter_to_live_nodes(configured_candidates, live_nodes)
    branch_candidates = filter_to_live_nodes(branch_candidates, live_nodes)
    if branch_candidates:
        candidate_tests = sorted(dict.fromkeys(configured_candidates + branch_candidates))
        candidate_resolution_mode = "union_configured_branch_context"
    else:
        candidate_tests = configured_candidates
        candidate_resolution_mode = "configured_fallback"
    result = {
        "mutant_id": mutant["mutant_id"],
        "scope_id": mutant["scope_id"],
        "classification_hint": mutant.get("classification_hint"),
        "description": mutant.get("description"),
        "file": mutant["file"],
        "target_symbol": mutant["target_symbol"],
        "status_on_survive": mutant.get("status_on_survive"),
        "configured_candidate_count": len(configured_candidates),
        "branch_context_candidate_count": len(branch_candidates),
        "resolved_candidate_count": len(candidate_tests),
        "candidate_resolution_mode": candidate_resolution_mode,
        "candidate_tests": candidate_tests,
        "restore_attempted": False,
        "restore_passed": False,
        "git_status_after_restore": [],
    }
    if not candidate_tests:
        result["status"] = "uncovered"
        return result
    baseline = run_pytest(candidate_tests, worktree=worktree, python_cmd=python_cmd)
    result["baseline"] = baseline
    if baseline["status"] != "passed":
        result["status"] = "error"
        return result
    apply_result = apply_mutant(mutant, worktree=worktree)
    for key, value in apply_result.items():
        if key == "original_text":
            continue
        if key == "file":
            result["patched_file"] = value
            continue
        result[key] = value
    if apply_result["status"] != "applied":
        result["status"] = apply_result["status"]
        return result
    original_text = apply_result["original_text"]
    per_test_rows = []
    try:
        compile_run = run_command([python_cmd, "-m", "compileall", mutant["file"]], cwd=worktree, env={**os.environ, "PYTHONPATH": "."})
        result["compile"] = {
            "returncode": compile_run.returncode,
            "stdout": compile_run.stdout,
            "stderr": compile_run.stderr,
        }
        if compile_run.returncode != 0:
            result["status"] = "incompetent"
            return result
        focused = run_pytest(candidate_tests, worktree=worktree, python_cmd=python_cmd)
        result["focused"] = focused
        overall_status = classify_result(focused)
        result["status"] = overall_status
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
        result["killing_tests"] = killing_tests
        result["non_killing_tests"] = non_killing_tests
        result["timeout_tests"] = timeout_tests
        result["error_tests"] = error_tests
        result["per_test_rows"] = per_test_rows
        result["attribution_status"] = "suite_interaction_kill" if overall_status == "killed" and not killing_tests else "complete"
        return result
    finally:
        result["restore_attempted"] = True
        restored = restore_file(file_path, original_text)
        result["restore_passed"] = restored
        result["restored_file_hash"] = sha256_file(file_path)
        result["restored_symbol_hash"] = sha256_text(symbol_text(file_path, mutant["target_symbol"])[0])
        result["git_status_after_restore"] = git_status_lines(worktree)


def write_outputs(output_dir: Path, results: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(row["status"] for row in results)
    kill_rows = []
    unique_by_test: dict[str, list[str]] = defaultdict(list)
    shared_by_test: dict[str, list[str]] = defaultdict(list)
    suite_interaction_kills = 0
    for row in results:
        if row["status"] == "killed":
            if row.get("attribution_status") == "suite_interaction_kill":
                suite_interaction_kills += 1
            if len(row.get("killing_tests", [])) == 1:
                unique_by_test[row["killing_tests"][0]].append(row["mutant_id"])
            elif len(row.get("killing_tests", [])) > 1:
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
    write_json(
        output_dir / "survivor_classification.json",
        {"classifications": [{"mutant_id": row["mutant_id"], "classification": row.get("classification_hint") or "unclassified_survivor", "description": row.get("description"), "file": row.get("file"), "target_symbol": row.get("target_symbol")} for row in results if row["status"] == "survived"]},
    )
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
    if bool(args.all) == bool(args.mutant):
        raise SystemExit("choose_exactly_one_of_all_or_mutant")
    manifest = load_manifest(resolve_path(args.manifest))
    output_dir = resolve_path(args.output_dir)
    worktree = resolve_path(args.worktree)
    branch_context_dir = resolve_path(args.branch_context_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    selected = [mutant for mutant in manifest["mutants"] if args.all or mutant["mutant_id"] == args.mutant]
    results = []
    for mutant in selected:
        try:
            results.append(run_single_mutant(mutant, worktree=worktree, python_cmd=args.python, branch_context_dir=branch_context_dir))
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "mutant_id": mutant["mutant_id"],
                    "scope_id": mutant["scope_id"],
                    "classification_hint": mutant.get("classification_hint"),
                    "description": mutant.get("description"),
                    "file": mutant["file"],
                    "target_symbol": mutant["target_symbol"],
                    "status": "error",
                    "error_message": f"{type(exc).__name__}: {exc}",
                    "restore_attempted": False,
                    "restore_passed": False,
                    "git_status_after_restore": git_status_lines(worktree),
                }
            )
    counts = write_outputs(output_dir, results)
    restore_failures = sum(1 for row in results if row.get("restore_attempted") and not row.get("restore_passed"))
    cleanup_failures = sum(1 for row in results if row.get("git_status_after_restore"))
    result_count = len(results)
    status = "completed"
    if result_count != len(selected) or any(counts[key] for key in ("timeout", "uncovered", "incompetent", "stale_patch", "error")) or restore_failures or cleanup_failures:
        status = "failed"
    summary = {
        "status": status,
        "selected_mutant_count": len(selected),
        "result_count": result_count,
        "counts": counts,
        "source_restore_failures": restore_failures,
        "cleanup_failures": cleanup_failures,
    }
    write_json(output_dir / "semantic_summary.json", summary)
    return 0 if status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
