from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[1]
_COLLECTED_PATH = os.environ.get("EASYADS_BASELINE_COLLECTED_PATH")
_NODE_RESULTS_PATH = os.environ.get("EASYADS_BASELINE_NODE_RESULTS_PATH")
_WARNING_RESULTS_PATH = os.environ.get("EASYADS_BASELINE_WARNING_RESULTS_PATH")

_MEMORY_ADDRESS_RE = re.compile(r"0x[0-9a-fA-F]+")
_WHITESPACE_RE = re.compile(r"\s+")


def _repo_relative(path_value: str | os.PathLike[str] | None) -> str | None:
    if path_value is None:
        return None
    try:
        path = Path(path_value).resolve()
    except OSError:
        return str(path_value)
    try:
        return path.relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _normalize_warning_message(message: str) -> str:
    collapsed = _WHITESPACE_RE.sub(" ", message).strip()
    return _MEMORY_ADDRESS_RE.sub("0xADDR", collapsed)


def _warning_location(location: tuple[str, int, str] | None) -> str | None:
    if not location:
        return None
    filename, lineno, _ = location
    rel = _repo_relative(filename) or filename
    return f"{rel}:{lineno}"


class BaselinePlugin:
    def __init__(self) -> None:
        self.collected_node_ids: list[str] = []
        self.node_records: dict[str, dict[str, Any]] = {}
        self.warning_groups: dict[tuple[str, str], dict[str, Any]] = {}

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        self.collected_node_ids = [item.nodeid for item in session.items]

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        node_id = report.nodeid
        record = self.node_records.setdefault(
            node_id,
            {
                "node_id": node_id,
                "file": _repo_relative(str(report.fspath)) or str(report.fspath),
                "outcome": None,
                "phase": None,
                "setup_seconds": 0.0,
                "call_seconds": 0.0,
                "teardown_seconds": 0.0,
                "total_seconds": 0.0,
            },
        )
        phase_key = f"{report.when}_seconds"
        if phase_key in record:
            record[phase_key] += float(report.duration or 0.0)
        record["total_seconds"] = (
            record["setup_seconds"] + record["call_seconds"] + record["teardown_seconds"]
        )

        if report.when == "call":
            if getattr(report, "wasxfail", False):
                record["outcome"] = "xfailed" if report.skipped else "xpassed"
            elif report.passed:
                record["outcome"] = "passed"
            elif report.failed:
                record["outcome"] = "failed"
            elif report.skipped:
                record["outcome"] = "skipped"
            record["phase"] = report.when
            return

        if report.failed:
            record["outcome"] = "error"
            record["phase"] = report.when
            return

        if report.when == "setup" and report.skipped:
            if getattr(report, "wasxfail", False):
                record["outcome"] = "xfailed"
            else:
                record["outcome"] = "skipped"
            record["phase"] = report.when
            return

        if report.when == "teardown" and record["outcome"] is None:
            record["outcome"] = "passed"
            record["phase"] = report.when

    def pytest_warning_recorded(
        self,
        warning_message: Any,
        when: str,
        nodeid: str | None,
        location: tuple[str, int, str] | None,
    ) -> None:
        category = warning_message.category.__name__
        normalized_message = _normalize_warning_message(str(warning_message.message))
        key = (category, normalized_message)
        group = self.warning_groups.setdefault(
            key,
            {
                "category": category,
                "normalized_message": normalized_message,
                "count": 0,
                "locations": set(),
                "node_ids": set(),
                "when": set(),
            },
        )
        group["count"] += 1
        loc = _warning_location(location)
        if loc:
            group["locations"].add(loc)
        if nodeid:
            group["node_ids"].add(nodeid)
        group["when"].add(when)

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        if _COLLECTED_PATH:
            _write_json(Path(_COLLECTED_PATH), {"collected_node_ids": self.collected_node_ids})
        if _NODE_RESULTS_PATH:
            node_results = sorted(self.node_records.values(), key=lambda item: item["node_id"])
            _write_json(Path(_NODE_RESULTS_PATH), {"node_results": node_results, "exitstatus": exitstatus})
        if _WARNING_RESULTS_PATH:
            warnings = []
            category_counts: dict[str, int] = defaultdict(int)
            total_warning_events = 0
            for group in sorted(
                self.warning_groups.values(),
                key=lambda item: (-item["count"], item["category"], item["normalized_message"]),
            ):
                locations = sorted(group["locations"])
                count = int(group["count"])
                total_warning_events += count
                category_counts[group["category"]] += count
                warnings.append(
                    {
                        "category": group["category"],
                        "normalized_message": group["normalized_message"],
                        "count": count,
                        "locations": locations,
                    }
                )
            payload = {
                "total_warning_events": total_warning_events,
                "unique_warning_groups": len(warnings),
                "categories": dict(sorted(category_counts.items())),
                "warnings": warnings,
            }
            _write_json(Path(_WARNING_RESULTS_PATH), payload)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def pytest_configure(config: pytest.Config) -> None:
    config.pluginmanager.register(BaselinePlugin(), "easyads-test-baseline-plugin")
