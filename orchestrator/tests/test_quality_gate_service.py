from orchestrator.app.quality_gate.schemas import QualityCheckResult, VLMQualityGateResult, VLMQualityRequest
from orchestrator.app.quality_gate.service import deterministic_gate, run_quality_gate


class FakeAdapter:
    def __init__(self, result):
        self.result = result

    def inspect(self, *, image_path, request):
        return self.result


def test_deterministic_gate_background_text_retries():
    result = deterministic_gate(request=VLMQualityRequest(stage="background"), detected_text=["SALE"])

    assert result.decision == "retry"
    assert result.fake_text.status == "fail"


def test_quality_gate_disabled_returns_unavailable(monkeypatch):
    monkeypatch.setenv("EASYADS_VLM_GATE_ENABLED", "false")

    result = run_quality_gate(image_path="x.png", request=VLMQualityRequest(stage="background"))

    assert result.decision == "unavailable"


def test_quality_gate_uses_adapter_when_enabled(monkeypatch):
    monkeypatch.setenv("EASYADS_VLM_GATE_ENABLED", "true")
    adapter_result = VLMQualityGateResult(
        stage="background",
        provider="local_openai_compat",
        model_name="vlm",
        copy_safe_area=QualityCheckResult(status="pass", score=1, confidence=1),
        decision="pass",
        overall_score=0.9,
        confidence=0.9,
    )

    result = run_quality_gate(image_path="x.png", request=VLMQualityRequest(stage="background"), local_adapter=FakeAdapter(adapter_result))

    assert result.provider == "local_openai_compat"
    assert result.decision == "pass"

