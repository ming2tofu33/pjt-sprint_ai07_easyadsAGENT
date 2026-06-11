"""Database backend settings."""

from __future__ import annotations

from typing import Literal

from orchestrator.app.core.config import _get_env
from orchestrator.app.db.errors import DatabaseConfigurationError

DbBackend = Literal["memory", "postgres"]


def get_db_backend() -> DbBackend:
    value = str(_get_env("EASYADS_DB_BACKEND", "memory") or "memory").strip().lower()
    if value == "postgres":
        return "postgres"
    return "memory"


def get_database_url(required: bool = False) -> str | None:
    value = _get_env("DATABASE_URL", "").strip()
    if required and not value:
        raise DatabaseConfigurationError("DATABASE_URL is required when EASYADS_DB_BACKEND=postgres.")
    return value or None


def is_postgres_enabled() -> bool:
    if get_db_backend() != "postgres":
        return False
    get_database_url(required=True)
    return True


def get_demo_workspace_id() -> str | None:
    return _get_env("EASYADS_DEMO_WORKSPACE_ID", "").strip() or None


def get_demo_user_id() -> str | None:
    return _get_env("EASYADS_DEMO_USER_ID", "").strip() or None


def allow_demo_workspace_fallback() -> bool:
    value = str(_get_env("EASYADS_ALLOW_DEMO_WORKSPACE_FALLBACK", "false") or "false").strip().lower()
    return value in {"1", "true", "yes", "on"}


def get_max_threads_per_workspace() -> int:
    """Maximum number of (non-archived) chat threads allowed per workspace.

    Defaults to 3. Falls back to 3 for missing/invalid/non-positive values.
    """
    raw = _get_env("EASYADS_MAX_THREADS_PER_WORKSPACE", "3") or "3"
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return 3
    return value if value > 0 else 3
