"""Chat thread & message API DTOs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from orchestrator.app.api.schemas.common import ApiMeta
from orchestrator.app.schemas.chat_state_snapshots import ChatStateSnapshotResponse

# ---------------------------------------------------------------------------
# 기본 타입
# ---------------------------------------------------------------------------

ChatThreadStatus = Literal[
    "draft",
    "generating",
    "completed",
    "failed",
    "archived",
]

ChatMessageRole = Literal[
    "user",
    "assistant",
    "system",
]

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ChatThreadCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: str | None = Field(default=None, alias="userId")
    title: str | None = Field(default=None, max_length=120)
    brand_kit_id: str | None = Field(default=None, alias="brandKitId")
    project_id: str | None = Field(default=None, alias="projectId")
    final_brief: dict[str, Any] = Field(default_factory=dict, alias="finalBrief")

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            return None
        return v.strip() if v else v


class ChatThreadUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(default=None, max_length=120)
    brand_kit_id: str | None = Field(default=None, alias="brandKitId")
    project_id: str | None = Field(default=None, alias="projectId")
    final_brief: dict[str, Any] | None = Field(default=None, alias="finalBrief")

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            return None
        return v.strip() if v else v


class ChatMessageCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    role: ChatMessageRole
    content: str | None = Field(default=None, max_length=20_000)
    payload: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = Field(default=None, alias="createdBy")

    @field_validator("content", mode="before")
    @classmethod
    def strip_content(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            return stripped if stripped else None
        return v

    @model_validator(mode="after")
    def content_or_payload_required(self) -> "ChatMessageCreateRequest":
        if not self.content and not self.payload:
            raise ValueError("content 또는 payload 중 하나는 반드시 있어야 합니다.")
        return self


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ChatThreadResponse(BaseModel):
    thread_id: str
    title: str | None = None
    status: ChatThreadStatus
    brand_kit_id: str | None = None
    project_id: str | None = None
    final_brief: dict[str, Any] = Field(default_factory=dict)
    active_job_id: str | None = None
    has_final_output: bool = False
    last_message_at: str
    archived_at: str | None = None
    created_at: str
    updated_at: str


class ChatMessageResponse(BaseModel):
    message_id: str
    thread_id: str
    sequence_no: int
    role: ChatMessageRole
    content: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    job_id: str | None = None
    event_type: str | None = None
    created_at: str


# ---------------------------------------------------------------------------
# List / wrapper responses
# ---------------------------------------------------------------------------


class ChatThreadListResponse(BaseModel):
    success: Literal[True] = True
    threads: list[ChatThreadResponse]
    total: int
    meta: ApiMeta = Field(default_factory=ApiMeta)


class ChatThreadCreateResponse(BaseModel):
    success: Literal[True] = True
    thread: ChatThreadResponse
    meta: ApiMeta = Field(default_factory=ApiMeta)


class ChatThreadGetResponse(BaseModel):
    success: Literal[True] = True
    thread: ChatThreadResponse
    meta: ApiMeta = Field(default_factory=ApiMeta)


class ChatMessageListResponse(BaseModel):
    success: Literal[True] = True
    messages: list[ChatMessageResponse]
    total: int
    meta: ApiMeta = Field(default_factory=ApiMeta)


class ChatMessageCreateResponse(BaseModel):
    success: Literal[True] = True
    message: ChatMessageResponse
    meta: ApiMeta = Field(default_factory=ApiMeta)


class ChatThreadStateGetResponse(BaseModel):
    success: Literal[True] = True
    snapshot: ChatStateSnapshotResponse | None = None
    meta: ApiMeta = Field(default_factory=ApiMeta)
