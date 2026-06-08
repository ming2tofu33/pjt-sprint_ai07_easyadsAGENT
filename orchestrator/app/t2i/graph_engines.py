"""Graph-compatible adapters for non-OpenAI T2I lanes."""

from __future__ import annotations

import base64
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from orchestrator.app.modal import settings as modal_settings
from orchestrator.app.modal.client import submit_modal_t2i_job
from orchestrator.app.modal.errors import ModalExecutionError, ModalResultError
from orchestrator.app.modal.schemas import ModalPollResult, ModalT2IRequest
from orchestrator.app.t2i.base import BaseT2IEngine
from orchestrator.app.t2i.engines.base import T2IGenerationInput
from orchestrator.app.t2i.engines.registry import get_t2i_engine as get_guarded_t2i_engine
from orchestrator.app.t2i.schemas import T2IRequest, T2IResult
from orchestrator.app.t2i.settings import (
    T2IEngineNotEnabledError,
    T2IEngineUnavailableError,
    load_t2i_settings,
)

GraphActualEngineName = Literal["flux", "sd35_large", "flux2_klein_4b"]

_RUN_MODE_BY_ENGINE: dict[GraphActualEngineName, str] = {
    "flux": "flux_schnell_real",
    "sd35_large": "sd35_large_real",
    "flux2_klein_4b": "flux2_klein_4b",
}

_RENDER_MODE_BY_ENGINE: dict[GraphActualEngineName, str] = {
    "flux": "flux_schnell",
    "sd35_large": "sd35_large",
    "flux2_klein_4b": "flux2_klein_4b",
}


def get_graph_actual_t2i_engine(name: GraphActualEngineName) -> BaseT2IEngine:
    """Return a graph-compatible engine adapter for FLUX/SD.

    Modal is preferred when explicitly enabled. Otherwise we fall back to the
    existing guarded local engine lane so local smoke tests still exercise the
    same graph API surface.
    """
    settings = load_t2i_settings()
    if name == "flux2_klein_4b":
        if settings.flux2_klein_backend == "modal":
            return ModalGraphT2IEngine(name)
        return GuardedLocalGraphT2IEngine(name)
    if modal_settings.is_modal_execution_enabled():
        return ModalGraphT2IEngine(name)
    if name == "sd35_large" and settings.enable_sd35_local:
        try:
            from orchestrator.app.t2i.sd35_adapter import SD35LargeGraphEngine

            return SD35LargeGraphEngine()
        except ImportError:
            pass
    return GuardedLocalGraphT2IEngine(name)


class ModalGraphT2IEngine(BaseT2IEngine):
    """Submit FLUX/SD graph generation to Modal and return a pending call id."""

    def __init__(self, name: GraphActualEngineName) -> None:
        self.name = name

    def load(self) -> None:
        return None

    def unload(self) -> None:
        return None

    def is_loaded(self) -> bool:
        readiness = modal_settings.get_modal_readiness()
        return bool(readiness["enabled"] and not readiness["missing_requirements"])

    def health(self) -> dict[str, Any]:
        readiness = modal_settings.get_modal_readiness()
        available = bool(readiness["enabled"] and not readiness["missing_requirements"])
        return {
            "available": available,
            "loaded": False,
            "execution_backend": "modal",
            "modal": readiness,
            "function_name_present": bool(
                modal_settings.get_modal_function_name(run_mode=_RUN_MODE_BY_ENGINE[self.name], engine=self.name)
            ),
            "reason": None if available else _modal_unavailable_reason(readiness),
        }

    def generate(self, request: T2IRequest) -> T2IResult:
        if self.name == "sd35_large":
            try:
                from orchestrator.app.t2i.sd35_adapter import SD35LargeGraphEngine

                return SD35LargeGraphEngine().generate(request)
            except ImportError:
                pass

        started = perf_counter()
        metadata = dict(request.metadata or {})
        job_id = str(metadata.get("job_id") or "graph-job")
        output_dir = Path(request.output_dir or Path("data") / "outputs" / job_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        modal_request = _build_modal_graph_request(engine=self.name, request=request, metadata=metadata, job_id=job_id)
        submit_result = None
        try:
            submit_result = submit_modal_t2i_job(modal_request)
            if not submit_result.modal_call_id:
                return _error_result(
                    self.name,
                    request,
                    started,
                    metadata={
                        **metadata,
                        "execution_backend": "modal",
                        "modal_submit_status": submit_result.status,
                    },
                    error=submit_result.message or "Modal generation did not return a call id.",
                )
        except ModalExecutionError as exc:
            return _error_result(
                self.name,
                request,
                started,
                metadata={
                    **metadata,
                    "execution_backend": "modal",
                    "modal_submit_status": getattr(submit_result, "status", None),
                },
                error=str(exc),
            )

        return T2IResult(
            engine=self.name,
            image_paths=[],
            seed=request.seed,
            latency_ms=int((perf_counter() - started) * 1000),
            width=request.width,
            height=request.height,
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            metadata={
                **metadata,
                "execution_backend": "modal",
                "modal_call_id_present": True,
                "modal_call_id": submit_result.modal_call_id,
                "modal_status": "submitted",
                "modal_provider": "modal",
                "render_mode": _RENDER_MODE_BY_ENGINE[self.name],
                "modal_result_transport": "inline_base64",
            },
        )


class GuardedLocalGraphT2IEngine(BaseT2IEngine):
    """Bridge graph T2I requests to the existing guarded local engine registry."""

    def __init__(self, name: GraphActualEngineName) -> None:
        self.name = name

    def load(self) -> None:
        return None

    def unload(self) -> None:
        return None

    def is_loaded(self) -> bool:
        return False

    def health(self) -> dict[str, Any]:
        settings = load_t2i_settings()
        enabled = settings.enable_flux2_klein_local and settings.flux2_klein_backend == "local_diffusers" if self.name == "flux2_klein_4b" else (settings.enable_flux_local if self.name == "flux" else settings.enable_sd35_local)
        model_id = settings.flux2_klein_model_id if self.name == "flux2_klein_4b" else (settings.flux_model_id if self.name == "flux" else settings.sd35_model_id)
        return {
            "available": bool(enabled),
            "loaded": False,
            "execution_backend": "local",
            "model_id": model_id,
            "reason": None if enabled else f"{self.name} local lane is disabled.",
        }

    def generate(self, request: T2IRequest) -> T2IResult:
        started = perf_counter()
        metadata = dict(request.metadata or {})
        job_id = str(metadata.get("job_id") or "graph-job")
        output_dir = Path(request.output_dir or Path("data") / "outputs" / job_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            guarded_engine = get_guarded_t2i_engine(self.name)
            output = guarded_engine.generate(
                T2IGenerationInput(
                    job_id=job_id,
                    prompt=request.prompt,
                    negative_prompt=request.negative_prompt,
                    width=request.width,
                    height=request.height,
                    num_images=request.num_images,
                    output_dir=output_dir.as_posix(),
                    metadata=metadata,
                )
            )
        except T2IEngineNotEnabledError as exc:
            return _error_result(
                self.name,
                request,
                started,
                metadata={**metadata, "execution_backend": "local", "error_code": "t2i_engine_not_enabled"},
                error=str(exc),
            )
        except T2IEngineUnavailableError as exc:
            return _error_result(
                self.name,
                request,
                started,
                metadata={
                    **metadata,
                    "execution_backend": "local",
                    "error_code": getattr(exc, "error_code", "t2i_engine_unavailable"),
                },
                error=str(exc),
            )

        return T2IResult(
            engine=self.name,
            image_paths=list(output.image_paths),
            seed=request.seed,
            latency_ms=output.latency_ms or int((perf_counter() - started) * 1000),
            width=request.width,
            height=request.height,
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            metadata={
                **metadata,
                **output.metadata,
                "execution_backend": "local",
            },
            error=None if output.image_paths else f"{self.name} did not return an image.",
        )


def write_modal_graph_result_image(*, output_dir: Path, poll_result: ModalPollResult) -> str:
    """Persist an inline Modal result image in the graph output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    image_bytes = poll_result.image_bytes
    if image_bytes is None and poll_result.image_b64:
        try:
            image_bytes = base64.b64decode(poll_result.image_b64, validate=True)
        except Exception as exc:
            raise ModalResultError("Modal returned invalid image_b64.") from exc
    if not image_bytes:
        raise ModalResultError("Modal succeeded without image bytes.")

    target = output_dir / "final_0.png"
    target.write_bytes(image_bytes)
    return target.as_posix()


def _build_modal_graph_request(
    *,
    engine: GraphActualEngineName,
    request: T2IRequest,
    metadata: dict[str, Any],
    job_id: str,
) -> ModalT2IRequest:
    run_mode = _RUN_MODE_BY_ENGINE[engine]
    params = _safe_t2i_params(metadata)
    if request.steps is not None:
        params["num_inference_steps"] = request.steps
    if request.guidance_scale is not None:
        params["guidance_scale"] = request.guidance_scale
    if engine == "flux":
        params.setdefault("render_mode", "flux_schnell")
        params.setdefault("num_inference_steps", 4)
        params.setdefault("guidance_scale", 0.0)
    elif engine == "flux2_klein_4b":
        settings = load_t2i_settings()
        params.setdefault("render_mode", "flux2_klein_4b")
        params.setdefault("num_inference_steps", settings.flux2_klein_num_inference_steps)
        params.setdefault("guidance_scale", settings.flux2_klein_guidance_scale)
    else:
        params.setdefault("render_mode", "sd35_large")
        params.setdefault("num_inference_steps", 8)
        params.setdefault("guidance_scale", 4.0)

    return ModalT2IRequest(
        job_id=job_id,
        thread_id=str(metadata.get("thread_id") or "") or None,
        workspace_id=str(metadata.get("workspace_id") or "graph_workspace"),
        run_mode=run_mode,
        engine=engine,
        prompt=request.prompt,
        negative_prompt=request.negative_prompt,
        width=request.width,
        height=request.height,
        num_images=1,
        seed=request.seed,
        model_name=metadata.get("model_name") or engine,
        params=params,
        metadata={
            **metadata,
            "modal_result_transport": "inline_base64",
            "graph_execution_mode": "graph_job",
        },
    )


def _safe_t2i_params(metadata: dict[str, Any]) -> dict[str, Any]:
    params = metadata.get("t2i_params") if isinstance(metadata, dict) else None
    if not isinstance(params, dict):
        params = {}
    allowed_keys = {
        "width",
        "height",
        "seed",
        "num_inference_steps",
        "guidance_scale",
        "max_sequence_length",
        "model_id",
    }
    return {key: value for key, value in params.items() if key in allowed_keys}


def _error_result(
    engine: GraphActualEngineName,
    request: T2IRequest,
    started: float,
    *,
    metadata: dict[str, Any],
    error: str,
) -> T2IResult:
    return T2IResult(
        engine=engine,
        image_paths=[],
        seed=request.seed,
        latency_ms=int((perf_counter() - started) * 1000),
        width=request.width,
        height=request.height,
        prompt=request.prompt,
        negative_prompt=request.negative_prompt,
        metadata=metadata,
        error=error,
    )


def _modal_unavailable_reason(readiness: dict[str, Any]) -> str:
    missing = readiness.get("missing_requirements") or []
    if missing:
        return "Modal execution is unavailable. Missing requirements: " + ", ".join(missing)
    if not readiness.get("enabled"):
        return "Modal execution is disabled."
    return "Modal execution is unavailable."
