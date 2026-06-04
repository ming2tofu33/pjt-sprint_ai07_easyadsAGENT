"""Lazy Modal client wrapper."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from orchestrator.app.modal import settings
from orchestrator.app.modal.errors import ModalExecutionUnavailableError, ModalJobPollError, ModalJobSubmitError
from orchestrator.app.modal.schemas import ModalPollResult, ModalSubmitResult, ModalT2IRequest


def submit_modal_t2i_job(request: ModalT2IRequest, *, client: object | None = None) -> ModalSubmitResult:
    settings.require_modal_ready()
    if client is not None and hasattr(client, "submit"):
        return client.submit(request)
    try:
        modal = _import_modal()
        environment_name = settings.get_modal_environment()
        if environment_name:
            function = modal.Function.from_name(
                settings.get_modal_app_name(),
                settings.get_modal_function_name(),
                environment_name=environment_name,
            )
        else:
            function = modal.Function.from_name(settings.get_modal_app_name(), settings.get_modal_function_name())
        function_call = function.spawn(request.model_dump(mode="json"))
    except ModalExecutionUnavailableError:
        raise
    except Exception as exc:
        raise ModalJobSubmitError("Modal job submit failed.") from exc
    modal_call_id = _extract_modal_call_id(function_call)
    metadata = {}
    if modal_call_id.startswith("synthetic_modal_call_"):
        metadata["synthetic_call_id"] = True
    return ModalSubmitResult(
        submitted=True,
        modal_call_id=modal_call_id,
        provider_job_id=modal_call_id,
        status="submitted",
        metadata=metadata,
    )


def poll_modal_t2i_result(modal_call_id: str, *, client: object | None = None) -> ModalPollResult:
    if client is not None and hasattr(client, "poll"):
        return client.poll(modal_call_id)
    try:
        modal = _import_modal()
        function_call = modal.FunctionCall.from_id(modal_call_id)
        raw_result = function_call.get(timeout=settings.get_modal_poll_timeout_seconds())
    except ModalExecutionUnavailableError:
        raise
    except TimeoutError:
        return ModalPollResult(status="running", modal_call_id=modal_call_id)
    except Exception as exc:
        raise ModalJobPollError("Modal job poll failed.") from exc
    return _coerce_modal_poll_result(raw_result, modal_call_id)


def _import_modal():
    try:
        import modal  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise ModalExecutionUnavailableError("modal SDK is unavailable.") from exc
    return modal


def _extract_modal_call_id(function_call: object) -> str:
    for attr in ("object_id", "call_id"):
        value = getattr(function_call, attr, None)
        if value:
            return str(value)
    return f"synthetic_modal_call_{uuid4().hex}"


def _coerce_modal_poll_result(raw_result: Any, modal_call_id: str) -> ModalPollResult:
    if isinstance(raw_result, ModalPollResult):
        return raw_result
    if isinstance(raw_result, dict):
        payload = dict(raw_result)
        payload.setdefault("modal_call_id", modal_call_id)
        if not payload.get("status"):
            payload["status"] = "succeeded" if payload.get("image_b64") or payload.get("image_bytes") else "unknown"
        return ModalPollResult(**payload)
    return ModalPollResult(
        status="failed",
        modal_call_id=modal_call_id,
        error={
            "error_code": "modal_invalid_result",
            "message": "Modal returned an unsupported result payload.",
            "result_type": type(raw_result).__name__,
        },
    )
