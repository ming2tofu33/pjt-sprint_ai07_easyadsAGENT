"""Workspace repository."""

from __future__ import annotations

from uuid import uuid4

from orchestrator.app.db.json import jsonb_param
from orchestrator.app.db.session import db_transaction
from orchestrator.app.db.settings import get_demo_user_id, get_demo_workspace_id


def get_workspace(workspace_id: str, connection: object | None = None) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute("select * from workspaces where id = %s", (workspace_id,))
            return cur.fetchone()


def get_workspace_for_user(*, workspace_id: str, user_id: str, connection: object | None = None) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select w.*
                from workspaces w
                where w.id = %s::uuid
                  and (
                    w.owner_user_id = %s
                    or exists (
                      select 1
                      from workspace_members wm
                      where wm.workspace_id = w.id
                        and wm.user_id = %s
                    )
                  )
                """,
                (workspace_id, user_id, user_id),
            )
            return cur.fetchone()


def ensure_demo_workspace(workspace_id: str | None = None, user_id: str | None = None, connection: object | None = None) -> dict:
    workspace_id = workspace_id or get_demo_workspace_id()
    user_id = user_id or get_demo_user_id()
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            if workspace_id:
                cur.execute("select * from workspaces where id = %s", (workspace_id,))
                existing = cur.fetchone()
                if existing:
                    return existing
                cur.execute(
                    """
                    insert into workspaces (id, name, owner_user_id, metadata)
                    values (%s, %s, %s, %s::jsonb)
                    returning *
                    """,
                    (workspace_id, "Demo Workspace", user_id, jsonb_param({"source": "demo_fallback"})),
                )
                return cur.fetchone()
            cur.execute(
                """
                insert into workspaces (name, owner_user_id, metadata)
                values (%s, %s, %s::jsonb)
                returning *
                """,
                (f"Demo Workspace {uuid4().hex[:8]}", user_id, jsonb_param({"source": "demo_fallback"})),
            )
            return cur.fetchone()


def _workspace_source_for_account_type(account_type: str | None) -> str:
    return "supabase_guest" if account_type == "guest" else "supabase_auth"


def ensure_user_workspace(user_id: str, account_type: str | None = None, connection: object | None = None) -> dict:
    requested_account_type = account_type if account_type in {"guest", "user"} else None
    target_source = _workspace_source_for_account_type(requested_account_type)
    target_account_type = "guest" if requested_account_type == "guest" else "user"
    target_name = "Guest Workspace" if target_account_type == "guest" else "User Workspace"
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select pg_advisory_xact_lock(hashtext(%s))",
                (f"workspace_owner:{user_id}",),
            )
            cur.execute(
                """
                select w.*
                from workspaces w
                left join chat_threads ct on ct.workspace_id = w.id
                left join generation_jobs gj on gj.workspace_id = w.id
                where w.owner_user_id = %s
                group by w.id
                order by
                  (count(distinct ct.id) + count(distinct gj.id) > 0) desc,
                  (w.metadata->>'source' = 'supabase_auth') desc,
                  max(greatest(
                    coalesce(ct.updated_at, ct.created_at, 'epoch'::timestamptz),
                    coalesce(gj.updated_at, gj.created_at, 'epoch'::timestamptz)
                  )) desc nulls last,
                  w.created_at asc
                limit 1
                """,
                (user_id,),
            )
            existing = cur.fetchone()
            if existing:
                if requested_account_type is None:
                    return existing
                metadata = existing.get("metadata") if isinstance(existing.get("metadata"), dict) else {}
                existing_source = metadata.get("source")
                if existing_source == target_source:
                    return existing
                if target_source == "supabase_guest" and existing_source == "supabase_auth":
                    return existing
                cur.execute(
                    """
                    update workspaces
                    set name = %s,
                        metadata = coalesce(metadata, '{}'::jsonb) || %s::jsonb,
                        updated_at = now()
                    where id = %s
                    returning *
                    """,
                    (
                        target_name,
                        jsonb_param({
                            "source": target_source,
                            "account_type": target_account_type,
                            "normalized_from": existing_source or "legacy_workspace",
                        }),
                        existing["id"],
                    ),
                )
                return cur.fetchone() or existing
            cur.execute(
                """
                insert into workspaces (name, owner_user_id, metadata)
                values (%s, %s, %s::jsonb)
                returning *
                """,
                (
                    target_name,
                    user_id,
                    jsonb_param({
                        "source": target_source,
                        "account_type": target_account_type,
                    }),
                ),
            )
            return cur.fetchone()
