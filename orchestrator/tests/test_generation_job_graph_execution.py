"""Tests for execute_generation_job_graph and state restoration."""

import pytest
from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest
from orchestrator.app.generation_jobs.service import create_generation_job, reset_generation_job_store_for_tests
from orchestrator.app.chat_threads.service import reset_chat_thread_store_for_tests
from orchestrator.app.generation_jobs.execution import execute_generation_job_graph

@pytest.fixture(autouse=True)
def reset_stores():
    reset_generation_job_store_for_tests()
    reset_chat_thread_store_for_tests()
    from orchestrator.app.chat_threads.state_service import _SNAPSHOTS_MEM_LOCK, _SNAPSHOTS_MEM
    with _SNAPSHOTS_MEM_LOCK:
        _SNAPSHOTS_MEM.clear()
    yield

def test_execute_generation_job_graph_state_restoration(monkeypatch):
    class MockGraph:
        def invoke(self, payload: dict) -> dict:
            state = dict(payload)
            state["status"] = "completed"
            state["result_payload"] = {"final_image_path": "/fake/path.png", "final_brief": {"user_input": state["user_input"]}}
            state["final_image_path"] = "/fake/path.png"
            return state

    monkeypatch.setattr("orchestrator.app.graph.builder.build_marketing_graph", lambda: MockGraph())
    
    req1 = GenerationJobCreateRequest(
        user_input="turn 1 prompt",
        run_mode="graph_immediate",
        copy_generation_mode="auto",
    )
    job1 = create_generation_job(req1)
    assert job1.status == "queued"
    
    executed1 = execute_generation_job_graph(job1.job_id, req1)
    assert executed1.status == "done"
    
    received_payload = {}
    class MockGraph2:
        def invoke(self, payload: dict) -> dict:
            nonlocal received_payload
            received_payload = dict(payload)
            state = dict(payload)
            state["status"] = "completed"
            state["result_payload"] = {"final_image_path": "/fake/path2.png", "final_brief": {"user_input": state["user_input"]}}
            state["final_image_path"] = "/fake/path2.png"
            return state
            
    monkeypatch.setattr("orchestrator.app.graph.builder.build_marketing_graph", lambda: MockGraph2())
    
    req2 = GenerationJobCreateRequest(
        user_input="turn 2 prompt",
        run_mode="graph_immediate",
        thread_id=job1.thread_id,
        user_id=job1.user_id,
        copy_generation_mode="custom",
    )
    job2 = create_generation_job(req2)
    executed2 = execute_generation_job_graph(job2.job_id, req2)
    
    assert executed2.status == "done"
    assert received_payload["user_input"] == "turn 2 prompt"
    assert received_payload["copy_generation_mode"] == "custom"
    assert received_payload["job_id"] == job2.job_id
    assert received_payload["thread_id"] == job1.thread_id

def test_execute_generation_job_graph_waiting_user_input(monkeypatch):
    class MockGraphWaiting:
        def invoke(self, payload: dict) -> dict:
            state = dict(payload)
            state["status"] = "waiting_user_input"
            state["messages"] = [{"role": "assistant", "content": "Please answer this."}]
            return state

    monkeypatch.setattr("orchestrator.app.graph.builder.build_marketing_graph", lambda: MockGraphWaiting())
    
    req = GenerationJobCreateRequest(
        user_input="start",
        run_mode="graph_immediate",
    )
    job = create_generation_job(req)
    executed = execute_generation_job_graph(job.job_id, req)
    
    if executed.status == "failed":
        print("ERROR:", executed.error)
        
    assert executed.status == "waiting_user_input"
    assert executed.progress.current_stage == "waiting_user_input"
