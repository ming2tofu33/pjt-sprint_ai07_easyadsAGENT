from typing import get_args

import pytest
from pydantic import ValidationError

from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.schemas import llm_marketing as schema


def test_copy_generation_mode_literal_and_initial_request_fields():
    assert set(get_args(schema.CopyGenerationMode)) == {"suggest_candidates", "auto_pilot", "no_copy", "custom_input"}

    request = schema.InitialMarketingRequest(user_input="ready", copy_generation_mode="no_copy")
    state = create_initial_marketing_state(request)

    assert state["copy_generation_mode"] == "no_copy"
    assert state["copy_required"] is False
    assert state["text_overlay_pending"] is False


def test_copy_mode_related_schema_models_validate():
    candidate = schema.CopyCandidate(id="copy_1", headline="오늘의 메뉴")
    output = schema.CopyCandidateListOutput(candidates=[candidate], recommended_candidate_id="copy_1")
    custom = schema.CustomCopyInput(headline="직접 쓴 문구")
    tone = schema.ToneBindingOutput(tone_profile="warm", forbidden_claims=["no phone"])
    inference = schema.CopyModeInferenceOutput(copy_generation_mode="auto_pilot", confidence=0.8, source="heuristic")

    assert output.generation_mode == "suggest_candidates"
    assert custom.headline == "직접 쓴 문구"
    assert tone.tone_profile == "warm"
    assert inference.confidence == 0.8
    with pytest.raises(ValidationError):
        schema.CopyModeInferenceOutput(copy_generation_mode="auto_pilot", confidence=1.5, source="heuristic")
