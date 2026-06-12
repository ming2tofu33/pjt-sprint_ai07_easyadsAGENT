"""Postgres-gated proof that HITL interrupts survive a process restart.

Run with: EASYADS_DB_BACKEND=postgres DATABASE_URL=postgresql://... \
    uv run python -m pytest orchestrator/tests/test_checkpointer_durable_resume.py -q
"""

import os
import uuid
from typing import TypedDict

import pytest

requires_postgres = pytest.mark.skipif(
    os.environ.get("EASYADS_DB_BACKEND") != "postgres" or not os.environ.get("DATABASE_URL"),
    reason="requires EASYADS_DB_BACKEND=postgres and DATABASE_URL",
)


class _State(TypedDict):
    answer: str


def _build_graph(checkpointer):
    from langgraph.graph import END, StateGraph
    from langgraph.types import interrupt

    def ask(state: _State) -> _State:
        value = interrupt({"question": "continue?"})
        return {"answer": str(value)}

    graph = StateGraph(_State)
    graph.add_node("ask", ask)
    graph.set_entry_point("ask")
    graph.add_edge("ask", END)
    return graph.compile(checkpointer=checkpointer)


@requires_postgres
def test_interrupt_survives_checkpointer_rebuild():
    from langgraph.types import Command

    from orchestrator.app.graph.checkpointer import _build_postgres_checkpointer

    thread_id = f"durable-resume-test-{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}

    # Process #1: hit the interrupt.
    first_graph = _build_graph(_build_postgres_checkpointer())
    result = first_graph.invoke({"answer": ""}, config=config)
    assert "__interrupt__" in result

    # Process #2: brand-new checkpointer + graph instance (fresh pool, fresh
    # compile) — only the DB rows connect the two. This is the restart case
    # InMemorySaver could never satisfy.
    second_graph = _build_graph(_build_postgres_checkpointer())
    resumed = second_graph.invoke(Command(resume="yes"), config=config)
    assert resumed["answer"] == "yes"
