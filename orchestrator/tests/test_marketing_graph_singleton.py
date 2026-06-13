"""Tests for the lazy marketing graph singleton."""


def test_get_marketing_graph_is_cached(monkeypatch):
    from orchestrator.app.api import marketing_graph as mg

    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    mg.get_marketing_graph.cache_clear()
    try:
        assert mg.get_marketing_graph() is mg.get_marketing_graph()
    finally:
        mg.get_marketing_graph.cache_clear()


def test_get_marketing_graph_uses_factory_checkpointer(monkeypatch):
    from langgraph.checkpoint.memory import InMemorySaver

    from orchestrator.app.api import marketing_graph as mg

    sentinel = InMemorySaver()
    monkeypatch.setattr(mg, "get_checkpointer", lambda: sentinel)
    mg.get_marketing_graph.cache_clear()
    try:
        graph = mg.get_marketing_graph()
        assert graph.checkpointer is sentinel
    finally:
        mg.get_marketing_graph.cache_clear()


def test_generation_job_graph_returns_singleton(monkeypatch):
    from orchestrator.app.api import marketing_graph as mg
    from orchestrator.app.generation_jobs.execution import get_generation_job_graph

    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    mg.get_marketing_graph.cache_clear()
    try:
        assert get_generation_job_graph() is mg.get_marketing_graph()
    finally:
        mg.get_marketing_graph.cache_clear()
