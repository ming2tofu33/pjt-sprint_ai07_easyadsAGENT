"""FastAPI app factory for backend API routers."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

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


def create_app() -> FastAPI:
    app = FastAPI(
        title="EasyAds Orchestrator API",
        version="0.1.0",
    )

    app.middleware("http")(enforce_internal_secret)

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
