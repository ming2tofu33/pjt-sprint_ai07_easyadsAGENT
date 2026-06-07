"""Asset metadata repository."""

from __future__ import annotations

from orchestrator.app.db.session import db_transaction
from orchestrator.app.db.json import jsonb_param


def create_asset(
    *,
    workspace_id: str,
    bucket: str,
    object_key: str,
    kind: str,
    public_asset_id: str | None = None,
    storage_provider: str = "r2",
    mime_type: str | None = None,
    size_bytes: int | None = None,
    width: int | None = None,
    height: int | None = None,
    checksum_sha256: str | None = None,
    public_url: str | None = None,
    signed_url_expires_at: str | None = None,
    metadata: dict | None = None,
    thread_id: str | None = None,
    project_id: str | None = None,
    created_by: str | None = None,
    connection: object | None = None,
) -> dict:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            # If public_asset_id is not provided, generate a fallback (though it should be provided by service)
            import uuid
            effective_public_id = public_asset_id or f"asset_{uuid.uuid4().hex}"
            cur.execute(
                """
                insert into assets (
                public_asset_id, workspace_id, thread_id, project_id, created_by,
                bucket, object_key, kind, storage_provider,
                mime_type, size_bytes, width, height, checksum_sha256,
                public_url, signed_url_expires_at, metadata
                )
                values (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s::jsonb
                )
                returning *
                """,
                (
                    effective_public_id,
                    workspace_id,
                    thread_id,
                    project_id,
                    created_by,
                    bucket,
                    object_key,
                    kind,
                    storage_provider,
                    mime_type,
                    size_bytes,
                    width,
                    height,
                    checksum_sha256,
                    public_url,
                    signed_url_expires_at,
                    jsonb_param(metadata or {}),
                ),
            )
            return cur.fetchone()


def get_asset_by_public_id(
    public_asset_id: str,
    *,
    workspace_id: str,
    created_by: str | None = None,
    for_update: bool = False,
    connection: object | None = None,
) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            query = "select * from assets where public_asset_id = %s and workspace_id = %s"
            params = [public_asset_id, workspace_id]
            if created_by:
                query += " and created_by = %s"
                params.append(created_by)
            query += " and deleted_at is null"
            if for_update:
                query += " for update"
                
            cur.execute(query, tuple(params))
            return cur.fetchone()


def update_asset(
    asset_id: str,
    *,
    workspace_id: str,
    mime_type: str | None = None,
    size_bytes: int | None = None,
    width: int | None = None,
    height: int | None = None,
    checksum_sha256: str | None = None,
    public_url: str | None = None,
    metadata_merge: dict | None = None,
    connection: object | None = None,
) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            updates = ["updated_at = now()"]
            params = []
            
            if mime_type is not None:
                updates.append("mime_type = %s")
                params.append(mime_type)
            if size_bytes is not None:
                updates.append("size_bytes = %s")
                params.append(size_bytes)
            if width is not None:
                updates.append("width = %s")
                params.append(width)
            if height is not None:
                updates.append("height = %s")
                params.append(height)
            if checksum_sha256 is not None:
                updates.append("checksum_sha256 = %s")
                params.append(checksum_sha256)
            if public_url is not None:
                updates.append("public_url = %s")
                params.append(public_url)
            if metadata_merge:
                # Merge jsonb dictionary
                updates.append("metadata = metadata || %s::jsonb")
                params.append(jsonb_param(metadata_merge))
                
            params.append(asset_id)
            params.append(workspace_id)
            
            cur.execute(
                f"update assets set {', '.join(updates)} where id = %s and workspace_id = %s returning *",
                tuple(params),
            )
            return cur.fetchone()


def get_asset(asset_id: str, connection: object | None = None) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute("select * from assets where id = %s", (asset_id,))
            return cur.fetchone()


def get_asset_by_object_key(bucket: str, object_key: str, connection: object | None = None) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute("select * from assets where bucket = %s and object_key = %s", (bucket, object_key))
            return cur.fetchone()
