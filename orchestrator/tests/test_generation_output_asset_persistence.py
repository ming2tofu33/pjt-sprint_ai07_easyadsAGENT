from contextlib import contextmanager

from orchestrator.app.generation_jobs import service


@contextmanager
def fake_db_transaction():
    yield object()


def test_mark_done_creates_local_dev_asset_and_generation_output(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction)
    events = []
    assets = []
    outputs = []
    row = {
        "id": "job_uuid",
        "public_job_id": "job_db",
        "workspace_id": "workspace_uuid",
        "thread_id": "thread_uuid",
        "requested_by": "demo_user",
        "status": "queued",
        "current_stage": "queued",
        "progress_percent": 0,
        "selected_reference_template_id": None,
        "output_path": None,
        "result_payload": None,
        "error": {},
        "metadata": {"public_thread_id": "thread_db"},
        "created_at": "2026-06-02T00:00:00+00:00",
        "updated_at": "2026-06-02T00:00:00+00:00",
    }

    def mark_done(job_id, result_payload, output_path=None, metadata=None, connection=None):
        row.update(
            {
                "status": "done",
                "current_stage": "completed",
                "progress_percent": 100,
                "result_payload": result_payload,
                "output_path": output_path,
                "error": {},
                "metadata": metadata or row["metadata"],
            }
        )
        return row

    monkeypatch.setattr(service.generation_job_repo, "get_generation_job_row", lambda job_id, connection=None: row)
    monkeypatch.setattr(service.generation_job_repo, "mark_generation_job_done_row", mark_done)
    monkeypatch.setattr(service.asset_repo, "create_asset", lambda **kwargs: assets.append({"id": "asset_uuid", **kwargs}) or assets[-1])
    monkeypatch.setattr(
        service.generation_output_repo,
        "create_generation_output",
        lambda **kwargs: outputs.append({"id": "output_uuid", "asset_id": kwargs["asset_id"], **kwargs}) or outputs[-1],
    )
    marked_final = []

    monkeypatch.setattr(
        service.generation_output_repo,
        "mark_output_final",
        lambda output_id, connection=None: marked_final.append(output_id) or {
            "id": output_id,
            "asset_id": "asset_uuid",
            "is_final": True,
        },
    )
    monkeypatch.setattr(service.chat_thread_repo, "update_chat_thread_status", lambda *args, **kwargs: {"id": "thread_uuid"})
    monkeypatch.setattr(service.generation_job_event_repo, "record_generation_job_event", lambda **kwargs: events.append(kwargs) or {"id": "event_uuid"})

    done = service.mark_generation_job_done(
        "job_db",
        result_payload={
            "schema_version": "result_artifact_v1",
            "final_image_path": "data/outputs/job_db/final_0.png",
            "final_image_url": None,
            "download_url": None,
        },
        output_path="data/outputs/job_db/final_0.png",
    )

    assert done.status == "done"
    assert assets[0]["storage_provider"] == "local_dev"
    assert assets[0]["bucket"] == "local-dev"
    assert assets[0]["object_key"] == "data/outputs/job_db/final_0.png"
    assert assets[0]["metadata"]["public_serving"] is False
    assert outputs[0]["asset_id"] == "asset_uuid"
    assert outputs[0]["is_final"] is False
    assert marked_final == ["output_uuid"]
    assert outputs[0]["variant_index"] == 0
    assert [event["event_type"] for event in events] == ["done", "output_created"]
    assert done.result_payload["final_image_url"] is None
    assert done.result_payload["download_url"] is None


def test_mark_done_without_final_path_still_completes_thread(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction)

    events = []
    thread_updates = []
    row = {
        "id": "job_uuid",
        "public_job_id": "job_db",
        "workspace_id": "workspace_uuid",
        "thread_id": "thread_uuid",
        "requested_by": "demo_user",
        "status": "queued",
        "current_stage": "queued",
        "progress_percent": 0,
        "selected_reference_template_id": None,
        "output_path": None,
        "result_payload": None,
        "error": {},
        "metadata": {"public_thread_id": "thread_db"},
        "created_at": "2026-06-02T00:00:00+00:00",
        "updated_at": "2026-06-02T00:00:00+00:00",
    }

    def mark_done(job_id, result_payload, output_path=None, metadata=None, connection=None):
        row.update(
            {
                "status": "done",
                "current_stage": "completed",
                "progress_percent": 100,
                "result_payload": result_payload,
                "output_path": output_path,
                "error": {},
                "metadata": metadata or row["metadata"],
            }
        )
        return row

    monkeypatch.setattr(service.generation_job_repo, "get_generation_job_row", lambda job_id, connection=None: row)
    monkeypatch.setattr(service.generation_job_repo, "mark_generation_job_done_row", mark_done)
    monkeypatch.setattr(service.asset_repo, "create_asset", lambda **kwargs: (_ for _ in ()).throw(AssertionError("asset should not be created")))
    monkeypatch.setattr(service.generation_output_repo, "create_generation_output", lambda **kwargs: (_ for _ in ()).throw(AssertionError("output should not be created")))
    monkeypatch.setattr(service.chat_thread_repo, "update_chat_thread_status", lambda *args, **kwargs: thread_updates.append((args, kwargs)) or {"id": "thread_uuid"})
    monkeypatch.setattr(service.generation_job_event_repo, "record_generation_job_event", lambda **kwargs: events.append(kwargs) or {"id": "event_uuid"})

    done = service.mark_generation_job_done(
        "job_db",
        result_payload={
            "schema_version": "result_artifact_v1",
            "final_image_url": None,
            "download_url": None,
        },
        output_path=None,
    )

    assert done.status == "done"
    assert [event["event_type"] for event in events] == ["done"]
    assert thread_updates[0][1]["status"] == "completed"
    assert thread_updates[0][1]["active_job_id"] is None
    assert thread_updates[0][1]["final_output_id"] is None