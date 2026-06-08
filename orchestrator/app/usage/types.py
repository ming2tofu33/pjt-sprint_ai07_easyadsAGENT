"""Usage tracking constants and shared types."""

from __future__ import annotations

from typing import Literal

UsageEventType = Literal[
    "llm_call",
    "t2i_generation",
    "r2_upload",
    "r2_storage_added",
    "r2_storage_removed",
    "modal_gpu_runtime",
]

UsageUnit = Literal["call", "image", "byte", "second"]
UsagePlan = Literal["free", "economic", "premium", "internal_benchmark"]

USAGE_EVENT_TYPES: set[str] = {
    "llm_call",
    "t2i_generation",
    "r2_upload",
    "r2_storage_added",
    "r2_storage_removed",
    "modal_gpu_runtime",
}

USAGE_UNITS: set[str] = {"call", "image", "byte", "second"}
USAGE_PLANS: set[str] = {"free", "economic", "premium", "internal_benchmark"}

SUMMARY_METRICS = [
    "llmCalls",
    "llmInputTokens",
    "llmOutputTokens",
    "llmTotalTokens",
    "t2iImages",
    "r2UploadBytes",
    "r2StorageBytesAdded",
    "r2StorageBytesRemoved",
    "estimatedNetStorageBytes",
    "modalGpuSeconds",
    "estimatedCostUsd",
]
