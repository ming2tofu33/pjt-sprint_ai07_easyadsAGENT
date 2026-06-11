from __future__ import annotations

import orchestrator.app.graph.builder as graph_builder


def test_intake_graph_routes_through_input_evidence_normalizer(monkeypatch):
    trace: list[str] = []

    def input_node(state):
        trace.append("input")
        return state

    def normalizer_node(state):
        trace.append("input_evidence_normalizer")
        return {"input_evidence_bundle": {"schema_version": "input_evidence_bundle_v1"}, "input_normalization_status": "completed"}

    def validator_node(state):
        trace.append("validator")
        return {"missing_fields": [], "validator_output": {"status": "ok"}}

    monkeypatch.setattr(graph_builder, "input_node", input_node)
    monkeypatch.setattr(graph_builder, "input_evidence_normalizer_node", normalizer_node)
    monkeypatch.setattr(graph_builder, "validator_node", validator_node)

    graph = graph_builder.build_intake_graph()
    graph.invoke({"user_input": "카페 치즈케이크 홍보", "job_id": "graph-test", "thread_id": "graph-test"}, config={"configurable": {"thread_id": "graph-test"}})

    assert trace[:3] == ["input", "input_evidence_normalizer", "validator"]

