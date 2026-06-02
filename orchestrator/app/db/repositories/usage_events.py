"""Usage event repository."""

from __future__ import annotations

from orchestrator.app.db.session import db_transaction
from orchestrator.app.db.json import jsonb_param


def record_usage_event(
    *,
    workspace_id: str,
    event_type: str,
    created_by: str | None = None,
    thread_id: str | None = None,
    job_id: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    plan: str | None = None,
    quantity: float | None = None,
    unit: str | None = None,
    cost_usd: float | None = None,
    metadata: dict | None = None,
    connection: object | None = None,
) -> dict:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into usage_events (
                  workspace_id, thread_id, job_id, created_by, event_type, provider, model_name,
                  plan, quantity, unit, cost_usd, metadata
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                returning *
                """,
                (
                    workspace_id,
                    thread_id,
                    job_id,
                    created_by,
                    event_type,
                    provider,
                    model_name,
                    plan,
                    quantity,
                    unit,
                    cost_usd,
                    jsonb_param(metadata or {}),
                ),
            )
            return cur.fetchone()


def list_usage_events(workspace_id: str, limit: int = 100, connection: object | None = None) -> list[dict]:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select * from usage_events
                where workspace_id = %s
                order by created_at desc
                limit %s
                """,
                (workspace_id, limit),
            )
            return list(cur.fetchall())
