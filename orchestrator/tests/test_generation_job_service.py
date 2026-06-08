from datetime import datetime, timedelta, timezone

import pytest

from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest, GenerationJobResponse, GenerationProgress
from orchestrator.app.generation_jobs.service import (
    create_generation_job,
    get_generation_job,
    mark_generation_job_running,
    maybe_mark_stale_generation_job_failed,
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


def test_create_generation_job_graph_job_degrades_metadata():
    job = create_generation_job(
        GenerationJobCreateRequest(
            user_input="Create an ad",
            run_mode="graph_job",
        )
    )

    assert job.status == "queued"
    assert job.metadata["requested_run_mode"] == "graph_job"
    assert job.metadata["effective_run_mode"] == "graph_job"
    assert job.metadata["execution_mode"] == "pending_graph_execution"
    assert job.output_path is None
    assert job.result_payload is None


def test_maybe_mark_stale_generation_job_failed_keeps_fresh_running_job():
    now = datetime(2026, 6, 8, 9, 0, tzinfo=timezone.utc)
    fresh_job = GenerationJobResponse(
        job_id="job_fresh",
        status="running",
        progress=GenerationProgress(progress_percent=50, current_stage="planning", stage_order=[]),
        created_at=(now - timedelta(minutes=1)).isoformat(),
        updated_at=(now - timedelta(minutes=1)).isoformat(),
        metadata={},
    )

    result = maybe_mark_stale_generation_job_failed(fresh_job, now=now, stale_after_seconds=900)

    assert result is fresh_job


def test_maybe_mark_stale_generation_job_failed_fails_old_running_job():
    now = datetime(2026, 6, 8, 9, 0, tzinfo=timezone.utc)
    job = create_generation_job(GenerationJobCreateRequest(user_input="햄버거 광고", run_mode="graph_job"))
    running = mark_generation_job_running(job.job_id, stage="planning")
    stale_running = running.model_copy(
        update={
            "updated_at": (now - timedelta(minutes=30)).isoformat(),
            "metadata": {**(running.metadata or {}), "execution_mode": "graph_execution"},
        }
    )

    result = maybe_mark_stale_generation_job_failed(stale_running, now=now, stale_after_seconds=900)

    assert result.status == "failed"
    assert result.progress.current_stage == "failed"
    assert result.error is not None
    assert result.error.error_code == "generation_job_stale_running"
    assert result.metadata["execution_mode"] == "stale_running_recovered"
    assert result.metadata["stale_running_stage"] == "planning"


def test_graph_job_snapshot_preserves_selected_engine():
    request = GenerationJobCreateRequest(
        user_input="카페 신메뉴 광고 만들어줘",
        run_mode="graph_job",
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
