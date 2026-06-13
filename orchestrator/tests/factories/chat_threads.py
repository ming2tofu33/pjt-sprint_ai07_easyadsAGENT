from copy import deepcopy


def make_chat_thread_row(**overrides) -> dict[str, object]:
    row = {
        "id": "uuid-1",
        "public_thread_id": "thread_abc",
        "workspace_id": "ws-1",
        "title": "Test",
        "status": "draft",
        "brand_kit_id": None,
        "project_id": None,
        "final_brief": {},
        "active_job_id": None,
        "final_output_id": None,
        "last_message_at": "2026-01-01T00:00:00+00:00",
        "archived_at": None,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "total": 0,
    }
    row.update(overrides)
    return deepcopy(row)
