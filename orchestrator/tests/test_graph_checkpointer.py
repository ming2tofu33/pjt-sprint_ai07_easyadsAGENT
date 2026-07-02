"""Tests for the checkpointer factory."""

import logging

import pytest
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from orchestrator.app.db.errors import DatabaseConfigurationError
from orchestrator.app.graph.checkpointer import get_checkpointer


def test_memory_checkpointer_when_db_backend_memory(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    get_checkpointer.cache_clear()
    try:
        checkpointer = get_checkpointer()
        assert isinstance(checkpointer, BaseCheckpointSaver)
        assert type(checkpointer).__name__ == "InstrumentedCheckpointer"
        assert type(checkpointer._inner).__name__ in {"InMemorySaver", "MemorySaver"}
    finally:
        get_checkpointer.cache_clear()


def test_checkpointer_is_process_singleton(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    get_checkpointer.cache_clear()
    try:
        assert get_checkpointer() is get_checkpointer()
    finally:
        get_checkpointer.cache_clear()


def test_memory_checkpointer_logs_warning(monkeypatch, caplog):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    get_checkpointer.cache_clear()
    try:
        caplog.set_level(logging.WARNING)
        get_checkpointer()
        assert "LangGraph InMemorySaver checkpointer is active" in caplog.text
    finally:
        get_checkpointer.cache_clear()


def test_strict_runtime_rejects_memory_checkpointer(monkeypatch):
    monkeypatch.setenv("EASYADS_ENV", "production")
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_checkpointer.cache_clear()
    try:
        with pytest.raises(DatabaseConfigurationError, match="Postgres DB backend is required"):
            get_checkpointer()
    finally:
        get_checkpointer.cache_clear()


def test_postgres_branch_is_selected(monkeypatch):
    """Postgres mode must route to the postgres builder (without a real DB)."""
    import orchestrator.app.graph.checkpointer as cp

    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid:5432/db")
    sentinel = InMemorySaver()
    monkeypatch.setattr(cp, "_build_postgres_checkpointer", lambda: sentinel)
    cp.get_checkpointer.cache_clear()
    try:
        wrapped = cp.get_checkpointer()
        assert isinstance(wrapped, BaseCheckpointSaver)
        assert wrapped._inner is sentinel
    finally:
        cp.get_checkpointer.cache_clear()
