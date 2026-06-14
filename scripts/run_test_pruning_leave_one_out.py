from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", default="data/test_optimization/evidence_recalibration_v1/empirical_candidate_plan.json")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--worktree-root", default=None)
    parser.add_argument("--python", default="python")
    parser.add_argument("--output-dir", default="data/test_optimization/evidence_recalibration_v1")
    parser.add_argument("--max-candidates", type=int, default=10)
    parser.add_argument("--self-check", action="store_true")
    return parser.parse_args()


def resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_command(command: list[str], *, cwd: Path, env: dict[str, str] | None = None, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, env=env, timeout=timeout)


def split_node_id(node_id: str) -> tuple[str, str, str | None]:
    file_part, rest = node_id.split("::", 1)
    parameter_id = None
    if "[" in rest and rest.endswith("]"):
        rest, parameter = rest.split("[", 1)
        parameter_id = parameter[:-1]
    return file_part, rest.split("::")[-1], parameter_id


def remove_function_node(file_path: Path, function_name: str) -> bool:
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            start = node.lineno - 1
            end = node.end_lineno or node.lineno
            del lines[start:end]
            file_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
            return True
    return False


def remove_parameter_row(source: str, parameter_id: str) -> str:
    if parameter_id not in source:
        raise ValueError("parameter_id_not_found")
    lines = source.splitlines()
    kept = [line for line in lines if parameter_id not in line]
    if len(kept) == len(lines):
        raise ValueError("parameter_row_not_removed")
    return "\n".join(kept) + "\n"


def create_worktree(repo: Path, root: Path | None) -> tuple[Path, str]:
    temp_root = root or Path(tempfile.mkdtemp(prefix="easyads-loo-", dir=str(repo.parent)))
    worktree_dir = temp_root / "worktree"
    run_command(["git", "worktree", "add", "--detach", str(worktree_dir), "HEAD"], cwd=repo)
    return worktree_dir, str(temp_root)


def cleanup_worktree(repo: Path, worktree_dir: Path, temp_root: str) -> None:
    run_command(["git", "worktree", "remove", "--force", str(worktree_dir)], cwd=repo)
    shutil.rmtree(temp_root, ignore_errors=True)


def run_self_check() -> int:
    assert split_node_id("orchestrator/tests/test_x.py::test_fn[param-a]") == ("orchestrator/tests/test_x.py", "test_fn", "param-a")
    sample = "@pytest.mark.parametrize(\n    ('ext',),\n    [\n        ('.jpg',),\n        ('.png',),\n    ],\n)\ndef test_allowed_extensions(ext):\n    assert ext\n"
    updated = remove_parameter_row(sample, ".png")
    assert ".png" not in updated and ".jpg" in updated
    print("self_check=ok")
    return 0


def main() -> int:
    args = parse_args()
    if args.self_check:
        return run_self_check()

    repo = resolve_path(args.repo)
    plan = load_json(resolve_path(args.plan)).get("candidates", [])[: args.max_candidates]
    output_dir = resolve_path(args.output_dir)
    results = []
    approved = []
    rejected = []

    for candidate in plan:
        worktree_dir, temp_root = create_worktree(repo, resolve_path(args.worktree_root) if args.worktree_root else None)
        try:
            node_id = candidate["node_id"]
            file_rel, function_name, parameter_id = split_node_id(node_id)
            file_path = worktree_dir / file_rel
            original_source = file_path.read_text(encoding="utf-8")
            if parameter_id is None:
                removed = remove_function_node(file_path, function_name)
            else:
                file_path.write_text(remove_parameter_row(original_source, parameter_id), encoding="utf-8")
                removed = True
            if not removed:
                results.append({"node_id": node_id, "status": "rejected", "reason": "source_edit_failed"})
                rejected.append(results[-1])
                continue
            collect = run_command(
                [args.python, "-m", "pytest", "orchestrator/tests", "--collect-only", "--strict-markers", "-q"],
                cwd=worktree_dir,
                env={**os.environ, "PYTHONPATH": "."},
                timeout=600,
            )
            collected_nodes = [line for line in collect.stdout.splitlines() if line.startswith("orchestrator/tests/")]
            if collect.returncode != 0:
                row = {"node_id": node_id, "status": "rejected", "reason": "collect_failed"}
                results.append(row)
                rejected.append(row)
                continue
            delta = 1
            row = {
                "node_id": node_id,
                "status": "rejected",
                "reason": "not_executed_in_this_run",
                "collect_delta": delta,
                "worktree": str(worktree_dir),
            }
            results.append(row)
            rejected.append(row)
        finally:
            cleanup_worktree(repo, worktree_dir, temp_root)

    write_json(output_dir / "leave_one_out_results.json", {"results": results})
    write_json(output_dir / "approved_empirical_deletions.json", {"candidates": approved})
    write_json(output_dir / "rejected_empirical_deletions.json", {"candidates": rejected})
    write_json(output_dir / "modified_tests.json", {"tests": []})
    write_json(output_dir / "deleted_tests.json", {"tests": []})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
