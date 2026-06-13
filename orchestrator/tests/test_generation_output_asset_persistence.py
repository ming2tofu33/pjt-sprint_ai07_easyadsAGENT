from orchestrator.app.generation_jobs import service


from unittest.mock import MagicMock
from orchestrator.tests.factories.generation_jobs import fake_db_transaction, make_generation_job_row


def test_mark_done_creates_local_dev_asset_and_generation_output(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_ASSET_STORAGE_BACKEND", "local_dev")
    monkeypatch.setenv("EASYADS_ENABLE_R2_UPLOAD", "false")
    monkeypatch.setenv("EASYADS_R2_UPLOAD_REQUIRED", "false")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction)
    events = []
    assets = []
    outputs = []
    row = make_generation_job_row(
        public_job_id="job_db",
        workspace_id="workspace_uuid",
        selected_reference_template_id=None,
        metadata={"public_thread_id": "thread_db"},
    )

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
    monkeypatch.setattr(service.generation_job_repo, "update_generation_job_row", lambda job_id, connection=None, **fields: row.update(fields) or row)
    monkeypatch.setattr(service.asset_repo, "create_asset", lambda **kwargs: assets.append({"id": "asset_uuid", **kwargs}) or assets[-1])
    monkeypatch.setattr(
        service.generation_output_repo,
        "create_generation_output",
        lambda **kwargs: outputs.append({"id": "output_uuid", "asset_id": kwargs["asset_id"], **kwargs}) or outputs[-1],
    )
    monkeypatch.setattr("orchestrator.app.archive.service.sync_archive_for_output", MagicMock())
    marked_final = []

    monkeypatch.setattr(
        service.generation_output_repo,
        "mark_output_final",
        lambda output_id, *args, **kwargs: marked_final.append(output_id) or {
            "id": output_id,
            "asset_id": "asset_uuid",
            "is_final": True,
        },
    )
    monkeypatch.setattr(service.chat_thread_repo, "complete_chat_thread_generation", lambda **kwargs: {"id": "thread_uuid", **kwargs})
    monkeypatch.setattr(service.chat_message_repo, "append_chat_message", lambda **kwargs: {"id": "msg_uuid"})
    monkeypatch.setattr(service.state_service, "get_latest_thread_state_snapshot", lambda **kwargs: None)
    monkeypatch.setattr(service.state_service, "save_thread_state_snapshot", lambda **kwargs: {"snapshot_id": "snap_uuid"})
    monkeypatch.setattr(service.generation_job_event_repo, "record_generation_job_event", lambda **kwargs: events.append(kwargs) or {"id": "event_uuid"})
    monkeypatch.setattr(service.chat_thread_repo, "get_chat_thread_by_public_id", lambda thread_id, **kwargs: {"id": "thread_uuid", "active_job_id": "job_uuid"})
    monkeypatch.setattr(service.chat_message_repo, "append_generation_job_chat_event", lambda **kwargs: {"id": "msg_uuid"})

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
    assert outputs[0]["previous_output_id"] is None
    assert outputs[0]["is_final"] is False
    assert marked_final == ["output_uuid"]
    assert outputs[0]["variant_index"] == 0
    assert [event["event_type"] for event in events] == ["archive_linked", "done", "output_created"]
    assert done.result_payload["final_image_url"] is None
    assert done.result_payload["download_url"] is None


def test_mark_done_without_final_path_still_completes_thread(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction)

    events = []
    thread_updates = []
    row = make_generation_job_row(
        public_job_id="job_db",
        workspace_id="workspace_uuid",
        selected_reference_template_id=None,
        metadata={"public_thread_id": "thread_db"},
    )

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
    monkeypatch.setattr(service.generation_job_repo, "update_generation_job_row", lambda job_id, connection=None, **fields: row.update(fields) or row)
    monkeypatch.setattr(service.asset_repo, "create_asset", lambda **kwargs: (_ for _ in ()).throw(AssertionError("asset should not be created")))
    monkeypatch.setattr(service.generation_output_repo, "create_generation_output", lambda **kwargs: (_ for _ in ()).throw(AssertionError("output should not be created")))
    monkeypatch.setattr(service.chat_thread_repo, "complete_chat_thread_generation", lambda **kwargs: thread_updates.append(kwargs) or {"id": "thread_uuid"})
    monkeypatch.setattr(service.chat_message_repo, "append_chat_message", lambda **kwargs: {"id": "msg_uuid"})
    monkeypatch.setattr(service.state_service, "get_latest_thread_state_snapshot", lambda **kwargs: None)
    monkeypatch.setattr(service.state_service, "save_thread_state_snapshot", lambda **kwargs: {"snapshot_id": "snap_uuid"})
    monkeypatch.setattr(service.generation_job_event_repo, "record_generation_job_event", lambda **kwargs: events.append(kwargs) or {"id": "event_uuid"})
    monkeypatch.setattr(service.chat_thread_repo, "get_chat_thread_by_public_id", lambda thread_id, **kwargs: {"id": "thread_uuid", "active_job_id": "job_uuid"})
    monkeypatch.setattr(service.chat_message_repo, "append_generation_job_chat_event", lambda **kwargs: {"id": "msg_uuid"})

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
    assert thread_updates[0]["expected_active_job_id"] == "job_uuid"
    assert thread_updates[0]["final_output_id"] is None
