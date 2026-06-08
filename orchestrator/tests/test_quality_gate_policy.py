from orchestrator.app.quality_gate.policy import aggregate_quality_decision, should_call_api_deep
from orchestrator.app.quality_gate.schemas import QualityCheckResult, VLMQualityGateResult


def test_watermark_rejects():
    result = VLMQualityGateResult(
        stage="background",
        provider="deterministic",
        model_name="rule",
        watermark=QualityCheckResult(status="fail", score=0.95, confidence=0.9),
        decision="pass",
        confidence=0.9,
    )

    assert aggregate_quality_decision(result).decision == "reject"


def test_background_fake_text_retries():
    result = VLMQualityGateResult(
        stage="background",
        provider="deterministic",
        model_name="rule",
        fake_text=QualityCheckResult(status="fail", score=0.9, confidence=0.9),
        confidence=0.9,
    )

    assert aggregate_quality_decision(result).decision == "retry"


def test_plan_routing_free_never_calls_api():
    result = VLMQualityGateResult(stage="background", provider="local", model_name="m", decision="manual_review")

    assert should_call_api_deep(plan="free", stage="background", local_result=result) is False
    assert should_call_api_deep(plan="premium", stage="background", local_result=result) is True

