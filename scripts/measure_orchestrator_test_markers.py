from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from scripts._test_marker_taxonomy import PRIMARY_MARKERS, TRAIT_MARKERS, build_invariant_violations


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure pytest marker taxonomy inventory.")
    parser.add_argument("--tests-root", default="orchestrator/tests")
    parser.add_argument("--output-dir", default="data/test_optimization/marker_taxonomy")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ensure_repo_root_cwd()
    tests_root = (REPO_ROOT / args.tests_root).resolve()
    output_dir = (REPO_ROOT / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    inventory_path = output_dir / "_marker_inventory_raw.json"
    command = [
        "uv",
        "run",
        "--no-sync",
        "python",
        "-m",
        "pytest",
        tests_root.relative_to(REPO_ROOT).as_posix(),
        "--collect-only",
        "--strict-markers",
        "-q",
        "-p",
        "scripts._test_marker_inventory_plugin",
    ]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env={
            **dict(**__import__("os").environ),
            "UV_PROJECT_ENVIRONMENT": ".venv",
            "PYTHONPATH": ".",
            "EASYADS_MARKER_INVENTORY_PATH": str(inventory_path),
        },
        capture_output=True,
        text=True,
    )
    (output_dir / "collect.log").write_text(
        "$ " + " ".join(command) + "\n" + completed.stdout + ("\n[stderr]\n" + completed.stderr if completed.stderr else ""),
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)

    payload = load_json(inventory_path)
    nodes = payload["nodes"]
    counts = build_counts(nodes)
    unclassified = [node for node in nodes if len(node["primary_markers"]) == 0]
    conflicts = [node for node in nodes if len(node["primary_markers"]) > 1]
    violations = []
    for node in nodes:
        reasons = build_invariant_violations(node)
        if reasons:
            violations.append(
                {
                    "node_id": node["node_id"],
                    "file": node["file"],
                    "reasons": reasons,
                }
            )

    external_actual = [
        node
        for node in nodes
        if "external" in node["trait_markers"] or "actual" in node["trait_markers"]
    ]
    critical_regression = [
        node
        for node in nodes
        if "critical" in node["trait_markers"] or "regression" in node["trait_markers"]
    ]

    write_json(output_dir / "marker_nodes.json", {"nodes": nodes})
    write_json(output_dir / "marker_counts.json", counts)
    write_json(output_dir / "unclassified_tests.json", {"nodes": unclassified})
    write_json(output_dir / "primary_marker_conflicts.json", {"nodes": conflicts})
    write_json(output_dir / "marker_invariant_violations.json", {"nodes": violations})
    write_json(output_dir / "external_actual_tests.json", {"nodes": external_actual})
    write_json(output_dir / "critical_regression_tests.json", {"nodes": critical_regression})
    write_json(
        output_dir / "marker_summary.json",
        {
            "status": "completed",
            "collected_nodes": len(nodes),
            "unclassified_count": len(unclassified),
            "primary_conflict_count": len(conflicts),
            "invariant_violation_count": len(violations),
            "primary_counts": counts["primary"],
            "trait_counts": counts["traits"],
        },
    )
    return 0


def ensure_repo_root_cwd() -> None:
    if Path.cwd().resolve() != REPO_ROOT:
        raise SystemExit(f"run from repository root: {REPO_ROOT}")


def build_counts(nodes: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    primary_counts = Counter()
    trait_counts = Counter()
    for node in nodes:
        for name in node["primary_markers"]:
            primary_counts[name] += 1
        for name in node["trait_markers"]:
            trait_counts[name] += 1
    return {
        "primary": {name: primary_counts.get(name, 0) for name in PRIMARY_MARKERS},
        "traits": {name: trait_counts.get(name, 0) for name in TRAIT_MARKERS},
    }


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
