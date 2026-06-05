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
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            state = dict(payload)
            state["status"] = "done"
            state["result_payload"] = {"final_image_path": "/fake/path.png", "final_brief": {"user_input": state["user_input"]}}
            state["final_image_path"] = "/fake/path.png"
            return state

    monkeypatch.setattr("orchestrator.app.graph.builder.build_marketing_graph", lambda: MockGraph())
    
    req1 = GenerationJobCreateRequest(
        user_input="turn 1 prompt",
        run_mode="graph_immediate",
        copy_generation_mode="auto_pilot",
    )
    job1 = create_generation_job(req1)
    assert job1.status == "queued"
    
    executed1 = execute_generation_job_graph(job1.job_id, req1)
    if executed1.status == "failed":
        print("ERROR1:", executed1.error)
    assert executed1.status == "done"
    
    received_payload = {}
    class MockGraph2:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            nonlocal received_payload
            received_payload = dict(payload)
            state = dict(payload)
            state["status"] = "done"
            state["result_payload"] = {"final_image_path": "/fake/path2.png", "final_brief": {"user_input": state["user_input"]}}
            state["final_image_path"] = "/fake/path2.png"
            return state
            
    monkeypatch.setattr("orchestrator.app.graph.builder.build_marketing_graph", lambda: MockGraph2())
    
    req2 = GenerationJobCreateRequest(
        user_input="turn 2 prompt",
        run_mode="graph_immediate",
        thread_id=job1.thread_id,
        user_id=job1.user_id,
        copy_generation_mode="custom_input",
    )
    job2 = create_generation_job(req2)
    executed2 = execute_generation_job_graph(job2.job_id, req2)
    
    assert executed2.status == "done"
    assert received_payload["user_input"] == "turn 2 prompt"
    assert received_payload["copy_generation_mode"] == "custom_input"
    assert received_payload["job_id"] == job2.job_id
    assert received_payload["thread_id"] == job1.thread_id

def test_execute_generation_job_graph_waiting_user_input(monkeypatch):
    class MockGraphWaiting:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            state = dict(payload)
            state["__interrupt__"] = True
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

def test_execute_generation_job_graph_waiting_and_resume(monkeypatch):
    class MockGraphWaiting:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            state = dict(payload)
            state["__interrupt__"] = True
            state["status"] = "waiting_user_input"
            state["messages"] = [{"role": "assistant", "content": "Please provide more details."}]
            state["business_type"] = "cafe" # Ensure context is kept
            return state

    monkeypatch.setattr("orchestrator.app.graph.builder.build_marketing_graph", lambda: MockGraphWaiting())
    
    req1 = GenerationJobCreateRequest(
        user_input="start cafe ad",
        run_mode="graph_immediate",
    )
    job1 = create_generation_job(req1)
    executed1 = execute_generation_job_graph(job1.job_id, req1)
    
    assert executed1.status == "waiting_user_input"
    
    from orchestrator.app.chat_threads.service import get_chat_thread
    thread = get_chat_thread(job1.thread_id, job1.user_id)
    assert thread.active_job_id is None
    
    # 5. 동일 thread로 두 번째 GenerationJob 생성 성공
    req2 = GenerationJobCreateRequest(
        user_input="resume with more details",
        run_mode="graph_immediate",
        thread_id=job1.thread_id,
        user_id=job1.user_id,
    )
    job2 = create_generation_job(req2)
    assert job2.job_id != job1.job_id
    
    # Check input snapshot
    from orchestrator.app.chat_threads.state_service import get_latest_thread_state_for_user
    snap = get_latest_thread_state_for_user(job1.thread_id, job1.user_id)
    assert snap.snapshot_kind == "restored_input"
    assert snap.state_payload["business_type"] == "cafe"
    assert snap.state_payload["user_input"] == "resume with more details"
