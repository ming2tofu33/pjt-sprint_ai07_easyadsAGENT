from __future__ import annotations

import pytest
from pydantic import ValidationError

from orchestrator.app.schemas.input_evidence import EvidenceItem
from orchestrator.app.schemas.intake_understanding import IntakeUnderstandingResult


def _evidence(key: str, value: str, *, source: str = "deterministic_parser") -> EvidenceItem:
    return EvidenceItem(
        key=key,
        value=value,
        normalized_value=value,
        source=source,
        evidence_class="verified_fact",
        confidence=0.9,
        usable_for_copy=True,
        source_ref=value,
    )


def test_intake_understanding_result_accepts_grounded_open_domain_fields():
    result = IntakeUnderstandingResult(
        business_candidate="beauty",
        advertised_subject="프리미엄 뷰티샵",
        advertised_subject_type="business",
        campaign_intent_candidate="store_opening",
        ad_format_candidate="poster",
        tone_candidates=["premium"],
        mood_candidates=["elegant"],
        evidence_items=[
            _evidence("business_candidate", "beauty"),
            _evidence("advertised_subject", "프리미엄 뷰티샵"),
            _evidence("advertised_subject_type", "business"),
            _evidence("campaign_intent_candidate", "store_opening"),
            _evidence("ad_format_candidate", "poster"),
            _evidence("tone_candidates", "premium"),
            _evidence("mood_candidates", "elegant"),
        ],
        confidence_by_field={"business_candidate": 0.92},
        ambiguity_flags=["beauty_subtype_ambiguous"],
        extraction_mode="deterministic_only",
    )

    assert result.business_candidate == "beauty"
    assert result.tone_candidates == ("premium",)
    assert result.mood_candidates == ("elegant",)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("business_candidate", 123),
        ("advertised_subject_type", True),
        ("tone_candidates", ["premium", 1]),
    ],
)
def test_intake_understanding_result_rejects_non_string_values(field_name: str, value: object):
    kwargs = {
        "advertised_subject": "뷰티샵",
        "advertised_subject_type": "business",
        "evidence_items": [
            _evidence("advertised_subject", "뷰티샵"),
            _evidence("advertised_subject_type", "business"),
        ],
        "extraction_mode": "deterministic_only",
    }
    kwargs[field_name] = value
    if field_name == "business_candidate":
        kwargs["evidence_items"].append(_evidence("business_candidate", "beauty"))
    if field_name == "tone_candidates":
        kwargs["evidence_items"].append(_evidence("tone_candidates", "premium"))

    with pytest.raises(ValidationError):
        IntakeUnderstandingResult(**kwargs)


def test_intake_understanding_result_requires_evidence_for_present_fields():
    with pytest.raises(ValidationError, match="business_candidate requires evidence"):
        IntakeUnderstandingResult(
            business_candidate="beauty",
            extraction_mode="deterministic_only",
        )
