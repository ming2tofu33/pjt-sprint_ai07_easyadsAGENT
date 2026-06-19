"""Asset upload service."""

from __future__ import annotations

import logging
import re
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from orchestrator.app.api.schemas.assets import (
    PUBLIC_ASSET_ID_PATTERN,
    AssetInfo,
    AssetPresignRequest,
    AssetPresignResponse,
    AssetResponse,
    UploadInstruction,
)
from orchestrator.app.assets.errors import (
    ConflictError,
    NotFoundError,
    PayloadTooLargeError,
    ServiceUnavailableError,
    UnprocessableEntityError,
    UnsupportedMediaTypeError,
)
from orchestrator.app.db.repositories import assets as asset_repo
from orchestrator.app.db.session import db_transaction
from orchestrator.app.storage import settings as storage_settings
from orchestrator.app.storage.errors import R2StorageUnavailableError
from orchestrator.app.storage.object_keys import build_upload_object_key
from orchestrator.app.storage.r2_service import (
    create_presigned_put_url,
    create_r2_client,
    download_file_from_r2,
    head_object,
)
from orchestrator.app.usage import service as usage_service
from orchestrator.app.vision.settings import get_vision_settings

logger = logging.getLogger(__name__)
_MAX_UPLOAD_FILENAME_LENGTH = 255


def _iso(dt: datetime | str | None) -> str:
    if not dt:
        return ""
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


def _resolve_workspace_id(
    workspace_id: str | None,
    *,
    user_id: str | None,
    account_type: str | None = None,
) -> str:
    from orchestrator.app.assets.errors import AssetWorkspaceForbidden, AssetWorkspaceRequired
    from orchestrator.app.db.workspace_scope import (
        WorkspaceScopeForbidden,
        WorkspaceScopeRequired,
        resolve_workspace_scope,
    )
    
    try:
        if account_type:
            return resolve_workspace_scope(workspace_id, user_id, account_type=account_type)
        return resolve_workspace_scope(workspace_id, user_id)
    except WorkspaceScopeRequired as exc:
        raise AssetWorkspaceRequired(
            "Workspace information is required.",
            "asset_workspace_required",
        ) from exc
    except WorkspaceScopeForbidden as exc:
        raise AssetWorkspaceForbidden(
            "Workspace access denied.",
            "asset_workspace_forbidden",
        ) from exc


def _validate_public_asset_id(public_asset_id: str) -> None:
    if not re.match(PUBLIC_ASSET_ID_PATTERN, public_asset_id or ""):
        raise UnprocessableEntityError("Invalid asset ID format.", error_code="invalid_asset_id")


def _normalize_upload_filename(filename: str) -> str:
    basename = Path(filename.replace("\\", "/")).name.strip()
    basename = "".join(ch for ch in basename if ch >= " " and ch != "\x7f")
    if not basename or len(basename) > _MAX_UPLOAD_FILENAME_LENGTH:
        raise UnprocessableEntityError("Invalid filename provided.", error_code="invalid_filename")
    return basename


def _normalize_mime(value: Any) -> str | None:
    if not value:
        return None
    return str(value).split(";", 1)[0].strip().lower()


def _row_to_response(row: dict) -> AssetResponse:
    metadata = row.get("metadata") or {}
    upload_meta = metadata.get("upload") or {}
    status = upload_meta.get("status") or "pending"
    
    image_url = row.get("public_url")
    if (
        status == "ready"
        and not image_url
        and row.get("storage_provider") == "r2"
    ):
        try:
            from orchestrator.app.storage.r2_service import create_r2_client
            from orchestrator.app.storage.url_policy import resolve_asset_urls
            urls = resolve_asset_urls(
                client=create_r2_client(),
                bucket=row["bucket"],
                object_key=row["object_key"],
            )
            image_url = urls.get("public_url") or urls.get("final_image_url")
        except R2StorageUnavailableError:
            image_url = None
        
    return AssetResponse(
        asset_id=str(row.get("public_asset_id")),
        kind=str(row.get("kind")),
        status=status,
        image_url=image_url,
        mime_type=row.get("mime_type"),
        size_bytes=row.get("size_bytes"),
        width=row.get("width"),
        height=row.get("height"),
        storage_provider=str(row.get("storage_provider")),
        created_at=_iso(row.get("created_at")),
        updated_at=_iso(row.get("updated_at")),
        metadata={
            "upload": {
                "status": status,
                "error_code": upload_meta.get("error_code")
            },
            "original_filename": upload_meta.get("original_filename"),
            "processed_width": (metadata.get("preprocess") or {}).get("processed_width"),
            "processed_height": (metadata.get("preprocess") or {}).get("processed_height"),
        },
    )


def get_asset_response(
    public_asset_id: str,
    workspace_id: str | None = None,
    user_id: str | None = None,
    account_type: str | None = None,
) -> AssetResponse:
    from orchestrator.app.db import settings as db_settings
    resolved_user_id = user_id or db_settings.get_demo_user_id()
    resolved_ws = _resolve_workspace_id(workspace_id, user_id=resolved_user_id, account_type=account_type)
    with db_transaction() as conn:
        row = asset_repo.get_asset_by_public_id(
            public_asset_id,
            workspace_id=resolved_ws,
            created_by=resolved_user_id,
            connection=conn,
        )
        if not row:
            raise NotFoundError(message="Asset not found", error_code="asset_not_found")
    
    return _row_to_response(row)


def presign_asset_upload(
    req: AssetPresignRequest,
    *,
    user_id: str | None = None,
    account_type: str | None = None,
) -> AssetPresignResponse:
    vision_settings = get_vision_settings()
    
    # 1. Validation
    try:
        storage_settings.require_r2_ready()
    except R2StorageUnavailableError as exc:
        raise ServiceUnavailableError(str(exc), error_code="asset_upload_unavailable") from exc

    safe_filename = _normalize_upload_filename(req.filename)

    ext = Path(safe_filename).suffix.lower()
    if ext not in vision_settings.allowed_extensions:
        raise UnprocessableEntityError(f"Unsupported extension: {ext}", error_code="invalid_image_asset")
        
    _ALLOWED_MIMES_BY_EXTENSION = {
        ".jpg": {"image/jpeg"},
        ".jpeg": {"image/jpeg"},
        ".png": {"image/png"},
        ".webp": {"image/webp"},
    }
    allowed_mimes_for_ext = _ALLOWED_MIMES_BY_EXTENSION.get(ext, set())
    if req.mime_type not in allowed_mimes_for_ext:
        raise UnsupportedMediaTypeError(
            "File extension and MIME type do not match.", 
            error_code="asset_media_type_mismatch"
        )
        
    max_bytes = vision_settings.max_file_size_mb * 1024 * 1024
    if req.size_bytes > max_bytes:
        raise PayloadTooLargeError("File size exceeds limit", error_code="asset_too_large")

    from orchestrator.app.db import settings as db_settings
    resolved_user_id = user_id or db_settings.get_demo_user_id()

    with db_transaction() as conn:
        workspace_id = _resolve_workspace_id(req.workspace_id, user_id=resolved_user_id, account_type=account_type)
        
        public_asset_id = f"asset_{uuid.uuid4().hex}"
        object_key = build_upload_object_key(workspace_id=workspace_id, public_asset_id=public_asset_id, extension=ext)
        bucket = storage_settings.get_r2_bucket()
        if not bucket:
            raise ServiceUnavailableError("R2 bucket unavailable", error_code="asset_storage_unavailable")
            
        ttl = storage_settings.get_r2_signed_url_ttl_seconds()
        try:
            client = create_r2_client()
            presigned_url = create_presigned_put_url(
                client=client,
                bucket=bucket,
                object_key=object_key,
                content_type=req.mime_type,
                expires_in=ttl,
            )
        except R2StorageUnavailableError as exc:
            raise ServiceUnavailableError(
                "Asset upload storage is unavailable.",
                error_code="asset_storage_unavailable",
            ) from exc

        metadata = {
            "origin": "user_upload",
            "upload": {
                "status": "pending",
                "expected_mime_type": req.mime_type,
                "expected_size_bytes": req.size_bytes,
                "original_filename": safe_filename,
            }
        }
        
        internal_thread_id = None
        if req.thread_id:
            from orchestrator.app.db.repositories.chat_threads import get_chat_thread_by_public_id
            thread = get_chat_thread_by_public_id(req.thread_id, workspace_id=workspace_id, connection=conn)
            if not thread:
                raise UnprocessableEntityError("Thread not found", error_code="thread_not_found")
            internal_thread_id = str(thread["id"])
            
        asset_repo.create_asset(
            workspace_id=workspace_id,
            bucket=bucket,
            object_key=object_key,
            kind=req.kind,
            public_asset_id=public_asset_id,
            storage_provider="r2",
            mime_type=req.mime_type,
            size_bytes=req.size_bytes,
            metadata=metadata,
            thread_id=internal_thread_id,
            created_by=resolved_user_id,
            connection=conn,
        )

        expires_at = datetime.now(UTC) + timedelta(seconds=ttl)
        
        return AssetPresignResponse(
            asset=AssetInfo(
                asset_id=public_asset_id,
                kind=req.kind,
                status="pending",
            ),
            upload=UploadInstruction(
                method="PUT",
                url=presigned_url,
                headers={"Content-Type": req.mime_type},
                expires_at=_iso(expires_at),
            )
        )


def validate_upload_head(
    *,
    asset: dict,
    head: dict | None,
    expected_mime_type: str | None,
    expected_size_bytes: int | None,
) -> dict:
    """Validate storage HEAD metadata without exposing the storage location."""
    del asset, expected_mime_type
    head = head or {}
    actual_size = head.get("ContentLength")
    if not actual_size or actual_size <= 0:
        raise UnprocessableEntityError("Invalid file size.", error_code="asset_size_mismatch")
    if expected_size_bytes is not None and actual_size != expected_size_bytes:
        raise ConflictError(
            "Uploaded object size does not match presigned request.",
            error_code="asset_size_mismatch",
        )
    if actual_size > get_vision_settings().max_file_size_mb * 1024 * 1024:
        raise PayloadTooLargeError("File too large", error_code="asset_too_large")
    return {"size_bytes": actual_size, "mime_type": head.get("ContentType")}


def decode_image_metadata(*, local_path: str | Path, mime_type: str | None = None) -> dict:
    """Decode image metadata from a private temporary file."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        with Image.open(local_path) as image:
            original_format = image.format
            original_mode = image.mode
            raw_width, raw_height = image.size
            image.verify()
        with Image.open(local_path) as image:
            image.load()
            orientation = image.getexif().get(274) if hasattr(image, "getexif") else None
            transposed = ImageOps.exif_transpose(image)
            rgb_image = transposed.convert("RGB")
            rgb_image.load()
            processed_width, processed_height = rgb_image.size
            detected_mime = Image.MIME.get(image.format)
    except Image.DecompressionBombError as exc:
        raise PayloadTooLargeError(
            "Image is a decompression bomb.",
            error_code="asset_pixel_count_too_large",
        ) from exc
    except (UnidentifiedImageError, OSError) as exc:
        raise UnprocessableEntityError(
            "Invalid or corrupted image asset.",
            error_code="invalid_image_asset",
        ) from exc
    return {
        "format": original_format,
        "mode": original_mode,
        "width": raw_width,
        "height": raw_height,
        "processed_width": processed_width,
        "processed_height": processed_height,
        "orientation": orientation,
        "mime_type": _normalize_mime(detected_mime or mime_type),
    }


def validate_image_constraints(
    *,
    kind: str,
    mime_type: str | None,
    size_bytes: int,
    width: int,
    height: int,
    image_format: str | None,
    expected_mime_type: str | None,
    storage_mime_type: str | None,
) -> None:
    """Apply the existing upload size, pixel, format, and MIME policies."""
    del kind
    vision_settings = get_vision_settings()
    if size_bytes > vision_settings.max_file_size_mb * 1024 * 1024:
        raise PayloadTooLargeError("File too large", error_code="asset_too_large")
    max_pixels = getattr(vision_settings, "max_pixel_count", 89478485)
    if width * height > max_pixels:
        raise PayloadTooLargeError(
            "Image pixel count exceeds limit.",
            error_code="asset_pixel_count_too_large",
        )
    if image_format not in {"JPEG", "PNG", "WEBP"}:
        raise UnprocessableEntityError(
            f"Unsupported image format: {image_format}",
            error_code="unsupported_asset_media_type",
        )
    normalized_expected = _normalize_mime(expected_mime_type)
    normalized_storage = _normalize_mime(storage_mime_type)
    if normalized_expected and mime_type != normalized_expected:
        raise UnsupportedMediaTypeError(
            "Detected format does not match expected MIME type.",
            error_code="asset_media_type_mismatch",
        )
    if normalized_storage and normalized_storage != mime_type:
        raise UnsupportedMediaTypeError(
            "R2 Content-Type does not match detected format.",
            error_code="asset_media_type_mismatch",
        )


def persist_asset_ready(
    *,
    asset: dict,
    workspace_id: str,
    user_id: str | None,
    storage_metadata: dict,
    image_metadata: dict,
) -> dict:
    """Atomically transition a still-pending asset to ready."""
    upload_meta = ((asset.get("metadata") or {}).get("upload") or {})
    width = image_metadata["width"]
    height = image_metadata["height"]
    processed_width = image_metadata["processed_width"]
    processed_height = image_metadata["processed_height"]
    metadata_merge = {
        "upload": {**upload_meta, "status": "ready", "completed_at": _iso(datetime.now(UTC))},
        "image": {
            "format": image_metadata["format"],
            "mime_type": image_metadata["mime_type"] or storage_metadata["mime_type"] or "application/octet-stream",
            "width": width,
            "height": height,
            "mode": image_metadata["mode"],
            "size_bytes": storage_metadata["size_bytes"],
            "checksum_sha256": storage_metadata["checksum_sha256"],
        },
        "preprocess": {
            "status": "validated",
            "mode": "exif_transpose_and_decode_validation",
            "original_width": width,
            "original_height": height,
            "processed_width": processed_width,
            "processed_height": processed_height,
            "exif_transposed": bool(
                image_metadata["orientation"] in {5, 6, 7, 8}
                or (processed_width, processed_height) != (width, height)
            ),
        },
    }
    with db_transaction() as conn:
        current_row = asset_repo.get_asset_by_public_id(
            str(asset["public_asset_id"]),
            workspace_id=workspace_id,
            created_by=user_id,
            for_update=True,
            connection=conn,
        )
        if not current_row:
            raise ConflictError("Asset state changed during upload completion.", error_code="asset_completion_conflict")
        current_status = ((current_row.get("metadata") or {}).get("upload") or {}).get("status")
        if current_status == "ready":
            return current_row
        if current_status != "pending":
            raise ConflictError("Asset upload is no longer pending", error_code="asset_upload_not_pending")
        updated_row = asset_repo.update_asset(
            str(asset["id"]),
            workspace_id=workspace_id,
            mime_type=image_metadata["mime_type"] or storage_metadata["mime_type"],
            size_bytes=storage_metadata["size_bytes"],
            width=width,
            height=height,
            checksum_sha256=storage_metadata["checksum_sha256"],
            public_url=None,
            metadata_merge=metadata_merge,
            pending_only_upload_status=True,
            connection=conn,
        )
        if not updated_row:
            raise ConflictError("Asset state changed during upload completion.", error_code="asset_completion_conflict")
        return updated_row


def mark_upload_failed(
    *,
    public_asset_id: str,
    workspace_id: str,
    user_id: str | None,
    reason: str,
) -> None:
    with db_transaction() as conn:
        row = asset_repo.get_asset_by_public_id(
            public_asset_id,
            workspace_id=workspace_id,
            created_by=user_id,
            for_update=True,
            connection=conn,
        )
        if row:
            upload_status = ((row.get("metadata") or {}).get("upload") or {}).get("status")
            if upload_status != "pending":
                return
                
            asset_repo.update_asset(
                str(row["id"]),
                workspace_id=workspace_id,
                metadata_merge={
                    "upload": {
                        **((row.get("metadata") or {}).get("upload") or {}),
                        "status": "failed",
                        "error_code": reason,
                        "failed_at": _iso(datetime.now(UTC)),
                    }
                },
                pending_only_upload_status=True,
                connection=conn,
            )

def complete_asset_upload(
    public_asset_id: str,
    workspace_id: str | None = None,
    user_id: str | None = None,
    account_type: str | None = None,
) -> AssetResponse:
    from orchestrator.app.assets.errors import AssetServiceError
    from orchestrator.app.db import settings as db_settings
    _validate_public_asset_id(public_asset_id)
    resolved_user_id = user_id or db_settings.get_demo_user_id()
    resolved_ws = _resolve_workspace_id(workspace_id, user_id=resolved_user_id, account_type=account_type)
    try:
        updated_row = _complete_asset_upload_internal(
            public_asset_id=public_asset_id,
            workspace_id=resolved_ws,
            user_id=resolved_user_id,
        )
        return _row_to_response(updated_row)
    except AssetServiceError as exc:
        _TERMINAL_UPLOAD_ERROR_CODES = {
            "invalid_image_asset",
            "unsupported_asset_media_type",
            "asset_media_type_mismatch",
            "asset_too_large",
            "asset_pixel_count_too_large",
            "asset_size_mismatch",
        }
        if exc.error_code in _TERMINAL_UPLOAD_ERROR_CODES:
            mark_upload_failed(
                public_asset_id=public_asset_id,
                workspace_id=resolved_ws,
                user_id=resolved_user_id,
                reason=exc.error_code or "internal_error",
            )
        raise


def _load_asset_for_completion(public_asset_id: str, workspace_id: str, user_id: str | None) -> tuple[dict, dict]:
    with db_transaction() as conn:
        row = asset_repo.get_asset_by_public_id(
            public_asset_id,
            workspace_id=workspace_id,
            created_by=user_id,
            for_update=True,
            connection=conn,
        )
        if not row:
            raise NotFoundError(message="Asset not found", error_code="asset_not_found")
        upload_meta = ((row.get("metadata") or {}).get("upload") or {})
        status = upload_meta.get("status")
        if status == "ready":
            return row, upload_meta
        if status != "pending":
            raise ConflictError("Asset upload is not pending", error_code="asset_upload_not_pending")
        return row, upload_meta


def _complete_asset_upload_internal(public_asset_id: str, workspace_id: str, user_id: str | None) -> dict:
    _validate_public_asset_id(public_asset_id)
    row, upload_meta = _load_asset_for_completion(public_asset_id, workspace_id, user_id)
    if upload_meta.get("status") == "ready":
        return row
    bucket = row.get("bucket")
    object_key = row.get("object_key")
    # Storage and decode work remains outside database transactions.
    try:
        if not bucket or not object_key:
            raise ConflictError(
                "Asset storage metadata is incomplete.",
                error_code="asset_storage_metadata_invalid",
            )
        client = create_r2_client()
        head_res = head_object(client=client, bucket=bucket, object_key=object_key)
    except R2StorageUnavailableError as exc:
        raise ServiceUnavailableError(
            "Asset storage is temporarily unavailable.",
            error_code="asset_storage_unavailable",
        ) from exc
        
    storage_metadata = validate_upload_head(
        asset=row,
        head=head_res,
        expected_mime_type=upload_meta.get("expected_mime_type"),
        expected_size_bytes=upload_meta.get("expected_size_bytes"),
    )
    with tempfile.TemporaryDirectory() as tmp_dir:
        ext = Path(object_key).suffix
        local_path = Path(tmp_dir) / f"downloaded{ext}"
        
        try:
            download_file_from_r2(client=client, bucket=bucket, object_key=object_key, target_path=local_path)
        except R2StorageUnavailableError as exc:
            raise ConflictError("Failed to download object", error_code="file_not_found") from exc
        downloaded_size = local_path.stat().st_size
        if downloaded_size != storage_metadata["size_bytes"]:
            raise UnprocessableEntityError(
                "Downloaded object size does not match R2 metadata.",
                error_code="asset_size_mismatch",
            )
            
        image_metadata = decode_image_metadata(
            local_path=local_path,
            mime_type=storage_metadata["mime_type"],
        )
        validate_image_constraints(
            kind=str(row.get("kind") or ""),
            mime_type=image_metadata["mime_type"],
            size_bytes=storage_metadata["size_bytes"],
            width=image_metadata["width"],
            height=image_metadata["height"],
            image_format=image_metadata["format"],
            expected_mime_type=upload_meta.get("expected_mime_type"),
            storage_mime_type=storage_metadata["mime_type"],
        )
        from orchestrator.app.storage.file_metadata import get_file_checksum
        checksum = get_file_checksum(local_path)
        storage_metadata["checksum_sha256"] = checksum
        updated_row = persist_asset_ready(
            asset=row,
            workspace_id=workspace_id,
            user_id=user_id,
            storage_metadata=storage_metadata,
            image_metadata=image_metadata,
        )
        _record_r2_upload_usage_for_asset(
            updated_row,
            storage_metadata["size_bytes"],
            checksum,
            connection=None,
        )
        return updated_row


def _record_r2_upload_usage_for_asset(
    row: dict,
    size_bytes: int | None,
    checksum_sha256: str | None,
    *,
    connection: object | None,
) -> None:
    if not size_bytes or size_bytes <= 0 or row.get("storage_provider") != "r2":
        return
    try:
        usage_service.record_r2_upload_usage(
            workspace_id=str(row["workspace_id"]),
            quantity=size_bytes,
            created_by=row.get("created_by"),
            thread_id=str(row.get("thread_id")) if row.get("thread_id") else None,
            provider="cloudflare_r2",
            plan=None,
            idempotency_key=f"r2_upload:{row.get('public_asset_id') or row.get('id')}:{checksum_sha256 or size_bytes}",
            metadata={
                "asset_public_id": row.get("public_asset_id"),
                "asset_kind": row.get("kind"),
                "source": "asset_upload_complete",
                "size_bytes": size_bytes,
                "mime_type": row.get("mime_type"),
                "width": row.get("width"),
                "height": row.get("height"),
            },
            connection=connection,
        )
    except Exception:
        logger.warning("Failed to record R2 asset upload usage.", exc_info=True)
