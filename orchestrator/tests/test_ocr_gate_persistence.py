from orchestrator.app.ocr_gate.persistence import build_ocr_event_payload, build_ocr_gate_payload


def test_ocr_gate_payload_excludes_raw_provider_fields():
    result = {"stage": "background", "provider": "fake", "status": "fail", "decision": "retry_image", "revision_action": "retry_image", "unexpected_text": [{"text": "SALE"}], "raw_response": {"secret": "x"}}

    payload = build_ocr_gate_payload(background=result)

    assert payload["background"]["unexpected_text_count"] == 1
    assert "raw_response" not in str(payload)


def test_event_payload_is_public_safe_summary():
    payload = build_ocr_event_payload({"stage": "final_ad", "provider": "fake", "status": "pass", "decision": "pass", "unexpected_text": [], "expected_matches": [{}]})

    assert payload["expected_match_count"] == 1
    assert "base64" not in str(payload).lower()

