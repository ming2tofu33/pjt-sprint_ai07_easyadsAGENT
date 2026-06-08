"""Cloudflare R2 upload service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from orchestrator.app.storage import settings
from orchestrator.app.storage.errors import R2StorageUnavailableError, R2UploadError
from orchestrator.app.storage.file_metadata import get_file_size, guess_mime_type, read_image_dimensions
from orchestrator.app.storage.r2_client import create_r2_client
from orchestrator.app.storage.url_policy import resolve_asset_urls


@dataclass(frozen=True)
class UploadedAsset:
    bucket: str
    object_key: str
    storage_provider: str
    mime_type: str | None
    size_bytes: int | None
    public_url: str | None
    final_image_url: str | None
    download_url: str | None
    signed_url_expires_at: str | None
    metadata: dict
    width: int | None = None
    height: int | None = None


def upload_file_to_r2(
    *,
    local_path: str | Path,
    object_key: str,
    content_type: str | None = None,
    metadata: dict | None = None,
    client: object | None = None,
) -> UploadedAsset:
    path = Path(local_path)
    if not path.exists() or not path.is_file():
        raise R2UploadError(f"Local upload source was not found: {path}")
    settings.require_r2_ready()
    bucket = settings.get_r2_bucket()
    if not bucket:
        raise R2StorageUnavailableError("R2 bucket is unavailable.")
    effective_client = client or create_r2_client()
    mime_type = content_type or guess_mime_type(path)
    extra_args = {}
    if mime_type:
        extra_args["ContentType"] = mime_type
    try:
        if extra_args:
            effective_client.upload_file(str(path), bucket, object_key, ExtraArgs=extra_args)
        else:
            effective_client.upload_file(str(path), bucket, object_key)
    except Exception as exc:
        raise R2UploadError("R2 upload failed.") from exc
    urls = resolve_asset_urls(client=effective_client, bucket=bucket, object_key=object_key)
    width, height = read_image_dimensions(path)
    return UploadedAsset(
        bucket=bucket,
        object_key=object_key,
        storage_provider="r2",
        mime_type=mime_type,
        size_bytes=get_file_size(path),
        public_url=urls["public_url"],
        final_image_url=urls["final_image_url"],
        download_url=urls["download_url"],
        signed_url_expires_at=urls["signed_url_expires_at"],
        metadata={
            **(metadata or {}),
            "public_serving": True,
            "url_mode": urls["url_mode"],
            "source": "generation_job_r2_upload",
        },
        width=width,
        height=height,
    )


def create_presigned_put_url(
    *,
    client: object | None = None,
    bucket: str,
    object_key: str,
    content_type: str,
    expires_in: int = 3600,
) -> str:
    effective_client = client or create_r2_client()
    try:
        url = effective_client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": bucket,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
        )
        return url
    except Exception as exc:
        raise R2StorageUnavailableError("Failed to generate presigned upload URL.") from exc


def download_file_from_r2(
    *,
    client: object | None = None,
    bucket: str,
    object_key: str,
    target_path: str | Path,
) -> Path:
    effective_client = client or create_r2_client()
    path = Path(target_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        effective_client.download_file(bucket, object_key, str(path))
        return path
    except Exception as exc:
        raise R2StorageUnavailableError(f"Failed to download from R2: {object_key}") from exc


def head_object(
    *,
    client: object | None = None,
    bucket: str,
    object_key: str,
) -> dict:
    effective_client = client or create_r2_client()
    try:
        response = effective_client.head_object(Bucket=bucket, Key=object_key)
        return response
    except Exception as exc:
        raise R2StorageUnavailableError(f"Failed to head R2 object: {object_key}") from exc
