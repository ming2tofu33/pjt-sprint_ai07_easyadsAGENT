import json

from PIL import Image

from orchestrator.app.ocr_gate.adapters.local_http import LocalHTTPOCRAdapter
from orchestrator.app.ocr_gate.adapters.stub import FakeOCRAdapter, StubOCRAdapter
from orchestrator.app.ocr_gate.schemas import OCRSpan


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps({"spans": [{"text": "SALE", "confidence": 0.9, "box": {"x1": 1, "y1": 2, "x2": 3, "y2": 4}}]}).encode("utf-8")


def test_stub_adapter_unavailable():
    result = StubOCRAdapter().extract_text(image_path="x.png", stage="background")

    assert result.status == "unavailable"


def test_fake_adapter_uses_spans():
    span = OCRSpan(text="SALE", normalized_text="sale", confidence=0.9)

    assert FakeOCRAdapter([span]).extract_text(image_path="x.png", stage="background").spans == [span]


def test_local_http_payload_includes_image_data(monkeypatch, tmp_path):
    captured = {}
    image_path = tmp_path / "fixture.png"
    Image.new("RGB", (4, 4), "white").save(image_path)

    def fake_urlopen(req, timeout):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr("orchestrator.app.ocr_gate.adapters.local_http.urlrequest.urlopen", fake_urlopen)
    result = LocalHTTPOCRAdapter(endpoint="http://localhost:1/ocr").extract_text(image_path=str(image_path), stage="background")

    assert captured["body"]["image"].startswith("data:image/png;base64,")
    assert captured["body"]["stage"] == "background"
    assert result.status == "ok"

