"""Generation output repository."""

from __future__ import annotations

from orchestrator.app.db.session import db_transaction
from orchestrator.app.db.json import jsonb_param


def create_generation_output(
    *,
    workspace_id: str,
    thread_id: str,
    job_id: str | None = None,
    asset_id: str,
    thumbnail_asset_id: str | None = None,
    variant_index: int = 0,
    output_type: str = "final_image",
    result_payload: dict | None = None,
    is_final: bool = False,
    metadata: dict | None = None,
    connection: object | None = None,
) -> dict:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into generation_outputs (
                  workspace_id, thread_id, job_id, asset_id, thumbnail_asset_id, variant_index,
                  output_type, result_payload, is_final, metadata
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb)
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
                ),
            )
            return cur.fetchone()


def list_generation_outputs(thread_id: str, connection: object | None = None) -> list[dict]:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select * from generation_outputs where thread_id = %s order by created_at desc",
                (thread_id,),
            )
            return list(cur.fetchall())


def mark_output_final(output_id: str, connection: object | None = None) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute("select thread_id from generation_outputs where id = %s", (output_id,))
            row = cur.fetchone()
            if not row:
                return None
            cur.execute("update generation_outputs set is_final = false where thread_id = %s", (row["thread_id"],))
            cur.execute(
                """
                update generation_outputs
                set is_final = true, updated_at = now()
                where id = %s
                returning *
                """,
                (output_id,),
            )
            return cur.fetchone()
