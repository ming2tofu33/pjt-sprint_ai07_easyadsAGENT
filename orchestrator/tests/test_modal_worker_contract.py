import base64

from modal_apps.easyads_t2i_worker import _render_mock_png_base64, generate_image


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
