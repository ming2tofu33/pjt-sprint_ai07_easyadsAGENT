"""Generation Output service layer."""

from __future__ import annotations

from datetime import datetime
import logging

from orchestrator.app.api.schemas.generation_outputs import GenerationOutputResponse
from orchestrator.app.db.repositories import generation_outputs as output_repo
from orchestrator.app.db.repositories import chat_threads as thread_repo
from orchestrator.app.archive.service import sync_archive_for_output
from orchestrator.app.artifacts.service import sanitize_result_artifact_payload_for_api, browser_usable_url
from orchestrator.app.db.session import db_transaction

logger = logging.getLogger(__name__)


class GenerationOutputNotFound(LookupError):
    pass


class GenerationOutputPersistenceUnavailable(RuntimeError):
    """Raised when the generation output storage is not available or corrupted."""


def _iso(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)



def _row_to_response(row: dict) -> GenerationOutputResponse:
    if not row.get("public_output_id"):
        raise GenerationOutputPersistenceUnavailable("Generation output public ID is missing.")

    image_url = browser_usable_url(row.get("image_url"))
    thumbnail_url = browser_usable_url(row.get("thumbnail_url"))

    safe_payload = sanitize_result_artifact_payload_for_api(row.get("result_payload") or {})
    
    download_url = None
    if safe_payload.get("download_url"):
        download_url = browser_usable_url(safe_payload["download_url"])
    elif safe_payload.get("final_image_url"):
        download_url = browser_usable_url(safe_payload["final_image_url"])
        
    if not image_url and download_url:
        image_url = download_url

    return GenerationOutputResponse(
        output_id=row["public_output_id"],
        thread_id=row.get("public_thread_id"),
        job_id=row.get("public_job_id"),
        variant_index=row.get("variant_index", 0),
        output_type=row.get("output_type", "final_image"),
        is_final=row.get("is_final", False),
        image_url=image_url,
        thumbnail_url=thumbnail_url,
        download_url=download_url,
        mime_type=row.get("asset_mime_type"),
        width=row.get("asset_width"),
        height=row.get("asset_height"),
        storage_provider=row.get("storage_provider"),
        result_payload=safe_payload,
        created_at=_iso(row.get("created_at")),
        updated_at=_iso(row.get("updated_at")),
    )


def get_generation_output(public_output_id: str, *, workspace_id: str) -> GenerationOutputResponse:
    row = output_repo.get_generation_output_by_public_id(public_output_id=public_output_id, workspace_id=workspace_id)
    if not row:
        raise GenerationOutputNotFound(f"Generation output {public_output_id} not found.")
    return _row_to_response(row)


def list_generation_outputs(
    *,
    workspace_id: str,
    public_thread_id: str | None = None,
    public_job_id: str | None = None,
    is_final: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[GenerationOutputResponse], int]:
    rows = output_repo.list_generation_outputs(
        workspace_id=workspace_id,
        public_thread_id=public_thread_id,
        public_job_id=public_job_id,
        is_final=is_final,
        limit=limit,
        offset=offset,
    )
    total = output_repo.count_generation_outputs(
        workspace_id=workspace_id,
        public_thread_id=public_thread_id,
        public_job_id=public_job_id,
        is_final=is_final,
    )
    return [_row_to_response(r) for r in rows], total


def select_final_generation_output(public_output_id: str, *, workspace_id: str) -> GenerationOutputResponse:
    with db_transaction() as conn:
        # 1. 대상 output 조회
        row = output_repo.get_generation_output_by_public_id(public_output_id=public_output_id, workspace_id=workspace_id, connection=conn)
        if not row:
            raise GenerationOutputNotFound(f"Generation output {public_output_id} not found.")
            
        internal_output_id = row["id"]
        
        # 2. 트랜잭션 내에서 mark_output_final
        updated_row = output_repo.mark_output_final(output_id=internal_output_id, workspace_id=workspace_id, connection=conn)
        if not updated_row:
            raise GenerationOutputNotFound(f"Generation output {public_output_id} not found during update.")
            
        # 3. Archive 연동 갱신
        sync_archive_for_output(workspace_id=workspace_id, internal_output_id=str(internal_output_id), connection=conn)
        
        # 갱신된 데이터를 다시 조회 (조인이 필요하므로)
        refreshed_row = output_repo.get_generation_output_by_public_id(public_output_id=public_output_id, workspace_id=workspace_id, connection=conn)
        
    return _row_to_response(refreshed_row or row)
