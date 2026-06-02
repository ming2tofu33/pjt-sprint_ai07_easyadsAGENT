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
