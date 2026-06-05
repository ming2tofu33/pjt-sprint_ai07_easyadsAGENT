from typing import Any
from pydantic import BaseModel, Field

class ChatStateSnapshotResponse(BaseModel):
    snapshot_id: str
    thread_id: str
    job_id: str | None = None
    source_message_id: str | None = None
    parent_snapshot_id: str | None = None
    snapshot_version: int
    schema_version: int
    snapshot_kind: str
    state_payload: dict[str, Any] = Field(default_factory=dict)
    changed_fields: list[str] = Field(default_factory=list)
    selected_reference_template_id: str | None = None
    reference_template_snapshot: dict[str, Any] = Field(default_factory=dict)
    brand_kit_snapshot: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
