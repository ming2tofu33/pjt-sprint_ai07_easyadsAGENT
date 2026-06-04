import pytest

from orchestrator.app.db.errors import DatabaseConfigurationError
from orchestrator.app.db.settings import (
    get_database_url,
    get_db_backend,
    get_demo_user_id,
    get_demo_workspace_id,
    is_postgres_enabled,
)


def test_default_backend_is_memory(monkeypatch):
    monkeypatch.delenv("EASYADS_DB_BACKEND", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert get_db_backend() == "memory"
    assert get_database_url() is None
    assert is_postgres_enabled() is False


def test_unknown_backend_falls_back_to_memory(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "unknown")

    assert get_db_backend() == "memory"


def test_postgres_backend_requires_database_url(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert get_db_backend() == "postgres"
    with pytest.raises(DatabaseConfigurationError, match="DATABASE_URL is required"):
        is_postgres_enabled()


def test_demo_env_values(monkeypatch):
    monkeypatch.setenv("EASYADS_DEMO_WORKSPACE_ID", "workspace-demo")
    monkeypatch.setenv("EASYADS_DEMO_USER_ID", "demo_user")

    assert get_demo_workspace_id() == "workspace-demo"
    assert get_demo_user_id() == "demo_user"
