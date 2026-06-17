"""Generation job repository."""

from __future__ import annotations

from orchestrator.app.db.session import db_transaction
from orchestrator.app.db.json import jsonb_param

JSONB_FIELDS = {"result_payload", "error", "metadata", "brief", "brand_kit_snapshot", "params", "request_payload"}


def create_generation_job_row(
    *,
    public_job_id: str,
    workspace_id: str,
    thread_id: str | None,
    requested_by: str | None,
    status: str,
    current_stage: str,
    progress_percent: int,
    selected_reference_template_id: str | None,
    input_asset_id: str | None = None,
    reference_asset_id: str | None = None,
    output_path: str | None,
    result_payload: dict | None,
    error: dict | None,
    metadata: dict,
    run_mode: str | None = None,
    engine: str | None = None,
    model_provider: str | None = None,
    model_name: str | None = None,
    model_version: str | None = None,
    prompt_text: str | None = None,
    prompt_hash: str | None = None,
    prompt_preview: str | None = None,
    brief: dict | None = None,
    brand_kit_snapshot: dict | None = None,
    params: dict | None = None,
    request_payload: dict | None = None,
    parent_job_id: str | None = None,
    previous_output_id: str | None = None,
    regeneration_depth: int = 0,
    regeneration_idempotency_key: str | None = None,
    connection: object | None = None,
) -> dict:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into generation_jobs (
                  public_job_id, workspace_id, thread_id, requested_by, status, current_stage,
                  progress_percent, selected_reference_template_id, input_asset_id, reference_asset_id, output_path, result_payload, error, metadata,
                  run_mode, engine, model_provider, model_name, model_version, prompt_text, prompt_hash,
                  prompt_preview, brief, brand_kit_snapshot, params, request_payload,
                  parent_job_id, previous_output_id, regeneration_depth, regeneration_idempotency_key, queued_at
                )
                values (
                  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb,
                  %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
                  %s, %s, %s, %s, now()
                )
                returning *
                """,
                (
                    public_job_id,
                    workspace_id,
                    thread_id,
                    requested_by,
                    status,
                    current_stage,
                    progress_percent,
                    selected_reference_template_id,
                    input_asset_id,
                    reference_asset_id,
                    output_path,
                    jsonb_param(result_payload or {}),
                    jsonb_param(error or {}),
                    jsonb_param(metadata or {}),
                    run_mode,
                    engine,
                    model_provider,
                    model_name,
                    model_version,
                    prompt_text,
                    prompt_hash,
                    prompt_preview,
                    jsonb_param(brief or {}),
                    jsonb_param(brand_kit_snapshot or {}),
                    jsonb_param(params or {}),
                    jsonb_param(request_payload or {}),
                    parent_job_id,
                    previous_output_id,
                    regeneration_depth,
                    regeneration_idempotency_key,
                ),
            )
            return cur.fetchone()


def get_generation_job_by_regeneration_idempotency_key(
    *,
    workspace_id: str,
    idempotency_key: str,
    connection: object | None = None,
) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select gj.*, ct.public_thread_id as public_thread_id
                from generation_jobs gj
                left join chat_threads ct on ct.id = gj.thread_id
                where gj.workspace_id = %s and gj.regeneration_idempotency_key = %s
                """,
                (workspace_id, idempotency_key),
            )
            return cur.fetchone()


def get_generation_job_internal_by_public_id(job_id: str, connection: object | None = None) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select gj.*, ct.public_thread_id as public_thread_id
                from generation_jobs gj
                left join chat_threads ct on ct.id = gj.thread_id
                where gj.public_job_id = %s
                """,
                (job_id,),
            )
            return cur.fetchone()


def get_generation_job_scope_row_by_public_id(
    job_id: str,
    connection: object | None = None,
) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    gj.workspace_id,
                    gj.requested_by,
                    gj.metadata ->> 'user_id' as metadata_user_id
                from generation_jobs gj
                where gj.public_job_id = %s
                """,
                (job_id,),
            )
            return cur.fetchone()


def get_generation_job_row(job_id: str, connection: object | None = None) -> dict | None:
    return get_generation_job_internal_by_public_id(job_id, connection=connection)


def get_generation_job_by_public_id(
    public_job_id: str,
    *,
    workspace_id: str,
    connection: object | None = None,
    for_update: bool = False,
) -> dict | None:
    lock_clause = " for update of gj" if for_update else ""
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select gj.*, ct.public_thread_id as public_thread_id
                from generation_jobs gj
                left join chat_threads ct on ct.id = gj.thread_id
                where gj.public_job_id = %s and gj.workspace_id = %s::uuid
                {lock_clause}
                """,
                (public_job_id, workspace_id),
            )
            return cur.fetchone()


def get_latest_waiting_generation_job_for_thread(
    *,
    public_thread_id: str,
    workspace_id: str,
    connection: object | None = None,
    for_update: bool = False,
) -> dict | None:
    lock_clause = " for update of gj" if for_update else ""
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select gj.*, ct.public_thread_id as public_thread_id
                from generation_jobs gj
                join chat_threads ct on ct.id = gj.thread_id
                where ct.public_thread_id = %s
                  and gj.workspace_id = %s::uuid
                  and gj.status = 'waiting_user_input'
                order by gj.updated_at desc, gj.created_at desc
                limit 1
                {lock_clause}
                """,
                (public_thread_id, workspace_id),
            )
            return cur.fetchone()


def get_generation_job_scoped_by_public_id(
    public_job_id: str,
    *,
    workspace_id: str,
    connection: object | None = None,
    for_update: bool = False,
) -> dict | None:
    return get_generation_job_by_public_id(
        public_job_id,
        workspace_id=workspace_id,
        connection=connection,
        for_update=for_update,
    )


def get_generation_job_db_by_id(job_id: str, *, workspace_id: str, connection: object | None = None) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select gj.*, ct.public_thread_id as public_thread_id, ct.title as thread_title
                from generation_jobs gj
                left join chat_threads ct on ct.id = gj.thread_id
                where gj.id = %s and gj.workspace_id = %s
                """,
                (job_id, workspace_id),
            )
            return cur.fetchone()


def get_generation_job_db(public_job_id: str, *, workspace_id: str, connection: object | None = None) -> dict | None:
    """public_job_id와 workspace_id로 Job 조회 (workspace 격리 보장)."""
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select gj.*, ct.public_thread_id as public_thread_id
                from generation_jobs gj
                left join chat_threads ct on ct.id = gj.thread_id
                where gj.public_job_id = %s and gj.workspace_id = %s
                """,
                (public_job_id, workspace_id),
            )
            return cur.fetchone()


def update_generation_job_row(job_id: str, connection: object | None = None, workspace_id: str | None = None, **fields) -> dict | None:
    allowed = {
        "status",
        "current_stage",
        "progress_percent",
        "output_path",
        "result_payload",
        "error",
        "metadata",
        "modal_call_id",
        "started_at",
        "finished_at",
    }
    updates = {key: value for key, value in fields.items() if key in allowed}
    if not updates:
        return get_generation_job_row(job_id, connection=connection)
    assignments = []
    values = []
    for key, value in updates.items():
        if key == "started_at" and value == "__now_if_null__":
            assignments.append("started_at = coalesce(started_at, now())")
            continue
        if key == "finished_at" and value == "__now__":
            assignments.append("finished_at = now()")
            continue
        assignments.append(f"{key} = %s::jsonb" if key in JSONB_FIELDS else f"{key} = %s")
        values.append(jsonb_param(value) if key in JSONB_FIELDS else value)
    values.append(job_id)
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            where = "public_job_id = %s"
            if workspace_id:
                where += " and workspace_id = %s::uuid"
                values.append(workspace_id)
            cur.execute(
                f"""
                update generation_jobs
                set {', '.join(assignments)}, updated_at = now()
                where {where}
                returning *
                """,
                tuple(values),
            )
            return cur.fetchone()


def update_generation_job_scoped(public_job_id: str, *, workspace_id: str, connection: object | None = None, **fields) -> dict | None:
    return update_generation_job_row(public_job_id, connection=connection, workspace_id=workspace_id, **fields)


def update_generation_job_internal(public_job_id: str, connection: object | None = None, **fields) -> dict | None:
    return update_generation_job_row(public_job_id, connection=connection, **fields)


def mark_generation_job_running_row(job_id: str, current_stage: str | None = None, connection: object | None = None, workspace_id: str | None = None) -> dict | None:
    return update_generation_job_row(
        job_id,
        status="running",
        current_stage=current_stage or "running",
        progress_percent=50,
        started_at="__now_if_null__",
        connection=connection,
        workspace_id=workspace_id,
    )


def mark_generation_job_done_row(
    job_id: str,
    result_payload: dict,
    output_path: str | None = None,
    metadata: dict | None = None,
    connection: object | None = None,
    workspace_id: str | None = None,
) -> dict | None:
    fields = {
        "status": "done",
        "current_stage": "completed",
        "progress_percent": 100,
        "result_payload": result_payload,
        "error": None,
        "finished_at": "__now__",
    }
    if output_path is not None:
        fields["output_path"] = output_path
    if metadata is not None:
        fields["metadata"] = metadata
    return update_generation_job_row(job_id, connection=connection, workspace_id=workspace_id, **fields)


def mark_generation_job_failed_row(
    job_id: str,
    error: dict,
    metadata: dict | None = None,
    connection: object | None = None,
    workspace_id: str | None = None,
) -> dict | None:
    fields = {"status": "failed", "current_stage": "failed", "error": error, "finished_at": "__now__"}
    if metadata is not None:
        fields["metadata"] = metadata
    return update_generation_job_row(job_id, connection=connection, workspace_id=workspace_id, **fields)


def attach_modal_call_id(
    public_job_id: str,
    modal_call_id: str,
    metadata: dict | None = None,
    connection: object | None = None,
) -> dict | None:
    fields = {"modal_call_id": modal_call_id}
    if metadata is not None:
        fields["metadata"] = metadata
    return update_generation_job_row(public_job_id, connection=connection, **fields)
