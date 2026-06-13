from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


STATUS_MAP = {
    "killed": "killed",
    "survived": "survived",
    "timeout": "timeout",
    "no tests": "uncovered",
    "uncovered": "uncovered",
    "suspicious": "error",
    "segfault": "error",
    "incompetent": "error",
    "error": "error",
}


def run_command(command: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, env=env)


def parse_results(output: str) -> list[dict[str, Any]]:
    rows = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ": " not in line:
            raise ValueError(f"unexpected_results_line:{line}")
        mutant_id, raw_status = line.split(": ", 1)
        normalized = STATUS_MAP.get(raw_status)
        if normalized is None:
            raise ValueError(f"unknown_status:{raw_status}")
        rows.append({"mutant_id": mutant_id, "raw_status": raw_status, "status": normalized})
    return rows


def collect_details(rows: list[dict[str, Any]], *, python_cmd: str, cwd: Path, env: dict[str, str]) -> list[dict[str, Any]]:
    details = []
    for row in rows:
        show = run_command([python_cmd, "-m", "mutmut", "show", row["mutant_id"]], cwd=cwd, env=env)
        tests = run_command([python_cmd, "-m", "mutmut", "tests-for-mutant", row["mutant_id"]], cwd=cwd, env=env)
        details.append(
            {
                **row,
                "show_returncode": show.returncode,
                "show_output": show.stdout,
                "killing_tests": [line.strip() for line in tests.stdout.splitlines() if line.strip()],
                "tests_for_mutant_returncode": tests.returncode,
            }
        )
    return details


def summarize(stats: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    generated = int(stats.get("total", 0))
    counts = {
        "killed": int(stats.get("killed", 0)),
        "survived": int(stats.get("survived", 0)),
        "timeout": int(stats.get("timeout", 0)),
        "uncovered": int(stats.get("no_tests", 0)),
        "error": int(stats.get("suspicious", 0)) + int(stats.get("segfault", 0)) + int(stats.get("incompetent", 0)),
    }
    listed = Counter(row["status"] for row in rows)
    total_normalized = counts["killed"] + counts["survived"] + counts["timeout"] + counts["uncovered"] + counts["error"]
    return {
        "generated": generated,
        "counts": counts,
        "count_consistent": generated == total_normalized and listed["survived"] <= counts["survived"] and listed["timeout"] <= counts["timeout"] and listed["uncovered"] <= counts["uncovered"] and listed["error"] <= counts["error"],
        "unknown_status_count": 0,
        "listed_result_rows": len(rows),
    }


def load_stats(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
