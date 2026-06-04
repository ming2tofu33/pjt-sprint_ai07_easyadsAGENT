"""URL policies for R2 assets."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from orchestrator.app.storage import settings


def build_public_r2_url(object_key: str) -> str | None:
    base_url = settings.get_r2_public_base_url()
    if not base_url:
        return None
    return f"{base_url}/{object_key.lstrip('/')}"


def generate_signed_get_url(*, client, bucket: str, object_key: str, expires_in: int) -> str:
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": object_key},
        ExpiresIn=expires_in,
    )


def resolve_asset_urls(*, client, bucket: str, object_key: str) -> dict:
    url_mode = settings.get_r2_url_mode()
    if url_mode == "public":
        url = build_public_r2_url(object_key)
        return {
            "url_mode": "public",
            "final_image_url": url,
            "download_url": url,
            "public_url": url,
            "signed_url_expires_at": None,
        }
    if url_mode == "signed":
        ttl = settings.get_r2_signed_url_ttl_seconds()
        url = generate_signed_get_url(client=client, bucket=bucket, object_key=object_key, expires_in=ttl)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)
        return {
            "url_mode": "signed",
            "final_image_url": url,
            "download_url": url,
            "public_url": None,
            "signed_url_expires_at": expires_at.isoformat(),
        }
    return {
        "url_mode": url_mode,
        "final_image_url": None,
        "download_url": None,
        "public_url": None,
        "signed_url_expires_at": None,
    }
