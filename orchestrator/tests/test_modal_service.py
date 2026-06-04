import base64
from pathlib import Path

from orchestrator.app.modal import service as modal_service
from orchestrator.app.modal.errors import ModalResultError
from orchestrator.app.modal.schemas import ModalPollResult
from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest


def test_build_modal_t2i_request_from_generation_job_row():
    row = {
        "public_job_id": "job_modal",
        "workspace_id": "workspace_uuid",
        "thread_id": "thread_uuid",
        "run_mode": "flux_local",
        "engine": "flux",
        "prompt_preview": "Create a premium cafe ad",
        "selected_reference_template_id": "seed_ref",
        "metadata": {"public_thread_id": "thread_public"},
    }

    request = modal_service.build_modal_t2i_request_from_job(job_row=row)

    assert request.job_id == "job_modal"
    assert request.thread_id == "thread_public"
    assert request.workspace_id == "workspace_uuid"
    assert request.engine == "flux"
    assert request.num_images == 1
    assert request.metadata["selected_reference_template_id"] == "seed_ref"


def test_build_modal_t2i_request_for_flux_schnell_real_includes_generation_params():
    row = {
        "public_job_id": "job_modal",
        "workspace_id": "workspace_uuid",
        "thread_id": "thread_uuid",
        "run_mode": "flux_schnell_real",
        "engine": "flux",
        "prompt_preview": "Create a premium cafe ad",
        "metadata": {"public_thread_id": "thread_public"},
    }
    generation_request = GenerationJobCreateRequest(
        userInput="Create a premium cafe ad",
        runMode="flux_schnell_real",
        metadata={
            "width": 768,
            "height": 768,
            "seed": 42,
            "t2i_params": {
                "num_inference_steps": 6,
                "guidance_scale": 0.0,
                "max_sequence_length": 256,
                "ignored": "not-forwarded",
            },
        },
    )

    request = modal_service.build_modal_t2i_request_from_job(
        job_row=row,
        generation_request=generation_request,
    )

    assert request.run_mode == "flux_schnell_real"
    assert request.engine == "flux"
    assert request.width == 768
    assert request.height == 768
    assert request.seed == 42
    assert request.params["render_mode"] == "flux_schnell"
    assert request.params["num_inference_steps"] == 6
    assert request.params["guidance_scale"] == 0.0
    assert request.params["max_sequence_length"] == 256
    assert "ignored" not in request.params


def test_build_modal_t2i_request_for_sd35_large_real_includes_generation_params():
    row = {
        "public_job_id": "job_modal",
        "workspace_id": "workspace_uuid",
        "thread_id": "thread_uuid",
        "run_mode": "sd35_large_real",
        "engine": "sd35_large",
        "prompt_preview": "Create a premium cafe ad",
        "metadata": {"public_thread_id": "thread_public"},
    }
    generation_request = GenerationJobCreateRequest(
        userInput="Create a premium cafe ad",
        runMode="sd35_large_real",
        metadata={
            "width": 768,
            "height": 768,
            "seed": 24,
            "t2i_params": {
                "num_inference_steps": 10,
                "guidance_scale": 4.5,
                "ignored": "not-forwarded",
            },
        },
    )

    request = modal_service.build_modal_t2i_request_from_job(
        job_row=row,
        generation_request=generation_request,
    )

    assert request.run_mode == "sd35_large_real"
    assert request.engine == "sd35_large"
    assert request.width == 768
    assert request.height == 768
    assert request.seed == 24
    assert request.params["render_mode"] == "sd35_large"
    assert request.params["num_inference_steps"] == 10
    assert request.params["guidance_scale"] == 4.5
    assert "ignored" not in request.params


def test_write_modal_result_image_to_output_dir_writes_decoded_image(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    payload = base64.b64encode(b"fake-png-bytes").decode("ascii")
    result = ModalPollResult(status="succeeded", modal_call_id="modal_call_1", image_b64=payload)

    final_path = modal_service.write_modal_result_image_to_output_dir(job_id="job_modal", poll_result=result)

    assert final_path == "data/outputs/job_modal/final_0.png"
    assert Path(final_path).read_bytes() == b"fake-png-bytes"


def test_modal_result_image_does_not_write_base64_to_result_payload(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    poll_result = ModalPollResult(
        status="succeeded",
        modal_call_id="modal_call_1",
        image_b64=base64.b64encode(b"image").decode("ascii"),
        result_payload={"prompt_summary": {"engine": "flux"}},
    )

    final_path = modal_service.write_modal_result_image_to_output_dir(job_id="job_modal", poll_result=poll_result)
    result_payload = {
        **poll_result.result_payload,
        "final_image_path": final_path,
        "download_path": final_path,
    }

    assert "image_b64" not in result_payload
    assert "image_bytes" not in result_payload


def test_write_modal_result_image_ignores_modal_filename_and_uses_final_png(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    payload = base64.b64encode(b"fake-png-bytes").decode("ascii")
    result = ModalPollResult(
        status="succeeded",
        modal_call_id="modal_call_1",
        image_b64=payload,
        filename="../../bad-name.txt",
    )

    final_path = modal_service.write_modal_result_image_to_output_dir(job_id="job_modal", poll_result=result)

    assert final_path == "data/outputs/job_modal/final_0.png"
    assert Path(final_path).read_bytes() == b"fake-png-bytes"
    assert not Path("data/outputs/job_modal/bad-name.txt").exists()


def test_write_modal_result_image_rejects_invalid_base64(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    result = ModalPollResult(
        status="succeeded",
        modal_call_id="modal_call_1",
        image_b64="not-valid-base64",
    )

    try:
        modal_service.write_modal_result_image_to_output_dir(job_id="job_modal", poll_result=result)
    except ModalResultError as exc:
        assert "invalid image_b64" in str(exc)
    else:
        raise AssertionError("Expected ModalResultError")
