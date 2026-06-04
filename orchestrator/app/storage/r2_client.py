"""Lazy R2 client creation."""

from __future__ import annotations

from orchestrator.app.storage.errors import R2StorageUnavailableError
from orchestrator.app.storage import settings


def create_r2_client():
    try:
        import boto3  # type: ignore
        from botocore.config import Config  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise R2StorageUnavailableError("boto3/botocore is unavailable for R2 upload.") from exc

    settings.require_r2_ready()
    return boto3.client(
        "s3",
        endpoint_url=settings.get_r2_endpoint_url(),
        aws_access_key_id=settings.get_r2_access_key_id(),
        aws_secret_access_key=settings.get_r2_secret_access_key(),
        region_name=settings.get_r2_region(),
        config=Config(signature_version="s3v4"),
    )
