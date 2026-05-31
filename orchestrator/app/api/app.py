"""FastAPI app factory for backend API routers."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from orchestrator.app.api.routers.brand_kits import router as brand_kits_router
from orchestrator.app.api.routers.references import router as references_router
from orchestrator.app.api.schemas.common import ErrorResponse


def create_app() -> FastAPI:
    app = FastAPI(
        title="EasyAds Orchestrator API",
        version="0.1.0",
    )

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

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        if request.url.path.startswith("/api/v1/brand-kits"):
            error = ErrorResponse(
                error_code="invalid_brand_kit_request",
                message="Invalid brand kit request.",
                detail=str(exc),
            )
            return JSONResponse(status_code=400, content=error.model_dump(mode="json"))

        return await request_validation_exception_handler(request, exc)

    return app