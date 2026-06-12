"""Tests for the checkpointer factory."""

from orchestrator.app.graph.checkpointer import get_checkpointer


def test_memory_checkpointer_when_db_backend_memory(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    get_checkpointer.cache_clear()
    try:
        checkpointer = get_checkpointer()
        # InMemorySaver (or its MemorySaver alias on older langgraph).
        assert type(checkpointer).__name__ in {"InMemorySaver", "MemorySaver"}
    finally:
        get_checkpointer.cache_clear()


def test_checkpointer_is_process_singleton(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    get_checkpointer.cache_clear()
    try:
        assert get_checkpointer() is get_checkpointer()
    finally:
        get_checkpointer.cache_clear()


def test_postgres_branch_is_selected(monkeypatch):
    """Postgres mode must route to the postgres builder (without a real DB)."""
    import orchestrator.app.graph.checkpointer as cp

    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid:5432/db")
    sentinel = object()
    monkeypatch.setattr(cp, "_build_postgres_checkpointer", lambda: sentinel)
    cp.get_checkpointer.cache_clear()
    try:
        assert cp.get_checkpointer() is sentinel
    finally:
        cp.get_checkpointer.cache_clear()
