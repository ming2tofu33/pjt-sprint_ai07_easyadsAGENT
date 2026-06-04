from pathlib import Path

import pytest

from orchestrator.app.artifacts.schemas import ResultArtifactPayload
from orchestrator.app.artifacts.service import (
    build_result_artifact_payload,
    get_job_output_dir,
    merge_final_asset_into_result_payload,
    normalize_repo_relative_artifact_path,
    sanitize_result_artifact_payload_for_api,
    write_json_artifact,
)


def test_get_job_output_dir_and_path_safety():
    assert get_job_output_dir("job_x").as_posix() == "data/outputs/job_x"
    for job_id in ["bad", "job_../x", "job_x/y", "job_x\\y"]:
        with pytest.raises(ValueError):
            get_job_output_dir(job_id)


def test_result_artifact_payload_dump_and_urls_null(tmp_path):
    output_dir = Path("data/outputs/job_contract")
    payload = build_result_artifact_payload(
        job_id="job_contract",
        background_image_path=output_dir / "background_0.png",
        final_image_path=output_dir / "final_0.png",
        metadata_path=output_dir / "metadata.json",
        prompt_path=output_dir / "prompt.json",
        validation_path=output_dir / "validation.json",
        prompt_summary={"template": "mock"},
        validation_summary={"overall_pass": True},
    )

    data = payload.model_dump(mode="json")
    assert data["schema_version"] == "result_artifact_v1"
    assert data["download_url"] is None
    assert data["final_image_url"] is None
    assert "data/outputs/job_contract" in data["final_image_path"]
    assert ResultArtifactPayload(**data)
    assert payload.download_path == "data/outputs/job_contract/final_0.png"
    assert payload.download_url is None
    assert payload.final_image_url is None

    artifact = tmp_path / "artifact.json"
    write_json_artifact(artifact, data)
    assert artifact.exists()


def test_normalize_repo_relative_artifact_path_blocks_absolute_and_keeps_repo_relative():
    assert normalize_repo_relative_artifact_path("data/outputs/job_x/final_0.png") == "data/outputs/job_x/final_0.png"
    assert normalize_repo_relative_artifact_path("C:/Users/UserK/secrets.png") is None
    assert normalize_repo_relative_artifact_path("/tmp/test.png") is None


def test_sanitize_result_artifact_payload_for_api_removes_secrets_and_unsafe_values():
    payload = {
        "final_image_path": "data/outputs/job_x/final_0.png",
        "final_image_url": "https://cdn.example.com/final_0.png",
        "download_url": "file:///tmp/final_0.png",
        "unsafe_path": "C:/Users/UserK/secret.txt",
        "nested": {"api_key": "should-not-leak", "safe": True},
    }

    sanitized = sanitize_result_artifact_payload_for_api(payload)

    assert sanitized["final_image_path"] == "data/outputs/job_x/final_0.png"
    assert sanitized["final_image_url"] == "https://cdn.example.com/final_0.png"
    assert sanitized["download_url"] is None
    assert sanitized["unsafe_path"] is None
    assert "api_key" not in sanitized["nested"]


def test_merge_final_asset_into_result_payload_builds_nested_assets_final():
    payload = {"schema_version": "result_artifact_v1"}
    asset_row = {
        "id": "asset_uuid",
        "kind": "result",
        "bucket": "easyads-dev",
        "object_key": "workspaces/w/threads/t/jobs/j/final_0.png",
        "mime_type": "image/png",
        "size_bytes": 123,
        "width": 1024,
        "height": 1024,
        "public_url": None,
        "metadata": {"source": "generation_job_r2_upload"},
    }

    class Uploaded:
        storage_provider = "r2"
        final_image_url = "https://cdn.example.com/final_0.png"
        download_url = "https://cdn.example.com/final_0.png"
        signed_url_expires_at = "2026-06-04T00:00:00Z"
        metadata = {"url_mode": "signed"}

    merged = merge_final_asset_into_result_payload(
        result_payload=payload,
        asset_row=asset_row,
        uploaded_asset=Uploaded(),
        storage_provider="r2",
    )

    assert merged["final_asset_id"] == "asset_uuid"
    assert merged["assets"]["final"]["asset_id"] == "asset_uuid"
    assert merged["assets"]["final"]["storage_provider"] == "r2"
    assert merged["assets"]["final"]["url_mode"] == "signed"
