from orchestrator.app.ocr_gate.persistence import build_ocr_event_payload, build_ocr_gate_payload, event_type_for_ocr_result
from orchestrator.app.llm.nodes.result import result_node


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
