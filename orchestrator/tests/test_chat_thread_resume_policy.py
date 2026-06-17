from types import SimpleNamespace

from orchestrator.app.chat_threads.resume_policy import compute_thread_resume_state


def _snapshot(kind: str, snapshot_id: str = "snapshot_1"):
    return SimpleNamespace(snapshot_kind=kind, snapshot_id=snapshot_id, state_payload={})


def test_resume_state_views_final_output_even_when_legacy_waiting_job_exists():
    state = compute_thread_resume_state(
        thread={
            "public_thread_id": "thread_done",
            "status": "draft",
            "active_public_job_id": None,
            "final_public_job_id": "job_done",
            "final_public_output_id": "output_done",
        },
        latest_snapshot=_snapshot("waiting_user_input"),
        waiting_job={
            "public_job_id": "job_waiting",
            "metadata": {"assistant_message": "어떤 업종의 광고인가요?"},
        },
    )

    assert state.action == "view_result"
    assert state.final_output_id == "output_done"
    assert state.resume_job_id == "job_done"
    assert state.reason == "thread_has_final_output"


def test_resume_state_answers_explicit_continuation_waiting_job_over_final_output():
    state = compute_thread_resume_state(
        thread={
            "public_thread_id": "thread_editing",
            "status": "draft",
            "active_public_job_id": None,
            "final_public_job_id": "job_done",
            "final_public_output_id": "output_done",
        },
        latest_snapshot=_snapshot("waiting_user_input"),
        waiting_job={
            "public_job_id": "job_waiting",
            "metadata": {
                "continuation_mode": "new_turn",
                "pending_interrupt": {"field": "business_type", "question": "어떤 업종의 광고인가요?"},
            },
        },
    )

    assert state.action == "answer_pending_job"
    assert state.resume_job_id == "job_waiting"
    assert state.final_output_id == "output_done"
    assert state.current_question == {"field": "business_type", "question": "어떤 업종의 광고인가요?"}


def test_resume_state_locks_running_thread():
    state = compute_thread_resume_state(
        thread={
            "public_thread_id": "thread_running",
            "status": "generating",
            "active_public_job_id": "job_running",
            "final_public_output_id": None,
        },
        latest_snapshot=None,
        waiting_job=None,
    )

    assert state.action == "locked_running"
    assert state.resume_job_id == "job_running"
    assert state.reason == "thread_has_active_job"


def test_resume_state_answers_pending_thread_without_output():
    state = compute_thread_resume_state(
        thread={
            "public_thread_id": "thread_pending",
            "status": "draft",
            "active_public_job_id": None,
            "final_public_output_id": None,
        },
        latest_snapshot=_snapshot("waiting_user_input"),
        waiting_job={
            "public_job_id": "job_waiting",
            "metadata": {
                "pending_interrupt": {"field": "business_type"},
                "assistant_message": "어떤 업종의 광고인가요?",
            },
        },
    )

    assert state.action == "answer_pending_job"
    assert state.resume_job_id == "job_waiting"
    assert state.current_question == {"field": "business_type"}


def test_resume_state_retries_failed_thread_without_output():
    state = compute_thread_resume_state(
        thread={
            "public_thread_id": "thread_failed",
            "status": "failed",
            "active_public_job_id": None,
            "final_public_output_id": None,
        },
        latest_snapshot=_snapshot("job_failed", snapshot_id="snapshot_failed"),
        waiting_job=None,
    )

    assert state.action == "retry_failed_job"
    assert state.latest_snapshot_id == "snapshot_failed"
    assert state.reason == "latest_snapshot_failed"


def test_resume_state_continues_plain_draft():
    state = compute_thread_resume_state(
        thread={
            "public_thread_id": "thread_draft",
            "status": "draft",
            "active_public_job_id": None,
            "final_public_output_id": None,
        },
        latest_snapshot=_snapshot("input"),
        waiting_job=None,
    )

    assert state.action == "continue_draft"
    assert state.reason == "thread_is_draft"


def test_resume_state_does_not_expose_internal_active_job_id():
    state = compute_thread_resume_state(
        thread={
            "public_thread_id": "thread_internal_active",
            "status": "draft",
            "active_public_job_id": None,
            "active_job_id": "internal-active-job",
            "final_public_output_id": None,
        },
        latest_snapshot=_snapshot("input"),
        waiting_job=None,
    )

    assert state.action == "continue_draft"
    assert state.resume_job_id is None


def test_resume_state_does_not_answer_pending_job_from_internal_waiting_job_id():
    state = compute_thread_resume_state(
        thread={
            "public_thread_id": "thread_internal_waiting",
            "status": "draft",
            "active_public_job_id": None,
            "final_public_output_id": None,
        },
        latest_snapshot=_snapshot("waiting_user_input"),
        waiting_job={
            "public_job_id": None,
            "job_id": "internal-waiting-job",
            "metadata": {
                "pending_interrupt": {"field": "business_type"},
                "assistant_message": "어떤 업종의 광고인가요?",
            },
        },
    )

    assert state.action == "continue_draft"
    assert state.resume_job_id is None


def test_resume_state_does_not_expose_internal_final_output_id():
    state = compute_thread_resume_state(
        thread={
            "public_thread_id": "thread_internal_output",
            "status": "draft",
            "active_public_job_id": None,
            "final_public_output_id": None,
            "final_output_id": "internal-final-output",
        },
        latest_snapshot=_snapshot("input"),
        waiting_job=None,
    )

    assert state.action == "continue_draft"
    assert state.final_output_id is None


def test_resume_state_does_not_expose_internal_snapshot_id():
    state = compute_thread_resume_state(
        thread={
            "public_thread_id": "thread_internal_snapshot",
            "status": "draft",
            "active_public_job_id": None,
            "final_public_output_id": None,
        },
        latest_snapshot=_snapshot("input", snapshot_id="internal-snapshot"),
        waiting_job=None,
    )

    assert state.action == "continue_draft"
    assert state.latest_snapshot_id is None
