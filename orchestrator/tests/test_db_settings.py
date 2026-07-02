import pytest

from orchestrator.app.core import config
from orchestrator.app.core.config import _load_dotenv
from orchestrator.app.db.errors import DatabaseConfigurationError
from orchestrator.app.db.settings import (
    get_database_url,
    get_db_backend,
    get_demo_user_id,
    get_demo_workspace_id,
    is_postgres_enabled,
)


def _isolate_dotenv(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    _load_dotenv.cache_clear()


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


def test_database_url_without_backend_enables_postgres(monkeypatch, tmp_path):
    _isolate_dotenv(monkeypatch, tmp_path)
    monkeypatch.delenv("EASYADS_DB_BACKEND", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/easyads")

    try:
        assert get_db_backend() == "postgres"
        assert is_postgres_enabled() is True
    finally:
        _load_dotenv.cache_clear()


def test_strict_runtime_requires_database_url(monkeypatch, tmp_path):
    _isolate_dotenv(monkeypatch, tmp_path)
    monkeypatch.delenv("EASYADS_DB_BACKEND", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("EASYADS_ENV", "production")

    try:
        with pytest.raises(DatabaseConfigurationError, match="Postgres DB backend is required"):
            is_postgres_enabled()
    finally:
        _load_dotenv.cache_clear()


def test_demo_env_values(monkeypatch):
    monkeypatch.setenv("EASYADS_DEMO_WORKSPACE_ID", "workspace-demo")
    monkeypatch.setenv("EASYADS_DEMO_USER_ID", "demo_user")

    assert get_demo_workspace_id() == "workspace-demo"
    assert get_demo_user_id() == "demo_user"
