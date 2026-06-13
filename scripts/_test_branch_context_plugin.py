from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import coverage
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = Path(
    os.environ.get(
        "EASYADS_BRANCH_CONTEXT_NODES_PATH",
        str(REPO_ROOT / "data/test_optimization/branch_context_v1/pytest_nodes.json"),
    )
)
SESSION_CONTEXT = "pytest::<session>"


def _repo_relative(path_value: str | os.PathLike[str] | None) -> str | None:
    if path_value is None:
        return None
    try:
        path = Path(path_value).resolve()
    except OSError:
        return str(path_value)
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


class BranchContextPlugin:
    def __init__(self) -> None:
        self.collected_node_ids: list[str] = []
        self.node_records: dict[str, dict[str, Any]] = {}
        self._coverage_available = False

    def pytest_sessionstart(self, session: pytest.Session) -> None:
        cov = coverage.Coverage.current()
        if cov is None:
            raise RuntimeError("coverage.Coverage.current() returned None; fail-closed")
        self._coverage_available = True
        cov.switch_context(SESSION_CONTEXT)

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        self.collected_node_ids = [item.nodeid for item in session.items]
        for item in session.items:
            self.node_records.setdefault(
                item.nodeid,
                {
                    "node_id": item.nodeid,
                    "file": _repo_relative(str(item.fspath)) or str(item.fspath),
                    "markers": sorted(marker.name for marker in item.iter_markers()),
                    "parameterized": "[" in item.nodeid and item.nodeid.endswith("]"),
                    "outcome": "notrun",
                    "skip": False,
                    "phases": {},
                },
            )

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_runtest_protocol(self, item: pytest.Item, nextitem: pytest.Item | None) -> Any:
        cov = coverage.Coverage.current()
        if cov is None:
            raise RuntimeError("coverage runtime missing during pytest_runtest_protocol")
        cov.switch_context(f"pytest::{item.nodeid}")
        try:
            yield
        finally:
            cov.switch_context(SESSION_CONTEXT)

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        record = self.node_records.setdefault(
            report.nodeid,
            {
                "node_id": report.nodeid,
                "file": _repo_relative(str(report.fspath)) or str(report.fspath),
                "markers": [],
                "parameterized": "[" in report.nodeid and report.nodeid.endswith("]"),
                "outcome": "notrun",
                "skip": False,
                "phases": {},
            },
        )
        record["phases"][report.when] = report.outcome
        if report.when == "call":
            if getattr(report, "wasxfail", False):
                record["outcome"] = "xfailed" if report.skipped else "xpassed"
            else:
                record["outcome"] = report.outcome
        elif report.failed:
            record["outcome"] = "error"
        elif report.when == "setup" and report.skipped:
            record["outcome"] = "skipped"
            record["skip"] = True
        elif report.when == "teardown" and record["outcome"] == "notrun":
            record["outcome"] = "passed"
        if report.skipped:
            record["skip"] = True

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        if self._coverage_available:
            cov = coverage.Coverage.current()
            if cov is None:
                raise RuntimeError("coverage runtime missing during pytest_sessionfinish")
            cov.switch_context(SESSION_CONTEXT)
        payload = {
            "exitstatus": exitstatus,
            "session_context": SESSION_CONTEXT,
            "collected_node_ids": self.collected_node_ids,
            "nodes": [self.node_records[node_id] for node_id in self.collected_node_ids],
        }
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def pytest_configure(config: pytest.Config) -> None:
    config.pluginmanager.register(BranchContextPlugin(), "easyads-branch-context-plugin")
