from dataclasses import dataclass

from orchestrator.app.artifacts.schemas import ResultArtifactPayload
from orchestrator.app.artifacts.service import (
    merge_final_asset_into_result_payload,
    sanitize_result_artifact_payload_for_api,
)
from orchestrator.app.generation_jobs.service import _job_response_from_db_row


@dataclass(frozen=True)
class FakeUploadedAsset:
    bucket: str = "easyads-dev"
    object_key: str = "workspaces/workspace_uuid/threads/thread_db/jobs/job_db/final_0.png"
    storage_provider: str = "r2"
    mime_type: str = "image/png"
    size_bytes: int = 123
    public_url: str | None = None
    final_image_url: str = "https://signed.example/final_0.png"
    download_url: str = "https://signed.example/final_0.png"
    signed_url_expires_at: str = "2026-06-03T00:00:00+00:00"
    metadata: dict | None = None
    width: int = 1200
    height: int = 1200

    def __post_init__(self):
        if self.metadata is None:
            object.__setattr__(self, "metadata", {"public_serving": True, "url_mode": "signed"})

@dataclass(frozen=True)
class FakeUploadedAssetNoMetadata:
    bucket: str = "easyads-dev"
    object_key: str = "workspaces/workspace_uuid/threads/thread_db/jobs/job_db/final_0.png"
    storage_provider: str = "r2"
    mime_type: str = "image/png"
    size_bytes: int = 123
    public_url: str | None = None
    final_image_url: str = "https://signed.example/final_0.png"
    download_url: str = "https://signed.example/final_0.png"
    signed_url_expires_at: str = "2026-06-03T00:00:00+00:00"
    metadata: dict | None = None
    width: int = 1200
    height: int = 1200

def test_result_artifact_payload_accepts_storage_backed_fields():
    payload = ResultArtifactPayload(
        job_id="job_contract",
        final_asset_id="asset_uuid",
        storage_provider="r2",
        bucket="easyads-dev",
        object_key="workspaces/workspace_uuid/threads/thread_db/jobs/job_db/final_0.png",
        url_mode="signed",
        final_image_url="https://signed.example/final_0.png",
        download_url="https://signed.example/final_0.png",
        assets={
            "final": {
                "asset_id": "asset_uuid",
                "kind": "result",
                "storage_provider": "r2",
                "bucket": "easyads-dev",
                "object_key": "workspaces/workspace_uuid/threads/thread_db/jobs/job_db/final_0.png",
                "final_image_url": "https://signed.example/final_0.png",
            }
        },
    )

    data = payload.model_dump(mode="json")

    assert data["schema_version"] == "result_artifact_v1"
    assert data["final_asset_id"] == "asset_uuid"
    assert data["final_image_url"].startswith("https://")
    assert data["download_url"].startswith("https://")
    assert data["assets"]["final"]["storage_provider"] == "r2"


def test_merge_final_asset_into_result_payload_for_r2_success():
    uploaded = FakeUploadedAsset()
    asset_row = {
        "id": "asset_uuid",
        "kind": "result",
        "storage_provider": "r2",
        "bucket": uploaded.bucket,
        "object_key": uploaded.object_key,
        "mime_type": "image/png",
        "size_bytes": 123,
        "width": 1200,
        "height": 1200,
        "metadata": {"public_serving": True},
    }

    payload = merge_final_asset_into_result_payload(
        result_payload={"schema_version": "result_artifact_v1", "final_image_path": "data/outputs/job_db/final_0.png"},
        asset_row=asset_row,
        uploaded_asset=uploaded,
        storage_provider="r2",
    )

    assert payload["final_asset_id"] == "asset_uuid"
    assert payload["storage_provider"] == "r2"
    assert payload["bucket"] == "easyads-dev"
    assert payload["object_key"] == uploaded.object_key
    assert payload["url_mode"] == "signed"
    assert payload["final_image_url"].startswith("https://")
    assert payload["download_url"].startswith("https://")
    assert payload["assets"]["final"]["asset_id"] == "asset_uuid"
    assert payload["assets"]["final"]["storage_provider"] == "r2"
    assert payload["assets"]["final"]["public_serving"] is True

def test_merge_final_asset_handles_uploaded_asset_with_none_metadata():
    uploaded = FakeUploadedAssetNoMetadata()
    asset_row = {
        "id": "asset_uuid",
        "kind": "result",
        "storage_provider": "r2",
        "bucket": uploaded.bucket,
        "object_key": uploaded.object_key,
        "metadata": {"public_serving": True, "url_mode": "signed"},
    }

    payload = merge_final_asset_into_result_payload(
        result_payload={"schema_version": "result_artifact_v1", "final_image_path": "data/outputs/job_db/final_0.png"},
        asset_row=asset_row,
        uploaded_asset=uploaded,
        storage_provider="r2",
    )

    assert payload["final_asset_id"] == "asset_uuid"
    assert payload["url_mode"] == "signed"
    assert payload["assets"]["final"]["storage_provider"] == "r2"

def test_merge_final_asset_into_result_payload_for_local_dev_fallback():
    payload = merge_final_asset_into_result_payload(
        result_payload={
            "schema_version": "result_artifact_v1",
            "final_image_path": "data/outputs/job_db/final_0.png",
            "final_image_url": None,
            "download_url": None,
        },
        asset_row={
            "id": "asset_local_uuid",
            "kind": "result",
            "storage_provider": "local_dev",
            "bucket": "local-dev",
            "object_key": "data/outputs/job_db/final_0.png",
            "metadata": {"public_serving": False},
        },
        storage_provider="local_dev",
    )

    assert payload["final_asset_id"] == "asset_local_uuid"
    assert payload["storage_provider"] == "local_dev"
    assert payload["bucket"] == "local-dev"
    assert payload["object_key"] == "data/outputs/job_db/final_0.png"
    assert payload["final_image_url"] is None
    assert payload["download_url"] is None
    assert payload["assets"]["final"]["public_serving"] is False


def test_sanitize_result_artifact_payload_removes_absolute_paths_unsafe_urls_and_secrets():
    payload = {
        "schema_version": "result_artifact_v1",
        "final_image_path": r"C:\Users\UserK\Downloads\easyads-local\data\outputs\job_x\final_0.png",
        "download_path": "/mnt/data/final_0.png",
        "final_image_url": "file:///tmp/final_0.png",
        "download_url": "data:image/png;base64,abc",
        "preview_image_url": "javascript:alert(2)",
        "copy_visual_preview_url": "file:///tmp/copy_preview.png",
        "thumbnail_url": "data:image/png;base64,thumbnail",
        "metadata": {
            "api_key": "sk-should-not-leak",
            "r2_secret_key": "r2-secret-should-not-leak",
            "nested": {
                "nested_access_key_id": "access-key-should-not-leak",
                "r2_secret": "secret",
                "safe": "visible",
            },
        },
        "assets": {
            "final": {
                "object_key": "/home/user/final_0.png",
                "final_image_url": "javascript:alert(1)",
            }
        },
    }

    sanitized = sanitize_result_artifact_payload_for_api(payload)
    text = str(sanitized)

    assert "C:\\Users\\UserK" not in text
    assert "/mnt/data" not in text
    assert "file://" not in text
    assert "data:image" not in text
    assert "javascript:" not in text
    assert sanitized.get("preview_image_url") is None
    assert sanitized.get("copy_visual_preview_url") is None
    assert sanitized.get("thumbnail_url") is None
    assert "javascript:alert(2)" not in text
    assert "file:///tmp/copy_preview.png" not in text
    assert "data:image/png;base64,thumbnail" not in text
    assert "sk-should-not-leak" not in text
    assert "secret" not in text
    assert "r2-secret-should-not-leak" not in text
    assert "access-key-should-not-leak" not in text
    assert "r2_secret_key" not in text
    assert "nested_access_key_id" not in text
    assert sanitized["metadata"]["nested"]["safe"] == "visible"


def test_generation_job_response_sanitizes_db_result_payload():
    row = {
        "public_job_id": "job_db",
        "thread_id": "thread_uuid",
        "status": "done",
        "current_stage": "completed",
        "progress_percent": 100,
        "selected_reference_template_id": None,
        "output_path": "data/outputs/job_db/final_0.png",
        "result_payload": {
            "schema_version": "result_artifact_v1",
            "final_image_path": "/tmp/final_0.png",
            "final_image_url": "file:///tmp/final_0.png",
            "download_url": "https://cdn.example/final_0.png",
            "metadata": {"access_key": "leak"},
        },
        "error": {},
        "metadata": {"public_thread_id": "thread_db"},
        "created_at": "2026-06-03T00:00:00+00:00",
        "updated_at": "2026-06-03T00:00:00+00:00",
    }

    job = _job_response_from_db_row(row)

    assert job.result_payload["download_url"] == "https://cdn.example/final_0.png"
    assert job.result_payload.get("final_image_url") is None
    assert "access_key" not in str(job.result_payload)
    assert "/tmp/final_0.png" not in str(job.result_payload)


def test_generation_job_response_sanitizes_absolute_output_path():
    row = {
        "public_job_id": "job_db",
        "thread_id": "thread_uuid",
        "status": "done",
        "current_stage": "completed",
        "progress_percent": 100,
        "selected_reference_template_id": None,
        "output_path": r"C:\Users\UserK\Downloads\easyads-local\data\outputs\job_db\final_0.png",
        "result_payload": {
            "schema_version": "result_artifact_v1",
            "final_image_path": "data/outputs/job_db/final_0.png",
            "download_url": "https://cdn.example/final_0.png",
        },
        "error": {},
        "metadata": {"public_thread_id": "thread_db"},
        "created_at": "2026-06-03T00:00:00+00:00",
        "updated_at": "2026-06-03T00:00:00+00:00",
    }

    job = _job_response_from_db_row(row)

    assert job.output_path is None
    assert "C:\\Users\\UserK" not in str(job.model_dump(mode="json"))
    assert job.result_payload["download_url"] == "https://cdn.example/final_0.png"


def test_sanitize_result_artifact_payload_rejects_non_artifact_relative_paths():
    payload = {
        "schema_version": "result_artifact_v1",
        "final_image_path": "private/final_0.png",
        "download_path": "secrets/final_0.png",
        "metadata_path": "data/outputs/job_db/metadata.json",
        "object_key": "workspaces/workspace_uuid/threads/thread_db/jobs/job_db/final_0.png",
    }

    sanitized = sanitize_result_artifact_payload_for_api(payload)

    assert sanitized.get("final_image_path") is None
    assert sanitized.get("download_path") is None
    assert sanitized["metadata_path"] == "data/outputs/job_db/metadata.json"
    assert sanitized["object_key"] == "workspaces/workspace_uuid/threads/thread_db/jobs/job_db/final_0.png"

def test_sanitize_result_artifact_payload_rejects_object_key_traversal():
    payload = {
        "schema_version": "result_artifact_v1",
        "object_key": "../workspaces/workspace_uuid/final_0.png",
        "assets": {
            "final": {
                "object_key": "workspaces/../secrets/final_0.png",
            }
        },
    }

    sanitized = sanitize_result_artifact_payload_for_api(payload)

    assert sanitized.get("object_key") is None
    assert sanitized["assets"]["final"].get("object_key") is None