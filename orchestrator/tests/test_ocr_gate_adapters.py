import json
from urllib.error import URLError

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


def test_local_http_file_missing_structured_error():
    result = LocalHTTPOCRAdapter(endpoint="http://localhost:1/ocr").extract_text(image_path="missing.png", stage="background")

    assert result.error_code == "ocr_input_not_found"


def test_local_http_connection_failed(monkeypatch, tmp_path):
    image_path = tmp_path / "fixture.png"
    Image.new("RGB", (4, 4), "white").save(image_path)
    monkeypatch.setattr("orchestrator.app.ocr_gate.adapters.local_http.urlrequest.urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(URLError("down")))

    result = LocalHTTPOCRAdapter(endpoint="http://localhost:1/ocr").extract_text(image_path=str(image_path), stage="background")

    assert result.error_code == "ocr_connection_failed"


def test_local_http_invalid_span_is_skipped(monkeypatch, tmp_path):
    class BadSpanResponse(FakeResponse):
        def read(self):
            return json.dumps({"spans": [{"text": "bad", "confidence": 9}, {"text": "SALE", "confidence": 0.9}]}).encode("utf-8")

    image_path = tmp_path / "fixture.png"
    Image.new("RGB", (4, 4), "white").save(image_path)
    monkeypatch.setattr("orchestrator.app.ocr_gate.adapters.local_http.urlrequest.urlopen", lambda *args, **kwargs: BadSpanResponse())

    result = LocalHTTPOCRAdapter(endpoint="http://localhost:1/ocr").extract_text(image_path=str(image_path), stage="background")

    assert result.status == "ok"
    assert [span.text for span in result.spans] == ["SALE"]
