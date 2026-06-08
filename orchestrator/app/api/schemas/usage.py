"""Usage API DTOs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from orchestrator.app.api.schemas.common import ApiMeta


class UsageWindow(BaseModel):
    start_at: str = Field(alias="startAt")
    end_at: str = Field(alias="endAt")
    timezone: Literal["UTC"] = "UTC"


class UsageTotals(BaseModel):
    llm_calls: int = Field(alias="llmCalls")
    llm_input_tokens: int = Field(alias="llmInputTokens")
    llm_output_tokens: int = Field(alias="llmOutputTokens")
    llm_total_tokens: int = Field(alias="llmTotalTokens")
    t2i_images: int = Field(alias="t2iImages")
    r2_upload_bytes: int = Field(alias="r2UploadBytes")
    r2_storage_bytes_added: int = Field(alias="r2StorageBytesAdded")
    r2_storage_bytes_removed: int = Field(alias="r2StorageBytesRemoved")
    estimated_net_storage_bytes: int = Field(alias="estimatedNetStorageBytes")
    modal_gpu_seconds: str = Field(alias="modalGpuSeconds")
    estimated_cost_usd: str = Field(alias="estimatedCostUsd")
    unpriced_event_count: int = Field(alias="unpricedEventCount")


class UsageQuotaItem(BaseModel):
    metric: str
    limit: int | str | None
    used: int | str
    remaining: int | str | None
    exceeded: bool
    configured: bool = False
    enforced: bool


class UsageBreakdownItem(BaseModel):
    key: str | None = None
    unit: str | None = None
    quantity: int | str
    estimated_cost_usd: int | str = Field(alias="estimatedCostUsd")


class UsageEventResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_id: str = Field(alias="eventId")
    event_type: str = Field(alias="eventType")
    workspace_id: str | None = Field(default=None, alias="workspaceId")
    created_by: str | None = Field(default=None, alias="createdBy")
    quantity: int | str = 1
    amount: int | str = 1
    unit: str = "call"
    provider: str | None = None
    model_name: str | None = Field(default=None, alias="modelName")
    plan: str | None = None
    cost_usd: int | str | None = Field(default=None, alias="costUsd")
    created_at: str | None = Field(default=None, alias="createdAt")


class UsageSummary(BaseModel):
    scope: Literal["workspace", "user"]
    plan: str
    window: UsageWindow
    totals: UsageTotals
    quota: list[UsageQuotaItem] = Field(default_factory=list)
    by_event_type: list[dict[str, Any]] = Field(default_factory=list, alias="byEventType")
    by_provider: list[dict[str, Any]] = Field(default_factory=list, alias="byProvider")
    by_model: list[dict[str, Any]] = Field(default_factory=list, alias="byModel")
    by_event_plan: list[dict[str, Any]] = Field(default_factory=list, alias="byEventPlan")


class UsageSummaryResponse(BaseModel):
    success: Literal[True] = True
    summary: UsageSummary | None = None
    period: str | None = None
    plan: str | None = None
    monthly_limit: int | None = None
    used: int | None = None
    remaining: int | None = None
    usage_rate: float | None = None
    events: list[UsageEventResponse] = Field(default_factory=list)
    meta: ApiMeta = Field(default_factory=ApiMeta)
