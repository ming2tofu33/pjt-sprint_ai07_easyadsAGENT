from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "scripts/critical_semantic_mutants_v1.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST.relative_to(REPO_ROOT)).replace("\\", "/"))
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--apply")
    parser.add_argument("--revert")
    parser.add_argument("--worktree", default=".")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_manifest(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def load_manifest(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    if payload.get("version") != 1:
        raise SystemExit("unsupported_manifest_version")
    if not isinstance(payload.get("mutants"), list) or not payload["mutants"]:
        raise SystemExit("manifest_has_no_mutants")
    return payload


def mutant_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["mutant_id"]: item for item in manifest["mutants"]}


def apply_replace_once(text: str, old: str, new: str) -> str:
    if old not in text:
        raise SystemExit("stale_patch_rejected")
    if text.count(old) != 1:
        raise SystemExit("non_unique_patch_target")
    return text.replace(old, new, 1)


def revert_replace_once(text: str, old: str, new: str) -> str:
    if new not in text:
        raise SystemExit("revert_target_missing")
    if text.count(new) != 1:
        raise SystemExit("non_unique_revert_target")
    return text.replace(new, old, 1)


def apply_mutant(worktree: Path, mutant: dict[str, Any]) -> Path:
    file_path = (worktree / mutant["file"]).resolve()
    text = file_path.read_text(encoding="utf-8")
    for op in mutant["operations"]:
        if op["type"] != "replace_once":
            raise SystemExit("unsupported_operation")
        text = apply_replace_once(text, op["old"], op["new"])
    file_path.write_text(text, encoding="utf-8")
    return file_path


def revert_mutant(worktree: Path, mutant: dict[str, Any]) -> Path:
    file_path = (worktree / mutant["file"]).resolve()
    text = file_path.read_text(encoding="utf-8")
    for op in reversed(mutant["operations"]):
        if op["type"] != "replace_once":
            raise SystemExit("unsupported_operation")
        text = revert_replace_once(text, op["old"], op["new"])
    file_path.write_text(text, encoding="utf-8")
    return file_path


def run_self_check() -> int:
    original = "alpha\nbeta\n"
    mutated = apply_replace_once(original, "beta", "gamma")
    assert mutated == "alpha\ngamma\n"
    reverted = revert_replace_once(mutated, "beta", "gamma")
    assert reverted == original
    try:
        apply_replace_once(original, "missing", "gamma")
    except SystemExit as exc:
        assert str(exc) == "stale_patch_rejected"
    print("self_check=ok")
    return 0


def main() -> int:
    args = parse_args()
    if args.self_check:
        return run_self_check()
    manifest = load_manifest(resolve_manifest(args.manifest))
    mutants = mutant_map(manifest)
    if args.list:
        print(json.dumps({"mutants": list(mutants.values())}, indent=2, ensure_ascii=False))
        return 0
    worktree = (REPO_ROOT / args.worktree).resolve() if not Path(args.worktree).is_absolute() else Path(args.worktree).resolve()
    if args.apply:
        path = apply_mutant(worktree, mutants[args.apply])
        print(json.dumps({"status": "applied", "mutant_id": args.apply, "file": str(path)}, ensure_ascii=False))
        return 0
    if args.revert:
        path = revert_mutant(worktree, mutants[args.revert])
        print(json.dumps({"status": "reverted", "mutant_id": args.revert, "file": str(path)}, ensure_ascii=False))
        return 0
    raise SystemExit("choose --list, --apply, --revert, or --self-check")


if __name__ == "__main__":
    raise SystemExit(main())
