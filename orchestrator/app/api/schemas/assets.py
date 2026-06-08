"""Asset API DTOs."""

from __future__ import annotations

from typing import Any, Literal
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


PUBLIC_ASSET_ID_PATTERN = r"^asset_[0-9a-f]{32}$"


AssetUploadKind = Literal["upload", "source", "reference"]
UploadMethod = Literal["PUT"]
UploadStatus = Literal["pending", "ready", "failed"]


class AssetPresignRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    kind: AssetUploadKind
    filename: str = Field(..., min_length=1)
    mime_type: str = Field(alias="mimeType", min_length=1)
    size_bytes: int = Field(..., gt=0, alias="sizeBytes")
    workspace_id: str | None = Field(default=None, alias="workspaceId")
    thread_id: str | None = Field(default=None, alias="threadId")


class UploadInstruction(BaseModel):
    method: UploadMethod = "PUT"
    url: str
    headers: dict[str, str] = Field(default_factory=dict)
    expires_at: str


class AssetInfo(BaseModel):
    asset_id: str
    kind: AssetUploadKind
    status: UploadStatus


class AssetPresignResponse(BaseModel):
    asset: AssetInfo
    upload: UploadInstruction


class AssetUploadMetadata(BaseModel):
    status: str | None = None
    error_code: str | None = None

class AssetResponseMetadata(BaseModel):
    upload: AssetUploadMetadata | None = None
    original_filename: str | None = None
    processed_width: int | None = None
    processed_height: int | None = None

class AssetResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    asset_id: str = Field(alias="assetId")
    kind: str
    status: str
    image_url: str | None = Field(default=None, alias="imageUrl")
    mime_type: str | None = Field(default=None, alias="mimeType")
    size_bytes: int | None = Field(default=None, alias="sizeBytes")
    width: int | None = None
    height: int | None = None
    storage_provider: str = Field(alias="storageProvider")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    metadata: AssetResponseMetadata | None = None


class AssetGetResponse(BaseModel):
    success: Literal[True] = True
    asset: AssetResponse


class AssetCompleteResponse(BaseModel):
    success: Literal[True] = True
    asset: AssetResponse
