"""Archive item repository."""

from __future__ import annotations

from orchestrator.app.db.json import jsonb_param
from orchestrator.app.db.session import db_transaction

_SELECT_ARCHIVE_LIST = """
select
    i.*,
    j.public_job_id as j_public_job_id,
    o.public_output_id,
    o.result_payload as output_result_payload,
    o.is_final,
    t.public_thread_id,
    a.public_url as asset_public_url,
    a.storage_provider,
    a.mime_type as asset_mime_type,
    a.width as asset_width,
    a.height as asset_height,
    ta.public_url as thumbnail_public_url
from archive_items i
left join generation_jobs j on j.id = i.job_id
left join generation_outputs o on o.id = i.output_id
left join chat_threads t on t.id = o.thread_id
left join assets a on a.id = i.asset_id
left join assets ta on ta.id = o.thumbnail_asset_id
"""


_SELECT_ARCHIVE_WITH_OUTPUT = """
select
    i.*,
    j.public_job_id as j_public_job_id,
    o.public_output_id,
    o.result_payload as output_result_payload,
    o.is_final,
    t.public_thread_id,
    a.public_url as asset_public_url,
    a.storage_provider,
    a.mime_type as asset_mime_type,
    a.width as asset_width,
    a.height as asset_height,
    ta.public_url as thumbnail_public_url
from archive_items i
left join generation_jobs j on j.id = i.job_id
left join generation_outputs o on o.id = i.output_id
left join chat_threads t on t.id = o.thread_id
left join assets a on a.id = i.asset_id
left join assets ta on ta.id = o.thumbnail_asset_id
"""


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
    public_archive_id: str | None = None,
    connection: object | None = None,
) -> dict:
    import uuid
    actual_public_id = public_archive_id or f"archive_{uuid.uuid4().hex}"
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into archive_items (
                  workspace_id, created_by, job_id, output_id, asset_id, public_job_id, title,
                  thumbnail_url, image_url, status, ad_format, platform, source, metadata, public_archive_id
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
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
                    actual_public_id,
                ),
            )
            return cur.fetchone()


def list_archive_item_rows(
    *,
    workspace_id: str,
    created_by: str | None = None,
    limit: int = 50,
    offset: int = 0,
    connection: object | None = None,
) -> list[dict]:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            filters = ["i.workspace_id = %s", "i.deleted_at is null"]
            params: list[object] = [workspace_id]
            if created_by:
                filters.append("i.created_by = %s")
                params.append(created_by)
            params.extend([limit, offset])
            where_clause = " and ".join(filters)
            cur.execute(
                f"""
                {_SELECT_ARCHIVE_LIST}
                where {where_clause}
                order by i.saved_at desc
                limit %s offset %s
                """,
                tuple(params),
            )
            return list(cur.fetchall())


def count_archive_item_rows(*, workspace_id: str, created_by: str | None = None, connection: object | None = None) -> int:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            filters = ["workspace_id = %s", "deleted_at is null"]
            params: list[object] = [workspace_id]
            if created_by:
                filters.append("created_by = %s")
                params.append(created_by)
            where_clause = " and ".join(filters)
            cur.execute(
                f"""
                select count(*) as total
                from archive_items
                where {where_clause}
                """,
                tuple(params),
            )
            row = cur.fetchone()
            return int(row["total"]) if row else 0


def soft_delete_archive_item_row(
    *,
    archive_item_id: str,
    workspace_id: str,
    created_by: str | None = None,
    connection: object | None = None,
) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            filters = ["public_archive_id = %s", "workspace_id = %s", "deleted_at is null"]
            params: list[object] = [archive_item_id, workspace_id]
            if created_by:
                filters.append("created_by = %s")
                params.append(created_by)
            cur.execute(
                f"""
                update archive_items
                set deleted_at = now(), updated_at = now()
                where {" and ".join(filters)}
                returning *
                """,
                tuple(params),
            )
            return cur.fetchone()


def update_archive_item_status_row(
    *,
    archive_item_id: str,
    workspace_id: str,
    status: str,
    created_by: str | None = None,
    connection: object | None = None,
) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            filters = ["public_archive_id = %s", "workspace_id = %s", "deleted_at is null"]
            params: list[object] = [archive_item_id, workspace_id]
            if created_by:
                filters.append("created_by = %s")
                params.append(created_by)
            cur.execute(
                f"""
                update archive_items
                set status = %s, updated_at = now()
                where {" and ".join(filters)}
                returning *
                """,
                tuple([status, *params]),
            )
            return cur.fetchone()


def get_archive_item_row(
    *,
    public_archive_id: str,
    workspace_id: str,
    created_by: str | None = None,
    connection: object | None = None,
) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            sql = f"""
                {_SELECT_ARCHIVE_WITH_OUTPUT}
                where i.public_archive_id = %s and i.workspace_id = %s and i.deleted_at is null
            """
            params: list[object] = [public_archive_id, workspace_id]
            if created_by:
                sql += " and i.created_by = %s"
                params.append(created_by)
            cur.execute(sql, tuple(params))
            return cur.fetchone()


def upsert_generated_archive_item_row(
    *,
    workspace_id: str,
    public_job_id: str,
    created_by: str | None,
    title: str,
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
    import uuid
    actual_public_id = f"archive_{uuid.uuid4().hex}"
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into archive_items (
                  workspace_id, created_by, job_id, output_id, asset_id, public_job_id, title,
                  thumbnail_url, image_url, status, ad_format, platform, source, metadata, public_archive_id
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                on conflict (workspace_id, public_job_id) where public_job_id is not null and deleted_at is null
                do update set
                  job_id = excluded.job_id,
                  output_id = excluded.output_id,
                  asset_id = excluded.asset_id,
                  title = excluded.title,
                  thumbnail_url = excluded.thumbnail_url,
                  image_url = excluded.image_url,
                  status = excluded.status,
                  ad_format = excluded.ad_format,
                  platform = excluded.platform,
                  metadata = excluded.metadata,
                  updated_at = now()
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
                    actual_public_id,
                ),
            )
            return cur.fetchone()
