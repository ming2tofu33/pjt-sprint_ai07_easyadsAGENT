from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "performance" / "checkpoint_artifact_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--self-check", action="store_true")
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_stub_payload() -> dict[str, Any]:
    return {
        "status": "policy_defined_not_planned",
        "destructive_retention_enabled": False,
        "reason": "Runtime checkpoint metadata inputs were not collected in the no-go audit path.",
        "required_runtime_inputs": [
            "job_status",
            "checkpoint_created_at",
            "last_resume_time",
            "thread_or_job_scope",
            "final_canonical_result_present",
            "retention_age",
        ],
        "candidates": [],
    }


def run_self_check() -> dict[str, Any]:
    payload = build_stub_payload()
    assert payload["destructive_retention_enabled"] is False
    assert payload["status"] == "policy_defined_not_planned"
    assert payload["candidates"] == []
    return {"status": "ok", "checked": ["stub_named_explicitly", "no_destructive_cleanup"]}


def main() -> None:
    args = parse_args()
    if args.self_check:
        print(json.dumps(run_self_check(), ensure_ascii=False))
        return
    output_dir = Path(args.output_dir)
    write_json(output_dir / "cleanup_candidates.json", build_stub_payload())


if __name__ == "__main__":
    main()
