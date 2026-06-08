"""Adapter protocol for runtime quality gate inspection."""

from __future__ import annotations

from typing import Protocol

from orchestrator.app.quality_gate.schemas import VLMQualityGateResult, VLMQualityRequest


class VLMQualityAdapter(Protocol):
    def inspect(self, *, image_path: str, request: VLMQualityRequest) -> VLMQualityGateResult:
        ...

