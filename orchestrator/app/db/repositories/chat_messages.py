"""Chat message repository."""

from __future__ import annotations

from orchestrator.app.db.session import db_transaction
from orchestrator.app.db.json import jsonb_param


def append_chat_message(
    workspace_id: str,
    thread_id: str,
    role: str,
    content: str | None,
    payload: dict | None = None,
    created_by: str | None = None,
    connection: object | None = None,
) -> dict:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute("select coalesce(max(sequence_no), 0) + 1 as next_sequence from chat_messages where thread_id = %s", (thread_id,))
            sequence_no = cur.fetchone()["next_sequence"]
            cur.execute(
                """
                insert into chat_messages (workspace_id, thread_id, sequence_no, role, content, payload, created_by)
                values (%s, %s, %s, %s, %s, %s::jsonb, %s)
                returning *
                """,
                (workspace_id, thread_id, sequence_no, role, content, jsonb_param(payload or {}), created_by),
            )
            return cur.fetchone()


def list_chat_messages(thread_id: str, limit: int = 100, connection: object | None = None) -> list[dict]:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select * from chat_messages
                where thread_id = %s
                order by sequence_no asc
                limit %s
                """,
                (thread_id, limit),
            )
            return list(cur.fetchall())
