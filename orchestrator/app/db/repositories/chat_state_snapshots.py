"""Chat state snapshots repository."""

from __future__ import annotations

from orchestrator.app.db.json import jsonb_param
from orchestrator.app.db.session import db_transaction

def create_chat_state_snapshot(
    *,
    public_snapshot_id: str,
    public_thread_id: str,
    workspace_id: str,
    snapshot_kind: str,
    state_payload: dict,
    changed_fields: list[str],
    generation_job_id: str | None = None,
    source_message_id: str | None = None,
    parent_snapshot_id: str | None = None,
    selected_reference_template_id: str | None = None,
    reference_template_snapshot: dict | None = None,
    brand_kit_snapshot: dict | None = None,
    snapshot_key: str | None = None,
    metadata: dict | None = None,
    created_by: str | None = None,
    connection: object | None = None,
) -> dict:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            # 1. Lock thread
            cur.execute(
                """
                select id, workspace_id
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

            thread_uuid = str(thread["id"])

            # 2. Idempotency Check
            if snapshot_key:
                cur.execute(
                    """
                    select s.*, t.public_thread_id, j.public_job_id, p.public_snapshot_id as parent_public_id, m.id as msg_uuid
                    from chat_state_snapshots s
                    join chat_threads t on t.id = s.thread_id
                    left join generation_jobs j on j.id = s.generation_job_id
                    left join chat_state_snapshots p on p.id = s.parent_snapshot_id
                    left join chat_messages m on m.id = s.source_message_id
                    where s.thread_id = %s::uuid and s.snapshot_key = %s
                    """,
                    (thread_uuid, snapshot_key)
                )
                existing = cur.fetchone()
                if existing:
                    return _map_snapshot_row(existing)

            # 3. Resolve parent ID
            parent_id_val = None
            if parent_snapshot_id:
                cur.execute(
                    "select id from chat_state_snapshots where public_snapshot_id = %s and thread_id = %s::uuid",
                    (parent_snapshot_id, thread_uuid),
                )
                parent_row = cur.fetchone()
                if not parent_row:
                    raise ValueError("chat_state_parent_snapshot_not_found")
                parent_id_val = str(parent_row["id"])

            # 4. Increment snapshot version
            cur.execute(
                "select coalesce(max(snapshot_version), 0) + 1 as next_version from chat_state_snapshots where thread_id = %s::uuid",
                (thread_uuid,),
            )
            snapshot_version = cur.fetchone()["next_version"]

            # 5. Insert
            cur.execute(
                """
                insert into chat_state_snapshots (
                    public_snapshot_id, workspace_id, thread_id, generation_job_id,
                    source_message_id, parent_snapshot_id, snapshot_version, schema_version,
                    snapshot_kind, state_payload, changed_fields,
                    selected_reference_template_id, reference_template_snapshot, brand_kit_snapshot,
                    snapshot_key, metadata, created_by
                )
                values (
                    %s, %s::uuid, %s::uuid, %s::uuid,
                    %s::uuid, %s::uuid, %s, 1,
                    %s, %s::jsonb, %s,
                    %s, %s::jsonb, %s::jsonb,
                    %s, %s::jsonb, %s
                )
                returning *
                """,
                (
                    public_snapshot_id, workspace_id, thread_uuid, generation_job_id,
                    source_message_id, parent_id_val, snapshot_version,
                    snapshot_kind, jsonb_param(state_payload), changed_fields,
                    selected_reference_template_id, jsonb_param(reference_template_snapshot or {}), jsonb_param(brand_kit_snapshot or {}),
                    snapshot_key, jsonb_param(metadata or {}), created_by
                )
            )
            inserted = cur.fetchone()

            # Refetch to get public ids
            cur.execute(
                """
                select s.*, t.public_thread_id, j.public_job_id, p.public_snapshot_id as parent_public_id, m.id as msg_uuid
                from chat_state_snapshots s
                join chat_threads t on t.id = s.thread_id
                left join generation_jobs j on j.id = s.generation_job_id
                left join chat_state_snapshots p on p.id = s.parent_snapshot_id
                left join chat_messages m on m.id = s.source_message_id
                where s.id = %s::uuid
                """,
                (str(inserted["id"]),)
            )
            return _map_snapshot_row(cur.fetchone())

def get_latest_chat_state_snapshot(
    public_thread_id: str,
    workspace_id: str,
    connection: object | None = None,
) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select s.*, t.public_thread_id, j.public_job_id, p.public_snapshot_id as parent_public_id, m.id as msg_uuid
                from chat_state_snapshots s
                join chat_threads t on t.id = s.thread_id
                left join generation_jobs j on j.id = s.generation_job_id
                left join chat_state_snapshots p on p.id = s.parent_snapshot_id
                left join chat_messages m on m.id = s.source_message_id
                where t.public_thread_id = %s and s.workspace_id = %s::uuid
                order by s.snapshot_version desc
                limit 1
                """,
                (public_thread_id, workspace_id)
            )
            row = cur.fetchone()
            return _map_snapshot_row(row) if row else None

def list_chat_state_snapshots(
    public_thread_id: str,
    workspace_id: str,
    limit: int = 100,
    offset: int = 0,
    connection: object | None = None,
) -> list[dict]:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select s.*, t.public_thread_id, j.public_job_id, p.public_snapshot_id as parent_public_id, m.id as msg_uuid
                from chat_state_snapshots s
                join chat_threads t on t.id = s.thread_id
                left join generation_jobs j on j.id = s.generation_job_id
                left join chat_state_snapshots p on p.id = s.parent_snapshot_id
                left join chat_messages m on m.id = s.source_message_id
                where t.public_thread_id = %s and s.workspace_id = %s::uuid
                order by s.snapshot_version desc
                limit %s offset %s
                """,
                (public_thread_id, workspace_id, limit, offset)
            )
            return [_map_snapshot_row(r) for r in cur.fetchall()]

def count_chat_state_snapshots(
    public_thread_id: str,
    workspace_id: str,
    connection: object | None = None,
) -> int:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select count(*) as total
                from chat_state_snapshots s
                join chat_threads t on t.id = s.thread_id
                where t.public_thread_id = %s and s.workspace_id = %s::uuid
                """,
                (public_thread_id, workspace_id)
            )
            row = cur.fetchone()
            return int(row["total"]) if row else 0

def get_chat_state_snapshot_by_public_id(
    public_snapshot_id: str,
    workspace_id: str,
    connection: object | None = None,
) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select s.*, t.public_thread_id, j.public_job_id, p.public_snapshot_id as parent_public_id, m.id as msg_uuid
                from chat_state_snapshots s
                join chat_threads t on t.id = s.thread_id
                left join generation_jobs j on j.id = s.generation_job_id
                left join chat_state_snapshots p on p.id = s.parent_snapshot_id
                left join chat_messages m on m.id = s.source_message_id
                where s.public_snapshot_id = %s and s.workspace_id = %s::uuid
                """,
                (public_snapshot_id, workspace_id)
            )
            row = cur.fetchone()
            return _map_snapshot_row(row) if row else None

def get_chat_state_snapshot_by_key(
    snapshot_key: str,
    thread_id: str,
    workspace_id: str,
    connection: object | None = None,
) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select s.*, t.public_thread_id, j.public_job_id, p.public_snapshot_id as parent_public_id, m.id as msg_uuid
                from chat_state_snapshots s
                join chat_threads t on t.id = s.thread_id
                left join generation_jobs j on j.id = s.generation_job_id
                left join chat_state_snapshots p on p.id = s.parent_snapshot_id
                left join chat_messages m on m.id = s.source_message_id
                where s.snapshot_key = %s and t.public_thread_id = %s and s.workspace_id = %s::uuid
                """,
                (snapshot_key, thread_id, workspace_id)
            )
            row = cur.fetchone()
            return _map_snapshot_row(row) if row else None

def _map_snapshot_row(row: dict) -> dict:
    res = dict(row)
    res["snapshot_id"] = res.pop("public_snapshot_id")
    res["thread_id"] = res.pop("public_thread_id", None)
    res["job_id"] = res.pop("public_job_id", None)
    res["parent_snapshot_id"] = res.pop("parent_public_id", None)
    
    # We don't expose db UUIDs. Format message id if present.
    msg_uuid = res.pop("msg_uuid", None)
    if msg_uuid:
        # Assuming msg_ + UUID hex convention for source message
        res["source_message_id"] = f"msg_{str(msg_uuid).replace('-', '')}"
    else:
        res["source_message_id"] = None
        
    return res
