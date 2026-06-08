"""Asset upload service."""

from __future__ import annotations

import re
import tempfile
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from orchestrator.app.api.schemas.assets import (
    AssetPresignRequest,
    AssetPresignResponse,
    AssetResponse,
    AssetInfo,
    UploadInstruction,
    PUBLIC_ASSET_ID_PATTERN,
)
from orchestrator.app.assets.errors import (
    NotFoundError,
    ConflictError,
    UnprocessableEntityError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
    ServiceUnavailableError,
)
from orchestrator.app.db.session import db_transaction
from orchestrator.app.db.repositories import assets as asset_repo
from orchestrator.app.storage import settings as storage_settings
from orchestrator.app.storage.r2_service import create_presigned_put_url, head_object, download_file_from_r2, create_r2_client
from orchestrator.app.storage.object_keys import build_upload_object_key
from orchestrator.app.storage.errors import R2StorageUnavailableError
from orchestrator.app.vision.settings import get_vision_settings


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
) -> str:
    from orchestrator.app.db.workspace_scope import (
        WorkspaceScopeForbidden,
        WorkspaceScopeRequired,
        resolve_workspace_scope,
    )
    from orchestrator.app.assets.errors import AssetWorkspaceRequired, AssetWorkspaceForbidden
    
    try:
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
    if not basename or len(basename) > 255:
        raise UnprocessableEntityError("Invalid filename provided.", error_code="invalid_filename")
    return basename


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
        except Exception:
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
) -> AssetResponse:
    resolved_ws = _resolve_workspace_id(workspace_id, user_id=user_id)
    with db_transaction() as conn:
        row = asset_repo.get_asset_by_public_id(public_asset_id, workspace_id=resolved_ws, connection=conn)
        if not row:
            raise NotFoundError(message="Asset not found", error_code="asset_not_found")
    
    return _row_to_response(row)


def presign_asset_upload(
    req: AssetPresignRequest,
    *,
    user_id: str | None = None,
) -> AssetPresignResponse:
    vision_settings = get_vision_settings()
    
    # 1. Validation
    try:
        storage_settings.require_r2_ready()
    except R2StorageUnavailableError as e:
        raise ServiceUnavailableError(str(e), error_code="asset_upload_unavailable")

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
        workspace_id = _resolve_workspace_id(req.workspace_id, user_id=resolved_user_id)
        
        public_asset_id = f"asset_{uuid.uuid4().hex}"
        object_key = build_upload_object_key(workspace_id=workspace_id, public_asset_id=public_asset_id, extension=ext)
        bucket = storage_settings.get_r2_bucket()
        if not bucket:
            raise ServiceUnavailableError("R2 bucket unavailable", error_code="asset_storage_unavailable")
            
        ttl = storage_settings.get_r2_signed_url_ttl_seconds()
        client = create_r2_client()
        try:
            presigned_url = create_presigned_put_url(
                client=client,
                bucket=bucket,
                object_key=object_key,
                content_type=req.mime_type,
                expires_in=ttl,
            )
        except R2StorageUnavailableError as exc:
            raise ServiceUnavailableError(str(exc), error_code="asset_storage_unavailable")

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
            
        row = asset_repo.create_asset(
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

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)
        
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


def _mark_asset_upload_failed(
    *,
    public_asset_id: str,
    workspace_id: str,
    error_code: str,
) -> None:
    with db_transaction() as conn:
        row = asset_repo.get_asset_by_public_id(
            public_asset_id,
            workspace_id=workspace_id,
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
                        "error_code": error_code,
                        "failed_at": _iso(datetime.now(timezone.utc)),
                    }
                },
                pending_only_upload_status=True,
                connection=conn,
            )

def complete_asset_upload(
    public_asset_id: str,
    workspace_id: str | None = None,
    user_id: str | None = None,
) -> AssetResponse:
    from orchestrator.app.assets.errors import AssetServiceError
    _validate_public_asset_id(public_asset_id)
    resolved_ws = _resolve_workspace_id(workspace_id, user_id=user_id)
    try:
        updated_row = _complete_asset_upload_internal(
            public_asset_id=public_asset_id,
            workspace_id=resolved_ws,
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
            _mark_asset_upload_failed(
                public_asset_id=public_asset_id,
                workspace_id=resolved_ws,
                error_code=exc.error_code or "internal_error",
            )
        raise

def _complete_asset_upload_internal(public_asset_id: str, workspace_id: str) -> AssetResponse:
    _validate_public_asset_id(public_asset_id)
    with db_transaction() as conn:
        row = asset_repo.get_asset_by_public_id(public_asset_id, workspace_id=workspace_id, for_update=True, connection=conn)
        if not row:
            raise NotFoundError(message="Asset not found", error_code="asset_not_found")
            
        meta = row.get("metadata") or {}
        upload_meta = meta.get("upload") or {}
        status = upload_meta.get("status")
        
        if status == "ready":
            # Just return, URL resolution will happen outside transaction
            return row
        if status != "pending":
            raise ConflictError("Asset upload is not pending", error_code="asset_upload_not_pending")
            
        bucket = row.get("bucket")
        object_key = row.get("object_key")
        row_id = str(row["id"])

    # Outside transaction: R2 fetching and processing
    client = create_r2_client()
    try:
        head_res = head_object(client=client, bucket=bucket, object_key=object_key)
    except R2StorageUnavailableError:
        raise ConflictError("File not found on R2 or incomplete", error_code="file_not_found")
        
    actual_size = head_res.get("ContentLength")
    actual_mime = head_res.get("ContentType")
    
    if not actual_size or actual_size <= 0:
        raise UnprocessableEntityError("Invalid file size.", error_code="asset_size_mismatch")
        
    expected_size = upload_meta.get("expected_size_bytes")
    if expected_size is not None and actual_size != expected_size:
        raise ConflictError("Uploaded object size does not match presigned request.", error_code="asset_size_mismatch")
    
    vision_settings = get_vision_settings()
    if actual_size > vision_settings.max_file_size_mb * 1024 * 1024:
        raise PayloadTooLargeError("File too large", error_code="asset_too_large")
        
    with tempfile.TemporaryDirectory() as tmp_dir:
        ext = Path(object_key).suffix
        local_path = Path(tmp_dir) / f"downloaded{ext}"
        
        try:
            download_file_from_r2(client=client, bucket=bucket, object_key=object_key, target_path=local_path)
        except R2StorageUnavailableError:
            raise ConflictError("Failed to download object", error_code="file_not_found")
        downloaded_size = local_path.stat().st_size
        if downloaded_size != actual_size:
            raise UnprocessableEntityError(
                "Downloaded object size does not match R2 metadata.",
                error_code="asset_size_mismatch",
            )
            
        from PIL import Image, ImageOps, UnidentifiedImageError
        
        try:
            with Image.open(local_path) as image:
                original_format = image.format
                original_mode = image.mode
                raw_width, raw_height = image.size
                orientation = image.getexif().get(274) if hasattr(image, "getexif") else None
                
                # Default max_pixel_count if not in settings
                max_pixels = getattr(vision_settings, "max_pixel_count", 89478485) # default max
                if raw_width * raw_height > max_pixels:
                    raise PayloadTooLargeError("Image pixel count exceeds limit.", error_code="asset_pixel_count_too_large")
                
                image.verify()
                
            with Image.open(local_path) as image:
                image.load()
                transposed = ImageOps.exif_transpose(image)
                processed_width, processed_height = transposed.size
                detected_mime = Image.MIME.get(image.format)
                
        except Image.DecompressionBombError as exc:
            raise PayloadTooLargeError("Image is a decompression bomb.", error_code="asset_pixel_count_too_large") from exc
        except (UnidentifiedImageError, OSError) as exc:
            raise UnprocessableEntityError("Invalid or corrupted image asset.", error_code="invalid_image_asset") from exc
            
        allowed_formats = {"JPEG", "PNG", "WEBP"}
        if original_format not in allowed_formats:
            raise UnprocessableEntityError(f"Unsupported image format: {original_format}", error_code="unsupported_asset_media_type")
            
        expected_mime = upload_meta.get("expected_mime_type")
        if expected_mime and detected_mime != expected_mime:
            raise UnsupportedMediaTypeError("Detected format does not match expected MIME type.", error_code="asset_media_type_mismatch")
            
        if actual_mime and actual_mime.split(";", 1)[0] != detected_mime:
            raise UnsupportedMediaTypeError("R2 Content-Type does not match detected format.", error_code="asset_media_type_mismatch")
            
        from orchestrator.app.storage.file_metadata import get_file_checksum
        checksum = get_file_checksum(local_path)
        
        meta_update = {
            "upload": {
                **upload_meta,
                "status": "ready",
                "completed_at": _iso(datetime.now(timezone.utc)),
            },
            "image": {
                "format": original_format,
                "mime_type": detected_mime or actual_mime or "application/octet-stream",
                "width": raw_width,
                "height": raw_height,
                "mode": original_mode,
                "size_bytes": actual_size,
                "checksum_sha256": checksum,
            },
            "preprocess": {
                "status": "validated",
                "mode": "exif_transpose_and_rgb_validation",
                "original_width": raw_width,
                "original_height": raw_height,
                "processed_width": processed_width,
                "processed_height": processed_height,
                "exif_transposed": bool(
                    orientation in {5, 6, 7, 8}
                    or (processed_width, processed_height) != (raw_width, raw_height)
                ),
            }
        }
        
        # We don't resolve URL inside the transaction
        
        with db_transaction() as conn:
            # Re-fetch to ensure it is still pending
            current_row = asset_repo.get_asset_by_public_id(public_asset_id, workspace_id=workspace_id, for_update=True, connection=conn)
            if not current_row:
                raise ConflictError("Asset state changed during upload completion.", error_code="asset_completion_conflict")
            
            curr_status = ((current_row.get("metadata") or {}).get("upload") or {}).get("status")
            if curr_status != "pending":
                if curr_status == "ready":
                    updated_row = current_row
                else:
                    raise ConflictError("Asset upload is no longer pending", error_code="asset_upload_not_pending")
            else:
                updated_row = asset_repo.update_asset(
                    row_id,
                    workspace_id=workspace_id,
                    mime_type=detected_mime or actual_mime,
                    size_bytes=actual_size,
                    width=raw_width,
                    height=raw_height,
                    checksum_sha256=checksum,
                    public_url=None, # URL will be generated dynamically
                    metadata_merge=meta_update,
                    pending_only_upload_status=True,
                    connection=conn,
                )
                
            if not updated_row:
                raise ConflictError("Asset state changed during upload completion.", error_code="asset_completion_conflict")
                
            return updated_row
