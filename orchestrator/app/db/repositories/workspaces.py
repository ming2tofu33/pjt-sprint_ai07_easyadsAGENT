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


def ensure_user_workspace(user_id: str, connection: object | None = None) -> dict:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select *
                from workspaces
                where owner_user_id = %s
                order by created_at asc
                limit 1
                """,
                (user_id,),
            )
            existing = cur.fetchone()
            if existing:
                return existing
            cur.execute(
                """
                insert into workspaces (name, owner_user_id, metadata)
                values (%s, %s, %s::jsonb)
                returning *
                """,
                ("User Workspace", user_id, jsonb_param({"source": "supabase_auth"})),
            )
            return cur.fetchone()
