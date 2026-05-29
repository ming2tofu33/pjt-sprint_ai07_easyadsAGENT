"""Usage API DTOs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from orchestrator.app.api.schemas.common import ApiMeta


class UsageEventResponse(BaseModel):
    event_id: str
    event_type: str
    amount: int = Field(default=1, ge=0)
    created_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class UsageSummaryResponse(BaseModel):
    success: Literal[True] = True
    period: str
    plan: str
    monthly_limit: int = Field(..., ge=0)
    used: int = Field(..., ge=0)
    remaining: int = Field(..., ge=0)
    usage_rate: float = Field(..., ge=0.0)
    events: list[UsageEventResponse] = Field(default_factory=list)
    meta: ApiMeta = Field(default_factory=ApiMeta)
