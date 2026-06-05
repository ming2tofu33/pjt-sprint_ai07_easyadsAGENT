"""Chat message repository."""

from __future__ import annotations

from orchestrator.app.db.json import jsonb_param
from orchestrator.app.db.session import db_transaction


def append_chat_message(
    *,
    public_thread_id: str,
    workspace_id: str,
    role: str,
    content: str | None,
    payload: dict | None = None,
    created_by: str | None = None,
    connection: object | None = None,
) -> dict:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, workspace_id, archived_at
                from chat_threads
                where public_thread_id = %s
                  and workspace_id = %s::uuid
                for update
                """,
                (public_thread_id, workspace_id),
            )
            thread = cur.fetchone()
            if not thread:
                raise ValueError(f"chat_thread not found: {public_thread_id}")
            if thread.get("archived_at") is not None:
                raise ValueError(f"chat_thread is archived: {public_thread_id}")

            thread_uuid = str(thread["id"])
            cur.execute(
                "select coalesce(max(sequence_no), 0) + 1 as next_seq from chat_messages where thread_id = %s::uuid",
                (thread_uuid,),
            )
            sequence_no = cur.fetchone()["next_seq"]
            cur.execute(
                """
                insert into chat_messages (workspace_id, thread_id, sequence_no, role, content, payload, created_by)
                values (%s::uuid, %s::uuid, %s, %s, %s, %s::jsonb, %s)
                returning *
                """,
                (workspace_id, thread_uuid, sequence_no, role, content, jsonb_param(payload or {}), created_by),
            )
            msg = cur.fetchone()
            cur.execute(
                """
                update chat_threads
                set last_message_at = now(),
                    updated_at = now(),
                    status = case
                      when %s = 'user' and status in ('completed', 'failed')
                      then 'draft'
                      else status
                    end
                where id = %s::uuid
                """,
                (role, thread_uuid),
            )
            return msg


def list_chat_messages(
    public_thread_id: str,
    workspace_id: str,
    limit: int = 100,
    offset: int = 0,
    connection: object | None = None,
) -> list[dict]:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select id from chat_threads where public_thread_id = %s and workspace_id = %s::uuid",
                (public_thread_id, workspace_id),
            )
            row = cur.fetchone()
            if not row:
                return []
            cur.execute(
                """
                select * from chat_messages
                where thread_id = %s::uuid
                order by sequence_no asc
                limit %s offset %s
                """,
                (str(row["id"]), limit, offset),
            )
            return list(cur.fetchall())


def count_chat_messages(
    public_thread_id: str,
    workspace_id: str,
    connection: object | None = None,
) -> int:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select count(*) as total
                from chat_messages m
                join chat_threads ct on ct.id = m.thread_id
                where ct.public_thread_id = %s
                  and ct.workspace_id = %s::uuid
                """,
                (public_thread_id, workspace_id),
            )
            row = cur.fetchone() or {}
            return int(row.get("total") or 0)
