"""Input evidence normalization contracts."""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


EvidenceSource = Literal["user_text", "image_vlm", "asset_metadata", "brand_profile", "reference_metadata"]
EvidenceClass = Literal["verified_fact", "visual_observation", "creative_inference"]
InputMode = Literal["text_only", "image_only", "text_and_image"]
ConflictType = Literal["identity_mismatch", "attribute_mismatch", "claim_mismatch", "brand_mismatch", "intent_mismatch"]
ConflictSeverity = Literal["warning", "clarification_required", "manual_review"]


class EvidenceItem(BaseModel):
    evidence_id: str = Field(default_factory=lambda: f"evidence_{uuid4().hex}")
    key: str
    value: str
    normalized_value: str | None = None
    source: EvidenceSource
    evidence_class: EvidenceClass
    confidence: float = Field(ge=0.0, le=1.0)
    usable_for_copy: bool
    source_ref: str | None = None
    rationale: str | None = None


class InputConflict(BaseModel):
    conflict_id: str = Field(default_factory=lambda: f"conflict_{uuid4().hex}")
    field: str
    text_value: str | None = None
    image_value: str | None = None
    metadata_value: str | None = None
    conflict_type: ConflictType
    severity: ConflictSeverity
    confidence: float = Field(ge=0.0, le=1.0)
    recommended_resolution: str


class InputEvidenceBundle(BaseModel):
    schema_version: Literal["input_evidence_bundle_v1"] = "input_evidence_bundle_v1"
    input_mode: InputMode
    user_text: str | None = None
    user_intent: str | None = None
    placement: str | None = None
    promotion_goal: str | None = None
    source_asset_id: str | None = None
    reference_asset_id: str | None = None
    source_image_sha256: str | None = None
    source_provenance: str | None = None
    explicit_product_mentions: list[str] = Field(default_factory=list)
    explicit_user_facts: list[EvidenceItem] = Field(default_factory=list)
    visual_observations: list[EvidenceItem] = Field(default_factory=list)
    asset_metadata_evidence: list[EvidenceItem] = Field(default_factory=list)
    brand_profile_evidence: list[EvidenceItem] = Field(default_factory=list)
    reference_evidence: list[EvidenceItem] = Field(default_factory=list)
    creative_inferences: list[EvidenceItem] = Field(default_factory=list)
    input_conflicts: list[InputConflict] = Field(default_factory=list)
    unknown_fields: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    clarification_required: bool = False
    manual_review_required: bool = False
    overall_confidence: float = Field(ge=0.0, le=1.0)
    provider_metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_source_contract(self):
        if self.input_mode == "image_only":
            invalid_user_facts = [item.key for item in self.explicit_user_facts if item.source == "user_text"]
            if invalid_user_facts:
                raise ValueError("image_only cannot contain user_text explicit_user_facts")
        for item in self.visual_observations:
            if item.source != "image_vlm" or item.evidence_class != "visual_observation":
                raise ValueError("visual_observations must be image_vlm visual_observation items")
        for item in self.creative_inferences:
            if item.usable_for_copy:
                raise ValueError("creative_inferences cannot be directly usable_for_copy")
        forbidden_values = ("data/outputs/", "data\\outputs\\", "output_dir", "source_image_path")
        for collection in (
            self.explicit_user_facts,
            self.visual_observations,
            self.asset_metadata_evidence,
            self.brand_profile_evidence,
            self.reference_evidence,
            self.creative_inferences,
        ):
            for item in collection:
                value = str(item.value)
                if any(marker in value for marker in forbidden_values):
                    raise ValueError("runtime metadata/local paths cannot be stored as EvidenceItem values")
        return self
