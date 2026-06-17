from __future__ import annotations

from orchestrator.app.graph.nodes import _resolve_intake_understanding, validator_node
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.intake_understanding_service import _source_text_hash
from orchestrator.app.schemas.input_evidence import EvidenceItem
from orchestrator.app.schemas.intake_understanding import IntakeUnderstandingResult
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest


def _validate(prompt: str) -> dict:
    state = create_initial_marketing_state(InitialMarketingRequest(user_input=prompt))
    return validator_node(state)


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


def test_validator_marks_missing_business_without_forcing_item_or_service():
    result = _validate("Create a poster for our premium beauty salon opening.")

    assert result["context"]["business_type"] is None
    assert result["context"]["item_or_service"] is None
    assert "business_type" in result["missing_fields"]
    assert result["intake_understanding_result"]["advertised_subject_type"] == "business"


def test_validator_propagates_structured_fallback_trace_when_interpreter_is_unavailable():
    result = _validate("Need an ad.")

    assert result["intake_extraction_trace"]["fallback_used"] is True
    assert result["intake_extraction_trace"]["fallback_reason"] == "brief_interpreter_not_enabled"


def test_resolve_intake_reuses_cache_only_for_matching_source_hash(monkeypatch):
    prompt = "Create an ad for Harbor Cafe."
    state = create_initial_marketing_state(InitialMarketingRequest(user_input=prompt))
    cached_result = IntakeUnderstandingResult(
        business_candidate="cafe",
        advertised_subject="Harbor Cafe",
        advertised_subject_type="business",
        evidence_items=[
            _evidence("business_candidate", "cafe"),
            _evidence("advertised_subject", "Harbor Cafe"),
            _evidence("advertised_subject_type", "business"),
        ],
        extraction_mode="deterministic_only",
    )
    state["intake_understanding_result"] = cached_result.model_dump()
    state["intake_extraction_trace"] = {"source_text_hash": _source_text_hash(prompt)}

    reused_result, reused_trace = _resolve_intake_understanding(state, prompt)
    assert reused_result.business_candidate == "cafe"
    assert reused_trace["source_text_hash"] == _source_text_hash(prompt)

    calls = {"count": 0}

    def fake_understand_intake(*args, **kwargs):
        calls["count"] += 1
        fresh = IntakeUnderstandingResult(
            advertised_subject="Harbor Bakery",
            advertised_subject_type="business",
            evidence_items=[
                _evidence("advertised_subject", "Harbor Bakery"),
                _evidence("advertised_subject_type", "business"),
            ],
            extraction_mode="deterministic_only",
        )
        return fresh, {"source_text_hash": _source_text_hash("Create an ad for Harbor Bakery.")}

    monkeypatch.setattr("orchestrator.app.graph.nodes.understand_intake", fake_understand_intake)
    fresh_result, fresh_trace = _resolve_intake_understanding(state, "Create an ad for Harbor Bakery.")

    assert calls["count"] == 1
    assert fresh_result.advertised_subject == "Harbor Bakery"
    assert fresh_trace["source_text_hash"] == _source_text_hash("Create an ad for Harbor Bakery.")


def test_validator_surfaces_unprojected_campaign_intent_candidate():
    result = _validate("Grand opening poster for Harbor Bakery.")

    assert result["intake_understanding_result"]["campaign_intent_candidate"] == "store_opening"
    assert result["context"]["promotion_goal"] is None
    assert result["validator_metadata"]["intake_understanding"]["unprojected_campaign_intent_candidate"] == "store_opening"
