"""Generation job event repository."""

from __future__ import annotations

from orchestrator.app.db.json import jsonb_param
from orchestrator.app.db.session import db_transaction


def record_generation_job_event(
    *,
    workspace_id: str,
    thread_id: str,
    job_id: str,
    event_type: str,
    message: str | None = None,
    payload: dict | None = None,
    connection: object | None = None,
) -> dict:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into generation_job_events (
                  workspace_id, thread_id, job_id, event_type, message, payload
                )
                values (%s, %s, %s, %s, %s, %s::jsonb)
                returning *
                """,
                (workspace_id, thread_id, job_id, event_type, message, jsonb_param(payload or {})),
            )
            return cur.fetchone()


def list_generation_job_events(job_id: str, limit: int = 100, connection: object | None = None) -> list[dict]:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select * from generation_job_events
                where job_id = %s
                order by created_at desc
                limit %s
                """,
                (job_id, limit),
            )
            return list(cur.fetchall())

def list_generation_job_events_by_public_job_id(
    public_job_id: str,
    limit: int = 100,
    connection: object | None = None,
) -> list[dict]:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select e.*
                from generation_job_events e
                join generation_jobs j on j.id = e.job_id
                where j.public_job_id = %s
                order by e.created_at desc
                limit %s
                """,
                (public_job_id, limit),
            )
            return list(cur.fetchall())