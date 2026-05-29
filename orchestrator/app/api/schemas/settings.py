"""User settings API DTOs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from orchestrator.app.api.schemas.common import ApiMeta


class NotificationSettingsResponse(BaseModel):
    email_enabled: bool = True
    push_enabled: bool = True
    job_completed: bool = True
    job_failed: bool = True
    marketing_updates: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class UserAppSettingsResponse(BaseModel):
    success: Literal[True] = True
    default_output_format: str = "png"
    default_ad_format: str = "instagram_feed"
    default_platform: str = "instagram"
    default_image_quality: str = "standard"
    notification_settings: NotificationSettingsResponse = Field(default_factory=NotificationSettingsResponse)
    metadata: dict[str, Any] = Field(default_factory=dict)
    meta: ApiMeta = Field(default_factory=ApiMeta)


class UserAppSettingsUpdateRequest(BaseModel):
    default_output_format: str | None = None
    default_ad_format: str | None = None
    default_platform: str | None = None
    default_image_quality: str | None = None
    notification_settings: NotificationSettingsResponse | None = None
    metadata: dict[str, Any] | None = None
