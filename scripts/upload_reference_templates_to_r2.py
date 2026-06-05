"""Upload permanent reference template images to Cloudflare R2.

The script reads orchestrator/app/reference_catalog/permanent_templates.json and
maps each catalog item to data/reference_templates/inbox/<source_file>.
It is dry-run by default. Pass --upload to write to R2.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.app.storage.errors import R2StorageUnavailableError, R2UploadError
from orchestrator.app.storage.r2_service import upload_file_to_r2


DEFAULT_MANIFEST_PATH = Path("orchestrator/app/reference_catalog/permanent_templates.json")
DEFAULT_SOURCE_ROOT = Path("data/reference_templates/inbox")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload permanent reference templates to R2.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--template-id", action="append", default=[], help="Upload only selected template id. Repeatable.")
    parser.add_argument("--upload", action="store_true", help="Actually upload files. Default is dry-run.")
    return parser.parse_args()


def load_items(manifest_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        items = payload.get("items") or payload.get("templates") or []
        return [item for item in items if isinstance(item, dict)]
    return []


def r2_object_key_for_item(item: dict[str, Any]) -> str | None:
    metadata = item.get("metadata") or {}
    if isinstance(metadata, dict) and metadata.get("r2_object_key"):
        return str(metadata["r2_object_key"])
    assets = item.get("assets") or {}
    if not isinstance(assets, dict):
        return None
    source_path = str(assets.get("source_image_path") or assets.get("preview_path") or assets.get("thumbnail_path") or "")
    return source_path.removeprefix("r2://") or None


def source_file_for_item(item: dict[str, Any]) -> str | None:
    metadata = item.get("metadata") or {}
    if isinstance(metadata, dict) and metadata.get("source_file"):
        return str(metadata["source_file"])
    return None


def main() -> int:
    args = parse_args()
    selected = set(args.template_id)
    items = load_items(args.manifest)
    if selected:
        items = [item for item in items if str(item.get("template_id")) in selected]

    if not items:
        print("No reference template items found.")
        return 1

    failures: list[str] = []
    for item in items:
        template_id = str(item.get("template_id") or "")
        source_file = source_file_for_item(item)
        object_key = r2_object_key_for_item(item)
        if not source_file or not object_key:
            failures.append(f"{template_id}: missing source_file or r2_object_key")
            continue

        local_path = args.source_root / source_file
        if not local_path.is_file():
            failures.append(f"{template_id}: missing local file {local_path}")
            continue

        if not args.upload:
            print(f"DRY-RUN {template_id}: {local_path} -> {object_key}")
            continue

        try:
            uploaded = upload_file_to_r2(
                local_path=local_path,
                object_key=object_key,
                metadata={
                    "source": "reference_template_upload",
                    "template_id": template_id,
                    "source_file": source_file,
                },
            )
        except (R2StorageUnavailableError, R2UploadError) as exc:
            failures.append(f"{template_id}: {exc}")
            continue
        print(f"UPLOADED {template_id}: {uploaded.object_key}")

    if failures:
        print("\nFailures:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    action = "uploaded" if args.upload else "checked"
    print(f"\n{len(items)} reference template image(s) {action}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
