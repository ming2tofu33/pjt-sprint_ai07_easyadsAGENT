from __future__ import annotations

import argparse
import ast
import json
import os
import platform
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILES = {
    "inventory": "inventory_before.txt",
    "junit": "baseline.xml",
    "duration": "duration_report.json",
    "warnings": "warning_report.json",
    "coverage": "coverage_baseline.json",
    "summary": "baseline_summary.json",
    "collect_log": "collect.log",
    "pytest_log": "pytest_full.log",
    "coverage_log": "coverage_full.log",
    "collected_nodes": "_collected_nodes.json",
    "node_results": "_node_results.json",
}
ACTUAL_ENV_VARS = [
    "EASYADS_ENABLE_LLM_CALLS",
    "EASYADS_ENABLE_GPT_IMAGE_2",
    "EASYADS_ENABLE_FLUX2_KLEIN_LOCAL",
    "EASYADS_VLM_ACTUAL",
    "LLM_ENABLE_API_CALL",
]
ACTUAL_ENV_PATTERNS = [re.compile(r"^EASYADS_.*_ACTUAL$")]
TRUTHY_VALUES = {"1", "true", "yes", "on"}


class MeasurementError(RuntimeError):
    def __init__(self, message: str, *, status: str = "measurement_failed") -> None:
        super().__init__(message)
        self.status = status


@dataclass(slots=True)
class TestFileStats:
    path: str
    physical_lines: int
    nonblank_lines: int
    test_function_count: int
    test_class_count: int


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure orchestrator test baseline artifacts.")
    parser.add_argument("--tests-root", default="orchestrator/tests")
    parser.add_argument("--output-dir", default="data/test_optimization")
    parser.add_argument("--top-slow-count", type=int, default=50)
    parser.add_argument("--python-executable", default=sys.executable)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ensure_repo_root_cwd()
    tests_root = resolve_existing_dir(args.tests_root, "tests root")
    output_dir = resolve_output_dir(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ensure_output_dir_safe(output_dir)
    summary = build_initial_summary(safe_run_metadata(), tests_root)

    try:
        ensure_coverage_available()
        run_meta = gather_run_metadata()
        summary.update(run_meta)
        actual_envs = detect_enabled_actual_envs()
        if actual_envs:
            raise MeasurementError(
                "actual external calls enabled: " + ", ".join(actual_envs),
                status="measurement_failed",
            )
        summary["actual_external_calls_enabled"] = False
        file_stats = collect_inventory(tests_root)
        apply_inventory_stats(summary, file_stats)
        write_inventory(output_dir / OUTPUT_FILES["inventory"], summary, file_stats, collected_counts=None)

        collected_node_ids = run_collection(args, tests_root, output_dir)
        summary["collected_node_count"] = len(collected_node_ids)
        write_inventory(
            output_dir / OUTPUT_FILES["inventory"],
            summary,
            file_stats,
            collected_counts=Counter(node_id.split("::", 1)[0] for node_id in collected_node_ids),
        )

        full_suite = run_full_suite(args, tests_root, output_dir)
        warning_report = load_json(output_dir / OUTPUT_FILES["warnings"])
        duration_report = build_duration_report(
            collected_node_ids=collected_node_ids,
            node_results=full_suite["node_results"],
            top_slow_count=args.top_slow_count,
            normal_full_suite_duration_seconds=full_suite["wall_clock_seconds"],
            pytest_reported_duration_seconds=sum(
                float(item["total_seconds"]) for item in full_suite["node_results"]
            ),
            coverage_full_suite_duration_seconds=0.0,
        )
        write_json(output_dir / OUTPUT_FILES["duration"], duration_report)
        apply_result_counts(summary, full_suite["node_results"])
        apply_warning_stats(summary, warning_report)
        summary["normal_full_suite_duration_seconds"] = full_suite["wall_clock_seconds"]
        summary["slowest_test"] = duration_report["top_slow_tests"][0] if duration_report["top_slow_tests"] else {}
        summary["largest_test_file_by_nodes"] = largest_file_by_nodes(duration_report["files"])
        summary["largest_test_file_by_lines"] = largest_file_by_lines(file_stats)

        if full_suite["exit_code"] != 0:
            summary["status"] = "test_failed"
            summary["failure_reason"] = f"pytest exit code {full_suite['exit_code']}"
            summary["failed_nodes"] = failed_node_ids(full_suite["node_results"])
            write_json(output_dir / OUTPUT_FILES["summary"], summary)
            validate_artifacts(output_dir, require_coverage=False)
            return full_suite["exit_code"] or 1

        coverage_result = run_coverage(args, tests_root, output_dir)
        duration_report["coverage_full_suite_duration_seconds"] = coverage_result["wall_clock_seconds"]
        write_json(output_dir / OUTPUT_FILES["duration"], duration_report)
        summary["coverage_full_suite_duration_seconds"] = coverage_result["wall_clock_seconds"]
        apply_coverage_stats(summary, load_json(output_dir / OUTPUT_FILES["coverage"]))
        summary["status"] = "completed"
        write_json(output_dir / OUTPUT_FILES["summary"], summary)
        validate_artifacts(output_dir, require_coverage=True)
        return 0
    except MeasurementError as exc:
        summary["status"] = exc.status
        summary["failure_reason"] = str(exc)
        write_json(output_dir / OUTPUT_FILES["summary"], summary)
        return 1
    except Exception as exc:  # pragma: no cover - fail-safe path
        summary["status"] = "measurement_failed"
        summary["failure_reason"] = f"{type(exc).__name__}: {exc}"
        write_json(output_dir / OUTPUT_FILES["summary"], summary)
        return 1


def ensure_repo_root_cwd() -> None:
    cwd = Path.cwd().resolve()
    if cwd != REPO_ROOT:
        raise MeasurementError(
            f"run this script from repository root: expected {REPO_ROOT}, got {cwd}",
        )


def ensure_coverage_available() -> None:
    try:
        metadata.version("coverage")
    except metadata.PackageNotFoundError as exc:
        raise MeasurementError("coverage is not installed in the current environment") from exc


def resolve_existing_dir(path_value: str, label: str) -> Path:
    path = (REPO_ROOT / path_value).resolve()
    if not path.is_dir():
        raise MeasurementError(f"{label} not found: {path_value}")
    return path


def resolve_output_dir(path_value: str) -> Path:
    path = (REPO_ROOT / path_value).resolve()
    try:
        path.relative_to(REPO_ROOT / "data" / "test_optimization")
    except ValueError as exc:
        raise MeasurementError("output dir must stay under data/test_optimization") from exc
    return path


def ensure_output_dir_safe(output_dir: Path) -> None:
    if output_dir == REPO_ROOT:
        raise MeasurementError("output dir cannot be repository root")


def gather_run_metadata() -> dict[str, Any]:
    return {
        "source_commit": git_output(["git", "rev-parse", "HEAD"]),
        "branch": git_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "pytest_version": metadata.version("pytest"),
        "coverage_version": metadata.version("coverage"),
    }


def safe_run_metadata() -> dict[str, Any]:
    payload = {
        "source_commit": "",
        "branch": "",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "pytest_version": "",
        "coverage_version": "",
    }
    try:
        payload["source_commit"] = git_output(["git", "rev-parse", "HEAD"])
        payload["branch"] = git_output(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    except Exception:
        pass
    try:
        payload["pytest_version"] = metadata.version("pytest")
    except Exception:
        pass
    try:
        payload["coverage_version"] = metadata.version("coverage")
    except Exception:
        pass
    return payload


def detect_enabled_actual_envs() -> list[str]:
    enabled = []
    for name, value in os.environ.items():
        if name in ACTUAL_ENV_VARS or any(pattern.match(name) for pattern in ACTUAL_ENV_PATTERNS):
            if value.strip().lower() in TRUTHY_VALUES:
                enabled.append(name)
    return sorted(enabled)


def build_initial_summary(run_meta: dict[str, Any], tests_root: Path) -> dict[str, Any]:
    return {
        "status": "measurement_failed",
        **run_meta,
        "test_root": tests_root.relative_to(REPO_ROOT).as_posix(),
        "test_file_count": 0,
        "test_physical_lines": 0,
        "test_nonblank_lines": 0,
        "ast_test_function_count": 0,
        "ast_test_class_count": 0,
        "collected_node_count": 0,
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "xfailed": 0,
        "xpassed": 0,
        "normal_full_suite_duration_seconds": 0.0,
        "coverage_full_suite_duration_seconds": 0.0,
        "line_coverage_percent": 0.0,
        "branch_coverage_percent": None,
        "line_coverage_totals": {},
        "branch_coverage_totals": {},
        "warning_event_count": 0,
        "unique_warning_group_count": 0,
        "slowest_test": {},
        "largest_test_file_by_nodes": {},
        "largest_test_file_by_lines": {},
        "production_code_changed": False,
        "test_code_changed": False,
        "actual_external_calls_enabled": False,
    }


def collect_inventory(tests_root: Path) -> list[TestFileStats]:
    seen: dict[str, Path] = {}
    for pattern in ("test_*.py", "*_test.py"):
        for path in tests_root.rglob(pattern):
            if path.is_file():
                seen[path.resolve().as_posix()] = path
    file_stats = []
    for path in sorted(seen.values(), key=lambda item: item.as_posix()):
        rel = path.relative_to(REPO_ROOT).as_posix()
        source = path.read_text(encoding="utf-8-sig")
        physical_lines = len(source.splitlines())
        nonblank_lines = sum(1 for line in source.splitlines() if line.strip())
        try:
            tree = ast.parse(source, filename=rel)
        except SyntaxError as exc:
            raise MeasurementError(f"AST parse failed for {rel}: {exc}", status="measurement_failed") from exc
        test_function_count, test_class_count = count_ast_tests(tree)
        file_stats.append(
            TestFileStats(
                path=rel,
                physical_lines=physical_lines,
                nonblank_lines=nonblank_lines,
                test_function_count=test_function_count,
                test_class_count=test_class_count,
            )
        )
    return file_stats


def count_ast_tests(tree: ast.AST) -> tuple[int, int]:
    function_count = 0
    class_count = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            function_count += 1
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            class_count += 1
    return function_count, class_count


def apply_inventory_stats(summary: dict[str, Any], file_stats: list[TestFileStats]) -> None:
    summary["test_file_count"] = len(file_stats)
    summary["test_physical_lines"] = sum(item.physical_lines for item in file_stats)
    summary["test_nonblank_lines"] = sum(item.nonblank_lines for item in file_stats)
    summary["ast_test_function_count"] = sum(item.test_function_count for item in file_stats)
    summary["ast_test_class_count"] = sum(item.test_class_count for item in file_stats)


def write_inventory(
    path: Path,
    summary: dict[str, Any],
    file_stats: list[TestFileStats],
    *,
    collected_counts: Counter[str] | None,
) -> None:
    top_by_lines = sorted(file_stats, key=lambda item: (-item.physical_lines, item.path))[:20]
    lines = [
        f"Baseline source commit: {summary['source_commit']}",
        f"Branch: {summary['branch']}",
        f"Timestamp UTC: {summary['timestamp_utc']}",
        f"Python version: {summary['python_version']}",
        f"Pytest version: {summary['pytest_version']}",
        f"Coverage version: {summary['coverage_version']}",
        "",
        f"Test root: {summary['test_root']}",
        f"Test file count: {summary['test_file_count']}",
        f"Physical LOC: {summary['test_physical_lines']}",
        f"Nonblank LOC: {summary['test_nonblank_lines']}",
        f"AST test function count: {summary['ast_test_function_count']}",
        f"AST test class count: {summary['ast_test_class_count']}",
        "",
        f"Collected pytest node count: {summary['collected_node_count'] or 'pending collection'}",
        "",
        "Top 20 files by collected node count:",
    ]
    if collected_counts:
        for file_path, count in sorted(collected_counts.items(), key=lambda item: (-item[1], item[0]))[:20]:
            lines.append(f"- {file_path}: {count}")
    else:
        lines.append("- pending collection")
    lines.extend(["", "Top 20 files by physical LOC:"])
    for item in top_by_lines:
        lines.append(f"- {item.path}: {item.physical_lines}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_collection(args: argparse.Namespace, tests_root: Path, output_dir: Path) -> list[str]:
    log_path = output_dir / OUTPUT_FILES["collect_log"]
    collected_path = output_dir / OUTPUT_FILES["collected_nodes"]
    node_results_path = output_dir / "_collect_node_results.json"
    warning_results_path = output_dir / "_collect_warning_results.json"
    command = [
        "uv",
        "run",
        "--no-sync",
        args.python_executable,
        "-m",
        "pytest",
        "--collect-only",
        tests_root.relative_to(REPO_ROOT).as_posix(),
        "-q",
        "-p",
        "scripts._test_baseline_plugin",
    ]
    completed, _ = run_command(
        command,
        log_path=log_path,
        extra_env={
            "PYTHONPATH": ".",
            "EASYADS_BASELINE_COLLECTED_PATH": str(collected_path),
            "EASYADS_BASELINE_NODE_RESULTS_PATH": str(node_results_path),
            "EASYADS_BASELINE_WARNING_RESULTS_PATH": str(warning_results_path),
        },
    )
    if completed.returncode != 0:
        raise MeasurementError(f"pytest collection failed with exit code {completed.returncode}", status="collection_failed")
    payload = load_json(collected_path)
    collected = payload.get("collected_node_ids", [])
    if not isinstance(collected, list):
        raise MeasurementError("invalid collected node payload")
    return [str(node_id) for node_id in collected]


def run_full_suite(args: argparse.Namespace, tests_root: Path, output_dir: Path) -> dict[str, Any]:
    log_path = output_dir / OUTPUT_FILES["pytest_log"]
    node_results_path = output_dir / OUTPUT_FILES["node_results"]
    warning_results_path = output_dir / OUTPUT_FILES["warnings"]
    junit_path = output_dir / OUTPUT_FILES["junit"]
    command = [
        "uv",
        "run",
        "--no-sync",
        args.python_executable,
        "-m",
        "pytest",
        tests_root.relative_to(REPO_ROOT).as_posix(),
        "-q",
        "--durations=0",
        f"--junitxml={junit_path.as_posix()}",
        "-p",
        "scripts._test_baseline_plugin",
    ]
    completed, wall_clock = run_command(
        command,
        log_path=log_path,
        extra_env={
            "PYTHONPATH": ".",
            "EASYADS_BASELINE_NODE_RESULTS_PATH": str(node_results_path),
            "EASYADS_BASELINE_WARNING_RESULTS_PATH": str(warning_results_path),
        },
    )
    node_payload = load_json(node_results_path)
    return {
        "exit_code": completed.returncode,
        "wall_clock_seconds": wall_clock,
        "node_results": node_payload.get("node_results", []),
    }


def run_coverage(args: argparse.Namespace, tests_root: Path, output_dir: Path) -> dict[str, Any]:
    erase_command = ["uv", "run", "--no-sync", "coverage", "erase"]
    erase_completed, _ = run_command(erase_command, log_path=output_dir / OUTPUT_FILES["coverage_log"], extra_env={"PYTHONPATH": "."}, append=False)
    if erase_completed.returncode != 0:
        raise MeasurementError(f"coverage erase failed with exit code {erase_completed.returncode}", status="coverage_failed")

    coverage_command = [
        "uv",
        "run",
        "--no-sync",
        "coverage",
        "run",
        "--branch",
        "-m",
        "pytest",
        tests_root.relative_to(REPO_ROOT).as_posix(),
        "-q",
    ]
    completed, wall_clock = run_command(
        coverage_command,
        log_path=output_dir / OUTPUT_FILES["coverage_log"],
        extra_env={"PYTHONPATH": "."},
        append=True,
    )
    if completed.returncode != 0:
        raise MeasurementError(f"coverage pytest failed with exit code {completed.returncode}", status="coverage_failed")

    json_command = [
        "uv",
        "run",
        "--no-sync",
        "coverage",
        "json",
        "-o",
        (output_dir / OUTPUT_FILES["coverage"]).as_posix(),
    ]
    json_completed, _ = run_command(
        json_command,
        log_path=output_dir / OUTPUT_FILES["coverage_log"],
        extra_env={"PYTHONPATH": "."},
        append=True,
    )
    if json_completed.returncode != 0:
        raise MeasurementError(f"coverage json failed with exit code {json_completed.returncode}", status="coverage_failed")
    return {"wall_clock_seconds": wall_clock}


def run_command(
    command: list[str],
    *,
    log_path: Path,
    extra_env: dict[str, str],
    append: bool = False,
) -> tuple[subprocess.CompletedProcess[str], float]:
    env = os.environ.copy()
    env.update(extra_env)
    start = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    elapsed = time.perf_counter() - start
    mode = "a" if append else "w"
    with log_path.open(mode, encoding="utf-8") as handle:
        handle.write("$ " + " ".join(command) + "\n")
        handle.write(completed.stdout)
        if completed.stderr:
            handle.write("\n[stderr]\n")
            handle.write(completed.stderr)
    return completed, elapsed


def build_duration_report(
    *,
    collected_node_ids: list[str],
    node_results: list[dict[str, Any]],
    top_slow_count: int,
    normal_full_suite_duration_seconds: float,
    pytest_reported_duration_seconds: float,
    coverage_full_suite_duration_seconds: float,
) -> dict[str, Any]:
    file_stats: dict[str, dict[str, Any]] = {}
    for node in node_results:
        file_path = str(node["file"])
        entry = file_stats.setdefault(
            file_path,
            {
                "file": file_path,
                "collected_nodes": 0,
                "executed_nodes": 0,
                "total_seconds": 0.0,
                "average_seconds": 0.0,
                "max_seconds": 0.0,
            },
        )
        entry["executed_nodes"] += 1
        total_seconds = float(node["total_seconds"])
        entry["total_seconds"] += total_seconds
        entry["max_seconds"] = max(entry["max_seconds"], total_seconds)
    collected_counts = Counter(node_id.split("::", 1)[0] for node_id in collected_node_ids)
    for file_path, count in collected_counts.items():
        entry = file_stats.setdefault(
            file_path,
            {
                "file": file_path,
                "collected_nodes": 0,
                "executed_nodes": 0,
                "total_seconds": 0.0,
                "average_seconds": 0.0,
                "max_seconds": 0.0,
            },
        )
        entry["collected_nodes"] = count
    files = sorted(file_stats.values(), key=lambda item: (-item["total_seconds"], item["file"]))
    for item in files:
        executed = item["executed_nodes"]
        item["average_seconds"] = item["total_seconds"] / executed if executed else 0.0
        item["total_seconds"] = round(item["total_seconds"], 6)
        item["average_seconds"] = round(item["average_seconds"], 6)
        item["max_seconds"] = round(item["max_seconds"], 6)

    sorted_nodes = sorted(
        node_results,
        key=lambda item: (-float(item["total_seconds"]), str(item["node_id"])),
    )[:top_slow_count]
    top_slow_tests = [
        {
            "rank": index,
            "node_id": item["node_id"],
            "file": item["file"],
            "outcome": item["outcome"],
            "total_seconds": round(float(item["total_seconds"]), 6),
        }
        for index, item in enumerate(sorted_nodes, start=1)
    ]
    return {
        "normal_full_suite_duration_seconds": round(normal_full_suite_duration_seconds, 6),
        "pytest_reported_duration_seconds": round(pytest_reported_duration_seconds, 6),
        "coverage_full_suite_duration_seconds": round(coverage_full_suite_duration_seconds, 6),
        "top_slow_tests": top_slow_tests,
        "files": files,
    }


def apply_result_counts(summary: dict[str, Any], node_results: list[dict[str, Any]]) -> None:
    counts = Counter(str(item["outcome"]) for item in node_results)
    summary["passed"] = counts.get("passed", 0)
    summary["failed"] = counts.get("failed", 0)
    summary["errors"] = counts.get("error", 0)
    summary["skipped"] = counts.get("skipped", 0)
    summary["xfailed"] = counts.get("xfailed", 0)
    summary["xpassed"] = counts.get("xpassed", 0)


def apply_warning_stats(summary: dict[str, Any], warning_report: dict[str, Any]) -> None:
    summary["warning_event_count"] = int(warning_report.get("total_warning_events", 0))
    summary["unique_warning_group_count"] = int(warning_report.get("unique_warning_groups", 0))


def largest_file_by_nodes(files: list[dict[str, Any]]) -> dict[str, Any]:
    if not files:
        return {}
    top = max(files, key=lambda item: (int(item["collected_nodes"]), -len(item["file"])))
    return {"file": top["file"], "collected_nodes": top["collected_nodes"]}


def largest_file_by_lines(file_stats: list[TestFileStats]) -> dict[str, Any]:
    if not file_stats:
        return {}
    top = max(file_stats, key=lambda item: (item.physical_lines, -len(item.path)))
    return {"file": top.path, "physical_lines": top.physical_lines}


def failed_node_ids(node_results: list[dict[str, Any]]) -> list[str]:
    return [
        item["node_id"]
        for item in node_results
        if item["outcome"] in {"failed", "error"}
    ]


def apply_coverage_stats(summary: dict[str, Any], coverage_report: dict[str, Any]) -> None:
    totals = coverage_report.get("totals", {})
    num_statements = totals.get("num_statements", 0)
    covered_lines = totals.get("covered_lines", 0)
    missing_lines = totals.get("missing_lines", 0)
    num_branches = totals.get("num_branches", 0)
    covered_branches = totals.get("covered_branches", 0)
    missing_branches = totals.get("missing_branches", 0)

    summary["line_coverage_percent"] = round((covered_lines / num_statements * 100.0), 4) if num_statements else 0.0
    if num_branches:
        summary["branch_coverage_percent"] = round((covered_branches / num_branches * 100.0), 4)
    else:
        summary["branch_coverage_percent"] = None
        summary["branch_coverage_reason"] = "coverage reported zero branch opportunities"
    summary["line_coverage_totals"] = {
        "num_statements": num_statements,
        "covered_lines": covered_lines,
        "missing_lines": missing_lines,
        "percent_covered": totals.get("percent_covered", 0.0),
    }
    summary["branch_coverage_totals"] = {
        "num_branches": num_branches,
        "covered_branches": covered_branches,
        "missing_branches": missing_branches,
    }


def validate_artifacts(output_dir: Path, *, require_coverage: bool) -> None:
    required = [
        output_dir / OUTPUT_FILES["inventory"],
        output_dir / OUTPUT_FILES["junit"],
        output_dir / OUTPUT_FILES["duration"],
        output_dir / OUTPUT_FILES["warnings"],
        output_dir / OUTPUT_FILES["summary"],
    ]
    if require_coverage:
        required.append(output_dir / OUTPUT_FILES["coverage"])
    for path in required:
        if not path.is_file() or path.stat().st_size == 0:
            raise MeasurementError(f"artifact missing or empty: {path.relative_to(REPO_ROOT).as_posix()}")
    for path in required:
        if path.suffix == ".json":
            load_json(path)
    validate_counts(output_dir, require_coverage=require_coverage)


def validate_counts(output_dir: Path, *, require_coverage: bool) -> None:
    del require_coverage
    collected = load_json(output_dir / OUTPUT_FILES["collected_nodes"]).get("collected_node_ids", [])
    node_results = load_json(output_dir / OUTPUT_FILES["node_results"]).get("node_results", [])
    duration_report = load_json(output_dir / OUTPUT_FILES["duration"])
    summary = load_json(output_dir / OUTPUT_FILES["summary"])
    junit_count = count_junit_testcases(output_dir / OUTPUT_FILES["junit"])
    executed_count = sum(int(item.get("executed_nodes", 0)) for item in duration_report.get("files", []))
    summary_count = (
        int(summary.get("passed", 0))
        + int(summary.get("failed", 0))
        + int(summary.get("errors", 0))
        + int(summary.get("skipped", 0))
        + int(summary.get("xfailed", 0))
        + int(summary.get("xpassed", 0))
    )
    if junit_count != len(node_results):
        raise MeasurementError(f"count mismatch: junit={junit_count}, node_results={len(node_results)}")
    if executed_count != len(node_results):
        raise MeasurementError(f"count mismatch: duration executed={executed_count}, node_results={len(node_results)}")
    if summary_count != len(node_results):
        raise MeasurementError(f"count mismatch: summary={summary_count}, node_results={len(node_results)}")
    if summary.get("status") == "completed" and len(collected) != len(node_results):
        raise MeasurementError(f"count mismatch: collected={len(collected)}, node_results={len(node_results)}")


def count_junit_testcases(path: Path) -> int:
    root = ET.parse(path).getroot()
    return len(root.findall(".//testcase"))


def git_output(command: list[str]) -> str:
    completed = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return completed.stdout.strip()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


if __name__ == "__main__":
    raise SystemExit(main())
