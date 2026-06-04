"""Safe artifact path and payload helpers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from orchestrator.app.artifacts.schemas import ResultArtifactAssetRef, ResultArtifactPayload


OUTPUTS_ROOT = Path("data") / "outputs"
URL_FIELDS = {
    "public_url",
    "final_image_url",
    "download_url",
    "preview_url",
    "preview_image_url",
    "copy_visual_preview_url",
    "thumbnail_url",
}
ASSET_ID_FIELD_BY_KIND = {
    "final": "final_asset_id",
    "background": "background_asset_id",
    "thumbnail": "thumbnail_asset_id",
    "copy_visual_preview": "copy_visual_preview_asset_id",
}
BLOCKED_RESULT_KEYS = {
    "api_key",
    "openai_api_key",
    "hf_token",
    "huggingface_token",
    "token",
    "authorization",
    "password",
    "secret",
    "service_role_key",
    "access_key",
    "secret_access_key",
    "r2_secret",
}
BLOCKED_RESULT_KEY_PATTERNS = (
    "api_key",
    "access_key",
    "secret",
    "token",
    "authorization",
    "password",
    "service_role_key",
)
REPO_RELATIVE_ARTIFACT_PREFIXES = ("data/outputs/", "data/logs/")
LOCAL_ABSOLUTE_PREFIXES = (
    "/home/",
    "/mnt/",
    "/tmp/",
    "/var/",
    "file://",
)


def _is_blocked_result_key(key: str | None) -> bool:
    if not key:
        return False
    lowered = key.lower()
    if lowered in BLOCKED_RESULT_KEYS:
        return True
    return any(pattern in lowered for pattern in BLOCKED_RESULT_KEY_PATTERNS)

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


def is_public_url(value: str | None) -> bool:
    if not value:
        return False
    normalized = value.strip().lower()
    return normalized.startswith("http://") or normalized.startswith("https://")


def is_local_absolute_path(value: str | None) -> bool:
    if not value:
        return False
    normalized = str(value).strip().replace("\\", "/")
    lowered = normalized.lower()
    if re.match(r"^[a-z]:/", lowered):
        return True
    return lowered.startswith(LOCAL_ABSOLUTE_PREFIXES)


def normalize_repo_relative_artifact_path(value: str | Path | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().replace("\\", "/")
    if not normalized or normalized.startswith("../") or "/../" in normalized:
        return None
    if is_local_absolute_path(normalized) or Path(normalized).is_absolute():
        return None
    if normalized.startswith(REPO_RELATIVE_ARTIFACT_PREFIXES):
        return normalized
    return None

def normalize_storage_object_key(value: str | Path | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().replace("\\", "/")
    if not normalized or normalized.startswith("../") or "/../" in normalized:
        return None
    if is_local_absolute_path(normalized) or Path(normalized).is_absolute():
        return None
    return normalized


def sanitize_result_artifact_payload_for_api(payload: dict | ResultArtifactPayload | None) -> dict | None:
    if payload is None:
        return None
    raw_payload = payload.model_dump(mode="json") if isinstance(payload, ResultArtifactPayload) else dict(payload)
    sanitized = _sanitize_result_value(raw_payload)
    if not isinstance(sanitized, dict):
        return None
    return sanitized


def build_storage_asset_ref(
    *,
    asset_row: dict | None = None,
    uploaded_asset: object | None = None,
    kind: str,
) -> ResultArtifactAssetRef:
    asset_row = asset_row or {}
    metadata = _safe_dict(asset_row.get("metadata"))
    uploaded_metadata = _safe_dict(getattr(uploaded_asset, "metadata", None))
    public_serving = uploaded_metadata.get("public_serving")
    if public_serving is None:
        public_serving = metadata.get("public_serving")
    return ResultArtifactAssetRef(
        asset_id=_string_or_none(asset_row.get("id") or asset_row.get("asset_id")),
        kind=kind,
        storage_provider=_string_or_none(asset_row.get("storage_provider") or getattr(uploaded_asset, "storage_provider", None)),
        bucket=_string_or_none(asset_row.get("bucket") or getattr(uploaded_asset, "bucket", None)),
        object_key=normalize_storage_object_key(asset_row.get("object_key") or getattr(uploaded_asset, "object_key", None)),
        mime_type=_string_or_none(asset_row.get("mime_type") or getattr(uploaded_asset, "mime_type", None)),
        size_bytes=asset_row.get("size_bytes") or getattr(uploaded_asset, "size_bytes", None),
        width=asset_row.get("width") or getattr(uploaded_asset, "width", None),
        height=asset_row.get("height") or getattr(uploaded_asset, "height", None),
        public_url=_public_url_or_none(asset_row.get("public_url") or getattr(uploaded_asset, "public_url", None)),
        final_image_url=_public_url_or_none(getattr(uploaded_asset, "final_image_url", None)),
        download_url=_public_url_or_none(getattr(uploaded_asset, "download_url", None)),
        preview_url=None,
        url_mode=_string_or_none(uploaded_metadata.get("url_mode") or metadata.get("url_mode")),
        signed_url_expires_at=_string_or_none(asset_row.get("signed_url_expires_at") or getattr(uploaded_asset, "signed_url_expires_at", None)),
        public_serving=bool(public_serving) if public_serving is not None else None,
        metadata=sanitize_result_artifact_payload_for_api(metadata) or {},
    )


def merge_final_asset_into_result_payload(
    *,
    result_payload: dict,
    asset_row: dict,
    uploaded_asset: object | None = None,
    storage_provider: str,
) -> dict:
    asset_ref = build_storage_asset_ref(asset_row=asset_row, uploaded_asset=uploaded_asset, kind="result")
    asset_data = asset_ref.model_dump(mode="json")
    assets = dict((result_payload or {}).get("assets") or {})
    assets["final"] = asset_data
    merged = {
        **(result_payload or {}),
        "final_asset_id": asset_ref.asset_id,
        "storage_provider": storage_provider,
        "bucket": asset_ref.bucket,
        "object_key": asset_ref.object_key,
        "url_mode": asset_ref.url_mode,
        "final_image_url": asset_ref.final_image_url,
        "download_url": asset_ref.download_url,
        "signed_url_expires_at": asset_ref.signed_url_expires_at,
        "assets": assets,
    }
    return sanitize_result_artifact_payload_for_api(merged) or merged


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


def _sanitize_result_value(value: Any, key: str | None = None) -> Any:
    if _is_blocked_result_key(key):
        return None
    if isinstance(value, dict):
        output = {}
        for raw_key, raw_value in value.items():
            key_text = str(raw_key)
            if _is_blocked_result_key(key_text):
                continue
            sanitized = _sanitize_result_value(raw_value, key=key_text)
            if sanitized is not None or _should_keep_null_field(key_text):
                output[key_text] = sanitized
        return output
    if isinstance(value, list):
        return [_sanitize_result_value(item) for item in value[:50]]
    if isinstance(value, bytes):
        return None
    if isinstance(value, str):
        if _is_url_field(key):
            return value if is_public_url(value) else None
        if _looks_like_base64_image(value):
            return None
        if is_local_absolute_path(value):
            return None
        if key == "object_key":
            return normalize_storage_object_key(value)
        if key == "output_dir" or (key and key.endswith("_path")):
            return normalize_repo_relative_artifact_path(value)
        if len(value) > 1000:
            return f"{value[:997]}..."
        return value
    return value

def _is_url_field(key: str | None) -> bool:
    return bool(key and (key in URL_FIELDS or key.endswith("_url")))


def _public_url_or_none(value: Any) -> str | None:
    return str(value) if isinstance(value, str) and is_public_url(value) else None


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_or_none(value: Any) -> str | None:
    return str(value) if value is not None else None


def _looks_like_base64_image(value: str) -> bool:
    lowered = value.strip().lower()
    return lowered.startswith("data:image/") or (len(value) > 4096 and ";base64," in lowered)


def _should_keep_null_field(key: str) -> bool:
    return key in URL_FIELDS or key.endswith("_url") or key.endswith("_asset_id") or key == "signed_url_expires_at"
