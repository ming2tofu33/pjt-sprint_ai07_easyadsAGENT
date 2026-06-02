"""Chat thread repository."""

from __future__ import annotations

from uuid import uuid4

from orchestrator.app.db.json import jsonb_param
from orchestrator.app.db.session import db_transaction


def create_chat_thread(
    workspace_id: str,
    created_by: str | None,
    title: str | None = None,
    brand_kit_id: str | None = None,
    project_id: str | None = None,
    final_brief: dict | None = None,
    connection: object | None = None,
) -> dict:
    public_thread_id = f"thread_{uuid4().hex}"
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into chat_threads (
                  public_thread_id, workspace_id, created_by, title, brand_kit_id, project_id, final_brief
                )
                values (%s, %s, %s, %s, %s, %s, %s::jsonb)
                returning *
                """,
                (public_thread_id, workspace_id, created_by, title, brand_kit_id, project_id, jsonb_param(final_brief or {})),
            )
            return cur.fetchone()


def get_chat_thread(thread_id: str, connection: object | None = None) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute("select * from chat_threads where public_thread_id = %s or id::text = %s", (thread_id, thread_id))
            return cur.fetchone()


def update_chat_thread_status(
    thread_id: str,
    status: str,
    active_job_id: str | None = None,
    final_output_id: str | None = None,
    connection: object | None = None,
) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update chat_threads
                set status = %s,
                    active_job_id = %s,
                    final_output_id = coalesce(%s, final_output_id),
                    updated_at = now()
                where public_thread_id = %s or id::text = %s
                returning *
                """,
                (status, active_job_id, final_output_id, thread_id, thread_id),
            )
            return cur.fetchone()
