"""FastAPI entrypoint for the EasyAds orchestrator service."""

from __future__ import annotations

from orchestrator.app.api.app import create_app

app = create_app()
