"""FastAPI entrypoint for the EasyAds orchestrator service."""

from __future__ import annotations

from fastapi import FastAPI

from orchestrator.app.api.chat import router as chat_router
from orchestrator.app.api.photo import router as photo_router

app = FastAPI(title="EasyAds Orchestrator", version="0.1.0")
app.include_router(chat_router)
app.include_router(photo_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
