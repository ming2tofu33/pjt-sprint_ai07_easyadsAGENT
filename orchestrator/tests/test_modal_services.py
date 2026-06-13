"""Consolidated modal services tests.

Merged from:
- orchestrator/tests/test_modal_client.py
- orchestrator/tests/test_modal_service.py
- orchestrator/tests/test_modal_settings.py
- orchestrator/tests/test_modal_usage_tracking.py
- orchestrator/tests/test_modal_worker_contract.py
"""



# ===== from test_modal_client.py =====
import sys
import types

from orchestrator.app.modal import client as modal_client
from orchestrator.app.modal.schemas import ModalT2IRequest


def _request(run_mode: str = "flux_local", engine: str = "flux") -> ModalT2IRequest:
    return ModalT2IRequest(
        job_id="job_modal",
        workspace_id="workspace_uuid",
        run_mode=run_mode,
        engine=engine,
        prompt="premium advertising background",
    )


def test_submit_modal_t2i_job_lazy_imports_modal(monkeypatch):
    captured = {}
    modal_module = types.ModuleType("modal")

    class FakeCall:
        object_id = "modal_call_123"

    class FakeFunction:
        @classmethod
        def from_name(cls, app_name, function_name):
            captured["app_name"] = app_name
            captured["function_name"] = function_name
            return cls()

        def spawn(self, payload):
            captured["payload"] = payload
            return FakeCall()

    modal_module.Function = FakeFunction
    monkeypatch.setitem(sys.modules, "modal", modal_module)
    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "modal")
    monkeypatch.setenv("EASYADS_ENABLE_MODAL_EXECUTION", "true")
    monkeypatch.setenv("MODAL_TOKEN_ID", "token-id")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "token-secret")

    result = modal_client.submit_modal_t2i_job(_request())

    assert result.modal_call_id == "modal_call_123"
    assert captured["app_name"] == "easyads-t2i"
    assert captured["function_name"] == "generate_image"
    assert captured["payload"]["job_id"] == "job_modal"


def test_submit_modal_t2i_job_routes_real_model_functions(monkeypatch):
    captured = []
    modal_module = types.ModuleType("modal")

    class FakeCall:
        object_id = "modal_call_123"

    class FakeFunction:
        @classmethod
        def from_name(cls, app_name, function_name):
            captured.append((app_name, function_name))
            return cls()

        def spawn(self, payload):
            return FakeCall()

    modal_module.Function = FakeFunction
    monkeypatch.setitem(sys.modules, "modal", modal_module)
    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "modal")
    monkeypatch.setenv("EASYADS_ENABLE_MODAL_EXECUTION", "true")
    monkeypatch.setenv("MODAL_TOKEN_ID", "token-id")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "token-secret")

    modal_client.submit_modal_t2i_job(_request(run_mode="flux2_klein_4b", engine="flux2_klein_4b"))
    modal_client.submit_modal_t2i_job(_request(run_mode="sd35_large_real", engine="sd35_large"))

    assert captured == [
        ("easyads-t2i", "generate_flux2_klein_image"),
        ("easyads-t2i", "generate_sd35_large_image"),
    ]


def test_submit_modal_t2i_job_accepts_injected_fake_client(monkeypatch):
    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "modal")
    monkeypatch.setenv("EASYADS_ENABLE_MODAL_EXECUTION", "true")
    monkeypatch.setenv("MODAL_TOKEN_ID", "token-id")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "token-secret")

    class FakeClient:
        def submit(self, request):
            assert request.job_id == "job_modal"
            return modal_client.ModalSubmitResult(
                submitted=True,
                modal_call_id="modal_call_fake",
                status="submitted",
            )

    result = modal_client.submit_modal_t2i_job(_request(), client=FakeClient())

    assert result.modal_call_id == "modal_call_fake"


def test_submit_modal_t2i_job_includes_sanitized_exception_detail(monkeypatch):
    modal_module = types.ModuleType("modal")

    class FakeFunction:
        @classmethod
        def from_name(cls, app_name, function_name):
            raise RuntimeError("auth failed for token-secret")

    modal_module.Function = FakeFunction
    monkeypatch.setitem(sys.modules, "modal", modal_module)
    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "modal")
    monkeypatch.setenv("EASYADS_ENABLE_MODAL_EXECUTION", "true")
    monkeypatch.setenv("MODAL_TOKEN_ID", "token-id")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "token-secret")

    try:
        modal_client.submit_modal_t2i_job(_request())
    except modal_client.ModalJobSubmitError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected ModalJobSubmitError")

    assert "RuntimeError" in message
    assert "[REDACTED]" in message
    assert "token-secret" not in message


def test_poll_modal_t2i_result_uses_function_call_from_id(monkeypatch):
    captured = {}
    modal_module = types.ModuleType("modal")

    class FakeFunctionCall:
        @classmethod
        def from_id(cls, modal_call_id):
            captured["modal_call_id"] = modal_call_id
            return cls()

        def get(self, timeout=0):
            captured["timeout"] = timeout
            return {
                "status": "succeeded",
                "image_b64": "aW1hZ2U=",
                "result_payload": {"schema_version": "result_artifact_v1"},
            }

    modal_module.FunctionCall = FakeFunctionCall
    monkeypatch.setitem(sys.modules, "modal", modal_module)
    monkeypatch.setenv("EASYADS_MODAL_POLL_TIMEOUT_SECONDS", "0")

    result = modal_client.poll_modal_t2i_result("modal_call_123")

    assert result.status == "succeeded"
    assert result.modal_call_id == "modal_call_123"
    assert result.image_b64 == "aW1hZ2U="
    assert captured == {"modal_call_id": "modal_call_123", "timeout": 0}


def test_poll_modal_t2i_result_reports_running_on_timeout(monkeypatch):
    modal_module = types.ModuleType("modal")

    class FakeFunctionCall:
        @classmethod
        def from_id(cls, modal_call_id):
            return cls()

        def get(self, timeout=0):
            raise TimeoutError("not ready")

    modal_module.FunctionCall = FakeFunctionCall
    monkeypatch.setitem(sys.modules, "modal", modal_module)

    result = modal_client.poll_modal_t2i_result("modal_call_pending")

    assert result.status == "running"
    assert result.modal_call_id == "modal_call_pending"


# ===== from test_modal_service.py =====
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


def test_build_modal_t2i_request_for_flux2_klein_includes_generation_params():
    row = {
        "public_job_id": "job_modal",
        "workspace_id": "workspace_uuid",
        "thread_id": "thread_uuid",
        "run_mode": "flux2_klein_4b",
        "engine": "flux2_klein_4b",
        "prompt_preview": "Create a premium cafe ad",
        "metadata": {"public_thread_id": "thread_public"},
    }
    generation_request = GenerationJobCreateRequest(
        userInput="Create a premium cafe ad",
        runMode="flux2_klein_4b",
        metadata={
            "width": 768,
            "height": 768,
            "seed": 42,
            "t2i_params": {
                "num_inference_steps": 6,
                "guidance_scale": 1.0,
                "ignored": "not-forwarded",
            },
        },
    )

    request = modal_service.build_modal_t2i_request_from_job(
        job_row=row,
        generation_request=generation_request,
    )

    assert request.run_mode == "flux2_klein_4b"
    assert request.engine == "flux2_klein_4b"
    assert request.width == 768
    assert request.height == 768
    assert request.seed == 42
    assert request.params["render_mode"] == "flux2_klein_4b"
    assert request.params["num_inference_steps"] == 6
    assert request.params["guidance_scale"] == 1.0
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


# ===== from test_modal_settings.py =====
from orchestrator.app.modal import settings


def test_modal_execution_defaults_to_local_disabled(monkeypatch):
    monkeypatch.delenv("EASYADS_T2I_EXECUTION_BACKEND", raising=False)
    monkeypatch.delenv("EASYADS_ENABLE_MODAL_EXECUTION", raising=False)

    assert settings.get_t2i_execution_backend() == "local"
    assert settings.is_modal_execution_enabled() is False


def test_modal_execution_unknown_backend_falls_back_to_local(monkeypatch):
    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "modall")
    monkeypatch.setenv("EASYADS_ENABLE_MODAL_EXECUTION", "true")

    readiness = settings.get_modal_readiness()

    assert settings.get_t2i_execution_backend() == "local"
    assert settings.is_modal_execution_enabled() is False
    assert readiness["backend_valid"] is False


def test_modal_readiness_redacts_tokens(monkeypatch):
    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "modal")
    monkeypatch.setenv("EASYADS_ENABLE_MODAL_EXECUTION", "true")
    monkeypatch.setenv("MODAL_TOKEN_ID", "token-id-should-not-leak")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "secret-should-not-leak")

    readiness = settings.get_modal_readiness()
    rendered = str(readiness)

    assert readiness["enabled"] is True
    assert readiness["token_id_present"] is True
    assert readiness["token_secret_present"] is True
    assert "token-id-should-not-leak" not in rendered
    assert "secret-should-not-leak" not in rendered


def test_modal_result_transport_unknown_falls_back_to_inline_base64(monkeypatch):
    monkeypatch.setenv("EASYADS_MODAL_RESULT_TRANSPORT", "weird")

    assert settings.get_modal_result_transport() == "inline_base64"


def test_modal_function_name_routes_real_model_modes(monkeypatch):
    monkeypatch.setenv("EASYADS_MODAL_FUNCTION_NAME", "generate_image")

    assert settings.get_modal_function_name(run_mode="flux_local_smoke", engine="flux") == "generate_image"
    assert settings.get_modal_function_name(run_mode="flux_schnell_real", engine="flux") == "generate_flux2_klein_image"
    assert settings.get_modal_function_name(run_mode="flux2_klein_4b", engine="flux2_klein_4b") == "generate_flux2_klein_image"
    assert settings.get_modal_function_name(run_mode="sd35_large_real", engine="sd35_large") == "generate_sd35_large_image"

    monkeypatch.setenv("EASYADS_MODAL_FLUX2_KLEIN_FUNCTION_NAME", "custom_flux2")
    monkeypatch.setenv("EASYADS_MODAL_FLUX_FUNCTION_NAME", "custom_flux_legacy")
    monkeypatch.setenv("EASYADS_MODAL_SD35_FUNCTION_NAME", "custom_sd35")

    assert settings.get_modal_function_name(run_mode="flux_schnell_real") == "custom_flux2"
    assert settings.get_modal_function_name(run_mode="flux2_klein_4b") == "custom_flux2"
    assert settings.get_modal_function_name(run_mode="sd35_large_real") == "custom_sd35"


# ===== from test_modal_usage_tracking.py =====
from orchestrator.app.modal import service as modal_service
from orchestrator.app.modal.schemas import ModalPollResult


def test_modal_usage_records_gpu_runtime(monkeypatch):
    calls = []
    row = {
        "id": "job_uuid",
        "workspace_id": "ws_uuid",
        "thread_id": "thread_uuid",
        "requested_by": "user1",
        "model_name": "flux",
        "metadata": {"user_plan": "premium"},
    }
    poll_result = ModalPollResult(
        status="succeeded",
        modal_call_id="modal_123",
        usage={"gpu_seconds": "12.5", "gpu_type": "a10g", "duration_ms": 12500},
    )
    monkeypatch.setattr(modal_service.usage_service, "record_modal_gpu_usage", lambda **kwargs: calls.append(kwargs))

    modal_service._record_usage(row, poll_result)

    assert calls[0]["workspace_id"] == "ws_uuid"
    assert calls[0]["runtime_seconds"] == "12.5"
    assert calls[0]["gpu_type"] == "a10g"
    assert calls[0]["modal_call_id"] == "modal_123"
    assert calls[0]["completion_status"] == "succeeded"
    assert calls[0]["created_by"] == "user1"


def test_modal_failed_run_records_runtime_when_available(monkeypatch):
    calls = []
    row = {"id": "job_uuid", "workspace_id": "ws_uuid", "thread_id": "thread_uuid", "requested_by": "user1", "metadata": {"user_plan": "premium"}}
    poll_result = ModalPollResult(status="failed", modal_call_id="modal_123", usage={"gpu_seconds": "3", "gpu_type": "a10g"})
    monkeypatch.setattr(modal_service.usage_service, "record_modal_gpu_usage", lambda **kwargs: calls.append(kwargs))

    modal_service._safe_record_modal_usage(row, poll_result)

    assert calls[0]["runtime_seconds"] == "3"
    assert calls[0]["completion_status"] == "failed"


def test_modal_success_records_gpu_runtime_and_t2i_image(monkeypatch):
    runtime_calls = []
    t2i_calls = []
    row = {"id": "job_uuid", "workspace_id": "ws_uuid", "thread_id": "thread_uuid", "requested_by": "user1", "engine": "flux", "metadata": {"user_plan": "premium"}}
    poll_result = ModalPollResult(status="succeeded", modal_call_id="modal_123", usage={"gpu_seconds": "3", "gpu_type": "a10g", "image_count": 1})
    monkeypatch.setattr(modal_service.usage_service, "record_modal_gpu_usage", lambda **kwargs: runtime_calls.append(kwargs))
    monkeypatch.setattr(modal_service.usage_service, "record_t2i_usage", lambda **kwargs: t2i_calls.append(kwargs))

    modal_service._safe_record_modal_usage(row, poll_result)
    modal_service._safe_record_modal_t2i_usage(row, poll_result)

    assert runtime_calls[0]["created_by"] == "user1"
    assert t2i_calls[0]["image_count"] == 1
    assert t2i_calls[0]["created_by"] == "user1"


def test_modal_usage_failure_does_not_break_job_completion(monkeypatch):
    row = {"id": "job_uuid", "workspace_id": "ws_uuid"}
    poll_result = ModalPollResult(status="succeeded", modal_call_id="modal_123", usage={"gpu_seconds": "3"})
    monkeypatch.setattr(modal_service.usage_service, "record_modal_gpu_usage", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    assert modal_service._safe_record_modal_usage(row, poll_result) is None


# ===== from test_modal_worker_contract.py =====
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
