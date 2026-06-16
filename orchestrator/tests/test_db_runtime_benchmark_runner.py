from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_controller_scenario_expansion():
    module = _load_module(Path("scripts/measure_db_runtime_paths.py"), "measure_db_runtime_paths")
    assert module.expanded_scenarios(["D1", "D6", "D7", "D9"]) == ["D1", "D6a", "D6b", "D7a", "D7b", "D9"]


def test_controller_self_check():
    module = _load_module(Path("scripts/measure_db_runtime_paths.py"), "measure_db_runtime_paths_self")
    payload = module.run_self_check()
    assert payload["status"] == "ok"
    assert "comparison" in payload["checked"]
