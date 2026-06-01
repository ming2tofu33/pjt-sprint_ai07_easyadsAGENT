from pathlib import Path

import pytest

from orchestrator.app.artifacts.schemas import ResultArtifactPayload
from orchestrator.app.artifacts.service import build_result_artifact_payload, get_job_output_dir, write_json_artifact


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
