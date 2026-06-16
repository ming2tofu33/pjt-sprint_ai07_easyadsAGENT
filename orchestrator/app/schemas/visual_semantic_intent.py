"""Visual semantic intent contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def normalize_required_text(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("value must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError("value must not be empty")
    return normalized


def normalize_string_list(values: list[str] | str | None) -> tuple[str, ...]:
    if values is None:
        return ()
    candidates = [values] if isinstance(values, str) else values
    normalized: list[str] = []
    seen: set[str] = set()
    for value in candidates:
        if not isinstance(value, str):
            raise ValueError("semantic list values must be strings")
        item = value.strip()
        if not item or item in seen:
            continue
        normalized.append(item)
        seen.add(item)
    return tuple(normalized)


def semantic_token_key(value: str) -> str:
    return value.strip().casefold()


class VisualSemanticIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subject_priority: float = Field(ge=0.0, le=1.0)
    environment_priority: float = Field(ge=0.0, le=1.0)
    text_priority: float = Field(ge=0.0, le=1.0)
    desired_moods: tuple[str, ...] = ()
    desired_materials: tuple[str, ...] = ()
    lighting_preferences: tuple[str, ...] = ()
    composition_preferences: tuple[str, ...] = ()
    required_visual_facts: tuple[str, ...] = ()
    prohibited_visual_elements: tuple[str, ...] = ()
    copy_presence_mode: str
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator(
        "desired_moods",
        "desired_materials",
        "lighting_preferences",
        "composition_preferences",
        "required_visual_facts",
        "prohibited_visual_elements",
        mode="before",
    )
    @classmethod
    def normalize_list_field(cls, value: Any) -> tuple[str, ...]:
        return normalize_string_list(value)

    @field_validator("copy_presence_mode", mode="before")
    @classmethod
    def normalize_copy_presence_mode(cls, value: Any) -> str:
        return normalize_required_text(value)

    @model_validator(mode="after")
    def reject_required_prohibited_conflicts(self) -> "VisualSemanticIntent":
        required_keys = {semantic_token_key(item) for item in self.required_visual_facts}
        prohibited_keys = {semantic_token_key(item) for item in self.prohibited_visual_elements}
        if required_keys & prohibited_keys:
            raise ValueError("visual fact cannot be both required and prohibited")
        return self


class SemanticIntentAttribution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field_name: str
    item_value: str | None = None
    evidence_refs: tuple[str, ...] = ()
    source_paths: tuple[str, ...] = ()
    is_derived: bool

    @field_validator("field_name", mode="before")
    @classmethod
    def normalize_field_name(cls, value: Any) -> str:
        return normalize_required_text(value)

    @field_validator("item_value", mode="before")
    @classmethod
    def normalize_item_value(cls, value: Any) -> str | None:
        if value is None:
            return None
        return normalize_required_text(value)

    @field_validator("evidence_refs", "source_paths", mode="before")
    @classmethod
    def normalize_refs(cls, value: Any) -> tuple[str, ...]:
        return normalize_string_list(value)

    @model_validator(mode="after")
    def require_grounding_reference(self) -> "SemanticIntentAttribution":
        if not self.evidence_refs and not self.source_paths:
            raise ValueError("attribution requires evidence_refs or source_paths")
        return self


class VisualSemanticIntentDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    intent: VisualSemanticIntent
    attributions: tuple[SemanticIntentAttribution, ...] = ()
    ambiguity_flags: tuple[str, ...] = ()

    @field_validator("ambiguity_flags", mode="before")
    @classmethod
    def normalize_ambiguity_flags(cls, value: Any) -> tuple[str, ...]:
        return normalize_string_list(value)


class VisualSemanticIntentGenerationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    intent: VisualSemanticIntent
    attributions: tuple[SemanticIntentAttribution, ...]
    ambiguity_flags: tuple[str, ...]
    input_projection_hash: str
    generator_id: str | None = None

    @field_validator("ambiguity_flags", mode="before")
    @classmethod
    def normalize_result_flags(cls, value: Any) -> tuple[str, ...]:
        return normalize_string_list(value)

    @field_validator("attributions", mode="before")
    @classmethod
    def normalize_attributions(cls, value: Any) -> tuple[SemanticIntentAttribution, ...]:
        return tuple(value or ())
