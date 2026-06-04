"""Archive item repository."""

from __future__ import annotations

from orchestrator.app.db.json import jsonb_param
from orchestrator.app.db.session import db_transaction


def create_archive_item_row(
    *,
    workspace_id: str,
    created_by: str | None,
    title: str,
    public_job_id: str | None = None,
    job_id: str | None = None,
    output_id: str | None = None,
    asset_id: str | None = None,
    thumbnail_url: str | None = None,
    image_url: str | None = None,
    status: str = "saved",
    ad_format: str | None = None,
    platform: str | None = None,
    source: str = "generated",
    metadata: dict | None = None,
    connection: object | None = None,
) -> dict:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into archive_items (
                  workspace_id, created_by, job_id, output_id, asset_id, public_job_id, title,
                  thumbnail_url, image_url, status, ad_format, platform, source, metadata
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                returning *
                """,
                (
                    workspace_id,
                    created_by,
                    job_id,
                    output_id,
                    asset_id,
                    public_job_id,
                    title,
                    thumbnail_url,
                    image_url,
                    status,
                    ad_format,
                    platform,
                    source,
                    jsonb_param(metadata or {}),
                ),
            )
            return cur.fetchone()


def list_archive_item_rows(
    *,
    workspace_id: str,
    limit: int = 50,
    offset: int = 0,
    connection: object | None = None,
) -> list[dict]:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select *
                from archive_items
                where workspace_id = %s and deleted_at is null
                order by saved_at desc
                limit %s offset %s
                """,
                (workspace_id, limit, offset),
            )
            return list(cur.fetchall())


def count_archive_item_rows(*, workspace_id: str, connection: object | None = None) -> int:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select count(*) as total
                from archive_items
                where workspace_id = %s and deleted_at is null
                """,
                (workspace_id,),
            )
            row = cur.fetchone()
            return int(row["total"]) if row else 0


def soft_delete_archive_item_row(
    *,
    archive_item_id: str,
    workspace_id: str,
    connection: object | None = None,
) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update archive_items
                set deleted_at = now(), updated_at = now()
                where id = %s and workspace_id = %s and deleted_at is null
                returning *
                """,
                (archive_item_id, workspace_id),
            )
            return cur.fetchone()
