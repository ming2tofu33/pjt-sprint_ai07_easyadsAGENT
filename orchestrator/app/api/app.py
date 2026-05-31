"""FastAPI app factory for backend API routers."""

from __future__ import annotations

from fastapi import FastAPI

from orchestrator.app.api.routers.references import router as references_router


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
    return app
