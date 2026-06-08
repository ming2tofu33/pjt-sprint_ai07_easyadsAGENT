"""R2 object key helpers."""

from __future__ import annotations

from pathlib import Path
import re


_SAFE_PART = re.compile(r"[^A-Za-z0-9_.-]+")


def safe_object_key_part(value: str) -> str:
    normalized = str(value).strip().replace("\\", "/")
    normalized = Path(normalized).name
    normalized = normalized.replace("..", "")
    normalized = _SAFE_PART.sub("_", normalized)
    normalized = normalized.strip("._")
    if not normalized:
        raise ValueError("Object key part must not be empty.")
    return normalized


def build_generation_object_key(*, workspace_id: str, thread_id: str, job_id: str, filename: str) -> str:
    return "/".join(
        [
            "workspaces",
            safe_object_key_part(workspace_id),
            "threads",
            safe_object_key_part(thread_id),
            "jobs",
            safe_object_key_part(job_id),
            safe_object_key_part(Path(filename).name),
        ]
    )


def build_upload_object_key(*, workspace_id: str, public_asset_id: str, extension: str) -> str:
    # ensure extension starts with a dot
    ext = extension.strip().lower()
    if not ext.startswith("."):
        ext = f".{ext}"
    if ext == ".jpeg":
        ext = ".jpg"
    
    return "/".join(
        [
            "workspaces",
            safe_object_key_part(workspace_id),
            "uploads",
            safe_object_key_part(public_asset_id),
            f"original{ext}",
        ]
    )
