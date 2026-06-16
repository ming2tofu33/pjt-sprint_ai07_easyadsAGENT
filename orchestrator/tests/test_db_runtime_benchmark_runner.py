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
    module.write_json(
        module.OUTPUT_DIR / "_self_check" / "benchmark_runs.json",
        {"phase_status": "completed", "runs": [], "scenario_summaries": []},
    )
    payload = module.run_self_check()
    assert payload["status"] == "ok"
    assert "comparison" in payload["checked"]


def test_contract_diff_reports_changed_path():
    module = _load_module(Path("scripts/measure_db_runtime_paths.py"), "measure_db_runtime_paths_diff")
    diffs = module.diff_payloads({"download_url": "a"}, {"download_url": "b"})
    assert diffs[0]["path"] == "$.download_url"


def test_d6_dynamic_timestamp_is_ignored_only_for_d6():
    module = _load_module(Path("scripts/measure_db_runtime_paths.py"), "measure_db_runtime_paths_canon")
    before = {"saved_at": "one", "download_url": "x"}
    after = {"saved_at": "two", "download_url": "x"}
    assert module.canonicalize_contract_payload(before, "D6b") == module.canonicalize_contract_payload(after, "D6b")
    assert module.canonicalize_contract_payload(before, "D5") != module.canonicalize_contract_payload(after, "D5")
