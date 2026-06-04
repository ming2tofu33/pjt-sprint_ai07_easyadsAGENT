import sys
import types

from orchestrator.app.modal import client as modal_client
from orchestrator.app.modal.schemas import ModalT2IRequest


def _request() -> ModalT2IRequest:
    return ModalT2IRequest(
        job_id="job_modal",
        workspace_id="workspace_uuid",
        run_mode="flux_local",
        engine="flux",
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
