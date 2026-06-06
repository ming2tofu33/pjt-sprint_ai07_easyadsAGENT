import pytest

from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest
from orchestrator.app.generation_jobs.service import (
    create_generation_job,
    get_generation_job,
    reset_generation_job_store_for_tests,
)
from orchestrator.app.chat_threads.service import reset_chat_thread_store_for_tests
from orchestrator.app.chat_threads.state_service import (
    get_chat_state_snapshot_by_key,
    reset_chat_state_snapshot_store_for_tests,
)


@pytest.fixture(autouse=True)
def reset_store():
    reset_generation_job_store_for_tests()
    reset_chat_thread_store_for_tests()
    reset_chat_state_snapshot_store_for_tests()
    yield
    reset_generation_job_store_for_tests()
    reset_chat_thread_store_for_tests()
    reset_chat_state_snapshot_store_for_tests()


def test_create_generation_job_defaults_and_lookup():
    job = create_generation_job(
        GenerationJobCreateRequest(
            user_input="Create a cafe ad",
            user_id="user_1",
            brand_kit_id="bk_1",
            selected_reference_template_id="seed_cafe_strawberry_feed_001",
            copy_generation_mode="auto_pilot",
            user_plan="free",
        )
    )

    assert job.job_id.startswith("job_")
    assert job.thread_id and job.thread_id.startswith("thread_")
    assert job.status == "queued"
    assert job.progress.progress_percent == 0
    assert job.progress.current_stage == "queued"
    assert "briefing" in job.progress.stage_order
    assert job.selected_reference_template_id == "seed_cafe_strawberry_feed_001"
    assert job.metadata["requested_run_mode"] == "queued_only"
    assert job.metadata["effective_run_mode"] == "queued_only"
    assert job.metadata["execution_mode"] == "queued_only"
    assert get_generation_job(job.job_id) == job


def test_create_generation_job_queued_only_metadata():
    job = create_generation_job(
        GenerationJobCreateRequest(
            user_input="Create an ad",
            run_mode="queued_only",
        )
    )

    assert job.status == "queued"
    assert job.metadata["requested_run_mode"] == "queued_only"
    assert job.metadata["effective_run_mode"] == "queued_only"
    assert job.metadata["execution_mode"] == "queued_only"


def test_create_generation_job_mock_immediate_pending_metadata():
    job = create_generation_job(
        GenerationJobCreateRequest(
            user_input="Create an ad",
            run_mode="mock_immediate",
        )
    )

    assert job.status == "queued"
    assert job.metadata["requested_run_mode"] == "mock_immediate"
    assert job.metadata["effective_run_mode"] == "mock_immediate"
    assert job.metadata["execution_mode"] == "pending_deterministic_mock"
    assert job.output_path is None
    assert job.result_payload is None


def test_create_generation_job_graph_immediate_degrades_metadata():
    job = create_generation_job(
        GenerationJobCreateRequest(
            user_input="Create an ad",
            run_mode="graph_immediate",
        )
    )

    assert job.status == "queued"
    assert job.metadata["requested_run_mode"] == "graph_immediate"
    assert job.metadata["effective_run_mode"] == "graph_immediate"
    assert job.metadata["execution_mode"] == "pending_graph_execution"
    assert job.output_path is None
    assert job.result_payload is None


def test_graph_immediate_snapshot_preserves_selected_engine():
    request = GenerationJobCreateRequest(
        user_input="카페 신메뉴 광고 만들어줘",
        run_mode="graph_immediate",
        metadata={
            "selected_engine": "flux_schnell",
            "requested_engine": "flux",
            "t2i_engine": "flux",
        },
    )

    job = create_generation_job(request)
    snapshot = get_chat_state_snapshot_by_key(
        snapshot_key=f"{job.job_id}:input",
        public_thread_id=job.thread_id,
        workspace_id="mem_workspace",
        user_id=job.user_id,
    )

    assert snapshot is not None
    assert job.metadata["engine_preference"] == "flux"
    assert job.metadata["t2i_engine"] == "flux"
    assert snapshot.state_payload["engine"] == "flux"
    assert snapshot.state_payload["current_brief"]["requested_engine"] == "flux"


def test_get_missing_generation_job_returns_none_and_reset_clears_store():
    job = create_generation_job(GenerationJobCreateRequest(user_input="Create an ad"))
    assert get_generation_job("job_missing") is None

    reset_generation_job_store_for_tests()
    assert get_generation_job(job.job_id) is None
