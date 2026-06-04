"""Safe artifact path and payload helpers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from orchestrator.app.artifacts.schemas import ResultArtifactPayload


OUTPUTS_ROOT = Path("data") / "outputs"
_SECRET_KEY_PATTERN = re.compile(
    r"(api[_-]?key|token|secret|authorization|password|service[_-]?role[_-]?key|access[_-]?key)",
    re.IGNORECASE,
)
_URL_KEY_PATTERN = re.compile(r"url$", re.IGNORECASE)
_PATH_KEY_PATTERN = re.compile(r"path$", re.IGNORECASE)


def get_job_output_dir(job_id: str) -> Path:
    if not job_id.startswith("job_") or ".." in job_id or "/" in job_id or "\\" in job_id or Path(job_id).is_absolute():
        raise ValueError("invalid generation job id")
    path = OUTPUTS_ROOT / job_id
    root = OUTPUTS_ROOT.resolve()
    resolved = path.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("generation job output path escaped outputs root")
    return path


def ensure_job_output_dir(job_id: str) -> Path:
    output_dir = get_job_output_dir(job_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def write_json_artifact(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_repo_relative_artifact_path(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.replace("\\", "/").strip()
    if not normalized:
        return None
    if normalized.startswith(("C:/", "D:/", "/tmp/", "/var/", "/mnt/", "/home/", "file://", "../", "..\\")):
        return None
    if normalized.startswith("data/outputs/") or normalized.startswith("data/logs/"):
        return normalized
    return None


def sanitize_result_artifact_payload_for_api(payload: object) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    sanitized = _sanitize_payload_value(payload)
    if not isinstance(sanitized, dict):
        return None
    return sanitized


def merge_final_asset_into_result_payload(
    *,
    result_payload: dict[str, Any] | None,
    asset_row: dict[str, Any] | None,
    uploaded_asset: object | None,
    storage_provider: str,
) -> dict[str, Any]:
    payload = dict(result_payload or {})
    asset_id = str(asset_row.get("id")) if asset_row and asset_row.get("id") is not None else None
    bucket = asset_row.get("bucket") if asset_row else None
    object_key = asset_row.get("object_key") if asset_row else None
    existing_final_asset = (payload.get("assets") or {}).get("final") or {}
    final_image_url = getattr(uploaded_asset, "final_image_url", None) or payload.get("final_image_url")
    download_url = getattr(uploaded_asset, "download_url", None) or payload.get("download_url")
    signed_url_expires_at = getattr(uploaded_asset, "signed_url_expires_at", None) or payload.get("signed_url_expires_at")
    url_mode = payload.get("url_mode")
    if uploaded_asset is not None:
        metadata = getattr(uploaded_asset, "metadata", {}) or {}
        if isinstance(metadata, dict):
            url_mode = metadata.get("url_mode") or url_mode

    merged_asset = {
        "asset_id": asset_id,
        "kind": asset_row.get("kind") if asset_row else "result",
        "storage_provider": storage_provider,
        "bucket": bucket,
        "object_key": object_key,
        "mime_type": asset_row.get("mime_type") if asset_row else existing_final_asset.get("mime_type"),
        "size_bytes": asset_row.get("size_bytes") if asset_row else existing_final_asset.get("size_bytes"),
        "width": asset_row.get("width") if asset_row else existing_final_asset.get("width"),
        "height": asset_row.get("height") if asset_row else existing_final_asset.get("height"),
        "public_url": asset_row.get("public_url") if asset_row else existing_final_asset.get("public_url"),
        "final_image_url": final_image_url,
        "download_url": download_url,
        "preview_url": existing_final_asset.get("preview_url"),
        "url_mode": url_mode,
        "signed_url_expires_at": signed_url_expires_at,
        "public_serving": bool(final_image_url or download_url),
        "metadata": (asset_row.get("metadata") if asset_row else existing_final_asset.get("metadata") or {}) or {},
    }

    return {
        **payload,
        "final_asset_id": asset_id,
        "storage_provider": storage_provider,
        "bucket": bucket,
        "object_key": object_key,
        "url_mode": url_mode,
        "final_image_url": final_image_url,
        "download_url": download_url,
        "signed_url_expires_at": signed_url_expires_at,
        "assets": {
            **(payload.get("assets") or {}),
            "final": merged_asset,
        },
    }


def build_result_artifact_payload(
    job_id: str,
    background_image_path: Path,
    final_image_path: Path,
    metadata_path: Path,
    prompt_path: Path,
    validation_path: Path,
    copy_path: Path | None = None,
    layout_path: Path | None = None,
    render_result_path: Path | None = None,
    prompt_summary: dict[str, Any] | None = None,
    validation_summary: dict[str, Any] | None = None,
    copy_summary: dict[str, Any] | None = None,
    layout_summary: dict[str, Any] | None = None,
    has_text_overlay: bool = True,
    engine: str = "mock",
    render_mode: str = "deterministic_mock",
) -> ResultArtifactPayload:
    output_dir = get_job_output_dir(job_id)
    return ResultArtifactPayload(
        job_id=job_id,
        output_dir=output_dir.as_posix(),
        background_image_path=background_image_path.as_posix(),
        final_image_path=final_image_path.as_posix(),
        metadata_path=metadata_path.as_posix(),
        prompt_path=prompt_path.as_posix(),
        validation_path=validation_path.as_posix(),
        copy_path=copy_path.as_posix() if copy_path else None,
        layout_path=layout_path.as_posix() if layout_path else None,
        render_result_path=render_result_path.as_posix() if render_result_path else None,
        download_path=final_image_path.as_posix(),
        download_url=None,
        final_image_url=None,
        prompt_summary=prompt_summary or {},
        validation_summary=validation_summary or {},
        copy_summary=copy_summary or {},
        layout_summary=layout_summary or {},
        has_text_overlay=has_text_overlay,
        engine=engine,
        render_mode=render_mode,
    )


def _sanitize_payload_value(value: object, *, key: str | None = None) -> object:
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for child_key, child_value in value.items():
            string_key = str(child_key)
            if _SECRET_KEY_PATTERN.search(string_key):
                continue
            sanitized_child = _sanitize_payload_value(child_value, key=string_key)
            if sanitized_child is None and _PATH_KEY_PATTERN.search(string_key):
                output[string_key] = None
                continue
            output[string_key] = sanitized_child
        return output
    if isinstance(value, list):
        return [_sanitize_payload_value(item) for item in value[:50]]
    if isinstance(value, str):
        if key and _URL_KEY_PATTERN.search(key):
            return value if value.startswith(("http://", "https://")) else None
        if key and _PATH_KEY_PATTERN.search(key):
            return normalize_repo_relative_artifact_path(value)
        if value.startswith(("file://", "data:image", "javascript:")):
            return None
        return value
    return value
