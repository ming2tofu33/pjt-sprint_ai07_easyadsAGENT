import pytest

from orchestrator.app.quality_gate.schemas import NormalizedBox, VLMQualityGateResult


def test_normalized_box_rejects_invalid_order():
    with pytest.raises(ValueError):
        NormalizedBox(x1=10, y1=10, x2=10, y2=20)


def test_quality_gate_result_has_no_raw_response_field():
    result = VLMQualityGateResult(stage="background", provider="deterministic", model_name="rule_based_v1")

    dumped = result.model_dump()
    assert "raw_response" not in dumped
    assert "chain_of_thought" not in dumped

