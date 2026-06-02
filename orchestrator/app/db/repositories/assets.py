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
            cur.execute(
                """
                insert into assets (
                  workspace_id, thread_id, project_id, created_by, kind, storage_provider, bucket,
                  object_key, mime_type, size_bytes, width, height, checksum_sha256, public_url,
                  signed_url_expires_at, metadata
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                returning *
                """,
                (
                    workspace_id,
                    thread_id,
                    project_id,
                    created_by,
                    kind,
                    storage_provider,
                    bucket,
                    object_key,
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
