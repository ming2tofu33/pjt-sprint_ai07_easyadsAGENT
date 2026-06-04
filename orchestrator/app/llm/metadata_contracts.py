"""Shared LLM/VLM metadata contract models and sanitizers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


LLM_METADATA_SCHEMA_VERSION = "llm_marketing_v1"

DO_NOT_INVENT_FIELDS = [
    "phone",
    "address",
    "price",
    "discount",
    "event_period",
]

NEGATIVE_TEXT_TERMS = [
    "text",
    "letters",
    "numbers",
    "Hangul",
    "logo",
    "watermark",
]

SENSITIVE_KEY_FRAGMENTS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "credential",
    "hf_token",
    "openai_api_key",
    "password",
    "private_key",
    "secret",
    "token",
)

ALLOWED_SENSITIVE_KEY_NAMES = {
    "completion_tokens",
    "cost_estimate",
    "prompt_tokens",
    "openai_api_key_present",
    "local_api_key_present",
    "token_usage",
    "total_tokens",
}

RAW_BINARY_KEY_FRAGMENTS = (
    "base64",
    "binary",
    "bytes",
    "file_bytes",
    "image_bytes",
    "raw_image",
)

HIDDEN_REASONING_KEYS = (
    "chain_of_thought",
    "chain-of-thought",
    "cot",
    "hidden_reasoning",
    "raw_reasoning",
    "reasoning_trace",
)

ALLOWED_REASONING_KEYS = {"reasoning_summary", "no_chain_of_thought"}


class LLMMetadataTrace(BaseModel):
    schema_version: str = LLM_METADATA_SCHEMA_VERSION
    job_id: str | None = None
    thread_id: str | None = None
    revision: int | None = None
    node_name: str


class LLMMetadataTask(BaseModel):
    objective: str
    output_schema: str


class LLMOutputRules(BaseModel):
    structured_output_only: bool = True
    no_chain_of_thought: bool = True
    include_reasoning_summary_only: bool = True


class LLMMetadataPayload(BaseModel):
    trace: LLMMetadataTrace
    task: LLMMetadataTask
    available_state: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)
    output_rules: LLMOutputRules = Field(default_factory=LLMOutputRules)

    def to_metadata_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def sanitize_metadata(value: Any) -> Any:
    """Return a JSON-safe value without secrets, raw bytes, or hidden reasoning."""
    if isinstance(value, BaseModel):
        value = value.model_dump()
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            if should_drop_metadata_key(key_str):
                continue
            sanitized[key_str] = sanitize_metadata(item)
        return sanitized
    if isinstance(value, (list, tuple, set)):
        return [sanitize_metadata(item) for item in value]
    if isinstance(value, bytes):
        return "[redacted_binary]"
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return f"[unsupported_metadata_value:{value.__class__.__name__}]"


def should_drop_metadata_key(key: str) -> bool:
    normalized = key.lower()
    if normalized in ALLOWED_SENSITIVE_KEY_NAMES:
        return False
    if normalized == "prompt":
        return True
    if normalized in ALLOWED_REASONING_KEYS:
        return False
    if normalized in HIDDEN_REASONING_KEYS:
        return True
    if "chain" in normalized and "thought" in normalized:
        return True
    if any(fragment in normalized for fragment in SENSITIVE_KEY_FRAGMENTS):
        return True
    return any(fragment in normalized for fragment in RAW_BINARY_KEY_FRAGMENTS)
