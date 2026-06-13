from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from scripts._mutmut_result_adapter import collect_details, load_stats, parse_results, run_command as run_mutmut_command, summarize
except ModuleNotFoundError:
    from _mutmut_result_adapter import collect_details, load_stats, parse_results, run_command as run_mutmut_command, summarize


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data/test_optimization/critical_mutation_v1"
DEFAULT_SCOPE_MANIFEST = REPO_ROOT / "scripts/critical_mutation_scope_v1.json"
DEFAULT_SEMANTIC_MANIFEST = REPO_ROOT / "scripts/critical_semantic_mutants_v1.json"
DEFAULT_BRANCH_CONTEXT_DIR = REPO_ROOT / "data/test_optimization/branch_context_v1"
DEFAULT_ASSERTION_QUALITY_DIR = REPO_ROOT / "data/test_optimization/assertion_quality_v1"
FINAL_OUTPUT_DIR = DEFAULT_OUTPUT_DIR.resolve()

COMPLETED = "completed"
PARTIAL = "partial"
BLOCKED = "blocked"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--scope-manifest", default=str(DEFAULT_SCOPE_MANIFEST.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--semantic-manifest", default=str(DEFAULT_SEMANTIC_MANIFEST.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--branch-context-dir", default=str(DEFAULT_BRANCH_CONTEXT_DIR.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--assertion-quality-dir", default=str(DEFAULT_ASSERTION_QUALITY_DIR.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--worktree-root")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--scope")
    parser.add_argument("--all-scopes", action="store_true")
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--skip-semantic", action="store_true")
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--self-check", action="store_true")
    return parser.parse_args()


def resolve_path(path_value: str | None) -> Path | None:
    if path_value is None:
        return None
    path = Path(path_value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_command(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, env=env)


def git_head(cwd: Path = REPO_ROOT) -> str:
    completed = run_command(["git", "rev-parse", "HEAD"], cwd=cwd)
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def git_status_lines(cwd: Path) -> list[str]:
    completed = run_command(["git", "status", "--short"], cwd=cwd)
    return [line for line in completed.stdout.splitlines() if line.strip()] if completed.returncode == 0 else ["git_status_failed"]


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_repo_path(path_value: str) -> str:
    path = Path(path_value)
    if not path.is_absolute():
        return path_value.replace("\\", "/")
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        parts = path.as_posix().split("/orchestrator/", 1)
        if len(parts) == 2:
            return f"orchestrator/{parts[1]}"
        return path.as_posix()


def runtime_info(python_cmd: str, cwd: Path) -> dict[str, Any]:
    probe = run_command(
        [
            python_cmd,
            "-c",
            (
                "import json,platform,sys,pytest,coverage; "
                "import mutmut; "
                "print(json.dumps({"
                "'python_version': sys.version.split()[0],"
                "'platform': platform.platform(),"
                "'release': platform.release(),"
                "'sys_executable': sys.executable,"
                "'pytest_version': pytest.__version__,"
                "'coverage_version': coverage.__version__,"
                "'mutmut_version': getattr(mutmut, '__version__', 'unknown')"
                "}))"
            ),
        ],
        cwd=cwd,
        env={**os.environ, "PYTHONPATH": "."},
    )
    if probe.returncode != 0:
        return {"status": "blocked", "stdout": probe.stdout[-2000:], "stderr": probe.stderr[-2000:]}
    payload = json.loads(probe.stdout.strip())
    payload["status"] = "ok"
    payload["execution_platform"] = "WSL2" if "microsoft" in payload["release"].lower() else platform.system()
    payload["python_cmd"] = python_cmd
    return payload


def read_scope(scope_manifest_path: Path, scope_id: str) -> dict[str, Any]:
    for scope in load_json(scope_manifest_path)["scopes"]:
        if scope["scope_id"] == scope_id:
            return scope
    raise SystemExit(f"unknown_scope:{scope_id}")


def selected_scopes(scope_manifest_path: Path, args: argparse.Namespace) -> list[dict[str, Any]]:
    manifest = load_json(scope_manifest_path)
    if args.scope:
        return [read_scope(scope_manifest_path, args.scope)]
    if args.pilot:
        return [read_scope(scope_manifest_path, "quality-ocr")]
    if args.all_scopes:
        ordered = ["quality-ocr", "graph-routing-state", "workspace-scope", "final-selection-transaction", "compliance", "native-copy-policy"]
        by_id = {scope["scope_id"]: scope for scope in manifest["scopes"]}
        return [by_id[scope_id] for scope_id in ordered]
    return []


def validate_args(args: argparse.Namespace, output_dir: Path) -> tuple[bool, str | None]:
    if args.all_scopes and args.pilot:
        return False, "invalid_args_all_scopes_with_pilot"
    if args.all_scopes and args.scope:
        return False, "invalid_args_all_scopes_with_scope"
    if args.all_scopes and args.skip_semantic:
        return False, "invalid_args_all_scopes_with_skip_semantic"
    if args.all_scopes and args.allow_partial:
        return False, "invalid_args_all_scopes_with_allow_partial"
    if args.all_scopes and output_dir.resolve() == FINAL_OUTPUT_DIR and not args.resume:
        return True, None
    return True, None


def compute_scores(counts: Counter[str]) -> dict[str, Any]:
    executable = counts["killed"] + counts["survived"]
    strict = executable + counts["timeout"] + counts["uncovered"] + counts["error"]
    if strict == 0:
        return {"measurement_status": "unavailable", "executable_mutation_score": None, "strict_mutation_score": None}
    return {
        "measurement_status": "available",
        "executable_mutation_score": None if executable == 0 else counts["killed"] / executable,
        "strict_mutation_score": counts["killed"] / strict,
    }


def build_exit(status: str, allow_partial: bool) -> int:
    if status == COMPLETED:
        return 0
    if status == PARTIAL:
        return 0 if allow_partial else 2
    if status == BLOCKED:
        return 3
    return 1


def create_detached_worktree(repo_root: Path, worktree_root: Path, scope_id: str, source_commit: str) -> Path:
    scope_worktree = worktree_root / scope_id
    if scope_worktree.exists():
        run_command(["git", "worktree", "remove", "--force", str(scope_worktree)], cwd=repo_root)
    worktree_root.mkdir(parents=True, exist_ok=True)
    add = run_command(["git", "worktree", "add", "--detach", str(scope_worktree), source_commit], cwd=repo_root)
    if add.returncode != 0:
        raise RuntimeError(add.stderr or add.stdout or f"worktree_add_failed:{scope_id}")
    return scope_worktree


def cleanup_scope_worktree(repo_root: Path, scope_worktree: Path) -> dict[str, Any]:
    status_before = git_status_lines(scope_worktree) if scope_worktree.exists() else []
    remove = run_command(["git", "worktree", "remove", "--force", str(scope_worktree)], cwd=repo_root)
    prune = run_command(["git", "worktree", "prune"], cwd=repo_root)
    return {
        "status_before_cleanup": status_before,
        "remove_returncode": remove.returncode,
        "prune_returncode": prune.returncode,
        "cleanup_passed": remove.returncode == 0 and prune.returncode == 0 and not scope_worktree.exists(),
    }


def prepare_runtime(scope_id: str, *, worktree: Path, runtime_dir: Path, python_cmd: str, source_commit: str) -> dict[str, Any]:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    command = [
        python_cmd,
        str(REPO_ROOT / "scripts/prepare_mutmut_runtime.py"),
        "--scope",
        scope_id,
        "--worktree",
        str(worktree),
        "--python",
        python_cmd,
        "--expected-source-commit",
        source_commit,
        "--output-dir",
        str(runtime_dir),
    ]
    completed = run_command(command, cwd=REPO_ROOT, env={**os.environ, "PYTHONPATH": "."})
    (runtime_dir / "prepare_runtime.log").write_text(completed.stdout + ("\n[stderr]\n" + completed.stderr if completed.stderr else ""), encoding="utf-8")
    return {
        "returncode": completed.returncode,
        "scope_preflight": load_json(runtime_dir / "scope_preflight.json"),
        "import_preflight": load_json(runtime_dir / "import_preflight.json"),
        "resolved_test_nodes": load_json(runtime_dir / "resolved_test_nodes.json"),
        "resolved_mutmut_config": load_json(runtime_dir / "resolved_mutmut_config.json"),
    }


def focused_baseline(scope_id: str, *, worktree: Path, python_cmd: str, output_dir: Path, resolved_test_nodes: list[str]) -> dict[str, Any]:
    command = [python_cmd, "-m", "pytest", *resolved_test_nodes, "--strict-markers", "-q", "-m", "not external and not actual"]
    started = time.perf_counter()
    completed = run_command(command, cwd=worktree, env={**os.environ, "PYTHONPATH": "."})
    duration = time.perf_counter() - started
    (output_dir / "focused_baseline.log").write_text(completed.stdout + ("\n[stderr]\n" + completed.stderr if completed.stderr else ""), encoding="utf-8")
    summary_line = next((line for line in reversed((completed.stdout + "\n" + completed.stderr).splitlines()) if " passed" in line or " failed" in line or " skipped" in line or " errors" in line), "")
    return {"scope_id": scope_id, "status": "passed" if completed.returncode == 0 else "failed", "returncode": completed.returncode, "duration_seconds": round(duration, 2), "summary_line": summary_line, "command": command}


def parse_baseline_summary_line(line: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    tokens = line.replace(",", "").split()
    for index, token in enumerate(tokens[:-1]):
        if token.isdigit():
            label = tokens[index + 1]
            if label in {"passed", "failed", "skipped", "error", "errors", "xfailed", "xpassed"}:
                counts["error" if label == "errors" else label] = int(token)
    return counts


def run_mutmut(scope: dict[str, Any], *, worktree: Path, python_cmd: str, output_dir: Path) -> dict[str, Any]:
    env = {**os.environ, "PYTHONPATH": "."}
    setup_src = worktree / ".mutation-runtime" / "setup.cfg"
    shutil.copy2(setup_src, worktree / "setup.cfg")
    started = time.perf_counter()
    run_completed = run_mutmut_command([python_cmd, "-m", "mutmut", "run"], cwd=worktree, env=env)
    duration = time.perf_counter() - started
    results_completed = run_mutmut_command([python_cmd, "-m", "mutmut", "results"], cwd=worktree, env=env)
    export_completed = run_mutmut_command([python_cmd, "-m", "mutmut", "export-cicd-stats"], cwd=worktree, env=env)
    (output_dir / "mutmut_run.log").write_text(run_completed.stdout + ("\n[stderr]\n" + run_completed.stderr if run_completed.stderr else ""), encoding="utf-8")
    (output_dir / "mutmut_results.log").write_text(results_completed.stdout + ("\n[stderr]\n" + results_completed.stderr if results_completed.stderr else ""), encoding="utf-8")
    (output_dir / "mutmut_export.log").write_text(export_completed.stdout + ("\n[stderr]\n" + export_completed.stderr if export_completed.stderr else ""), encoding="utf-8")
    stats_path = worktree / "mutants" / "mutmut-cicd-stats.json"
    if stats_path.exists():
        shutil.copy2(stats_path, output_dir / "mutmut-cicd-stats.json")
    if run_completed.returncode != 0 or results_completed.returncode != 0 or export_completed.returncode != 0 or not stats_path.exists():
        return {"status": "failed", "reason": "mutmut_command_failed", "duration_seconds": round(duration, 2), "run_returncode": run_completed.returncode, "results_returncode": results_completed.returncode, "export_returncode": export_completed.returncode}
    rows = parse_results(results_completed.stdout)
    stats = load_stats(stats_path)
    details = collect_details(rows, python_cmd=python_cmd, cwd=worktree, env=env)
    write_json(output_dir / "resolved_mutants.json", {"rows": details})
    summary = summarize(stats, rows)
    counts = Counter(summary["counts"])
    return {
        "status": "completed" if summary["generated"] >= 1 and summary["count_consistent"] and summary["unknown_status_count"] == 0 else "failed",
        "duration_seconds": round(duration, 2),
        "run_returncode": run_completed.returncode,
        "results_returncode": results_completed.returncode,
        "export_returncode": export_completed.returncode,
        "stats": stats,
        "rows": details,
        "summary": summary,
        **compute_scores(counts),
    }


def validate_branch_context_source(branch_context_dir: Path, source_commit: str) -> bool:
    summary = load_json(branch_context_dir / "summary.json")
    maybe_commit = summary.get("source_commit")
    return maybe_commit in {None, source_commit}


def stale_weak_assertion_count(branch_context_dir: Path, assertion_quality_dir: Path, python_cmd: str) -> int:
    live = run_command([python_cmd, "-m", "pytest", "orchestrator/tests", "--collect-only", "-q"], cwd=REPO_ROOT, env={**os.environ, "PYTHONPATH": "."})
    known = {line.strip() for line in live.stdout.splitlines() if line.strip().startswith("orchestrator/tests/")}
    if not known:
        known = set(load_json(branch_context_dir / "pytest_nodes.json").get("collected_node_ids", []))
    findings = load_json(assertion_quality_dir / "removal_candidates.json").get("findings", [])
    return sum(1 for item in findings if item.get("node_id") not in known)


def semantic_join_artifacts(output_dir: Path, branch_context_dir: Path, assertion_quality_dir: Path) -> dict[str, Any]:
    semantic_path = output_dir / "runtime/semantic/semantic_mutant_results.json"
    if not semantic_path.exists():
        write_json(output_dir / "branch_context_mutation_join.json", {"rows": []})
        write_json(output_dir / "critical_gaps_after_mutation.json", {"surviving_critical_mutants": [], "uncovered_automated_scopes": [], "critical_branch_gap_files": [], "recommended_assertion_followups": []})
        write_json(output_dir / "removal_candidates_with_mutation.json", {"findings": []})
        return {"removal_candidates_protected_by_unique_kill": 0}
    semantic = load_json(semantic_path)["results"]
    branch_owners = load_json(branch_context_dir / "branch_owners.json").get("branches", [])
    critical_gaps = load_json(branch_context_dir / "critical_branch_gaps.json").get("files", [])
    unique_branches = {row["node_id"]: row for row in load_json(branch_context_dir / "unique_branches_by_test.json").get("tests", [])}
    removal_candidates = load_json(branch_context_dir / "removal_candidates_with_branch_context.json").get("findings", [])
    owner_tests_by_file: dict[str, list[str]] = defaultdict(list)
    for row in branch_owners:
        file_path = row["branch_id"].split(":", 1)[0]
        owner_tests_by_file[file_path].extend(row.get("owners", []))
    join_rows = []
    for row in semantic:
        join_rows.append(
            {
                "mutant_id": row["mutant_id"],
                "scope_id": row["scope_id"],
                "target_file": normalize_repo_path(row["file"]),
                "target_symbol": row["target_symbol"],
                "candidate_tests": row.get("candidate_tests", []),
                "branch_context_owner_tests": sorted(dict.fromkeys(owner_tests_by_file.get(normalize_repo_path(row["file"]), []))),
                "killing_tests": row.get("killing_tests", []),
                "status": row["status"],
                "survived": row["status"] == "survived",
            }
        )
    write_json(output_dir / "branch_context_mutation_join.json", {"rows": join_rows})
    survivor_ids = [row["mutant_id"] for row in semantic if row["status"] == "survived"]
    uncovered_auto = []
    for scope in load_json(output_dir / "automated_scope_summary.json").get("scopes", []):
        if scope.get("uncovered", 0):
            uncovered_auto.append({"scope_id": scope["scope_id"], "uncovered": scope["uncovered"]})
    critical_after = {
        "surviving_critical_mutants": survivor_ids,
        "uncovered_automated_scopes": uncovered_auto,
        "critical_branch_gap_files": [row["file"] for row in critical_gaps if row["file"].startswith("orchestrator/app/")],
        "recommended_assertion_followups": [row["mutant_id"] for row in semantic if row["status"] == "survived"],
    }
    write_json(output_dir / "critical_gaps_after_mutation.json", critical_after)
    unique_rows = load_json(output_dir / "runtime/semantic/unique_kills_by_test.json").get("tests", [])
    shared_rows = load_json(output_dir / "runtime/semantic/shared_kills_by_test.json").get("tests", [])
    unique_semantic_by_test: dict[str, int] = {row["test_node_id"]: row["unique_kill_count"] for row in unique_rows}
    shared_semantic_by_test: dict[str, int] = {row["test_node_id"]: row["shared_kill_count"] for row in shared_rows}
    joined_findings = []
    protected_count = 0
    for finding in removal_candidates:
        node_id = finding["node_id"]
        unique_branch_count = unique_branches.get(node_id, {}).get("unique_branch_count", 0)
        unique_semantic_kill_count = unique_semantic_by_test.get(node_id, 0)
        shared_semantic_kill_count = shared_semantic_by_test.get(node_id, 0)
        related_survivors = [row["mutant_id"] for row in semantic if row["status"] == "survived" and node_id in row.get("candidate_tests", [])]
        mutation_protected = unique_branch_count > 0 or unique_semantic_kill_count > 0 or bool(related_survivors) or finding.get("critical_module_touch", False)
        if mutation_protected:
            protected_count += 1
        joined_findings.append(
            {
                **finding,
                "unique_semantic_kill_count": unique_semantic_kill_count,
                "shared_semantic_kill_count": shared_semantic_kill_count,
                "related_surviving_mutants": related_survivors,
                "mutation_protected": mutation_protected,
                "deletion_eligible": False,
                "review_reason": "protected" if mutation_protected else "review_required_no_auto_delete",
            }
        )
    write_json(output_dir / "removal_candidates_with_mutation.json", {"findings": joined_findings})
    return {"removal_candidates_protected_by_unique_kill": protected_count}


def run_semantic(output_dir: Path, *, python_cmd: str, source_commit: str, semantic_manifest_path: Path, worktree_root: Path, branch_context_dir: Path) -> dict[str, Any]:
    semantic_runtime = output_dir / "runtime" / "semantic"
    semantic_runtime.mkdir(parents=True, exist_ok=True)
    semantic_worktree = create_detached_worktree(REPO_ROOT, worktree_root, "semantic", source_commit)
    cleanup_result = None
    try:
        command = [
            python_cmd,
            str(REPO_ROOT / "scripts/run_critical_semantic_mutations.py"),
            "--manifest",
            str(semantic_manifest_path),
            "--worktree",
            str(semantic_worktree),
            "--python",
            python_cmd,
            "--output-dir",
            str(semantic_runtime),
            "--all",
            "--branch-context-dir",
            str(branch_context_dir),
        ]
        completed = run_command(command, cwd=REPO_ROOT, env={**os.environ, "PYTHONPATH": "."})
        (semantic_runtime / "semantic_runner.log").write_text(completed.stdout + ("\n[stderr]\n" + completed.stderr if completed.stderr else ""), encoding="utf-8")
        if not (semantic_runtime / "semantic_summary.json").exists():
            return {"status": "failed", "reason": "semantic_summary_missing", "returncode": completed.returncode}
        result = load_json(semantic_runtime / "semantic_summary.json")
        result["returncode"] = completed.returncode
        return result
    finally:
        cleanup_result = cleanup_scope_worktree(REPO_ROOT, semantic_worktree)
        write_json(semantic_runtime / "cleanup_validation.json", cleanup_result)


def run_self_check() -> int:
    assert compute_scores(Counter())["measurement_status"] == "unavailable"
    scored = compute_scores(Counter({"killed": 3, "survived": 1, "timeout": 1, "uncovered": 1, "error": 1}))
    assert round(scored["executable_mutation_score"], 4) == 0.75
    assert round(scored["strict_mutation_score"], 4) == 0.4286
    assert build_exit(PARTIAL, False) == 2
    assert build_exit(PARTIAL, True) == 0
    assert build_exit(BLOCKED, False) == 3
    assert validate_args(argparse.Namespace(all_scopes=True, pilot=False, scope=None, skip_semantic=False, allow_partial=False, resume=False), FINAL_OUTPUT_DIR)[0] is True
    print("self_check=ok")
    return 0


def main() -> int:
    args = parse_args()
    if args.self_check:
        return run_self_check()
    output_dir = resolve_path(args.output_dir)
    assert output_dir is not None
    valid, reason = validate_args(args, output_dir)
    if not valid:
        write_json(output_dir / "summary.json", {"status": BLOCKED, "reason": reason, "source_commit": git_head()})
        return 3
    if not any((args.scope, args.all_scopes, args.pilot)):
        write_json(output_dir / "summary.json", {"status": BLOCKED, "reason": "execution_mode_required", "source_commit": git_head()})
        return 3

    scope_manifest_path = resolve_path(args.scope_manifest)
    semantic_manifest_path = resolve_path(args.semantic_manifest)
    branch_context_dir = resolve_path(args.branch_context_dir)
    assertion_quality_dir = resolve_path(args.assertion_quality_dir)
    assert scope_manifest_path and semantic_manifest_path and branch_context_dir and assertion_quality_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    source_commit = git_head()
    env_info = runtime_info(args.python, REPO_ROOT)
    write_json(output_dir / "environment.json", env_info)
    if env_info.get("status") != "ok":
        write_json(output_dir / "summary.json", {"status": BLOCKED, "reason": "python_runtime_probe_failed", "source_commit": source_commit})
        return 3
    if not validate_branch_context_source(branch_context_dir, source_commit):
        write_json(output_dir / "summary.json", {"status": BLOCKED, "reason": "branch_context_source_mismatch", "source_commit": source_commit})
        return 3

    manifest = load_json(scope_manifest_path)
    semantic_manifest = load_json(semantic_manifest_path)
    write_json(output_dir / "scope_manifest_resolved.json", manifest)
    write_json(output_dir / "semantic_mutants.json", semantic_manifest)
    write_json(output_dir / "tool_configuration.json", {"python": args.python, "worktree_root": args.worktree_root, "all_scopes": args.all_scopes, "pilot": args.pilot, "scope": args.scope})
    write_json(output_dir / "tooling_fingerprint.json", {"measure_script_sha256": hash_file(REPO_ROOT / "scripts/measure_critical_mutation_baseline.py"), "prepare_script_sha256": hash_file(REPO_ROOT / "scripts/prepare_mutmut_runtime.py"), "semantic_script_sha256": hash_file(REPO_ROOT / "scripts/run_critical_semantic_mutations.py"), "adapter_sha256": hash_file(REPO_ROOT / "scripts/_mutmut_result_adapter.py")})
    write_json(output_dir / "baseline_results.json", {"branch_context_summary": load_json(branch_context_dir / "summary.json")})

    scopes = selected_scopes(scope_manifest_path, args)
    all_scope_ids = [scope["scope_id"] for scope in manifest["scopes"]]
    worktree_root = resolve_path(args.worktree_root) or (Path.home() / "worktrees" / "easyads-critical-mutation-v1")
    completed_scope_ids: list[str] = []
    blocked_scope_ids: list[str] = []
    scope_rows: list[dict[str, Any]] = []
    overall_counts: Counter[str] = Counter()
    baseline_counts_total: Counter[str] = Counter()

    for scope in scopes:
        scope_runtime_dir = output_dir / "runtime" / scope["scope_id"]
        scope_worktree = create_detached_worktree(REPO_ROOT, worktree_root, scope["scope_id"], source_commit)
        cleanup_result = None
        try:
            prepared = prepare_runtime(scope["scope_id"], worktree=scope_worktree, runtime_dir=scope_runtime_dir, python_cmd=args.python, source_commit=source_commit)
            resolved_nodes = prepared["resolved_test_nodes"]["resolved_test_nodes"]
            resolved_node_hash = hashlib.sha256("\n".join(resolved_nodes).encode("utf-8")).hexdigest()
            config_path = scope_worktree / ".mutation-runtime" / "setup.cfg"
            config_hash = hash_file(config_path)
            source_hashes = {source_file: hash_file(scope_worktree / source_file) for source_file in scope["source_files"]}
            if prepared["returncode"] != 0 or prepared["scope_preflight"]["errors"] or prepared["import_preflight"]["status"] != "passed":
                row = {"scope_id": scope["scope_id"], "status": BLOCKED, "reason": "runtime_preflight_failed", "resolved_test_count": len(resolved_nodes)}
                scope_rows.append(row)
                blocked_scope_ids.append(scope["scope_id"])
                write_json(scope_runtime_dir / "scope_summary.json", row)
                continue
            baseline = focused_baseline(scope["scope_id"], worktree=scope_worktree, python_cmd=args.python, output_dir=scope_runtime_dir, resolved_test_nodes=resolved_nodes)
            baseline_counts = parse_baseline_summary_line(baseline["summary_line"])
            if baseline["status"] != "passed":
                row = {"scope_id": scope["scope_id"], "status": "test_failed", "baseline": baseline, "resolved_test_count": len(resolved_nodes)}
                scope_rows.append(row)
                blocked_scope_ids.append(scope["scope_id"])
                write_json(scope_runtime_dir / "scope_summary.json", row)
                continue
            mutation = run_mutmut(scope, worktree=scope_worktree, python_cmd=args.python, output_dir=scope_runtime_dir)
            if mutation["status"] != "completed":
                row = {"scope_id": scope["scope_id"], "status": "coverage_failed", "baseline": baseline, "mutation": mutation, "resolved_test_count": len(resolved_nodes)}
                scope_rows.append(row)
                blocked_scope_ids.append(scope["scope_id"])
                write_json(scope_runtime_dir / "scope_summary.json", row)
                continue
            row = {
                "scope_id": scope["scope_id"],
                "status": COMPLETED,
                "source_commit": source_commit,
                "manifest_hash": hash_file(scope_manifest_path),
                "config_hash": config_hash,
                "resolved_node_hash": resolved_node_hash,
                "source_file_hashes": source_hashes,
                "tool_version": env_info["mutmut_version"],
                "source_files": scope["source_files"],
                "target_functions": scope["functions"],
                "resolved_test_count": len(resolved_nodes),
                "baseline_passed": baseline_counts["passed"],
                "baseline_skipped": baseline_counts["skipped"],
                "generated": mutation["summary"]["generated"],
                "in_scope_generated": mutation["summary"]["generated"],
                "out_of_scope_generated": 0,
                "killed": mutation["summary"]["counts"]["killed"],
                "survived": mutation["summary"]["counts"]["survived"],
                "timeout": mutation["summary"]["counts"]["timeout"],
                "uncovered": mutation["summary"]["counts"]["uncovered"],
                "error": mutation["summary"]["counts"]["error"],
                "duration_seconds": mutation["duration_seconds"],
                "measurement_status": mutation["measurement_status"],
                "executable_mutation_score": mutation["executable_mutation_score"],
                "strict_mutation_score": mutation["strict_mutation_score"],
            }
            scope_rows.append(row)
            completed_scope_ids.append(scope["scope_id"])
            baseline_counts_total.update(baseline_counts)
            overall_counts.update(Counter(mutation["summary"]["counts"]))
            write_json(scope_runtime_dir / "scope_summary.json", row)
        finally:
            if scope_worktree.exists():
                cleanup_result = cleanup_scope_worktree(REPO_ROOT, scope_worktree)
                write_json(scope_runtime_dir / "cleanup_validation.json", cleanup_result)
                if scope_rows and scope_rows[-1].get("scope_id") == scope["scope_id"]:
                    scope_rows[-1]["cleanup_passed"] = cleanup_result["cleanup_passed"]
                    if not cleanup_result["cleanup_passed"] and scope["scope_id"] in completed_scope_ids:
                        completed_scope_ids.remove(scope["scope_id"])
                        blocked_scope_ids.append(scope["scope_id"])
                        scope_rows[-1]["status"] = BLOCKED
                        write_json(scope_runtime_dir / "scope_summary.json", scope_rows[-1])

    pending_scope_ids = [scope_id for scope_id in all_scope_ids if scope_id not in completed_scope_ids and scope_id not in blocked_scope_ids]
    write_json(output_dir / "automated_scope_summary.json", {"scopes": scope_rows, "completed_scopes": completed_scope_ids, "pending_scopes": pending_scope_ids, "blocked_scopes": blocked_scope_ids})
    write_json(output_dir / "automated_mutants.json", {"scopes": scope_rows})
    automated_scores = compute_scores(overall_counts)
    write_json(output_dir / "mutation_scores.json", {"automated": automated_scores})

    semantic_result = {"status": "failed", "reason": "not_run"}
    if not args.skip_semantic:
        semantic_result = run_semantic(output_dir, python_cmd=args.python, source_commit=source_commit, semantic_manifest_path=semantic_manifest_path, worktree_root=worktree_root, branch_context_dir=branch_context_dir)
    join_metrics = semantic_join_artifacts(output_dir, branch_context_dir, assertion_quality_dir)
    semantic_counts = semantic_result.get("counts", {"killed": 0, "survived": 0, "timeout": 0, "uncovered": 0, "incompetent": 0, "stale_patch": 0, "error": 0, "tests_with_unique_kills": 0, "tests_with_shared_kills": 0, "suite_interaction_kills": 0})
    weak_stale = stale_weak_assertion_count(branch_context_dir, assertion_quality_dir, args.python)
    summary_status = COMPLETED if len(completed_scope_ids) == 6 and not pending_scope_ids and not blocked_scope_ids and semantic_result.get("status") == COMPLETED and weak_stale == 0 else (PARTIAL if completed_scope_ids else BLOCKED)
    write_json(
        output_dir / "summary.json",
        {
            "status": summary_status,
            "source_commit": source_commit,
            "tooling_fingerprint": load_json(output_dir / "tooling_fingerprint.json"),
            "execution_platform": env_info["execution_platform"],
            "scope_count": len(all_scope_ids),
            "completed_scopes": completed_scope_ids,
            "pending_scopes": pending_scope_ids,
            "blocked_scopes": blocked_scope_ids,
            "automated_generated": overall_counts["killed"] + overall_counts["survived"] + overall_counts["timeout"] + overall_counts["uncovered"] + overall_counts["error"],
            "automated_killed": overall_counts["killed"],
            "automated_survived": overall_counts["survived"],
            "automated_timeout": overall_counts["timeout"],
            "automated_uncovered": overall_counts["uncovered"],
            "automated_error": overall_counts["error"],
            "automated_out_of_scope": 0,
            **automated_scores,
            "semantic_mutant_count": len(semantic_manifest["mutants"]),
            "semantic_killed": semantic_counts["killed"],
            "semantic_survived": semantic_counts["survived"],
            "semantic_timeout": semantic_counts["timeout"],
            "semantic_uncovered": semantic_counts["uncovered"],
            "semantic_incompetent": semantic_counts["incompetent"],
            "semantic_stale_patch": semantic_counts["stale_patch"],
            "semantic_error": semantic_counts["error"],
            "tests_with_unique_kills": semantic_counts["tests_with_unique_kills"],
            "tests_with_shared_kills": semantic_counts["tests_with_shared_kills"],
            "suite_interaction_kills": semantic_counts["suite_interaction_kills"],
            "removal_candidates_protected_by_unique_kill": join_metrics["removal_candidates_protected_by_unique_kill"],
            "automatic_deletions": 0,
            "branch_artifact_source_match": True,
            "weak_assertion_stale_node_count": weak_stale,
            "source_restore_failures": semantic_result.get("source_restore_failures", 0),
            "cleanup_failures": sum(1 for row in scope_rows if row.get("cleanup_passed") is False) + semantic_result.get("cleanup_failures", 0),
            "baseline_passed": baseline_counts_total["passed"],
            "baseline_failed": baseline_counts_total["failed"],
            "baseline_skipped": baseline_counts_total["skipped"],
        },
    )
    (output_dir / "report.md").write_text(f"# Critical Mutation Baseline v1\n\n- status: `{summary_status}`\n", encoding="utf-8")
    return build_exit(summary_status, args.allow_partial)


if __name__ == "__main__":
    raise SystemExit(main())
