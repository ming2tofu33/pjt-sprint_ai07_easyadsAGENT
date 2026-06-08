"""Usage event repository."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from orchestrator.app.db.json import jsonb_param
from orchestrator.app.db.session import db_transaction


def record_usage_event(
    **kwargs,
) -> dict:
    return record_usage_event_once(**kwargs)


def record_usage_event_once(
    *,
    workspace_id: str,
    event_type: str,
    created_by: str | None = None,
    thread_id: str | None = None,
    job_id: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    plan: str | None = None,
    quantity: Decimal | int | str | None = 1,
    unit: str | None = None,
    cost_usd: Decimal | int | str | None = None,
    idempotency_key: str | None = None,
    metadata: dict | None = None,
    connection: object | None = None,
) -> dict:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into usage_events (
                  workspace_id, thread_id, job_id, created_by, event_type, provider, model_name,
                  plan, quantity, unit, cost_usd, idempotency_key, metadata
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                on conflict (workspace_id, idempotency_key)
                where idempotency_key is not null
                do nothing
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
                    _decimal_param(quantity),
                    unit,
                    _decimal_param(cost_usd),
                    idempotency_key,
                    jsonb_param(metadata or {}),
                ),
            )
            row = cur.fetchone()
            if row:
                return row
            if idempotency_key:
                cur.execute(
                    """
                    select * from usage_events
                    where workspace_id = %s and idempotency_key = %s
                    limit 1
                    """,
                    (workspace_id, idempotency_key),
                )
                existing = cur.fetchone()
                if existing:
                    return existing
            return {}


def list_usage_events(
    workspace_id: str,
    limit: int = 100,
    *,
    created_by: str | None = None,
    start_at: datetime | str | None = None,
    end_at: datetime | str | None = None,
    event_type: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    plan: str | None = None,
    connection: object | None = None,
) -> list[dict]:
    where, params = _build_filters(
        workspace_id=workspace_id,
        created_by=created_by,
        start_at=start_at,
        end_at=end_at,
        event_type=event_type,
        provider=provider,
        model_name=model_name,
        plan=plan,
    )
    params.append(limit)
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select * from usage_events
                {where}
                order by created_at desc
                limit %s
                """,
                tuple(params),
            )
            return list(cur.fetchall())


def count_usage_events(
    workspace_id: str,
    *,
    created_by: str | None = None,
    start_at: datetime | str | None = None,
    end_at: datetime | str | None = None,
    connection: object | None = None,
) -> int:
    where, params = _build_filters(workspace_id=workspace_id, created_by=created_by, start_at=start_at, end_at=end_at)
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(f"select count(*) as count from usage_events {where}", tuple(params))
            row = cur.fetchone() or {}
            return int(row.get("count") or 0)


def aggregate_usage_summary(
    workspace_id: str,
    *,
    created_by: str | None = None,
    start_at: datetime | str | None = None,
    end_at: datetime | str | None = None,
    event_type: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    plan: str | None = None,
    connection: object | None = None,
) -> dict:
    where, params = _build_filters(
        workspace_id=workspace_id,
        created_by=created_by,
        start_at=start_at,
        end_at=end_at,
        event_type=event_type,
        provider=provider,
        model_name=model_name,
        plan=plan,
    )
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select
                  coalesce(sum(case when event_type = 'llm_call' then quantity else 0 end), 0) as llm_calls,
                  coalesce(sum(case when event_type = 'llm_call' then coalesce((metadata->>'input_tokens')::numeric, 0) else 0 end), 0) as llm_input_tokens,
                  coalesce(sum(case when event_type = 'llm_call' then coalesce((metadata->>'output_tokens')::numeric, 0) else 0 end), 0) as llm_output_tokens,
                  coalesce(sum(case when event_type = 'llm_call' then coalesce((metadata->>'total_tokens')::numeric, 0) else 0 end), 0) as llm_total_tokens,
                  coalesce(sum(case when event_type = 't2i_generation' then quantity else 0 end), 0) as t2i_images,
                  coalesce(sum(case when event_type = 'r2_upload' then quantity else 0 end), 0) as r2_upload_bytes,
                  coalesce(sum(case when event_type = 'r2_storage_added' then quantity else 0 end), 0) as r2_storage_bytes_added,
                  coalesce(sum(case when event_type = 'r2_storage_removed' then quantity else 0 end), 0) as r2_storage_bytes_removed,
                  coalesce(sum(case when event_type = 'modal_gpu_runtime' then quantity else 0 end), 0) as modal_gpu_seconds,
                  coalesce(sum(cost_usd), 0) as estimated_cost_usd,
                  coalesce(sum(case when cost_usd is null then 1 else 0 end), 0) as unpriced_event_count
                from usage_events
                {where}
                """,
                tuple(params),
            )
            totals = dict(cur.fetchone() or {})
            totals["estimated_net_storage_bytes"] = (totals.get("r2_storage_bytes_added") or 0) - (totals.get("r2_storage_bytes_removed") or 0)
            for group_name, column in (
                ("by_event_type", "event_type"),
                ("by_provider", "provider"),
                ("by_model", "model_name"),
                ("by_event_plan", "plan"),
            ):
                cur.execute(
                    f"""
                    select {column} as key, coalesce(sum(quantity), 0) as quantity, coalesce(sum(cost_usd), 0) as estimated_cost_usd
                    from usage_events
                    {where}
                    group by {column}
                    order by {column}
                    """,
                    tuple(params),
                )
                totals[group_name] = list(cur.fetchall())
            return totals


def _build_filters(
    *,
    workspace_id: str,
    created_by: str | None = None,
    start_at: datetime | str | None = None,
    end_at: datetime | str | None = None,
    event_type: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    plan: str | None = None,
) -> tuple[str, list[Any]]:
    clauses = ["workspace_id = %s"]
    params: list[Any] = [workspace_id]
    if created_by:
        clauses.append("created_by = %s")
        params.append(created_by)
    if start_at:
        clauses.append("created_at >= %s")
        params.append(start_at)
    if end_at:
        clauses.append("created_at < %s")
        params.append(end_at)
    if event_type:
        clauses.append("event_type = %s")
        params.append(event_type)
    if provider:
        clauses.append("provider = %s")
        params.append(provider)
    if model_name:
        clauses.append("model_name = %s")
        params.append(model_name)
    if plan:
        clauses.append("plan = %s")
        params.append(plan)
    return "where " + " and ".join(clauses), params


def _decimal_param(value: Decimal | int | str | None) -> str | None:
    if value is None:
        return None
    return str(Decimal(str(value)))
