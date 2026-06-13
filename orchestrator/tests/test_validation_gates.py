"""Consolidated tests (real physical merge of source files).

Merged from:
- orchestrator/tests/test_ocr_gate_adapters.py
- orchestrator/tests/test_ocr_gate_background.py
- orchestrator/tests/test_ocr_gate_final_ad.py
- orchestrator/tests/test_ocr_gate_graph_integration.py
- orchestrator/tests/test_ocr_gate_persistence.py
- orchestrator/tests/test_ocr_gate_schemas.py
- orchestrator/tests/test_ocr_gate_service.py
- orchestrator/tests/test_ocr_gate_smoke.py
- orchestrator/tests/test_ocr_gate_text_normalization.py
- orchestrator/tests/test_ocr_gate_usage_tracking.py
- orchestrator/tests/test_quality_gate_actual_smoke.py
- orchestrator/tests/test_quality_gate_graph_integration.py
- orchestrator/tests/test_quality_gate_ocr.py
- orchestrator/tests/test_quality_gate_openai_adapter.py
- orchestrator/tests/test_quality_gate_policy.py
- orchestrator/tests/test_quality_gate_schemas.py
- orchestrator/tests/test_quality_gate_service.py
- orchestrator/tests/test_quality_gate_usage_tracking.py
"""


# ===== from test_ocr_gate_adapters.py =====
import json
from urllib.error import URLError

from PIL import Image

from orchestrator.app.ocr_gate.adapters.local_http import LocalHTTPOCRAdapter
from orchestrator.app.ocr_gate.adapters.stub import FakeOCRAdapter, StubOCRAdapter
from orchestrator.app.ocr_gate.schemas import OCRSpan
from orchestrator.tests.factories.validation_gate_payloads import make_normalized_box, make_ocr_span, make_ocr_validation_result
from orchestrator.tests.helpers.validation_gates import assert_validation_decision, assert_validation_status


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps({"spans": [{"text": "SALE", "confidence": 0.9, "box": {"x1": 1, "y1": 2, "x2": 3, "y2": 4}}]}).encode("utf-8")


def test_stub_adapter_unavailable():
    result = StubOCRAdapter().extract_text(image_path="x.png", stage="background")

    assert_validation_status(result, "unavailable")


def test_fake_adapter_uses_spans():
    span = make_ocr_span("SALE")

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
    assert_validation_status(result, "ok")


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

    assert_validation_status(result, "ok")
    assert [span.text for span in result.spans] == ["SALE"]


# ===== from test_ocr_gate_background.py =====
from orchestrator.app.ocr_gate.adapters.stub import FakeOCRAdapter, StubOCRAdapter
from orchestrator.app.ocr_gate.schemas import NormalizedBox, OCRSpan, OCRValidationRequest
from orchestrator.app.ocr_gate.service import run_ocr_gate
from orchestrator.app.ocr_gate.text_normalization import normalize_ocr_text


def _span(text, confidence=0.9):
    return make_ocr_span(text, confidence=confidence)


def test_background_no_text_passes():
    result = run_ocr_gate(request=OCRValidationRequest(stage="background", image_path="x.png"), adapter=FakeOCRAdapter([]))

    assert_validation_decision(result, "pass")


def test_background_sale_text_retries_image():
    result = run_ocr_gate(request=OCRValidationRequest(stage="background", image_path="x.png"), adapter=FakeOCRAdapter([_span("SALE 50%")]))

    assert result.fake_text is True
    assert_validation_decision(result, "retry_image")


def test_background_watermark_rejects():
    result = run_ocr_gate(request=OCRValidationRequest(stage="background", image_path="x.png"), adapter=FakeOCRAdapter([_span("SAMPLE")]))

    assert result.watermark_or_logo_text is True
    assert_validation_decision(result, "reject")


def test_stub_unavailable_manual_review():
    result = run_ocr_gate(request=OCRValidationRequest(stage="background", image_path="x.png"), adapter=StubOCRAdapter())

    assert_validation_status(result, "unavailable")
    assert_validation_decision(result, "manual_review")


def test_background_allows_known_brand_text():
    result = run_ocr_gate(
        request=OCRValidationRequest(stage="background", image_path="x.png", allow_brand_text=["EasyAds"]),
        adapter=FakeOCRAdapter([_span("EasyAds")]),
    )

    assert_validation_decision(result, "pass")


def test_tiny_ocr_area_is_filtered():
    tiny = make_ocr_span("SALE", confidence=0.99, box=make_normalized_box(1, 1, 2, 2))
    result = run_ocr_gate(request=OCRValidationRequest(stage="background", image_path="x.png"), adapter=FakeOCRAdapter([tiny]))

    assert_validation_decision(result, "pass")


# ===== from test_ocr_gate_final_ad.py =====
from orchestrator.app.ocr_gate.adapters.stub import FakeOCRAdapter
from orchestrator.app.ocr_gate.schemas import NormalizedBox, OCRSpan, OCRValidationRequest
from orchestrator.app.ocr_gate.service import run_ocr_gate
from orchestrator.app.ocr_gate.text_normalization import normalize_ocr_text


def _span__test_ocr_gate_final_ad(text, confidence=0.9):
    return make_ocr_span(text, confidence=confidence)


def _boxed_span(text, x1, y1, x2, y2, confidence=0.9):
    return make_ocr_span(text, confidence=confidence, box=make_normalized_box(x1, y1, x2, y2))


def test_final_expected_copy_matched_passes():
    request = OCRValidationRequest(stage="final_ad", image_path="x.png", expected_text=["여름 시즌 아이스라떼", "지금 주문하기"])

    result = run_ocr_gate(request=request, adapter=FakeOCRAdapter([_span__test_ocr_gate_final_ad("여름 시즌 아이스라떼"), _span__test_ocr_gate_final_ad("지금 주문하기")]))

    assert_validation_decision(result, "pass")


def test_final_missing_copy_retries_layout():
    request = OCRValidationRequest(stage="final_ad", image_path="x.png", expected_text=["여름 시즌 아이스라떼"])

    result = run_ocr_gate(request=request, adapter=FakeOCRAdapter([]))

    assert_validation_decision(result, "retry_layout")


def test_final_unexpected_extra_retries_image():
    request = OCRValidationRequest(stage="final_ad", image_path="x.png", expected_text=["여름 시즌 아이스라떼"])

    result = run_ocr_gate(request=request, adapter=FakeOCRAdapter([_span__test_ocr_gate_final_ad("여름 시즌 아이스라떼"), _span__test_ocr_gate_final_ad("SALE")]))

    assert_validation_decision(result, "retry_image")


def test_final_watermark_rejects():
    request = OCRValidationRequest(stage="final_ad", image_path="x.png", expected_text=["여름 시즌 아이스라떼"])

    result = run_ocr_gate(request=request, adapter=FakeOCRAdapter([_span__test_ocr_gate_final_ad("여름 시즌 아이스라떼"), _span__test_ocr_gate_final_ad("shutterstock")]))

    assert_validation_decision(result, "reject")


def test_expected_copy_can_match_split_ocr_spans():
    request = OCRValidationRequest(stage="final_ad", image_path="x.png", expected_text=["여름 시즌 아이스라떼"])

    result = run_ocr_gate(request=request, adapter=FakeOCRAdapter([_boxed_span("여름 시즌", 10, 10, 200, 80), _boxed_span("아이스라떼", 210, 10, 400, 80)]))

    assert_validation_decision(result, "pass")


def test_expected_copy_required_empty_text_manual_review():
    request = OCRValidationRequest(stage="final_ad", image_path="x.png", expected_text=[], expected_copy_required=True)

    result = run_ocr_gate(request=request, adapter=FakeOCRAdapter([]))

    assert_validation_decision(result, "manual_review")


def test_unexpected_text_priority_over_missing_copy():
    request = OCRValidationRequest(stage="final_ad", image_path="x.png", expected_text=["여름 시즌 아이스라떼"])

    result = run_ocr_gate(request=request, adapter=FakeOCRAdapter([_span__test_ocr_gate_final_ad("SALE")]))

    assert_validation_decision(result, "retry_image")


# ===== from test_ocr_gate_graph_integration.py =====
from orchestrator.app.llm.nodes.ocr_gate import background_ocr_gate_node, final_ocr_gate_node, ocr_image_revision_node, ocr_layout_revision_node
from orchestrator.app.ocr_gate.schemas import OCRValidationResult
from orchestrator.app.graph.builder import build_marketing_graph
from orchestrator.app.graph.routers import route_after_ocr_gate


def test_background_ocr_gate_state_update(monkeypatch):
    def fake_run_ocr_gate(**kwargs):
        return make_ocr_validation_result(provider="stub", status="unavailable", decision="manual_review", revision_action="manual_review")

    monkeypatch.setattr("orchestrator.app.llm.nodes.ocr_gate.run_ocr_gate", fake_run_ocr_gate)
    update = background_ocr_gate_node({"t2i_result": {"image_paths": ["background.png"]}, "user_plan": "free"})

    assert update["background_ocr_gate"]["decision"] == "manual_review"
    assert update["ocr_revision_action"] == "manual_review"


def test_final_ocr_gate_collects_expected_copy(monkeypatch):
    captured = {}

    def fake_run_ocr_gate(**kwargs):
        captured["request"] = kwargs["request"]
        return make_ocr_validation_result(stage="final_ad", decision="pass")

    monkeypatch.setattr("orchestrator.app.llm.nodes.ocr_gate.run_ocr_gate", fake_run_ocr_gate)
    update = final_ocr_gate_node({"final_image_path": "final.png", "copy_spec": {"headline": "여름 시즌 아이스라떼", "cta": "지금 주문하기"}})

    assert update["final_ocr_gate"]["decision"] == "pass"
    assert "여름 시즌 아이스라떼" in captured["request"].expected_text


def test_marketing_graph_registers_ocr_nodes():
    graph = build_marketing_graph()
    graph_data = graph.get_graph()
    node_names = {getattr(node, "id", None) for node in graph_data.nodes.values()} | set(graph_data.nodes)

    assert "background_ocr_gate" in node_names
    assert "final_ocr_gate" in node_names
    assert "ocr_image_revision" in node_names
    assert "ocr_layout_revision" in node_names


def test_revision_router_respects_feature_flag(monkeypatch):
    monkeypatch.setenv("EASYADS_OCR_REVISION_LOOP_ENABLED", "false")
    assert route_after_ocr_gate({"ocr_gate_decision": "retry_image", "ocr_revision_attempts": 0}) == "continue"

    monkeypatch.setenv("EASYADS_OCR_GATE_ENABLED", "true")
    monkeypatch.setenv("EASYADS_OCR_REVISION_LOOP_ENABLED", "true")
    monkeypatch.setenv("EASYADS_OCR_MAX_REVISIONS", "1")
    assert route_after_ocr_gate({"ocr_gate_decision": "retry_image", "ocr_revision_attempts": 0}) == "ocr_image_revision"
    assert route_after_ocr_gate({"ocr_gate_decision": "retry_image", "ocr_revision_attempts": 1}) == "manual_review_result"
    assert route_after_ocr_gate({"ocr_gate_decision": "retry_layout", "ocr_revision_attempts": 0}) == "ocr_layout_revision"
    assert route_after_ocr_gate({"ocr_gate_decision": "reject", "ocr_revision_attempts": 0}) == "rejected_result"
    assert route_after_ocr_gate({"ocr_gate_decision": "manual_review", "ocr_revision_attempts": 0}) == "manual_review_result"


def test_ocr_revision_nodes_mutate_state():
    image_update = ocr_image_revision_node(
        {
            "ocr_revision_attempts": 0,
            "ocr_gate_retry_feedback": ["remove fake text"],
            "t2i_request": {"prompt": "premium cafe", "negative_prompt": "blur", "seed": 10},
        }
    )
    assert image_update["ocr_revision_attempts"] == 1
    assert "no text" in image_update["t2i_request"]["prompt"]
    assert image_update["t2i_request"]["seed"] == 11

    layout_update = ocr_layout_revision_node(
        {
            "ocr_revision_attempts": 0,
            "text_layout_spec": {"safe_margin_ratio": 0.06, "slots": [{"inner_padding_ratio": 0.04, "max_lines": 2, "font_metric": {"base_size_ratio": 0.08}}]},
            "text_style_spec": {"typography": {"headline_size_ratio": 0.08}},
        }
    )
    assert layout_update["ocr_revision_attempts"] == 1
    assert layout_update["text_layout_spec"]["slots"][0]["max_lines"] == 3
    assert layout_update["text_style_spec"]["typography"]["headline_size_ratio"] < 0.08


def test_result_payload_marks_ocr_terminal_quality_state():
    from orchestrator.app.llm.nodes.result import result_node

    update = result_node(
        {
            "job_id": "job",
            "thread_id": "thread",
            "t2i_result": {"image_paths": ["background.png"]},
            "copy_generation_mode": "no_copy",
            "copy_required": False,
            "background_ocr_gate": {"stage": "background", "provider": "fake", "status": "fail", "decision": "reject", "revision_action": "reject"},
        }
    )
    payload = update["result_payload"]
    assert payload["qualityDecision"] == "reject"
    assert payload["qualityRejected"] is True
    assert payload["metadata"]["qualityRejected"] is True


def test_ocr_node_records_public_safe_event(monkeypatch):
    calls = []

    def fake_event(**kwargs):
        calls.append(kwargs)
        return {}

    def fake_run_ocr_gate(**kwargs):
        return OCRValidationResult(stage="background", provider="fake", status="fail", decision="retry_image", revision_action="retry_image", fake_text=True)

    monkeypatch.setattr("orchestrator.app.llm.nodes.ocr_gate.generation_job_event_repo.record_generation_job_event", fake_event)
    monkeypatch.setattr("orchestrator.app.llm.nodes.ocr_gate.run_ocr_gate", fake_run_ocr_gate)

    background_ocr_gate_node({"t2i_result": {"image_paths": ["x.png"]}, "workspace_id": "w", "usage_thread_db_id": "t", "usage_job_db_id": "j"})

    assert calls[0]["event_type"] == "ocr_gate_retry_requested"
    assert "base64" not in str(calls[0]["payload"]).lower()


# ===== from test_ocr_gate_persistence.py =====
from orchestrator.app.ocr_gate.persistence import build_ocr_event_payload, build_ocr_gate_payload, event_type_for_ocr_result


def test_ocr_gate_payload_excludes_raw_provider_fields():
    result = {"stage": "background", "provider": "fake", "status": "fail", "decision": "retry_image", "revision_action": "retry_image", "unexpected_text": [{"text": "SALE"}], "raw_response": {"secret": "x"}}

    payload = build_ocr_gate_payload(background=result)

    assert payload["background"]["unexpected_text_count"] == 1
    assert "raw_response" not in str(payload)


def test_event_payload_is_public_safe_summary():
    payload = build_ocr_event_payload({"stage": "final_ad", "provider": "fake", "status": "pass", "decision": "pass", "unexpected_text": [], "expected_matches": [{}]})

    assert payload["expected_match_count"] == 1
    assert "base64" not in str(payload).lower()


def test_overall_decision_uses_highest_severity():
    payload = build_ocr_gate_payload(
        background={"stage": "background", "provider": "fake", "status": "fail", "decision": "reject", "revision_action": "reject"},
        final={"stage": "final_ad", "provider": "fake", "status": "pass", "decision": "pass", "revision_action": "none"},
    )

    assert payload["decision"] == "reject"
    assert payload["revision_action"] == "reject"


def test_retry_image_beats_retry_layout():
    payload = build_ocr_gate_payload(
        background={"stage": "background", "provider": "fake", "status": "fail", "decision": "retry_image", "revision_action": "retry_image"},
        final={"stage": "final_ad", "provider": "fake", "status": "fail", "decision": "retry_layout", "revision_action": "retry_layout"},
    )

    assert payload["decision"] == "retry_image"
    assert payload["revision_action"] == "retry_image"


def test_unavailable_event_type_uses_status():
    assert event_type_for_ocr_result({"status": "unavailable", "decision": "manual_review"}) == "ocr_gate_unavailable"


def test_result_payload_contains_ocr_gate_summary():
    from orchestrator.app.llm.nodes.result import result_node

    update = result_node(
        {
            "job_id": "job",
            "thread_id": "thread",
            "t2i_result": {"image_paths": ["background.png"]},
            "copy_generation_mode": "no_copy",
            "copy_required": False,
            "background_ocr_gate": {"stage": "background", "provider": "fake", "status": "fail", "decision": "retry_image", "revision_action": "retry_image", "unexpected_text": [{"text": "SALE"}]},
        }
    )

    payload = update["result_payload"]
    assert payload["ocr_gate"]["decision"] == "retry_image"
    assert "background.png" not in str(payload["ocr_gate"])


# ===== from test_ocr_gate_schemas.py =====
import pytest
from pydantic import ValidationError

from orchestrator.app.ocr_gate.schemas import NormalizedBox, OCRSpan, OCRValidationResult
from orchestrator.app.ocr_gate.text_normalization import normalize_ocr_text


def test_ocr_span_and_bbox_schema():
    span = OCRSpan(text="SALE", normalized_text="sale", confidence=0.9, box=NormalizedBox(x1=1, y1=2, x2=3, y2=4))

    assert span.source == "ocr"


def test_invalid_bbox_is_rejected():
    with pytest.raises(ValidationError):
        NormalizedBox(x1=5, y1=2, x2=3, y2=4)


def test_decision_enum_rejects_unknown():
    with pytest.raises(ValidationError):
        OCRValidationResult(stage="background", provider="x", status="pass", decision="weird")


def test_raw_response_not_schema_field():
    result = OCRValidationResult(stage="background", provider="stub", status="unavailable", decision="manual_review")

    assert "raw_response" not in result.model_dump()
    assert normalize_ocr_text(" SALE 50%! ") == "sale50"


# ===== from test_ocr_gate_service.py =====
from orchestrator.app.ocr_gate.adapters.stub import FakeOCRAdapter, StubOCRAdapter
from orchestrator.app.ocr_gate.persistence import build_ocr_gate_payload, event_type_for_ocr_decision
from orchestrator.app.ocr_gate.schemas import OCRSpan, OCRValidationRequest
from orchestrator.app.ocr_gate.runtime_quality import aggregate_runtime_quality_decision
from orchestrator.app.ocr_gate.service import run_ocr_gate


def test_combined_payload_public_safe_summary():
    final = {"stage": "final_ad", "provider": "fake", "status": "fail", "decision": "retry_layout", "revision_action": "retry_layout", "unexpected_text": [], "expected_matches": [{}], "retry_feedback": ["bad"], "local_path": "hidden"}
    payload = build_ocr_gate_payload(final=final)

    assert payload["retry_required"] is True
    assert "local_path" not in str(payload)


def test_event_type_mapping():
    assert event_type_for_ocr_decision("retry_layout") == "ocr_gate_retry_requested"
    assert event_type_for_ocr_decision("reject") == "ocr_gate_rejected"
    assert event_type_for_ocr_decision("weird") == "ocr_gate_unavailable"


def test_unavailable_is_not_pass():
    result = run_ocr_gate(request=OCRValidationRequest(stage="final_ad", image_path="x.png"), adapter=StubOCRAdapter())

    assert result.decision == "manual_review"


def test_low_confidence_noise_filtered():
    result = run_ocr_gate(
        request=OCRValidationRequest(stage="background", image_path="x.png"),
        adapter=FakeOCRAdapter([OCRSpan(text="x", normalized_text="x", confidence=0.1)]),
    )

    assert result.decision == "pass"


def test_runtime_quality_rejects_ocr_watermark():
    ocr = run_ocr_gate(request=OCRValidationRequest(stage="background", image_path="x.png"), adapter=FakeOCRAdapter([OCRSpan(text="SAMPLE", normalized_text="sample", confidence=0.9)]))

    decision = aggregate_runtime_quality_decision(ocr_result=ocr, vlm_result={"decision": "pass"})

    assert decision.decision == "reject"


def test_runtime_quality_manual_when_ocr_and_vlm_unavailable():
    ocr = run_ocr_gate(request=OCRValidationRequest(stage="background", image_path="x.png"), adapter=StubOCRAdapter())

    decision = aggregate_runtime_quality_decision(ocr_result=ocr, vlm_result={"decision": "unavailable"})

    assert decision.decision == "manual_review"


def test_thresholds_are_clamped(monkeypatch):
    from orchestrator.app.ocr_gate import settings

    monkeypatch.setenv("EASYADS_OCR_EXPECTED_TEXT_MATCH_THRESHOLD", "2")
    monkeypatch.setenv("EASYADS_OCR_MALFORMED_TEXT_THRESHOLD", "3")
    monkeypatch.setenv("EASYADS_OCR_MIN_SPAN_CONFIDENCE", "-1")

    assert settings.get_expected_text_match_threshold() == 1.0
    assert settings.get_malformed_text_threshold() == 1.0
    assert settings.get_min_span_confidence() == 0.0


def test_local_http_provider_enabled_without_ocr_actual(monkeypatch):
    from orchestrator.app.ocr_gate.service import _build_adapter

    monkeypatch.setenv("EASYADS_OCR_GATE_ENABLED", "true")
    monkeypatch.setenv("EASYADS_OCR_PROVIDER", "local_http_ocr")
    monkeypatch.delenv("EASYADS_OCR_ACTUAL", raising=False)

    assert _build_adapter().provider == "local_http_ocr"


def test_unknown_provider_falls_back_to_stub(monkeypatch):
    from orchestrator.app.ocr_gate.service import _build_adapter

    monkeypatch.setenv("EASYADS_OCR_GATE_ENABLED", "true")
    monkeypatch.setenv("EASYADS_OCR_PROVIDER", "weird")

    assert _build_adapter().provider == "stub"


# ===== from test_ocr_gate_smoke.py =====
import json

from scripts import run_ocr_gate_smoke


def test_ocr_gate_smoke_writes_report(monkeypatch, tmp_path):
    monkeypatch.setattr(run_ocr_gate_smoke, "OUTPUT_DIR", tmp_path)

    assert run_ocr_gate_smoke.main([]) == 0
    report = json.loads((tmp_path / "ocr_gate_result.json").read_text(encoding="utf-8"))

    assert report["background"]["decision"] in {"retry_image", "reject"}
    assert report["final_ad"]["decision"] == "pass"
    assert report["actual_ocr"]["executed"] is False


# ===== from test_ocr_gate_text_normalization.py =====
from orchestrator.app.ocr_gate.text_normalization import normalize_ocr_text, text_similarity


def test_normalizes_korean_spacing_and_punctuation():
    assert normalize_ocr_text(" 여름  시즌\n아이스라떼! ") == "여름시즌아이스라떼"


def test_nfkc_and_casefold_preserve_digits():
    assert normalize_ocr_text("ＳＡＬＥ ５０％") == "sale50"


def test_similarity_threshold_helper():
    assert text_similarity("여름 시즌 아이스라떼", "여름시즌 아이스 라떼") > 0.72


# ===== from test_ocr_gate_usage_tracking.py =====
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


# ===== from test_quality_gate_actual_smoke.py =====
import os
import types

import pytest

from scripts import run_vlm_quality_gate_smoke as smoke


def test_vlm_quality_gate_smoke_rejects_modal_backend():
    args = types.SimpleNamespace(engine="flux2_klein_4b", backend="modal", actual=False)

    assert "modal_actual_forbidden_in_this_task" in smoke._missing_requirements(args)


def test_vlm_quality_gate_smoke_actual_requires_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("EASYADS_VLM_ACTUAL", raising=False)
    args = types.SimpleNamespace(engine="flux2_klein_4b", backend="local_diffusers", actual=True)

    assert "EASYADS_VLM_ACTUAL=1" in smoke._missing_requirements(args)


def test_vlm_quality_gate_smoke_redacts_secret_like_metadata():
    redacted = smoke._redact_metadata({"hf_token": "secret", "safe": "visible"})

    assert redacted["hf_token_present"] is True
    assert "secret" not in str(redacted)
    assert redacted["safe"] == "visible"


def test_quality_gate_actual_smoke_requires_opt_in():
    if os.getenv("EASYADS_VLM_ACTUAL") != "1":
        pytest.skip("actual smoke is opt-in")


# ===== from test_quality_gate_graph_integration.py =====
from orchestrator.app.llm.nodes.quality_gate import background_quality_gate_node


def test_background_quality_gate_node_serializes_state(monkeypatch):
    monkeypatch.setenv("EASYADS_VLM_GATE_ENABLED", "false")

    update = background_quality_gate_node({"final_image_path": "x.png", "user_plan": "free"})

    assert update["background_quality_gate"]["decision"] == "unavailable"
    assert update["quality_gate_decision"] == "unavailable"


# ===== from test_quality_gate_ocr.py =====
from orchestrator.app.quality_gate.ocr_validation import normalize_ocr_text as normalize_ocr_text__test_quality_gate_ocr, validate_ocr_text


def test_ocr_normalizes_korean_spacing_and_punctuation():
    assert normalize_ocr_text__test_quality_gate_ocr("딸기 라떼!") == normalize_ocr_text__test_quality_gate_ocr("딸기라떼")


def test_background_extra_text_fails():
    result = validate_ocr_text(expected_text=[], detected_text=["SALE 50%"])

    assert result.status == "fail"
    assert result.extra_text_count == 1


def test_final_copy_missing_expected_text():
    result = validate_ocr_text(expected_text=["딸기라떼 신메뉴"], detected_text=[])

    assert result.status == "fail"
    assert result.missing_text_count == 1


# ===== from test_quality_gate_openai_adapter.py =====
import json

from PIL import Image

from orchestrator.app.quality_gate.adapters.openai_compatible_vision import (
    OpenAICompatibleVisionAdapter,
    _build_payload,
)
from orchestrator.app.quality_gate.schemas import VLMQualityRequest


class FakeResponse__test_quality_gate_openai_adapter:
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


def test_openai_compatible_adapter_parses_compact_json(monkeypatch, tmp_path):
    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse__test_quality_gate_openai_adapter()

    monkeypatch.setattr("orchestrator.app.quality_gate.adapters.openai_compatible_vision.urlrequest.urlopen", fake_urlopen)

    image_path = tmp_path / "test-adapter.png"
    Image.new("RGB", (4, 4), "white").save(image_path)

    result = OpenAICompatibleVisionAdapter(base_url="http://localhost:1234/v1", model_name="local-vlm").inspect(
        image_path=str(image_path),
        request=VLMQualityRequest(stage="background", business_type="cafe"),
    )

    assert captured["url"] == "http://localhost:1234/v1/chat/completions"
    assert captured["body"]["messages"][0]["content"][1]["type"] == "image_url"
    assert result.provider == "local_openai_compat"
    assert result.decision == "pass"
    assert "raw" not in result.metadata


def test_openai_compatible_payload_avoids_chain_of_thought():
    payload = _build_payload(model="vlm", request=VLMQualityRequest(stage="final_ad", expected_text=["딸기라떼 신메뉴"]))
    text = payload["messages"][0]["content"][0]["text"]

    assert payload["response_format"] == {"type": "json_object"}
    assert "Do not include chain-of-thought" in text
    assert "딸기라떼 신메뉴" in text


# ===== from test_quality_gate_policy.py =====
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


# ===== from test_quality_gate_schemas.py =====
import pytest

from orchestrator.app.quality_gate.schemas import NormalizedBox as NormalizedBox__test_quality_gate_schemas, VLMQualityGateResult


def test_normalized_box_rejects_invalid_order():
    with pytest.raises(ValueError):
        NormalizedBox__test_quality_gate_schemas(x1=10, y1=10, x2=10, y2=20)


def test_quality_gate_result_has_no_raw_response_field():
    result = VLMQualityGateResult(stage="background", provider="deterministic", model_name="rule_based_v1")

    dumped = result.model_dump()
    assert "raw_response" not in dumped
    assert "chain_of_thought" not in dumped


# ===== from test_quality_gate_service.py =====
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


# ===== from test_quality_gate_usage_tracking.py =====
from orchestrator.app.quality_gate.schemas import VLMQualityGateResult, VLMQualityRequest
from orchestrator.app.quality_gate.service import run_quality_gate


class FakeAdapter__test_quality_gate_usage_tracking:
    def inspect(self, *, image_path, request):
        return VLMQualityGateResult(stage=request.stage, provider="local_openai_compat", model_name="qwen", decision="pass", overall_score=0.9, confidence=0.9)


def test_quality_gate_records_vlm_usage(monkeypatch):
    calls = []
    monkeypatch.setenv("EASYADS_VLM_GATE_ENABLED", "true")
    monkeypatch.setattr("orchestrator.app.quality_gate.service.usage_service.record_llm_usage", lambda **kwargs: calls.append(kwargs))

    run_quality_gate(
        image_path="x.png",
        request=VLMQualityRequest(stage="background", plan="premium"),
        local_adapter=FakeAdapter__test_quality_gate_usage_tracking(),
        workspace_id="ws",
        created_by="user",
        job_id="job_uuid",
        thread_id="thread_uuid",
    )

    assert calls[0]["task_name"] == "vlm_quality_gate"
    assert calls[0]["node_name"] == "background_quality_gate"
