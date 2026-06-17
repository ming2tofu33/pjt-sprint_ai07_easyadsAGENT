"""Chat thread repository."""

from __future__ import annotations

from uuid import uuid4

from orchestrator.app.chat_threads.errors import ChatThreadLimitReachedError
from orchestrator.app.db import settings as db_settings
from orchestrator.app.db.json import jsonb_param
from orchestrator.app.db.session import db_transaction

_SELECT_THREAD_WITH_ACTIVE_JOB = """
    select
        ct.*,
        aj.public_job_id as active_public_job_id,
        fo.public_output_id as final_public_output_id,
        fj.public_job_id as final_public_job_id
    from chat_threads ct
    left join generation_jobs aj on aj.id = ct.active_job_id
    left join generation_outputs fo on fo.id = ct.final_output_id
    left join generation_jobs fj on fj.id = fo.job_id
"""

_ALLOWED_UPDATE_FIELDS = {"title", "brand_kit_id", "project_id", "final_brief"}


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
    max_threads = db_settings.get_max_threads_per_workspace()
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            # Serialize per-workspace creation so concurrent inserts can't both
            # pass the count check. The advisory lock is released at tx end.
            cur.execute("select pg_advisory_xact_lock(hashtext(%s))", (str(workspace_id),))
            existing = count_chat_threads(workspace_id, include_archived=False, connection=conn)
            if existing >= max_threads:
                raise ChatThreadLimitReachedError(
                    f"Workspace already has the maximum of {max_threads} chat threads."
                )
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


def get_chat_thread_by_public_id(
    public_thread_id: str,
    workspace_id: str | None = None,
    connection: object | None = None,
    *,
    for_update: bool = False,
) -> dict | None:
    where = " where ct.public_thread_id = %s"
    params: list = [public_thread_id]
    if workspace_id:
        where += " and ct.workspace_id = %s::uuid"
        params.append(workspace_id)
    if for_update:
        where += " for update of ct"
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(_SELECT_THREAD_WITH_ACTIVE_JOB + where, tuple(params))
            return cur.fetchone()


def get_chat_thread(thread_id: str, connection: object | None = None) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select * from chat_threads
                where public_thread_id = %s or id::text = %s
                """,
                (thread_id, thread_id),
            )
            return cur.fetchone()


def list_chat_threads(
    workspace_id: str,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
    connection: object | None = None,
) -> list[dict]:
    where = "where ct.workspace_id = %s::uuid"
    if not include_archived:
        where += " and ct.archived_at is null"
    sql = (
        _SELECT_THREAD_WITH_ACTIVE_JOB
        + where
        + " order by ct.last_message_at desc, ct.created_at desc limit %s offset %s"
    )
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (workspace_id, limit, offset))
            return list(cur.fetchall())


def count_chat_threads(
    workspace_id: str,
    include_archived: bool = False,
    connection: object | None = None,
) -> int:
    where = "where workspace_id = %s::uuid"
    if not include_archived:
        where += " and archived_at is null"
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(f"select count(*) as total from chat_threads {where}", (workspace_id,))
            row = cur.fetchone() or {}
            return int(row.get("total") or 0)


def update_chat_thread(
    public_thread_id: str,
    workspace_id: str | None = None,
    connection: object | None = None,
    **fields,
) -> dict | None:
    safe = {k: v for k, v in fields.items() if k in _ALLOWED_UPDATE_FIELDS}
    if not safe:
        return get_chat_thread_by_public_id(public_thread_id, workspace_id=workspace_id, connection=connection)

    set_clauses = []
    params = []
    for key in safe:
        if key == "final_brief":
            set_clauses.append("final_brief = %s::jsonb")
            params.append(jsonb_param(safe[key] if safe[key] is not None else {}))
        else:
            set_clauses.append(f"{key} = %s")
            params.append(safe[key])
    set_clauses.append("updated_at = now()")
    params.append(public_thread_id)
    where = "public_thread_id = %s and archived_at is null"
    if workspace_id:
        where += " and workspace_id = %s::uuid"
        params.append(workspace_id)
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(f"update chat_threads set {', '.join(set_clauses)} where {where} returning *", params)
            return cur.fetchone()


def archive_chat_thread(
    public_thread_id: str,
    workspace_id: str | None = None,
    force: bool = False,
    connection: object | None = None,
) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update chat_threads
                set status = 'archived',
                    archived_at = now(),
                    active_job_id = null,
                    updated_at = now()
                where public_thread_id = %s
                  and (%s::uuid is null or workspace_id = %s::uuid)
                  and (%s::boolean = true or active_job_id is null)
                returning *
                """,
                (public_thread_id, workspace_id, workspace_id, force),
            )
            return cur.fetchone()


def restore_chat_thread(
    public_thread_id: str,
    workspace_id: str | None = None,
    connection: object | None = None,
) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update chat_threads
                set status = 'draft',
                    archived_at = null,
                    updated_at = now()
                where public_thread_id = %s
                  and archived_at is not null
                  and (%s::uuid is null or workspace_id = %s::uuid)
                returning *
                """,
                (public_thread_id, workspace_id, workspace_id),
            )
            return cur.fetchone()


def set_chat_thread_active_job(
    public_thread_id: str,
    active_job_id: str,
    status: str = "generating",
    workspace_id: str | None = None,
    connection: object | None = None,
) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update chat_threads
                set active_job_id = %s::uuid,
                    status = %s,
                    updated_at = now()
                where public_thread_id = %s
                  and (%s::uuid is null or workspace_id = %s::uuid)
                  and archived_at is null
                  and active_job_id is null
                returning *
                """,
                (active_job_id, status, public_thread_id, workspace_id, workspace_id),
            )
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


def complete_chat_thread_generation(
    *,
    public_thread_id: str,
    workspace_id: str,
    expected_active_job_id: str,
    final_output_id: str | None,
    final_brief: dict | None = None,
    connection: object | None = None,
) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            if final_brief is not None:
                cur.execute(
                    """
                    update chat_threads
                    set active_job_id = null,
                        status = 'completed',
                        final_output_id = coalesce(%s::uuid, final_output_id),
                        final_brief = %s::jsonb,
                        updated_at = now()
                    where public_thread_id = %s
                      and workspace_id = %s::uuid
                      and active_job_id = %s::uuid
                    returning *
                    """,
                    (final_output_id, jsonb_param(final_brief), public_thread_id, workspace_id, expected_active_job_id),
                )
            else:
                cur.execute(
                    """
                    update chat_threads
                    set active_job_id = null,
                        status = 'completed',
                        final_output_id = coalesce(%s::uuid, final_output_id),
                        updated_at = now()
                    where public_thread_id = %s
                      and workspace_id = %s::uuid
                      and active_job_id = %s::uuid
                    returning *
                    """,
                    (final_output_id, public_thread_id, workspace_id, expected_active_job_id),
                )
            return cur.fetchone()


def fail_chat_thread_generation(
    *,
    public_thread_id: str,
    workspace_id: str,
    expected_active_job_id: str,
    connection: object | None = None,
) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update chat_threads
                set active_job_id = null,
                    status = 'failed',
                    updated_at = now()
                where public_thread_id = %s
                  and workspace_id = %s::uuid
                  and active_job_id = %s::uuid
                returning *
                """,
                (public_thread_id, workspace_id, expected_active_job_id),
            )
            return cur.fetchone()


def pause_chat_thread_generation(
    *,
    public_thread_id: str,
    workspace_id: str,
    expected_active_job_id: str,
    connection: object | None = None,
) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update chat_threads
                set active_job_id = null,
                    status = 'draft',
                    updated_at = now()
                where public_thread_id = %s
                  and workspace_id = %s::uuid
                  and active_job_id = %s::uuid
                returning *
                """,
                (public_thread_id, workspace_id, expected_active_job_id),
            )
            return cur.fetchone()


def clear_chat_thread_active_job(
    public_thread_id: str,
    status: str,
    expected_active_job_id: str | None = None,
    connection: object | None = None,
) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update chat_threads
                set active_job_id = null,
                    status = %s,
                    updated_at = now()
                where public_thread_id = %s
                  and (%s::uuid is null or active_job_id = %s::uuid)
                returning *
                """,
                (status, public_thread_id, expected_active_job_id, expected_active_job_id),
            )
            return cur.fetchone()


def set_chat_thread_final_output(
    public_thread_id: str,
    final_output_id: str,
    final_brief: dict | None = None,
    connection: object | None = None,
) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            if final_brief is not None:
                cur.execute(
                    """
                    update chat_threads
                    set final_output_id = %s::uuid,
                        final_brief = %s::jsonb,
                        updated_at = now()
                    where public_thread_id = %s
                    returning *
                    """,
                    (final_output_id, jsonb_param(final_brief), public_thread_id),
                )
            else:
                cur.execute(
                    """
                    update chat_threads
                    set final_output_id = %s::uuid,
                        updated_at = now()
                    where public_thread_id = %s
                    returning *
                    """,
                    (final_output_id, public_thread_id),
                )
            return cur.fetchone()
