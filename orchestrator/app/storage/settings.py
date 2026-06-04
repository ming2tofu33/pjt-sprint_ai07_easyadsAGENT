"""Storage backend settings."""

from __future__ import annotations

from orchestrator.app.core.config import _get_env
from orchestrator.app.storage.errors import R2StorageUnavailableError


def _env_bool(name: str) -> bool:
    return str(_get_env(name, "")).strip().lower() in {"1", "true", "yes", "on"}


_ALLOWED_ASSET_STORAGE_BACKENDS = {"local_dev", "r2"}


def get_asset_storage_backend() -> str:
    value = str(_get_env("EASYADS_ASSET_STORAGE_BACKEND", "local_dev") or "local_dev").strip().lower()
    if value in _ALLOWED_ASSET_STORAGE_BACKENDS:
        return value
    return "local_dev"

def get_asset_storage_backend_raw() -> str:
    return str(_get_env("EASYADS_ASSET_STORAGE_BACKEND", "local_dev") or "local_dev").strip().lower()

def is_r2_upload_enabled() -> bool:
    return get_asset_storage_backend() == "r2" or _env_bool("EASYADS_ENABLE_R2_UPLOAD")


def is_r2_upload_required() -> bool:
    return _env_bool("EASYADS_R2_UPLOAD_REQUIRED")


def get_r2_bucket() -> str | None:
    return _get_env("EASYADS_R2_BUCKET", "").strip() or None


def get_r2_endpoint_url() -> str | None:
    return _get_env("EASYADS_R2_ENDPOINT_URL", "").strip() or None


def get_r2_access_key_id() -> str | None:
    return _get_env("EASYADS_R2_ACCESS_KEY_ID", "").strip() or None


def get_r2_secret_access_key() -> str | None:
    return _get_env("EASYADS_R2_SECRET_ACCESS_KEY", "").strip() or None


def get_r2_region() -> str:
    return _get_env("EASYADS_R2_REGION", "auto").strip() or "auto"


def get_r2_url_mode() -> str:
    value = (_get_env("EASYADS_R2_URL_MODE", "signed") or "signed").strip().lower()
    return value if value in {"signed", "public"} else "signed"


def get_r2_signed_url_ttl_seconds() -> int:
    raw = (_get_env("EASYADS_R2_SIGNED_URL_TTL_SECONDS", "3600") or "3600").strip()
    try:
        value = int(raw)
    except ValueError:
        return 3600
    return max(60, value)


def get_r2_public_base_url() -> str | None:
    return _get_env("EASYADS_R2_PUBLIC_BASE_URL", "").strip().rstrip("/") or None


def get_r2_readiness() -> dict:
    raw_backend = get_asset_storage_backend_raw()
    bucket = get_r2_bucket()
    endpoint = get_r2_endpoint_url()
    access_key_id = get_r2_access_key_id()
    secret = get_r2_secret_access_key()
    url_mode = get_r2_url_mode()
    public_base_url = get_r2_public_base_url()
    missing = []
    if is_r2_upload_enabled():
        if not bucket:
            missing.append("EASYADS_R2_BUCKET")
        if not endpoint:
            missing.append("EASYADS_R2_ENDPOINT_URL")
        if not access_key_id:
            missing.append("EASYADS_R2_ACCESS_KEY_ID")
        if not secret:
            missing.append("EASYADS_R2_SECRET_ACCESS_KEY")
        if url_mode == "public" and not public_base_url:
            missing.append("EASYADS_R2_PUBLIC_BASE_URL")
        if url_mode == "signed" and get_r2_signed_url_ttl_seconds() <= 0:
            missing.append("EASYADS_R2_SIGNED_URL_TTL_SECONDS")
    return {
        "backend": get_asset_storage_backend(),
        "backend_valid": raw_backend in _ALLOWED_ASSET_STORAGE_BACKENDS,
        "enabled": is_r2_upload_enabled(),
        "bucket_present": bool(bucket),
        "endpoint_url_present": bool(endpoint),
        "access_key_id_present": bool(access_key_id),
        "secret_access_key_present": bool(secret),
        "url_mode": url_mode,
        "public_base_url_present": bool(public_base_url),
        "missing_requirements": missing,
    }


def require_r2_ready() -> None:
    readiness = get_r2_readiness()
    if not readiness["enabled"]:
        raise R2StorageUnavailableError("R2 upload is disabled.")
    if readiness["missing_requirements"]:
        raise R2StorageUnavailableError(
            "R2 upload is unavailable. Missing requirements: " + ", ".join(readiness["missing_requirements"])
        )
