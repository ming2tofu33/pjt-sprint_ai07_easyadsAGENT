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

    modal_client.submit_modal_t2i_job(_request(run_mode="flux_schnell_real", engine="flux"))
    modal_client.submit_modal_t2i_job(_request(run_mode="sd35_large_real", engine="sd35_large"))

    assert captured == [
        ("easyads-t2i", "generate_flux_schnell_image"),
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
