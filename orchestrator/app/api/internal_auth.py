"""Internal API secret enforcement.

The orchestrator trusts caller-supplied identity (X-EasyAds-* headers and
userId query params) because the Next proxy and the BFF verify Supabase JWTs
upstream. This middleware closes the remaining gap — direct HTTP access to
the orchestrator — by requiring a shared secret from those trusted callers.

Opt-in by design: when EASYADS_INTERNAL_API_SECRET is unset/empty, all
requests pass (local dev, tests). When set, every request except /health
must carry a matching X-EasyAds-Internal-Secret header.
"""

from __future__ import annotations

import secrets

from fastapi import Request
from fastapi.responses import JSONResponse

from orchestrator.app.api.schemas.common import ErrorResponse
from orchestrator.app.core.config import _get_env

INTERNAL_SECRET_HEADER = "X-EasyAds-Internal-Secret"
EXEMPT_PATHS = {"/health"}


def get_internal_api_secret() -> str:
    return _get_env("EASYADS_INTERNAL_API_SECRET", "").strip()


async def enforce_internal_secret(request: Request, call_next):
    expected = get_internal_api_secret()
    if not expected or request.url.path in EXEMPT_PATHS:
        return await call_next(request)
    provided = request.headers.get(INTERNAL_SECRET_HEADER, "")
    # Encode to bytes: compare_digest on str raises for non-ASCII input,
    # and header values are attacker-controlled.
    if provided and secrets.compare_digest(provided.encode("utf-8"), expected.encode("utf-8")):
        return await call_next(request)
    error = ErrorResponse(
        error_code="invalid_internal_secret",
        message="Internal API secret is missing or invalid.",
    )
    return JSONResponse(status_code=401, content=error.model_dump(mode="json"))
