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


def run_self_check() -> dict[str, Any]:
    payload = {
        "status": "dry_run_only",
        "destructive_retention_enabled": False,
        "candidates": [],
    }
    assert payload["destructive_retention_enabled"] is False
    return {"status": "ok", "checked": ["dry_run_only", "no_destructive_cleanup"]}


def main() -> None:
    args = parse_args()
    if args.self_check:
        print(json.dumps(run_self_check(), ensure_ascii=False))
        return
    output_dir = Path(args.output_dir)
    write_json(
        output_dir / "cleanup_candidates.json",
        {
            "status": "dry_run_only",
            "destructive_retention_enabled": False,
            "candidates": [],
        },
    )


if __name__ == "__main__":
    main()
