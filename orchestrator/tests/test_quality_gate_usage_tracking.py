from orchestrator.app.quality_gate.schemas import VLMQualityGateResult, VLMQualityRequest
from orchestrator.app.quality_gate.service import run_quality_gate


class FakeAdapter:
    def inspect(self, *, image_path, request):
        return VLMQualityGateResult(stage=request.stage, provider="local_openai_compat", model_name="qwen", decision="pass", overall_score=0.9, confidence=0.9)


def test_quality_gate_records_vlm_usage(monkeypatch):
    calls = []
    monkeypatch.setenv("EASYADS_VLM_GATE_ENABLED", "true")
    monkeypatch.setattr("orchestrator.app.quality_gate.service.usage_service.record_llm_usage", lambda **kwargs: calls.append(kwargs))

    run_quality_gate(
        image_path="x.png",
        request=VLMQualityRequest(stage="background", plan="premium"),
        local_adapter=FakeAdapter(),
        workspace_id="ws",
        created_by="user",
        job_id="job_uuid",
        thread_id="thread_uuid",
    )

    assert calls[0]["task_name"] == "vlm_quality_gate"
    assert calls[0]["node_name"] == "background_quality_gate"

