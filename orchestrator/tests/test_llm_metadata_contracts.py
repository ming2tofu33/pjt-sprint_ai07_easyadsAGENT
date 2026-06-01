import json

from orchestrator.app.llm.metadata_builders import (
    build_background_validation_metadata,
    build_common_constraints_metadata,
    build_common_trace_metadata,
    build_copy_generation_metadata,
    build_copy_spec_parser_metadata,
    build_final_validation_metadata,
    build_image_prompt_planner_metadata,
    build_tone_binding_metadata,
    build_validator_metadata,
)
from orchestrator.app.llm.metadata_contracts import sanitize_metadata
from orchestrator.app.llm.node_runner import safe_metadata


def _sample_state():
    return {
        "schema_version": "llm_marketing_v1",
        "job_id": "job-1",
        "thread_id": "thread-1",
        "revision": 2,
        "context": {"business_type": "cafe", "item_or_service": "latte"},
        "ad_format_spec": {"ad_format": "instagram_feed", "width": 1080, "height": 1080},
        "layout_spec": {"layout_type": "single_panel", "copy_space": "bottom"},
        "tone_binding_output": {
            "forbidden_claims": ["no phone"],
            "channel_copy_rules": ["short headline"],
            "copy_constraints": ["preserve facts"],
        },
        "plan_policy": {"max_candidates": 3},
        "copy_generation_mode": "suggest_candidates",
        "copy_required": True,
        "text_overlay_pending": True,
        "marketing_copy": {"headline": "Fresh latte"},
        "copy_spec": {"items": [{"role": "headline", "text": "Fresh latte"}]},
        "text_layout_spec": {
            "reserved_text_areas": [{"x": 0.05, "y": 0.1, "w": 0.9, "h": 0.2}],
        },
        "text_style_spec": {"profile": "clean"},
        "image_prompt_spec": {
            "reserved_text_areas": [{"x": 0.05, "y": 0.1, "w": 0.9, "h": 0.2}],
        },
        "t2i_request": {
            "metadata": {
                "render_text_in_image": False,
                "reserved_text_areas": [{"x": 0.05, "y": 0.1, "w": 0.9, "h": 0.2}],
            },
        },
        "t2i_result": {"image_paths": ["data/outputs/job-1/mock.png"]},
        "final_image_path": "data/outputs/job-1/final.png",
        "render_result": {"final_image_path": "data/outputs/job-1/final.png"},
        "background_validation_report": {"overall_pass": True},
        "safe_area_report": {"overall_pass": True},
        "readability_report": {"overall_pass": True},
    }


def _walk_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_keys(item)


def test_common_trace_includes_job_thread_and_node():
    trace = build_common_trace_metadata(_sample_state(), "tone_binding")

    assert trace["schema_version"] == "llm_marketing_v1"
    assert trace["job_id"] == "job-1"
    assert trace["thread_id"] == "thread-1"
    assert trace["revision"] == 2
    assert trace["node_name"] == "tone_binding"


def test_common_constraints_keep_text_free_policy_and_do_not_invent_list():
    constraints = build_common_constraints_metadata(_sample_state())

    assert constraints["render_text_in_image"] is False
    assert constraints["must_not_include_text"] is True
    assert {"phone", "address", "price", "discount", "event_period"} <= set(constraints["do_not_invent"])


def test_builders_return_json_serializable_payloads_when_state_is_empty():
    builders = [
        build_validator_metadata,
        build_tone_binding_metadata,
        build_copy_generation_metadata,
        build_copy_spec_parser_metadata,
        build_image_prompt_planner_metadata,
        build_background_validation_metadata,
        build_final_validation_metadata,
    ]

    for builder in builders:
        payload = builder({})
        assert set(payload) == {"trace", "task", "available_state", "constraints", "output_rules"}
        json.dumps(payload)


def test_payloads_do_not_store_hidden_reasoning_secrets_or_raw_image_bytes():
    state = {
        **_sample_state(),
        "current_brief": {
            "chain_of_thought": "private reasoning",
            "raw_reasoning": "private raw reasoning",
            "reasoning_summary": "short user-safe summary",
            "openai_api_key": "secret-key",
            "raw_image_bytes": b"not allowed",
        },
    }

    payload = build_validator_metadata(state)
    payload_text = json.dumps(payload)

    assert "private reasoning" not in payload_text
    assert "private raw reasoning" not in payload_text
    assert "secret-key" not in payload_text
    assert "not allowed" not in payload_text
    assert payload["available_state"]["current_brief"]["reasoning_summary"] == "short user-safe summary"
    assert "no_chain_of_thought" in payload["output_rules"]
    assert "chain_of_thought" not in set(_walk_keys(payload["available_state"]))


def test_node_runner_safe_metadata_uses_shared_sanitizer():
    metadata = safe_metadata(
        {
            "prompt": "full prompt should not be stored",
            "openai_api_key": "secret-key",
            "image_bytes": b"raw",
            "reasoning_summary": "ok",
        }
    )

    assert "prompt" not in metadata
    assert "openai_api_key" not in metadata
    assert "image_bytes" not in metadata
    assert metadata["reasoning_summary"] == "ok"


def test_sanitizer_preserves_usage_tokens_but_drops_secret_tokens():
    metadata = sanitize_metadata(
        {
            "token_usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
            "hf_token": "secret-token",
            "authorization": "Bearer secret",
        }
    )

    assert metadata["token_usage"]["prompt_tokens"] == 10
    assert metadata["token_usage"]["completion_tokens"] == 4
    assert metadata["token_usage"]["total_tokens"] == 14
    assert "hf_token" not in metadata
    assert "authorization" not in metadata


def test_sanitizer_redacts_unknown_objects_without_using_str_value():
    class SecretishObject:
        def __str__(self):
            return "secret-from-str"

    metadata = sanitize_metadata({"custom_object": SecretishObject()})

    assert metadata["custom_object"] == "[unsupported_metadata_value:SecretishObject]"
    assert "secret-from-str" not in json.dumps(metadata)


def test_image_prompt_planner_metadata_prefers_current_text_layout_reserved_areas():
    state = {
        **_sample_state(),
        "text_layout_spec": {
            "reserved_text_areas": [{"x": 0.1, "y": 0.2, "w": 0.7, "h": 0.2}],
        },
        "image_prompt_spec": {
            "reserved_text_areas": [{"x": 0.6, "y": 0.6, "w": 0.2, "h": 0.2}],
        },
    }

    payload = build_image_prompt_planner_metadata(state)

    assert payload["available_state"]["reserved_text_areas"] == [{"x": 0.1, "y": 0.2, "w": 0.7, "h": 0.2}]
    assert payload["constraints"]["reserved_text_areas"] == [{"x": 0.1, "y": 0.2, "w": 0.7, "h": 0.2}]


def test_copy_generation_metadata_accepts_node_specific_output_schema():
    payload = build_copy_generation_metadata(
        _sample_state(),
        node_name="auto_pilot_copywriting",
        output_schema="CopywritingOutput",
    )

    assert payload["trace"]["node_name"] == "auto_pilot_copywriting"
    assert payload["task"]["output_schema"] == "CopywritingOutput"


def test_image_and_validation_builders_include_future_vlm_contract_inputs():
    state = _sample_state()

    image_payload = build_image_prompt_planner_metadata(state)
    background_payload = build_background_validation_metadata(state)
    final_payload = build_final_validation_metadata(state)

    assert image_payload["available_state"]["text_layout_spec"]
    assert image_payload["constraints"]["reserved_text_areas"]
    assert "Hangul" in image_payload["constraints"]["negative_prompt_required_terms"]
    assert background_payload["available_state"]["image_paths"] == ["data/outputs/job-1/mock.png"]
    assert background_payload["constraints"]["ocr_or_vlm_called"] is False
    assert final_payload["available_state"]["final_image_path"] == "data/outputs/job-1/final.png"
    assert final_payload["available_state"]["forbidden_claims"] == ["no phone"]
