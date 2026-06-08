import json

from orchestrator.app.quality_gate.adapters.openai_compatible_vision import (
    OpenAICompatibleVisionAdapter,
    _build_payload,
)
from orchestrator.app.quality_gate.schemas import VLMQualityRequest


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "decision": "pass",
                                    "overall_score": 0.9,
                                    "confidence": 0.9,
                                    "fake_text": {"status": "pass", "score": 0.9, "confidence": 0.9},
                                    "detected_text": [],
                                }
                            )
                        }
                    }
                ]
            }
        ).encode("utf-8")


def test_openai_compatible_adapter_parses_compact_json(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr("orchestrator.app.quality_gate.adapters.openai_compatible_vision.urlrequest.urlopen", fake_urlopen)

    result = OpenAICompatibleVisionAdapter(base_url="http://localhost:1234/v1", model_name="local-vlm").inspect(
        image_path="unused.png",
        request=VLMQualityRequest(stage="background", business_type="cafe"),
    )

    assert captured["url"] == "http://localhost:1234/v1/chat/completions"
    assert result.provider == "local_openai_compat"
    assert result.decision == "pass"
    assert "raw" not in result.metadata


def test_openai_compatible_payload_avoids_chain_of_thought():
    payload = _build_payload(model="vlm", request=VLMQualityRequest(stage="final_ad", expected_text=["딸기라떼 신메뉴"]))
    text = payload["messages"][0]["content"][0]["text"]

    assert payload["response_format"] == {"type": "json_object"}
    assert "Do not include chain-of-thought" in text
    assert "딸기라떼 신메뉴" in text
