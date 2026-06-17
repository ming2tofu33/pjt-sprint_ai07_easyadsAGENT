from types import SimpleNamespace

from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app
from orchestrator.app.chat_threads import service as chat_service


def test_thread_response_contains_resume_state_for_final_output(monkeypatch):
    monkeypatch.setattr(chat_service.db_settings, "get_db_backend", lambda: "postgres")
    monkeypatch.setattr(
        chat_service,
        "_ensure_workspace_for_user",
        lambda user_id, connection=None, account_type=None: {"id": "workspace_1"},
    )
    monkeypatch.setattr(
        chat_service.chat_thread_repo,
        "get_chat_thread_by_public_id",
        lambda *args, **kwargs: {
            "public_thread_id": "thread_done",
            "title": "프리미엄 뷰티살롱",
            "status": "draft",
            "brand_kit_id": None,
            "project_id": None,
            "final_brief": {},
            "active_public_job_id": None,
            "final_public_job_id": "job_done",
            "final_public_output_id": "output_done",
            "final_output_id": "internal-output-uuid",
            "last_message_at": "2026-06-17T03:37:45+00:00",
            "archived_at": None,
            "created_at": "2026-06-17T03:30:00+00:00",
            "updated_at": "2026-06-17T03:37:45+00:00",
        },
    )
    monkeypatch.setattr(
        chat_service.state_service,
        "get_latest_thread_state_snapshot",
        lambda *args, **kwargs: SimpleNamespace(
            snapshot_id="snapshot_waiting",
            snapshot_kind="waiting_user_input",
            state_payload={},
        ),
    )
    monkeypatch.setattr(
        chat_service.generation_job_repo,
        "get_latest_waiting_generation_job_for_thread",
        lambda *args, **kwargs: {
            "public_job_id": "job_waiting",
            "metadata": {"assistant_message": "어떤 업종의 광고인가요?"},
        },
    )

    thread = chat_service.get_chat_thread("thread_done", user_id="user_1")

    assert thread is not None
    assert thread.final_output_id == "output_done"
    assert thread.resume_state is not None
    assert thread.resume_state.action == "view_result"
    assert thread.resume_state.resume_job_id == "job_done"
    assert thread.resume_state.final_output_id == "output_done"


def test_resume_state_route_returns_pending_job(monkeypatch):
    app = create_app()
    client = TestClient(app)

    monkeypatch.setattr(
        chat_service,
        "get_chat_thread_resume_state",
        lambda thread_id, user_id=None, account_type=None: SimpleNamespace(
            action="answer_pending_job",
            thread_id=thread_id,
            resume_job_id="job_waiting",
            final_output_id=None,
            latest_snapshot_id="snapshot_waiting",
            snapshot_kind="waiting_user_input",
            reason="thread_has_waiting_job",
            current_question={"field": "business_type"},
        ),
    )

    response = client.get("/api/v1/chat-threads/thread_pending/resume-state")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["resume_state"]["action"] == "answer_pending_job"
    assert payload["resume_state"]["resume_job_id"] == "job_waiting"
    assert payload["resume_state"]["current_question"] == {"field": "business_type"}
