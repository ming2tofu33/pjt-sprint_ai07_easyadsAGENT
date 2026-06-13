from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCOPE_MANIFEST = REPO_ROOT / "scripts/critical_mutation_scope_v1.json"
DEFAULT_PYTEST_NODES = REPO_ROOT / "data/test_optimization/branch_context_v1/pytest_nodes.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data/test_optimization/critical_mutation_v1/runtime"
DEFAULT_ALSO_COPY = [
    "orchestrator/eval/",
    "orchestrator/tests/",
    "scripts/",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope")
    parser.add_argument("--worktree")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--scope-manifest", default=str(DEFAULT_SCOPE_MANIFEST.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--pytest-nodes", default=str(DEFAULT_PYTEST_NODES.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--python", default=os.environ.get("MUTATION_PYTHON", "python"))
    parser.add_argument("--expected-source-commit")
    parser.add_argument("--self-check", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def run_command(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, env=env)


def read_scope(scope_manifest_path: Path, scope_id: str) -> dict[str, Any]:
    manifest = load_json(scope_manifest_path)
    for scope in manifest["scopes"]:
        if scope["scope_id"] == scope_id:
            return scope
    raise SystemExit(f"unknown_scope:{scope_id}")


def function_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
    return names


def resolve_test_nodes(pytest_nodes_path: Path, patterns: list[str]) -> tuple[list[str], list[str]]:
    payload = load_json(pytest_nodes_path)
    node_ids = payload.get("collected_node_ids", [])
    matches: list[str] = []
    unmatched: list[str] = []
    for pattern in patterns:
        pattern_matches = [node_id for node_id in node_ids if node_id.startswith(pattern)]
        if pattern_matches:
            matches.extend(pattern_matches)
        else:
            unmatched.append(pattern)
    return sorted(dict.fromkeys(matches)), unmatched


def validate_scope(scope: dict[str, Any], *, source_root: Path, pytest_nodes_path: Path) -> tuple[dict[str, Any], bool]:
    errors: list[str] = []
    source_results = []
    all_names: set[str] = set()
    for source_file in scope["source_files"]:
        path = source_root / source_file
        valid_source = source_file.startswith("orchestrator/app/")
        exists = path.exists()
        names = function_names(path) if exists else set()
        all_names.update(names)
        source_results.append(
            {
                "source_file": source_file,
                "exists": exists,
                "valid_source_path": valid_source,
                "functions_found": sorted(names),
            }
        )
        if not valid_source:
            errors.append(f"invalid_source_path:{source_file}")
        if not exists:
            errors.append(f"missing_source_file:{source_file}")
    resolved_nodes, unmatched_patterns = resolve_test_nodes(pytest_nodes_path, scope["test_node_patterns"])
    if not resolved_nodes:
        errors.append("zero_test_matches")
    if unmatched_patterns:
        errors.extend([f"unmatched_pattern:{pattern}" for pattern in unmatched_patterns])
    if any(not pattern.startswith("orchestrator/tests/") for pattern in scope["test_node_patterns"]):
        errors.append("invalid_test_pattern")
    missing_functions = [name for name in scope["functions"] if name not in all_names]
    for name in missing_functions:
        errors.append(f"missing_target_function:{name}")
    return {
        "scope_id": scope["scope_id"],
        "source_files": source_results,
        "missing_functions": missing_functions,
        "resolved_test_count": len(resolved_nodes),
        "resolved_test_nodes_sample": resolved_nodes[:20],
        "unmatched_patterns": unmatched_patterns,
        "errors": errors,
    }, not errors


def build_mutmut_config(scope: dict[str, Any], resolved_test_nodes: list[str]) -> str:
    only_mutate = "\n".join(f"    {path}" for path in scope["source_files"])
    tests = "\n".join(f"    {node_id}" for node_id in resolved_test_nodes)
    also_copy = "\n".join(f"    {path}" for path in DEFAULT_ALSO_COPY)
    return "\n".join(
        [
            "[mutmut]",
            "source_paths = orchestrator/app/",
            "only_mutate =",
            only_mutate,
            "pytest_add_cli_args_test_selection =",
            tests,
            "pytest_add_cli_args =",
            "    --strict-markers",
            "    -q",
            "    -m",
            "    not external and not actual",
            "also_copy =",
            also_copy,
            "mutate_only_covered_lines = true",
            "use_setproctitle = false",
            "",
        ]
    )


def copy_path(src_root: Path, relative_path: str, dest_root: Path) -> None:
    src = src_root / relative_path.rstrip("/").replace("/", os.sep)
    dest = dest_root / relative_path.rstrip("/")
    if src.is_dir():
        shutil.copytree(src, dest, dirs_exist_ok=True)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def classify_missing_module(source_root: Path, module_name: str) -> str:
    repo_path = source_root / Path(*module_name.split("."))
    if repo_path.exists() or repo_path.with_suffix(".py").exists():
        return "sandbox_copy_missing"
    return "runtime_dependency_missing"


def worktree_integrity(worktree: Path, expected_source_commit: str | None) -> dict[str, Any]:
    head = run_command(["git", "rev-parse", "HEAD"], cwd=worktree)
    status = run_command(["git", "status", "--short"], cwd=worktree)
    source_dirty = any(line and not line.startswith("?? mutants") and not line.startswith("?? .mutation-runtime") for line in status.stdout.splitlines())
    ok = head.returncode == 0 and status.returncode == 0 and not source_dirty
    if expected_source_commit and head.stdout.strip() != expected_source_commit:
        ok = False
    return {
        "status": "passed" if ok else "failed",
        "head": head.stdout.strip(),
        "expected_source_commit": expected_source_commit,
        "git_status": status.stdout.splitlines(),
        "source_dirty": source_dirty,
    }


def sandbox_preflight(source_root: Path, worktree: Path, scope: dict[str, Any], resolved_test_nodes: list[str], python_cmd: str, setup_cfg_text: str) -> dict[str, Any]:
    runtime_root = worktree / ".mutation-runtime"
    sandbox = runtime_root / "preflight-sandbox"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    sandbox.mkdir(parents=True, exist_ok=True)
    copy_path(source_root, "orchestrator/app", sandbox)
    copy_path(source_root, "pyproject.toml", sandbox)
    for path_value in DEFAULT_ALSO_COPY:
        copy_path(source_root, path_value, sandbox)
    (sandbox / "setup.cfg").write_text(setup_cfg_text, encoding="utf-8")
    command = [python_cmd, "-m", "pytest", *resolved_test_nodes, "--collect-only", "--strict-markers", "-q"]
    completed = run_command(command, cwd=sandbox, env={**os.environ, "PYTHONPATH": "."})
    missing_modules = []
    for line in (completed.stderr + "\n" + completed.stdout).splitlines():
        marker = "ModuleNotFoundError: No module named "
        if marker in line:
            module_name = line.split(marker, 1)[1].strip().strip("'\"")
            missing_modules.append(
                {
                    "module": module_name,
                    "classification": classify_missing_module(source_root, module_name),
                }
            )
    return {
        "status": "passed" if completed.returncode == 0 else "failed",
        "command": command,
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
        "missing_modules": missing_modules,
        "sandbox_dir": str(sandbox),
    }


def run_self_check() -> int:
    assert classify_missing_module(REPO_ROOT, "scripts._test_marker_taxonomy") == "sandbox_copy_missing"
    assert classify_missing_module(REPO_ROOT, "PIL") == "runtime_dependency_missing"
    resolved, unmatched = resolve_test_nodes(REPO_ROOT / "data/test_optimization/branch_context_v1/pytest_nodes.json", ["orchestrator/tests/test_validation_gates.py::test_stub_adapter_unavailable"])
    assert resolved and not unmatched
    print("self_check=ok")
    return 0


def main() -> int:
    args = parse_args()
    if args.self_check:
        return run_self_check()
    if not args.scope or not args.worktree:
        raise SystemExit("--scope and --worktree are required unless --self-check is used")
    worktree = resolve_path(args.worktree)
    output_dir = resolve_path(args.output_dir)
    source_root = worktree
    scope = read_scope(resolve_path(args.scope_manifest), args.scope)
    integrity = worktree_integrity(worktree, args.expected_source_commit)
    scope_preflight, ok = validate_scope(scope, source_root=source_root, pytest_nodes_path=resolve_path(args.pytest_nodes))
    resolved_test_nodes, unmatched_patterns = resolve_test_nodes(resolve_path(args.pytest_nodes), scope["test_node_patterns"])
    setup_cfg_text = build_mutmut_config(scope, resolved_test_nodes)
    runtime_dir = worktree / ".mutation-runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "setup.cfg").write_text(setup_cfg_text, encoding="utf-8")
    (worktree / "setup.cfg").write_text(setup_cfg_text, encoding="utf-8")
    also_copy_manifest = []
    missing_paths = []
    for path_value in DEFAULT_ALSO_COPY:
        path = source_root / path_value.rstrip("/").replace("/", os.sep)
        record = {"path": path_value, "exists": path.exists()}
        also_copy_manifest.append(record)
        if not path.exists():
            missing_paths.append(record)
    import_preflight = sandbox_preflight(source_root, worktree, scope, resolved_test_nodes, args.python, setup_cfg_text) if ok and integrity["status"] == "passed" else {"status": "skipped"}
    write_json(output_dir / "resolved_test_nodes.json", {"scope_id": scope["scope_id"], "configured_patterns": scope["test_node_patterns"], "resolved_test_nodes": resolved_test_nodes, "resolved_test_count": len(resolved_test_nodes), "unmatched_patterns": unmatched_patterns})
    write_json(output_dir / "resolved_mutmut_config.json", {"scope_id": scope["scope_id"], "setup_cfg": setup_cfg_text, "tooling_root": str(REPO_ROOT), "source_worktree": str(source_root), "source_commit": integrity["head"]})
    write_json(output_dir / "also_copy_manifest.json", {"paths": also_copy_manifest})
    write_json(output_dir / "missing_paths.json", {"paths": missing_paths})
    write_json(output_dir / "scope_preflight.json", scope_preflight)
    write_json(output_dir / "worktree_integrity.json", integrity)
    write_json(output_dir / "import_preflight.json", import_preflight)
    return 0 if ok and integrity["status"] == "passed" and import_preflight.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
