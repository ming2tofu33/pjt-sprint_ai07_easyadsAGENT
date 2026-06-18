"""FastAPI app factory for backend API routers."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from uuid import UUID

from orchestrator.app.api.chat import router as chat_router
from orchestrator.app.api.internal_auth import enforce_internal_secret
from orchestrator.app.api.photo import router as photo_router
from orchestrator.app.api.routers.archive import router as archive_router
from orchestrator.app.api.routers.brand_kits import router as brand_kits_router
from orchestrator.app.api.routers.chat_threads import router as chat_threads_router
from orchestrator.app.api.routers.generation_jobs import router as generation_jobs_router
from orchestrator.app.api.routers.generation_outputs import router as generation_outputs_router
from orchestrator.app.api.routers.references import router as references_router
from orchestrator.app.api.routers.assets import router as assets_router
from orchestrator.app.api.routers.usage import router as usage_router
from orchestrator.app.api.routers.validation_feedback import router as validation_feedback_router
from orchestrator.app.api.schemas.common import ErrorResponse
from orchestrator.app.observability.performance import (
    bind_perf_context,
    build_event,
    new_request_id,
    new_trace_id,
    record_perf_event,
    reset_perf_context,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="EasyAds Orchestrator API",
        version="0.1.0",
    )

    app.middleware("http")(enforce_internal_secret)

    @app.middleware("http")
    async def performance_middleware(request: Request, call_next):
        incoming_trace = request.headers.get("X-EasyAds-Trace-Id")
        try:
            trace_id = str(UUID(incoming_trace)) if incoming_trace and len(incoming_trace) <= 36 else new_trace_id()
        except (ValueError, AttributeError):
            trace_id = new_trace_id()
        request_id = request.headers.get("X-Request-Id") or new_request_id()
        tokens = bind_perf_context(trace_id=trace_id, request_id=request_id)
        started_at = __import__("time").perf_counter_ns()
        response = None
        exception_type = None
        try:
            response = await call_next(request)
            response.headers.setdefault("X-EasyAds-Trace-Id", trace_id)
            response.headers.setdefault("X-Request-Id", request_id)
            return response
        except Exception as exc:
            exception_type = type(exc).__name__
            raise
        finally:
            duration_ms = (__import__("time").perf_counter_ns() - started_at) / 1_000_000
            route_template = request.scope.get("route").path if request.scope.get("route") else request.url.path
            status_code = getattr(response, "status_code", 500)
            size_bytes = None
            content_length = response.headers.get("content-length") if response is not None else None
            if content_length and str(content_length).isdigit():
                size_bytes = int(content_length)
            record_perf_event(
                build_event(
                    "api_request",
                    operation=f"{request.method} {route_template}",
                    duration_ms=duration_ms,
                    status="ok" if exception_type is None and status_code < 500 else "error",
                    metadata={
                        "method": request.method,
                        "route_template": route_template,
                        "status_code": status_code,
                        "response_size_bytes": size_bytes,
                        "content_length_source": "header" if size_bytes is not None else "unavailable",
                        "exception_type": exception_type,
                    },
                )
            )
            reset_perf_context(tokens)

    app.include_router(chat_router)
    app.include_router(photo_router)
    app.include_router(chat_router, prefix="/api")
    app.include_router(photo_router, prefix="/api")
    app.include_router(
        references_router,
        prefix="/api/v1",
        tags=["references"],
    )
    app.include_router(
        brand_kits_router,
        prefix="/api/v1",
        tags=["brand-kits"],
    )
    app.include_router(
        assets_router,
        prefix="/api/v1",
        tags=["assets"],
    )
    app.include_router(
        generation_jobs_router,
        prefix="/api/v1",
        tags=["generation-jobs"],
    )
    app.include_router(
        archive_router,
        prefix="/api/v1",
        tags=["archive"],
    )
    app.include_router(
        chat_threads_router,
        prefix="/api/v1",
        tags=["chat-threads"],
    )
    app.include_router(
        generation_outputs_router,
        prefix="/api/v1",
        tags=["generation-outputs"],
    )
    app.include_router(
        validation_feedback_router,
        prefix="/api/v1",
        tags=["validation-feedback"],
    )
    app.include_router(
        usage_router,
        prefix="/api/v1",
        tags=["usage"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        if request.url.path.startswith("/api/v1/brand-kits"):
            error = ErrorResponse(
                error_code="invalid_brand_kit_request",
                message="Invalid brand kit request.",
                detail=str(exc),
            )
            return JSONResponse(status_code=400, content=error.model_dump(mode="json"))
        if request.url.path.startswith("/api/v1/generation-jobs"):
            error = ErrorResponse(
                error_code="invalid_generation_job_request",
                message="Invalid generation job request.",
                detail=str(exc),
            )
            return JSONResponse(status_code=400, content=error.model_dump(mode="json"))
        if request.url.path.startswith("/api/v1/archive"):
            error = ErrorResponse(
                error_code="invalid_archive_request",
                message="Invalid archive request.",
                detail=str(exc),
            )
            return JSONResponse(status_code=400, content=error.model_dump(mode="json"))
        if request.url.path.endswith("/regenerate"):
            error = ErrorResponse(
                error_code="invalid_regeneration_request",
                message="Invalid regeneration request.",
                detail=str(exc),
            )
            return JSONResponse(status_code=400, content=error.model_dump(mode="json"))
        if request.url.path.endswith("/validation"):
            error = ErrorResponse(
                error_code="invalid_validation_feedback_request",
                message="Invalid validation feedback request.",
                detail=str(exc),
            )
            return JSONResponse(status_code=400, content=error.model_dump(mode="json"))
        if request.url.path.startswith("/api/v1/generation-outputs"):
            error = ErrorResponse(
                error_code="invalid_generation_output_request",
                message="Invalid generation output request.",
                detail=str(exc),
            )
            return JSONResponse(status_code=400, content=error.model_dump(mode="json"))
        if request.url.path.startswith("/api/v1/chat-threads"):
            error = ErrorResponse(
                error_code="invalid_chat_thread_request",
                message="Invalid chat thread request.",
                detail=str(exc),
            )
            return JSONResponse(status_code=400, content=error.model_dump(mode="json"))

        if request.url.path.startswith("/api/v1/assets"):
            error = ErrorResponse(
                error_code="invalid_asset_request",
                message="Invalid asset request.",
                detail=str(exc),
            )
            return JSONResponse(status_code=400, content=error.model_dump(mode="json"))
        if request.url.path.startswith("/api/v1/usage"):
            error = ErrorResponse(
                error_code="invalid_usage_request",
                message="Invalid usage request.",
                detail=str(exc),
            )
            return JSONResponse(status_code=400, content=error.model_dump(mode="json"))

        return await request_validation_exception_handler(request, exc)

    return app
