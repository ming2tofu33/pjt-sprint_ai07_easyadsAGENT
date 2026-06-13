from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data/test_optimization/critical_mutation_v1"
DEFAULT_SCOPE_MANIFEST = REPO_ROOT / "scripts/critical_mutation_scope_v1.json"
DEFAULT_SEMANTIC_MANIFEST = REPO_ROOT / "scripts/critical_semantic_mutants_v1.json"
DEFAULT_BRANCH_CONTEXT_DIR = REPO_ROOT / "data/test_optimization/branch_context_v1"
DEFAULT_ASSERTION_QUALITY_DIR = REPO_ROOT / "data/test_optimization/assertion_quality_v1"
DEFAULT_BASELINE_RESULTS = REPO_ROOT / "data/test_optimization/critical_mutation_v1/baseline_results.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--scope-manifest", default=str(DEFAULT_SCOPE_MANIFEST.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--semantic-manifest", default=str(DEFAULT_SEMANTIC_MANIFEST.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--branch-context-dir", default=str(DEFAULT_BRANCH_CONTEXT_DIR.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--assertion-quality-dir", default=str(DEFAULT_ASSERTION_QUALITY_DIR.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--baseline-results", default=str(DEFAULT_BASELINE_RESULTS.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--worktree")
    parser.add_argument("--runtime-dir")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--mutmut-config")
    parser.add_argument("--scope")
    parser.add_argument("--all-scopes", action="store_true")
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--skip-semantic", action="store_true")
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--self-check", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def run_command(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, env=env)


def normalize_status(value: str | None) -> str:
    mapping = {
        None: "error",
        "killed": "killed",
        "survived": "survived",
        "timeout": "timeout",
        "uncovered": "uncovered",
        "no tests": "uncovered",
        "error": "error",
        "incompetent": "error",
        "suspicious": "error",
        "segfault": "error",
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


def git_head() -> str:
    completed = run_command(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT)
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def runtime_info(python_cmd: str) -> dict[str, Any]:
    info: dict[str, Any] = {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "execution_platform": "WSL2" if "microsoft" in platform.release().lower() else platform.system(),
        "cpu_count": os.cpu_count(),
        "uv_available": shutil.which("uv") is not None,
        "mutmut_available": shutil.which("mutmut") is not None,
    }
    for label, command in (
        ("pytest_version", [python_cmd, "-m", "pytest", "--version"]),
        ("coverage_version", [python_cmd, "-m", "coverage", "--version"]),
        ("mutmut_version", [python_cmd, "-c", "import mutmut; print(getattr(mutmut, '__version__', 'unknown'))"]),
    ):
        completed = run_command(command, cwd=REPO_ROOT)
        info[label] = (completed.stdout.strip() or completed.stderr.strip() or None) if completed.returncode == 0 else None
    return info


def build_exit(status: str, allow_partial: bool) -> int:
    if status == "completed":
        return 0
    if status == "partial":
        return 2 if allow_partial else 1
    if status == "blocked":
        return 3
    return 1


def capture_tool_help(output_dir: Path, python_cmd: str, cwd: Path) -> None:
    help_dir = output_dir / "tool_help"
    help_dir.mkdir(parents=True, exist_ok=True)
    for name, command in (
        ("mutmut_version.txt", [python_cmd, "-m", "mutmut", "--version"]),
        ("mutmut_help.txt", [python_cmd, "-m", "mutmut", "--help"]),
        ("mutmut_run_help.txt", [python_cmd, "-m", "mutmut", "run", "--help"]),
    ):
        completed = run_command(command, cwd=cwd)
        payload = completed.stdout + (("\n[stderr]\n" + completed.stderr) if completed.stderr else "")
        (help_dir / name).write_text(f"exit_code={completed.returncode}\n{payload}", encoding="utf-8")


def read_scope(scope_manifest_path: Path, scope_id: str) -> dict[str, Any]:
    for scope in load_json(scope_manifest_path)["scopes"]:
        if scope["scope_id"] == scope_id:
            return scope
    raise SystemExit(f"unknown_scope:{scope_id}")


def test_files_for_scope(scope: dict[str, Any]) -> list[str]:
    return sorted({pattern.split("::", 1)[0] for pattern in scope["test_node_patterns"]})


def focused_baseline(scope: dict[str, Any], *, worktree: Path, python_cmd: str, output_dir: Path) -> dict[str, Any]:
    command = [python_cmd, "-m", "pytest", *test_files_for_scope(scope), "--strict-markers", "-q", "-m", "not external and not actual"]
    started = time.perf_counter()
    completed = run_command(command, cwd=worktree, env={**os.environ, "PYTHONPATH": "."})
    duration = time.perf_counter() - started
    (output_dir / f"{scope['scope_id']}_baseline.log").write_text(completed.stdout + ("\n[stderr]\n" + completed.stderr if completed.stderr else ""), encoding="utf-8")
    summary_line = next((line for line in reversed((completed.stdout + "\n" + completed.stderr).splitlines()) if " passed" in line or " failed" in line or " skipped" in line), "")
    return {
        "status": "passed" if completed.returncode == 0 else "failed",
        "command": command,
        "returncode": completed.returncode,
        "duration_seconds": round(duration, 2),
        "summary_line": summary_line,
    }


def prepare_runtime(scope_id: str, *, worktree: Path, runtime_dir: Path, python_cmd: str) -> dict[str, Any]:
    command = [
        python_cmd,
        str(REPO_ROOT / "scripts/prepare_mutmut_runtime.py"),
        "--scope",
        scope_id,
        "--worktree",
        str(worktree),
        "--python",
        python_cmd,
        "--output-dir",
        str(runtime_dir),
    ]
    completed = run_command(command, cwd=REPO_ROOT)
    (runtime_dir / "prepare_runtime.log").write_text(completed.stdout + ("\n[stderr]\n" + completed.stderr if completed.stderr else ""), encoding="utf-8")
    scope_preflight = load_json(runtime_dir / "scope_preflight.json")
    import_preflight = load_json(runtime_dir / "import_preflight.json")
    return {
        "returncode": completed.returncode,
        "scope_preflight": scope_preflight,
        "import_preflight": import_preflight,
    }


def run_mutmut(scope: dict[str, Any], *, worktree: Path, python_cmd: str, output_dir: Path) -> dict[str, Any]:
    shutil.copy2(worktree / ".mutation-runtime/setup.cfg", worktree / "setup.cfg")
    started = time.perf_counter()
    run_completed = run_command([python_cmd, "-m", "mutmut", "run"], cwd=worktree, env={**os.environ, "PYTHONPATH": "."})
    duration = time.perf_counter() - started
    (output_dir / f"{scope['scope_id']}_mutmut_run.log").write_text(run_completed.stdout + ("\n[stderr]\n" + run_completed.stderr if run_completed.stderr else ""), encoding="utf-8")
    stats_completed = run_command([python_cmd, "-m", "mutmut", "export-cicd-stats"], cwd=worktree, env={**os.environ, "PYTHONPATH": "."})
    (output_dir / f"{scope['scope_id']}_mutmut_export.log").write_text(stats_completed.stdout + ("\n[stderr]\n" + stats_completed.stderr if stats_completed.stderr else ""), encoding="utf-8")
    results_completed = run_command([python_cmd, "-m", "mutmut", "results"], cwd=worktree, env={**os.environ, "PYTHONPATH": "."})
    results_lines = [line.strip() for line in results_completed.stdout.splitlines() if line.strip()]
    stats_path = worktree / "mutants/mutmut-cicd-stats.json"
    stats = load_json(stats_path) if stats_path.exists() else {}
    counts = Counter()
    counts["killed"] = int(stats.get("killed", 0))
    counts["survived"] = int(stats.get("survived", 0))
    counts["timeout"] = int(stats.get("timeout", 0))
    counts["error"] = int(stats.get("suspicious", 0)) + int(stats.get("segfault", 0))
    counts["uncovered"] = int(stats.get("no_tests", 0))
    mutants = []
    for line in results_lines:
        mutant_id, raw_status = line.split(": ", 1)
        mutants.append({"mutant_id": mutant_id, "status": normalize_status(raw_status), "raw_status": raw_status})
    return {
        "status": "completed" if run_completed.returncode == 0 and stats_completed.returncode == 0 else "failed",
        "duration_seconds": round(duration, 2),
        "run_returncode": run_completed.returncode,
        "export_returncode": stats_completed.returncode,
        "results_returncode": results_completed.returncode,
        "stats": stats,
        "counts": dict(counts),
        "mutants": mutants,
        "scores": compute_scores(counts),
    }


def write_pending_artifacts(output_dir: Path, semantic_manifest: dict[str, Any], branch_summary: dict[str, Any], removal_candidates: dict[str, Any], resolved_scopes: list[dict[str, Any]]) -> None:
    write_json(output_dir / "semantic_mutants.json", semantic_manifest)
    write_json(output_dir / "semantic_mutant_results.json", {"results": []})
    write_json(output_dir / "mutant_test_kill_matrix.json", {"rows": []})
    write_json(output_dir / "unique_kills_by_test.json", {"tests": []})
    write_json(output_dir / "surviving_mutants.json", {"mutants": []})
    write_json(output_dir / "survivor_classification.json", {"classifications": []})
    write_json(output_dir / "uncovered_mutants.json", {"mutants": []})
    write_json(output_dir / "timeout_mutants.json", {"mutants": []})
    write_json(output_dir / "error_mutants.json", {"mutants": []})
    write_json(output_dir / "branch_context_mutation_join.json", {"status": "pending_runtime", "scope_ids": [scope["scope_id"] for scope in resolved_scopes]})
    write_json(output_dir / "critical_gaps_after_mutation.json", {"status": "pending_runtime", "files": branch_summary.get("critical_missing_branch_count")})
    write_json(
        output_dir / "removal_candidates_with_mutation.json",
        {"findings": [{**finding, "mutation_status": "pending_runtime", "mutation_protected": False} for finding in removal_candidates["findings"]]},
    )


def run_self_check() -> int:
    assert normalize_status("no tests") == "uncovered"
    counts = Counter({"killed": 3, "survived": 1, "timeout": 1, "error": 1})
    scores = compute_scores(counts)
    assert round(scores["executable_mutation_score"], 4) == 0.75
    assert round(scores["strict_mutation_score"], 4) == 0.5
    assert classify_survivor({"classification_hint": "workspace_scope_removed"}) == "workspace_scope_removed"
    print("self_check=ok")
    return 0


def main() -> int:
    args = parse_args()
    if args.self_check:
        return run_self_check()
    if not args.pilot and not args.scope and not args.all_scopes:
        output_dir = resolve_path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        write_json(output_dir / "summary.json", {"status": "blocked", "reason": "execution_mode_required", "source_commit": git_head()})
        return 3

    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    branch_summary = load_json(resolve_path(args.branch_context_dir) / "summary.json")
    removal_candidates = load_json(resolve_path(args.assertion_quality_dir) / "removal_candidates.json")
    semantic_manifest = load_json(resolve_path(args.semantic_manifest))
    scope_manifest = load_json(resolve_path(args.scope_manifest))
    all_scopes = scope_manifest["scopes"]
    selected_scopes = [read_scope(resolve_path(args.scope_manifest), args.scope)] if args.scope else ([read_scope(resolve_path(args.scope_manifest), "quality-ocr")] if args.pilot else all_scopes)
    worktree = resolve_path(args.worktree) if args.worktree else REPO_ROOT
    runtime_root = resolve_path(args.runtime_dir) if args.runtime_dir else output_dir / "runtime"
    python_cmd = args.python
    env_info = runtime_info(python_cmd)
    capture_tool_help(output_dir, python_cmd, worktree)

    if not env_info.get("mutmut_version"):
        write_json(output_dir / "summary.json", {"status": "blocked", "reason": "mutation_runtime_unavailable", "source_commit": git_head()})
        return 3

    write_json(output_dir / "environment.json", env_info)
    write_json(output_dir / "scope_manifest_resolved.json", {"version": 1, "scopes": all_scopes})
    write_json(output_dir / "tool_configuration.json", {"mutation_tool": "mutmut", "python": python_cmd, "worktree": str(worktree)})
    write_json(output_dir / "baseline_results.json", {"branch_context_summary": branch_summary})
    write_pending_artifacts(output_dir, semantic_manifest, branch_summary, removal_candidates, all_scopes)

    scope_rows = []
    completed_scopes = []
    pending_scopes = [scope["scope_id"] for scope in all_scopes if scope["scope_id"] not in {item["scope_id"] for item in selected_scopes}]
    overall_counts = Counter()

    for scope in selected_scopes:
        scope_runtime_dir = runtime_root / scope["scope_id"]
        prepared = prepare_runtime(scope["scope_id"], worktree=worktree, runtime_dir=scope_runtime_dir, python_cmd=python_cmd)
        if prepared["scope_preflight"]["errors"] or prepared["import_preflight"]["status"] != "passed":
            scope_rows.append(
                {
                    "scope_id": scope["scope_id"],
                    "status": "blocked",
                    "reason": "runtime_preflight_failed",
                    "scope_preflight": prepared["scope_preflight"],
                    "import_preflight": prepared["import_preflight"],
                }
            )
            pending_scopes.append(scope["scope_id"])
            continue
        baseline = focused_baseline(scope, worktree=worktree, python_cmd=python_cmd, output_dir=output_dir)
        if baseline["status"] != "passed":
            scope_rows.append({"scope_id": scope["scope_id"], "status": "blocked", "reason": "linux_baseline_failed", "baseline": baseline})
            pending_scopes.append(scope["scope_id"])
            continue
        mutation = run_mutmut(scope, worktree=worktree, python_cmd=python_cmd, output_dir=output_dir)
        completed_scopes.append(scope["scope_id"])
        overall_counts.update(mutation["counts"])
        scope_rows.append(
            {
                "scope_id": scope["scope_id"],
                "status": mutation["status"],
                "baseline": baseline,
                "mutation": mutation,
                "runtime_dir": str(scope_runtime_dir),
            }
        )
        if args.pilot:
            break

    automated_generated = sum(int(row["mutation"]["stats"].get("total", 0)) for row in scope_rows if row.get("mutation"))
    for scope in selected_scopes:
        if scope["scope_id"] not in completed_scopes and scope["scope_id"] not in pending_scopes:
            pending_scopes.append(scope["scope_id"])
    write_json(output_dir / "automated_scope_summary.json", {"scopes": scope_rows})
    write_json(
        output_dir / "automated_mutants.json",
        {
            "scopes": [
                {
                    "scope_id": row["scope_id"],
                    "stats": row["mutation"]["stats"],
                    "result_lines": row["mutation"]["mutants"],
                }
                for row in scope_rows
                if row.get("mutation")
            ]
        },
    )
    write_json(output_dir / "mutation_scores.json", {"status": "completed", **compute_scores(overall_counts)})

    status = "completed" if args.all_scopes and not pending_scopes else ("partial" if completed_scopes else "blocked")
    summary = {
        "status": status,
        "source_commit": git_head(),
        "python_version": env_info.get("python_version"),
        "mutation_tool": "mutmut",
        "mutation_tool_version": env_info.get("mutmut_version"),
        "execution_platform": env_info.get("execution_platform"),
        "baseline_collected_nodes": branch_summary.get("baseline_collected_nodes", 0),
        "baseline_passed": 0,
        "baseline_skipped": 0,
        "scope_count": len(all_scopes),
        "source_file_count": sum(len(scope["source_files"]) for scope in all_scopes),
        "target_function_count": sum(len(scope["functions"]) for scope in all_scopes),
        "automated_generated": automated_generated,
        "automated_killed": overall_counts["killed"],
        "automated_survived": overall_counts["survived"],
        "automated_timeout": overall_counts["timeout"],
        "automated_uncovered": overall_counts["uncovered"],
        "automated_error": overall_counts["error"],
        **compute_scores(overall_counts),
        "semantic_mutant_count": len(semantic_manifest["mutants"]),
        "semantic_killed": 0,
        "semantic_survived": 0,
        "tests_with_unique_kills": 0,
        "tests_with_shared_kills": 0,
        "covered_but_survived": overall_counts["survived"],
        "uncovered_mutant_count": overall_counts["uncovered"],
        "removal_candidates_protected_by_unique_kill": 0,
        "automatic_deletions": 0,
        "completed_scopes": completed_scopes,
        "pending_scopes": pending_scopes,
    }
    write_json(output_dir / "summary.json", summary)
    (output_dir / "report.md").write_text(f"# Critical Mutation Baseline v1\n\n- status: `{status}`\n", encoding="utf-8")
    return build_exit(status, args.allow_partial)


if __name__ == "__main__":
    raise SystemExit(main())
