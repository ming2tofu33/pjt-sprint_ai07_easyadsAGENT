from __future__ import annotations

from pathlib import Path

from scripts._test_marker_taxonomy import classify_node


def pytest_collection_modifyitems(config, items):
    del config
    for item in items:
        file_path = Path(str(item.fspath)).as_posix()
        primary, traits = classify_node(file_path, item.nodeid)
        item.add_marker(primary)
        for trait in sorted(traits):
            item.add_marker(trait)
