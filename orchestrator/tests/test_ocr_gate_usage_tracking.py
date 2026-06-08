from orchestrator.app.ocr_gate.adapters.stub import FakeOCRAdapter, StubOCRAdapter
from orchestrator.app.ocr_gate.schemas import OCRSpan, OCRValidationRequest
from orchestrator.app.ocr_gate.service import run_ocr_gate


def test_stub_and_fake_usage_not_recorded(monkeypatch):
    calls = []
    monkeypatch.setattr("orchestrator.app.ocr_gate.service.usage_service.record_llm_usage", lambda **kwargs: calls.append(kwargs))

    run_ocr_gate(request=OCRValidationRequest(stage="background", image_path="x.png"), adapter=StubOCRAdapter(), workspace_id="w")
    run_ocr_gate(request=OCRValidationRequest(stage="background", image_path="x.png"), adapter=FakeOCRAdapter([]), workspace_id="w")

    assert calls == []


def test_actual_provider_usage_recorded(monkeypatch):
    calls = []
    monkeypatch.setattr("orchestrator.app.ocr_gate.service.usage_service.record_llm_usage", lambda **kwargs: calls.append(kwargs))

    class ActualAdapter:
        provider = "local_http_ocr"

        def extract_text(self, *, image_path, stage):
            from orchestrator.app.ocr_gate.schemas import OCRExtractionResult

            return OCRExtractionResult(provider=self.provider, status="ok", spans=[OCRSpan(text="SALE", normalized_text="sale", confidence=0.9)])

    run_ocr_gate(request=OCRValidationRequest(stage="background", image_path="x.png"), adapter=ActualAdapter(), workspace_id="w")

    assert calls[0]["task_name"] == "ocr_gate"
    assert calls[0]["provider"] == "local_http_ocr"

