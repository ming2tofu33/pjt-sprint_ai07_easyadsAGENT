"""Tests for execute_generation_job_graph and state restoration."""

from contextlib import contextmanager

import pytest
from orchestrator.app.api.schemas.generation_jobs import (
    GenerationJobAnswerRequest,
    GenerationJobCreateRequest,
    GenerationJobResponse,
    GenerationProgress,
)
from orchestrator.app.generation_jobs.service import create_generation_job, reset_generation_job_store_for_tests
from orchestrator.app.chat_threads.service import list_chat_messages, reset_chat_thread_store_for_tests
from orchestrator.app.schemas.chat_state_snapshots import ChatStateSnapshotResponse
from orchestrator.app.generation_jobs.execution import (
    execute_generation_job_graph,
    poll_and_process_graph_modal_generation_job,
    resume_generation_job_graph,
)
from orchestrator.app.generation_jobs import execution

@pytest.fixture(autouse=True)
def reset_stores():
    reset_generation_job_store_for_tests()
    reset_chat_thread_store_for_tests()
    from orchestrator.app.chat_threads.state_service import _SNAPSHOTS_MEM_LOCK, _SNAPSHOTS_MEM
    with _SNAPSHOTS_MEM_LOCK:
        _SNAPSHOTS_MEM.clear()
    yield


class FakeInterrupt:
    def __init__(self, value):
        self.value = value


@contextmanager
def fake_db_transaction(connection=None):
    yield object()


def _graph_job_response(**overrides):
    payload = {
        "job_id": "job_graph_db",
        "thread_id": "thread_graph_db",
        "user_id": None,
        "brand_kit_id": None,
        "status": "queued",
        "progress": GenerationProgress(progress_percent=0, current_stage="queued"),
        "selected_reference_template_id": None,
        "output_path": None,
        "result_payload": {},
        "error": None,
        "created_at": "2026-06-06T00:00:00+00:00",
        "updated_at": "2026-06-06T00:00:00+00:00",
        "metadata": {},
    }
    payload.update(overrides)
    return GenerationJobResponse(**payload)


def test_execute_generation_job_graph_uses_job_workspace_for_input_snapshot(monkeypatch):
    captured = {}

    class MockGraph:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            state = dict(payload)
            state["status"] = "done"
            state["result_payload"] = {"final_image_path": "/fake/db-workspace.png"}
            state["final_image_path"] = "/fake/db-workspace.png"
            return state

    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr("orchestrator.app.db.session.db_transaction", fake_db_transaction)
    monkeypatch.setattr(execution, "get_generation_job", lambda job_id: _graph_job_response(job_id=job_id))
    monkeypatch.setattr(execution, "mark_generation_job_running", lambda *args, **kwargs: None)
    monkeypatch.setattr(execution, "mark_generation_job_done", lambda job_id, **kwargs: _graph_job_response(job_id=job_id, status="done"))
    monkeypatch.setattr("orchestrator.app.db.repositories.generation_jobs.get_generation_job_row", lambda *args, **kwargs: {
        "id": "internal_job_uuid",
        "public_job_id": "job_graph_db",
        "workspace_id": "workspace_from_job_row",
    })
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: MockGraph())

    def get_snapshot(**kwargs):
        captured.update(kwargs)
        return ChatStateSnapshotResponse(
            snapshot_id="snapshot_input",
            thread_id="thread_graph_db",
            job_id="job_graph_db",
            snapshot_version=1,
            schema_version=1,
            snapshot_kind="input",
            state_payload={"user_input": "카페 광고"},
            changed_fields=["user_input"],
            created_at="2026-06-06T00:00:00+00:00",
        )

    monkeypatch.setattr("orchestrator.app.chat_threads.state_service.get_chat_state_snapshot_by_key", get_snapshot)
    monkeypatch.setattr("orchestrator.app.chat_threads.state_service.save_thread_state_snapshot", lambda **kwargs: None)

    request = GenerationJobCreateRequest(userInput="카페 광고", runMode="graph_job")
    result = execute_generation_job_graph("job_graph_db", request)

    assert result.status == "done"
    assert captured["workspace_id"] == "workspace_from_job_row"
    assert captured["snapshot_key"] == "job_graph_db:input"


def test_execute_generation_job_graph_state_restoration(monkeypatch):
    class MockGraph:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            state = dict(payload)
            state["status"] = "done"
            state["result_payload"] = {"final_image_path": "/fake/path.png", "final_brief": {"user_input": state["user_input"]}}
            state["final_image_path"] = "/fake/path.png"
            return state

    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: MockGraph())
    
    req1 = GenerationJobCreateRequest(
        user_input="turn 1 prompt",
        run_mode="graph_job",
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
            
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: MockGraph2())
    
    req2 = GenerationJobCreateRequest(
        user_input="turn 2 prompt",
        run_mode="graph_job",
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


def test_execute_generation_job_graph_receives_selected_engine(monkeypatch):
    received_payload = {}

    class MockGraph:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            nonlocal received_payload
            received_payload = dict(payload)
            state = dict(payload)
            state["status"] = "done"
            state["result_payload"] = {
                "final_image_path": "/fake/graph-engine.png",
                "final_brief": {"user_input": state["user_input"]},
            }
            state["final_image_path"] = "/fake/graph-engine.png"
            return state

    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: MockGraph())

    request = GenerationJobCreateRequest(
        user_input="정교한 베이커리 광고 만들어줘",
        run_mode="graph_job",
        metadata={
            "selected_engine": "sd35_large",
            "requested_engine": "sd35_large",
            "t2i_engine": "sd35_large",
        },
    )
    job = create_generation_job(request)

    executed = execute_generation_job_graph(job.job_id, request)

    assert executed.status == "done"
    assert received_payload["engine"] == "sd35_large"
    assert received_payload["current_brief"]["requested_engine"] == "sd35_large"


def test_execute_generation_job_graph_persists_modal_pending_state(monkeypatch, tmp_path):
    class MockGraph:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            state = dict(payload)
            state.update(
                {
                    "status": "modal_running",
                    "copy_generation_mode": "no_copy",
                    "copy_required": False,
                    "text_overlay_pending": False,
                    "copy_spec": {"schema_version": "1.0", "copy_mode": "no_copy", "items": []},
                    "text_layout_spec": {
                        "schema_version": "1.0",
                        "template": "no_text",
                        "canvas_width": 2,
                        "canvas_height": 2,
                        "slots": [],
                        "reserved_text_areas": [],
                    },
                    "t2i_request": {
                        "prompt": "clean cafe poster background",
                        "negative_prompt": "",
                        "width": 2,
                        "height": 2,
                        "num_images": 1,
                        "output_dir": str(tmp_path / "job-modal-pending"),
                        "metadata": {"requested_engine": "flux"},
                    },
                    "t2i_result": {
                        "engine": "flux",
                        "image_paths": [],
                        "seed": None,
                        "latency_ms": 12,
                        "width": 2,
                        "height": 2,
                        "prompt": "clean cafe poster background",
                        "negative_prompt": "",
                        "metadata": {
                            "execution_backend": "modal",
                            "modal_call_id_present": True,
                            "modal_call_id": "modal_call_graph_1",
                            "requested_engine": "flux",
                        },
                        "error": None,
                    },
                }
            )
            return state

    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: MockGraph())

    request = GenerationJobCreateRequest(user_input="카페 광고", run_mode="graph_job")
    job = create_generation_job(request)
    executed = execute_generation_job_graph(job.job_id, request)

    assert executed.status == "running"
    assert executed.progress.current_stage == "modal_running"
    assert executed.metadata["graph_modal_pending"] is True
    assert executed.metadata["modal_call_id"] == "modal_call_graph_1"

    from orchestrator.app.chat_threads.state_service import get_chat_state_snapshot_by_key

    snapshot = get_chat_state_snapshot_by_key(
        snapshot_key=f"{job.job_id}:graph_modal_pending",
        public_thread_id=job.thread_id,
        workspace_id="mem_workspace",
        user_id=job.user_id,
    )
    assert snapshot is not None
    assert snapshot.state_payload["t2i_request"]["output_dir"] == str(tmp_path / "job-modal-pending")
    assert snapshot.state_payload["t2i_result"]["metadata"]["modal_call_id"] == "modal_call_graph_1"


def test_graph_modal_poll_completion_runs_post_t2i_nodes(monkeypatch, tmp_path):
    class MockGraph:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            state = dict(payload)
            state.update(
                {
                    "status": "modal_running",
                    "copy_generation_mode": "no_copy",
                    "copy_required": False,
                    "text_overlay_pending": False,
                    "copy_spec": {"schema_version": "1.0", "copy_mode": "no_copy", "items": []},
                    "text_layout_spec": {
                        "schema_version": "1.0",
                        "template": "no_text",
                        "canvas_width": 2,
                        "canvas_height": 2,
                        "slots": [],
                        "reserved_text_areas": [],
                    },
                    "t2i_request": {
                        "prompt": "clean cafe poster background",
                        "negative_prompt": "",
                        "width": 2,
                        "height": 2,
                        "num_images": 1,
                        "output_dir": str(tmp_path / "job-modal-complete"),
                        "metadata": {"requested_engine": "flux"},
                    },
                    "t2i_result": {
                        "engine": "flux",
                        "image_paths": [],
                        "seed": None,
                        "latency_ms": 12,
                        "width": 2,
                        "height": 2,
                        "prompt": "clean cafe poster background",
                        "negative_prompt": "",
                        "metadata": {
                            "execution_backend": "modal",
                            "modal_call_id_present": True,
                            "modal_call_id": "modal_call_graph_2",
                            "requested_engine": "flux",
                        },
                        "error": None,
                    },
                }
            )
            return state

    from orchestrator.app.modal.schemas import ModalPollResult

    png_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAEklEQVR42mP8z8AARLJgYGBgAAA2AQH/"
        "wH9tWQAAAABJRU5ErkJggg=="
    )
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: MockGraph())
    monkeypatch.setattr(
        "orchestrator.app.modal.client.poll_modal_t2i_result",
        lambda modal_call_id: ModalPollResult(
            status="succeeded",
            modal_call_id=modal_call_id,
            image_b64=png_b64,
            metadata={"modal_test": True},
        ),
    )

    request = GenerationJobCreateRequest(user_input="카페 광고", run_mode="graph_job")
    job = create_generation_job(request)
    pending = execute_generation_job_graph(job.job_id, request)
    assert pending.status == "running"

    completed = poll_and_process_graph_modal_generation_job(job.job_id)

    assert completed is not None
    assert completed.status == "done"
    assert completed.metadata["execution_mode"] == "graph_modal_completed"
    assert completed.result_payload["status"] == "done"
    assert completed.result_payload["output_path"].replace("\\", "/") == str(tmp_path / "job-modal-complete" / "final_0.png").replace("\\", "/")
    assert completed.result_payload["validation_summary"]["background"]["overall_pass"] is True


def test_execute_generation_job_graph_receives_source_image_path(monkeypatch):
    received_payload = {}

    class MockGraph:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            nonlocal received_payload
            received_payload = dict(payload)
            state = dict(payload)
            state["status"] = "done"
            state["result_payload"] = {
                "final_image_path": "/fake/photo-source.png",
                "final_brief": {"user_input": state["user_input"]},
            }
            state["final_image_path"] = "/fake/photo-source.png"
            return state

    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: MockGraph())

    request = GenerationJobCreateRequest(
        user_input="이 사진으로 신메뉴 광고 만들어줘",
        run_mode="graph_job",
        sourceImagePath="data/uploads/photo_1.png",
    )
    job = create_generation_job(request)

    executed = execute_generation_job_graph(job.job_id, request)

    assert executed.status == "done"
    assert received_payload["source_image_path"] == "data/uploads/photo_1.png"


def test_execute_generation_job_graph_receives_reference_image_path(monkeypatch):
    received_payload = {}

    class MockGraph:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            nonlocal received_payload
            received_payload = dict(payload)
            state = dict(payload)
            state["status"] = "done"
            state["result_payload"] = {
                "final_image_path": "/fake/reference-style.png",
                "final_brief": {"user_input": state["user_input"]},
            }
            state["final_image_path"] = "/fake/reference-style.png"
            return state

    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: MockGraph())

    request = GenerationJobCreateRequest(
        user_input="이 레퍼런스 분위기로 광고 만들어줘",
        run_mode="graph_job",
        referenceImagePath="data/uploads/reference_1.png",
    )
    job = create_generation_job(request)

    executed = execute_generation_job_graph(job.job_id, request)

    assert executed.status == "done"
    assert received_payload["reference_image_path"] == "data/uploads/reference_1.png"


def test_execute_generation_job_graph_receives_selected_ui_values(monkeypatch):
    received_payload = {}

    class MockGraph:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            nonlocal received_payload
            received_payload = dict(payload)
            state = dict(payload)
            state["status"] = "done"
            state["result_payload"] = {
                "final_image_path": "/fake/selected-ui-values.png",
                "final_brief": {"user_input": state["user_input"]},
            }
            state["final_image_path"] = "/fake/selected-ui-values.png"
            return state

    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: MockGraph())

    request = GenerationJobCreateRequest(
        user_input="선택값으로 광고 만들어줘",
        run_mode="graph_job",
        selectedCopyId="copy_2",
        selectedChannelId="instagram-story",
        selectedTone="상큼한",
        customDirection="제품을 화면 중앙에 크게",
        userCustomHeadline="오늘만 딸기라떼 반값",
        userCustomSubcopy="오후 2시부터 5시까지",
    )
    job = create_generation_job(request)

    executed = execute_generation_job_graph(job.job_id, request)

    assert executed.status == "done"
    assert received_payload["selected_copy_id"] == "copy_2"
    assert received_payload["selected_channel_id"] == "instagram-story"
    assert received_payload["selected_tone"] == "상큼한"
    assert received_payload["custom_direction"] == "제품을 화면 중앙에 크게"
    assert received_payload["user_custom_headline"] == "오늘만 딸기라떼 반값"
    assert received_payload["user_custom_subcopy"] == "오후 2시부터 5시까지"


def test_execute_generation_job_graph_waiting_user_input(monkeypatch):
    class MockGraphWaiting:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            state = dict(payload)
            state["__interrupt__"] = True
            state["status"] = "waiting_user_input"
            state["messages"] = [{"role": "assistant", "content": "Please answer this."}]
            return state

    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: MockGraphWaiting())
    
    req = GenerationJobCreateRequest(
        user_input="start",
        run_mode="graph_job",
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

    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: MockGraphWaiting())
    
    req1 = GenerationJobCreateRequest(
        user_input="start cafe ad",
        run_mode="graph_job",
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
        run_mode="graph_job",
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


def test_waiting_generation_job_exposes_pending_option_question(monkeypatch):
    class MockGraphWaiting:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            state = dict(payload)
            state["__interrupt__"] = [
                FakeInterrupt(
                    {
                        "type": "option_question",
                        "job_id": state["job_id"],
                        "thread_id": state["thread_id"],
                        "option_question": {
                            "field": "business_type",
                            "question": "어떤 업종의 광고인가요?",
                            "options": [
                                {"id": 1, "label": "카페", "value": "cafe"},
                                {"id": 2, "label": "직접 입력", "value": "custom"},
                            ],
                        },
                    }
                )
            ]
            state["status"] = "waiting_user_input"
            state["context"] = {"business_type": "beauty_nail"}
            state["missing_fields"] = ["item_or_service"]
            state["messages"] = []
            return state

    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: MockGraphWaiting())

    request = GenerationJobCreateRequest(user_input="광고 만들어줘", run_mode="graph_job")
    job = create_generation_job(request)
    executed = execute_generation_job_graph(job.job_id, request)

    assert executed.status == "waiting_user_input"
    assert executed.metadata["pending_interrupt"]["type"] == "option_question"
    assert executed.metadata["pending_interrupt"]["option_question"]["field"] == "business_type"
    assert executed.metadata["context"]["business_type"] == "beauty_nail"
    assert executed.metadata["missing_fields"] == ["item_or_service"]
    messages, _total = list_chat_messages(job.thread_id, user_id=job.user_id)
    assert messages[-1].content == "어떤 업종의 광고인가요?"


def test_resume_generation_job_graph_continues_waiting_job(monkeypatch):
    calls = []
    expected_job_id = None
    expected_thread_id = None

    class MockSharedGraph:
        def invoke(self, payload, config: dict | None = None) -> dict:
            nonlocal expected_job_id, expected_thread_id
            calls.append(payload)
            if len(calls) == 1:
                state = dict(payload)
                expected_job_id = state["job_id"]
                expected_thread_id = state["thread_id"]
                state["__interrupt__"] = [
                    FakeInterrupt(
                        {
                            "type": "option_question",
                            "job_id": state["job_id"],
                            "thread_id": state["thread_id"],
                            "option_question": {
                                "field": "business_type",
                                "question": "어떤 업종인가요?",
                                "options": [{"id": 1, "label": "카페", "value": "cafe"}],
                            },
                        }
                    )
                ]
                state["status"] = "waiting_user_input"
                state["messages"] = [{"role": "assistant", "content": "어떤 업종인가요?"}]
                return state

            assert getattr(payload, "resume", None) == {
                "job_id": expected_job_id,
                "thread_id": expected_thread_id,
                "field": "business_type",
                "value": "cafe",
                "display_text": "카페",
            }
            return {
                "job_id": expected_job_id,
                "thread_id": expected_thread_id,
                "status": "done",
                "result_payload": {"final_image_path": "/fake/final.png"},
                "final_image_path": "/fake/final.png",
            }

    shared_graph = MockSharedGraph()
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: shared_graph)

    request = GenerationJobCreateRequest(user_input="광고 만들어줘", run_mode="graph_job")
    job = create_generation_job(request)
    job = execute_generation_job_graph(job.job_id, request)
    assert job.status == "waiting_user_input"

    answer = GenerationJobAnswerRequest(field="business_type", value="cafe", display_text="카페")
    resumed = resume_generation_job_graph(job.job_id, answer)

    assert resumed.status == "done"
    assert len(calls) == 2
    messages, _total = list_chat_messages(job.thread_id)
    assert [message.content for message in messages if message.role in {"user", "assistant"}] == [
        "광고 만들어줘",
        "어떤 업종인가요?",
        "카페",
    ]
