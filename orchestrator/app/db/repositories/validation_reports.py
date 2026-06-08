"""Validation report repository."""

from __future__ import annotations

from uuid import uuid4

from orchestrator.app.db.json import jsonb_param
from orchestrator.app.db.session import db_transaction


def create_validation_report(
    *,
    workspace_id: str,
    thread_id: str | None,
    job_id: str,
    output_id: str,
    status: str,
    decision: str,
    validation_summary: dict,
    failure_types: list[str],
    suggested_actions: list[dict],
    source_reports: dict,
    created_by: str | None = None,
    public_validation_report_id: str | None = None,
    schema_version: str = "validation_feedback_v1",
    connection: object | None = None,
) -> dict:
    public_id = public_validation_report_id or f"validation_{uuid4().hex}"
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into validation_reports (
                  public_validation_report_id, workspace_id, thread_id, job_id, output_id,
                  created_by, status, decision, validation_summary, failure_types,
                  suggested_actions, source_reports, schema_version
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s)
                returning *
                """,
                (
                    public_id,
                    workspace_id,
                    thread_id,
                    job_id,
                    output_id,
                    created_by,
                    status,
                    decision,
                    jsonb_param(validation_summary),
                    jsonb_param(failure_types),
                    jsonb_param(suggested_actions),
                    jsonb_param(source_reports),
                    schema_version,
                ),
            )
            return cur.fetchone()


def get_latest_validation_report_for_output(
    *,
    public_output_id: str,
    workspace_id: str,
    connection: object | None = None,
) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select vr.*, o.public_output_id, j.public_job_id
                from validation_reports vr
                join generation_outputs o on o.id = vr.output_id
                join generation_jobs j on j.id = vr.job_id
                where o.public_output_id = %s and vr.workspace_id = %s
                order by vr.created_at desc
                limit 1
                """,
                (public_output_id, workspace_id),
            )
            return cur.fetchone()


def get_validation_report_by_public_id(
    *,
    public_validation_report_id: str,
    workspace_id: str,
    connection: object | None = None,
) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select vr.*, o.public_output_id, j.public_job_id
                from validation_reports vr
                join generation_outputs o on o.id = vr.output_id
                join generation_jobs j on j.id = vr.job_id
                where vr.public_validation_report_id = %s and vr.workspace_id = %s
                """,
                (public_validation_report_id, workspace_id),
            )
            return cur.fetchone()
