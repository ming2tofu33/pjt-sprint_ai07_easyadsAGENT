"""Generation output repository."""

from __future__ import annotations

from orchestrator.app.db.session import db_transaction
from orchestrator.app.db.json import jsonb_param


def create_generation_output(
    *,
    workspace_id: str,
    thread_id: str,
    job_id: str | None = None,
    asset_id: str | None = None,
    thumbnail_asset_id: str | None = None,
    variant_index: int = 0,
    output_type: str = "final_image",
    result_payload: dict | None = None,
    is_final: bool = False,
    metadata: dict | None = None,
    public_output_id: str | None = None,
    connection: object | None = None,
) -> dict:
    import uuid
    actual_public_id = public_output_id or f"output_{uuid.uuid4().hex}"
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into generation_outputs (
                  workspace_id, thread_id, job_id, asset_id, thumbnail_asset_id, variant_index,
                  output_type, result_payload, is_final, metadata, public_output_id
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s)
                returning *
                """,
                (
                    workspace_id,
                    thread_id,
                    job_id,
                    asset_id,
                    thumbnail_asset_id,
                    variant_index,
                    output_type,
                    jsonb_param(result_payload or {}),
                    is_final,
                    jsonb_param(metadata or {}),
                    actual_public_id,
                ),
            )
            return cur.fetchone()


def get_generation_output_by_public_id(
    public_output_id: str,
    *,
    workspace_id: str,
    connection: object | None = None,
) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select o.*,
                       t.public_thread_id,
                       j.public_job_id,
                       a.public_url as image_url,
                       ta.public_url as thumbnail_url,
                       a.storage_provider,
                       a.mime_type as asset_mime_type,
                       a.width as asset_width,
                       a.height as asset_height
                from generation_outputs o
                left join chat_threads t on o.thread_id = t.id
                left join generation_jobs j on o.job_id = j.id
                left join assets a on o.asset_id = a.id
                left join assets ta on o.thumbnail_asset_id = ta.id
                where o.public_output_id = %s and o.workspace_id = %s
                """,
                (public_output_id, workspace_id),
            )
            return cur.fetchone()


def get_generation_output_by_id(
    output_id: str,
    *,
    workspace_id: str,
    connection: object | None = None,
) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select o.*,
                       t.public_thread_id,
                       j.public_job_id,
                       a.public_url as image_url,
                       ta.public_url as thumbnail_url,
                       a.storage_provider,
                       a.mime_type as asset_mime_type,
                       a.width as asset_width,
                       a.height as asset_height
                from generation_outputs o
                left join chat_threads t on o.thread_id = t.id
                left join generation_jobs j on o.job_id = j.id
                left join assets a on o.asset_id = a.id
                left join assets ta on o.thumbnail_asset_id = ta.id
                where o.id = %s and o.workspace_id = %s
                """,
                (output_id, workspace_id),
            )
            return cur.fetchone()


def list_generation_outputs(
    *,
    workspace_id: str,
    public_thread_id: str | None = None,
    public_job_id: str | None = None,
    is_final: bool | None = None,
    limit: int = 50,
    offset: int = 0,
    connection: object | None = None,
) -> list[dict]:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            filters = ["o.workspace_id = %s"]
            params: list[object] = [workspace_id]

            if public_thread_id:
                filters.append("t.public_thread_id = %s")
                params.append(public_thread_id)
            if public_job_id:
                filters.append("j.public_job_id = %s")
                params.append(public_job_id)
            if is_final is not None:
                filters.append("o.is_final = %s")
                params.append(is_final)

            params.extend([limit, offset])

            cur.execute(
                f"""
                select o.*,
                       t.public_thread_id,
                       j.public_job_id,
                       a.public_url as image_url,
                       ta.public_url as thumbnail_url,
                       a.storage_provider,
                       a.mime_type as asset_mime_type,
                       a.width as asset_width,
                       a.height as asset_height
                from generation_outputs o
                left join chat_threads t on o.thread_id = t.id
                left join generation_jobs j on o.job_id = j.id
                left join assets a on o.asset_id = a.id
                left join assets ta on o.thumbnail_asset_id = ta.id
                where {" and ".join(filters)}
                order by o.created_at desc
                limit %s offset %s
                """,
                tuple(params),
            )
            return list(cur.fetchall())


def count_generation_outputs(
    *,
    workspace_id: str,
    public_thread_id: str | None = None,
    public_job_id: str | None = None,
    is_final: bool | None = None,
    connection: object | None = None,
) -> int:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            filters = ["o.workspace_id = %s"]
            params: list[object] = [workspace_id]

            if public_thread_id:
                filters.append("t.public_thread_id = %s")
                params.append(public_thread_id)
            if public_job_id:
                filters.append("j.public_job_id = %s")
                params.append(public_job_id)
            if is_final is not None:
                filters.append("o.is_final = %s")
                params.append(is_final)

            cur.execute(
                f"""
                select count(*) as total
                from generation_outputs o
                left join chat_threads t on o.thread_id = t.id
                left join generation_jobs j on o.job_id = j.id
                where {" and ".join(filters)}
                """,
                tuple(params),
            )
            row = cur.fetchone()
            return int(row["total"]) if row else 0


def mark_output_final(
    output_id: str,
    *,
    workspace_id: str | None = None,
    connection: object | None = None,
) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            # 1. 대상 output을 workspace scope와 함께 조회
            filters = ["id = %s"]
            params = [output_id]
            if workspace_id:
                filters.append("workspace_id = %s")
                params.append(workspace_id)
                
            cur.execute(f"select thread_id from generation_outputs where {' and '.join(filters)}", tuple(params))
            row = cur.fetchone()
            if not row:
                return None
                
            thread_id = row["thread_id"]
            
            # 2. 대상 output의 thread row를 FOR UPDATE
            cur.execute("select id from chat_threads where id = %s for update", (thread_id,))
            if not cur.fetchone():
                return None
                
            # 3. 같은 thread의 기존 is_final=true를 false로 변경
            cur.execute("update generation_outputs set is_final = false where thread_id = %s and is_final = true", (thread_id,))
            
            # 4. 대상 output을 is_final=true로 변경
            cur.execute(
                """
                update generation_outputs
                set is_final = true, updated_at = now()
                where id = %s
                returning *
                """,
                (output_id,),
            )
            updated_output = cur.fetchone()
            
            # 5. chat_threads.final_output_id를 대상 internal output UUID로 변경
            # 6. thread.updated_at 갱신
            cur.execute(
                """
                update chat_threads
                set final_output_id = %s, updated_at = now()
                where id = %s
                """,
                (output_id, thread_id),
            )
            return updated_output
