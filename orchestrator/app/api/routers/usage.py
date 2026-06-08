"""Usage summary API router."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter

from orchestrator.app.api.errors import raise_api_error
from orchestrator.app.api.schemas.usage import UsageSummaryResponse
from orchestrator.app.db import settings as db_settings
from orchestrator.app.db.workspace_scope import WorkspaceScopeForbidden, WorkspaceScopeRequired, resolve_workspace_scope
from orchestrator.app.llm.plan_policy import normalize_user_plan
from orchestrator.app.usage.errors import UsageError
from orchestrator.app.usage.service import get_usage_summary


router = APIRouter(prefix="/usage", tags=["Usage"])


@router.get("/summary", response_model=UsageSummaryResponse)
def usage_summary(
    workspace_id: str | None = None,
    workspaceId: str | None = None,
    scope: Literal["workspace", "user"] = "workspace",
    startAt: str | None = None,
    endAt: str | None = None,
    plan: str | None = None,
    user_id: str | None = None,
) -> UsageSummaryResponse:
    resolved_user = user_id or db_settings.get_demo_user_id()
    try:
        workspace = resolve_workspace_scope(workspace_id or workspaceId, resolved_user)
        summary = get_usage_summary(
            workspace_id=workspace,
            scope=scope,
            created_by=resolved_user if scope == "user" else None,
            plan=normalize_user_plan(plan),
            start_at=_parse_optional_datetime(startAt),
            end_at=_parse_optional_datetime(endAt),
        )
    except WorkspaceScopeRequired:
        raise_api_error(400, "usage_workspace_required", "Workspace information is required.")
    except WorkspaceScopeForbidden:
        raise_api_error(403, "usage_workspace_forbidden", "Workspace access denied.")
    except UsageError as exc:
        raise_api_error(exc.status_code, exc.error_code, exc.message)
    return UsageSummaryResponse(summary=summary)


def _parse_optional_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        raise_api_error(400, "invalid_usage_range", "Invalid usage date range.")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
