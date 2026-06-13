from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from scripts._test_marker_taxonomy import PRIMARY_MARKERS, TRAIT_MARKERS, taxonomy_marker_names


_OUTPUT_PATH = os.environ.get("EASYADS_MARKER_INVENTORY_PATH")
_REPO_ROOT = Path(__file__).resolve().parents[1]


class MarkerInventoryPlugin:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        for item in session.items:
            names = taxonomy_marker_names([mark.name for mark in item.iter_markers()])
            primary = [name for name in names if name in PRIMARY_MARKERS]
            traits = [name for name in names if name in TRAIT_MARKERS]
            self.records.append(
                {
                    "node_id": item.nodeid,
                    "file": _repo_relative(str(item.fspath)),
                    "primary_markers": sorted(primary),
                    "trait_markers": sorted(traits),
                    "all_markers": sorted(names),
                }
            )

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        del session
        if not _OUTPUT_PATH:
            return
        path = Path(_OUTPUT_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "exitstatus": exitstatus,
                    "nodes": sorted(self.records, key=lambda item: str(item["node_id"])),
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )


def _repo_relative(path_value: str) -> str:
    path = Path(path_value).resolve()
    try:
        return path.relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def pytest_configure(config: pytest.Config) -> None:
    config.pluginmanager.register(MarkerInventoryPlugin(), "easyads-test-marker-inventory-plugin")
