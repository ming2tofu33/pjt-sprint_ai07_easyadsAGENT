"""Workspace scope resolver for APIs."""

from __future__ import annotations

from orchestrator.app.db import settings as db_settings
from orchestrator.app.db.repositories import workspaces as workspace_repo


class WorkspaceScopeRequired(ValueError):
    """Raised when no workspace can be resolved."""


class WorkspaceScopeForbidden(PermissionError):
    """Raised when the requested workspace is not available for the user."""


def resolve_workspace_scope(workspace_id: str | None = None, user_id: str | None = None, account_type: str | None = None) -> str:
    uid = (user_id or db_settings.get_demo_user_id() or "").strip()
    req_ws = (workspace_id or "").strip()
    
    if uid:
        if account_type:
            workspace = workspace_repo.ensure_user_workspace(user_id=uid, account_type=account_type)
        else:
            workspace = workspace_repo.ensure_user_workspace(user_id=uid)
        resolved_id = str(workspace["id"])
        if req_ws and req_ws != resolved_id:
            raise WorkspaceScopeForbidden("Workspace is not available for the authenticated user.")
        return resolved_id
        
    resolved = (db_settings.get_demo_workspace_id() or "").strip()
    if not resolved:
        raise WorkspaceScopeRequired("workspace_id or EASYADS_DEMO_WORKSPACE_ID is required.")
        
    if req_ws and req_ws != resolved:
        raise WorkspaceScopeForbidden("Workspace is not available.")
        
    return resolved
