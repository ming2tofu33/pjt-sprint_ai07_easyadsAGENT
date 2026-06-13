from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock


DEFAULT_WORKSPACE_ID = "11111111-1111-1111-1111-111111111111"


@contextmanager
def fake_db_transaction():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    yield conn


def make_generation_job_row(
    *,
    public_job_id: str = "job_db",
    workspace_id: str = DEFAULT_WORKSPACE_ID,
    thread_id: str = "thread_uuid",
    requested_by: str = "demo_user",
    status: str = "queued",
    selected_reference_template_id: str | None = None,
    output_path: str | None = None,
    result_payload=None,
    error=None,
    metadata: dict | None = None,
):
    now = datetime.now(timezone.utc)
    return {
        "id": "job_uuid",
        "public_job_id": public_job_id,
        "workspace_id": workspace_id,
        "thread_id": thread_id,
        "requested_by": requested_by,
        "status": status,
        "current_stage": "completed" if status == "done" else status,
        "progress_percent": 100 if status == "done" else 0,
        "selected_reference_template_id": selected_reference_template_id,
        "output_path": output_path,
        "result_payload": result_payload,
        "error": error if error is not None else {},
        "created_at": now,
        "updated_at": now,
        "metadata": metadata or {},
    }
