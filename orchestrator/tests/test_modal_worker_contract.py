import base64

from modal_apps.easyads_t2i_worker import (
    _flux2_klein_generation_options,
    _is_real_flux2_klein_request,
    _is_real_sd35_request,
    _render_mock_png_base64,
    _sd35_generation_options,
    generate_flux2_klein_image,
    generate_image,
    generate_sd35_large_image,
)


def test_modal_worker_mock_image_is_png():
    image_b64 = _render_mock_png_base64(
        {
            "job_id": "job_modal",
            "engine": "flux",
            "prompt": "premium cafe ad",
            "width": 512,
            "height": 512,
        }
    )

    assert base64.b64decode(image_b64).startswith(b"\x89PNG")


def test_modal_worker_function_contract_can_run_locally():
    result = generate_image.local(
        {
            "job_id": "job_modal",
            "engine": "flux",
            "prompt": "premium cafe ad",
            "width": 512,
            "height": 512,
        }
    )

    assert result["status"] == "succeeded"
    assert result["mime_type"] == "image/png"
    assert base64.b64decode(result["image_b64"]).startswith(b"\x89PNG")
    assert result["result_payload"]["schema_version"] == "result_artifact_v1"
    assert result["result_payload"]["render_mode"] == "modal_mock_worker"
    assert result["usage"]["gpu_seconds"] == 0


def test_modal_worker_mock_function_rejects_real_model_modes():
    result = generate_image.local(
        {
            "job_id": "job_modal",
            "engine": "flux2_klein_4b",
            "run_mode": "flux2_klein_4b",
            "prompt": "premium cafe ad",
        }
    )

    assert result["status"] == "failed"
    assert result["error"]["error_code"] == "modal_function_mismatch"
    assert "model-specific Modal function" in result["error"]["message"]

    sd35_result = generate_image.local(
        {
            "job_id": "job_modal",
            "engine": "sd35_large",
            "run_mode": "sd35_large_real",
            "prompt": "premium cafe ad",
        }
    )

    assert sd35_result["status"] == "failed"
    assert sd35_result["error"]["error_code"] == "modal_function_mismatch"


def test_modal_worker_real_flux2_klein_function_rejects_smoke_mode_without_loading_model():
    result = generate_flux2_klein_image.local(
        {
            "job_id": "job_modal",
            "engine": "flux2_klein_4b",
            "run_mode": "flux_local_smoke",
            "prompt": "premium cafe ad",
        }
    )

    assert result["status"] == "failed"
    assert result["error"]["error_code"] == "modal_real_flux2_klein_run_mode_required"


def test_modal_worker_real_sd35_function_rejects_smoke_mode_without_loading_model():
    result = generate_sd35_large_image.local(
        {
            "job_id": "job_modal",
            "engine": "sd35_large",
            "run_mode": "sd35_local_smoke",
            "prompt": "premium cafe ad",
        }
    )

    assert result["status"] == "failed"
    assert result["error"]["error_code"] == "modal_real_sd35_run_mode_required"


def test_modal_worker_real_flux2_klein_request_detection():
    assert _is_real_flux2_klein_request({"run_mode": "flux2_klein_4b"}) is True
    assert _is_real_flux2_klein_request({"run_mode": "flux_schnell_real"}) is True
    assert _is_real_flux2_klein_request({"run_mode": "flux_local_smoke"}) is False
    assert _is_real_flux2_klein_request({"params": {"render_mode": "flux2_klein_4b"}}) is True
    assert _is_real_flux2_klein_request({"params": {"render_mode": "flux_schnell"}}) is True


def test_modal_worker_real_sd35_request_detection():
    assert _is_real_sd35_request({"run_mode": "sd35_large_real"}) is True
    assert _is_real_sd35_request({"run_mode": "sd35_local_smoke"}) is False
    assert _is_real_sd35_request({"params": {"render_mode": "sd35_large"}}) is True


def test_modal_worker_flux2_klein_options_are_bounded_and_snapped():
    options = _flux2_klein_generation_options(
        {
            "width": 333,
            "height": 4097,
            "seed": "123",
            "params": {
                "num_inference_steps": 50,
                "guidance_scale": 99.0,
                "max_sequence_length": 999,
            },
        }
    )

    assert options == {
        "width": 320,
        "height": 1024,
        "num_inference_steps": 28,
        "guidance_scale": 20.0,
        "seed": 123,
    }


def test_modal_worker_sd35_options_are_bounded_and_snapped():
    options = _sd35_generation_options(
        {
            "width": 333,
            "height": 4097,
            "seed": "456",
            "params": {
                "num_inference_steps": 50,
                "guidance_scale": 99.0,
            },
        }
    )

    assert options == {
        "width": 512,
        "height": 1024,
        "num_inference_steps": 28,
        "guidance_scale": 10.0,
        "seed": 456,
    }
