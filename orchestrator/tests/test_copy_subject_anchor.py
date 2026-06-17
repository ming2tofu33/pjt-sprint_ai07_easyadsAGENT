from __future__ import annotations

import pytest

from orchestrator.app.llm.copy_fallbacks import generate_fallback_candidates
from orchestrator.app.llm.copy_recommendation_lineage import build_copy_input_projection
from orchestrator.app.llm.copy_subject_anchor import resolve_copy_subject_anchor
from orchestrator.app.schemas.llm_marketing import MarketingContext


def _state(
    *,
    item_or_service: str | None = None,
    advertised_subject: str | None = "Beauty Salon",
    rejected_item_candidate: str | None = None,
    rejection_reason: str | None = None,
    user_input: str = "Create a premium opening poster for a Beauty Salon.",
    campaign_intent: str = "store_opening",
) -> dict:
    return {
        "user_input": user_input,
        "context": {
            "business_type": "beauty",
            "item_or_service": item_or_service,
            "extra": {
                "advertised_subject": advertised_subject,
                "business_phrase": advertised_subject,
                "rejected_item_candidate": rejected_item_candidate,
                "rejection_reason": rejection_reason,
                "intake_evidence_refs": ["user_input"],
            },
        },
        "current_brief": {
            "advertised_subject": advertised_subject,
            "advertised_subject_type": "business",
            "campaign_intent": campaign_intent,
        },
        "validator_metadata": {
            "intake_understanding": {
                "rejected_item_candidate": rejected_item_candidate,
                "rejection_reason": rejection_reason,
                "evidence_refs": ["user_input"],
                "source_text": user_input,
            }
        },
    }


def test_contaminated_item_uses_advertised_subject_anchor():
    anchor = resolve_copy_subject_anchor(
        _state(item_or_service="Create a premium opening poster for a Beauty Salon.")
    )

    assert anchor.value == "Beauty Salon"
    assert anchor.source == "advertised_subject"
    assert anchor.evidence_refs == ("user_input",)


def test_normal_item_uses_item_anchor():
    anchor = resolve_copy_subject_anchor(
        _state(item_or_service="signature facial care", campaign_intent="new_service_launch")
    )

    assert anchor.value == "signature facial care"
    assert anchor.source == "item_or_service"


def test_business_level_subject_conflict_uses_advertised_subject():
    anchor = resolve_copy_subject_anchor(_state(item_or_service="Beauty Salon"))

    assert anchor.value == "Beauty Salon"
    assert anchor.source == "advertised_subject"


def test_direct_marketing_context_input_uses_resolver():
    context = MarketingContext(
        business_type="retail",
        item_or_service="Notion",
        extra={"intake_evidence_refs": ["context"]},
    )

    anchor = resolve_copy_subject_anchor(context)

    assert anchor.value == "Notion"
    assert anchor.source == "item_or_service"


def test_plain_context_dict_input_uses_resolver():
    anchor = resolve_copy_subject_anchor({"business_type": "retail", "item_or_service": "Adidas"})

    assert anchor.value == "Adidas"
    assert anchor.source == "item_or_service"


def test_whole_prompt_candidate_is_blocked():
    source = "Create a bright banner ad for salad aimed at office workers in Gangnam."
    anchor = resolve_copy_subject_anchor(
        _state(
            item_or_service=source,
            advertised_subject=None,
            rejected_item_candidate=source,
            rejection_reason="whole_prompt_candidate",
            user_input=source,
        )
    )

    assert anchor.value is None
    assert anchor.source == "generic_safe_fallback"
    assert anchor.validation_status == "rejected"


def test_rejected_item_not_used_in_final_fallback_candidates():
    state = _state(
        item_or_service="Create a premium opening poster for a Beauty Salon.",
        rejected_item_candidate="Create a premium opening poster for a Beauty Salon.",
        rejection_reason="request_residue",
    )
    candidates = generate_fallback_candidates(state)
    joined = " ".join(" ".join(filter(None, [candidate.headline, candidate.subcopy, candidate.cta])) for candidate in candidates)

    assert "Create a premium opening poster" not in joined
    assert "Beauty Salon" in joined


@pytest.mark.parametrize("item", ["Notion", "Adidas", "salad"])
def test_safe_brand_and_product_names_are_allowed(item):
    anchor = resolve_copy_subject_anchor(
        _state(item_or_service=item, campaign_intent="new_product_launch", advertised_subject=None)
    )

    assert anchor.value == item
    assert anchor.source == "item_or_service"


def test_lineage_reports_anchor_source_evidence_and_reason():
    projection = build_copy_input_projection(
        _state(
            item_or_service="Create a premium opening poster for a Beauty Salon.",
            rejected_item_candidate="Create a premium opening poster for a Beauty Salon.",
            rejection_reason="request_residue",
        )
    )

    assert projection["copy_subject_anchor"] == "Beauty Salon"
    assert projection["copy_subject_source"] == "advertised_subject"
    assert projection["copy_subject_evidence_refs"] == ["user_input"]
    assert projection["copy_subject_validation_status"] == "accepted"
    assert projection["copy_subject_rejection_reason"] == "request_residue"
