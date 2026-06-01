"""Metadata builders for future LLM/VLM-capable nodes."""

from __future__ import annotations

import json
from typing import Any

from orchestrator.app.llm.metadata_contracts import (
    DO_NOT_INVENT_FIELDS,
    LLM_METADATA_SCHEMA_VERSION,
    NEGATIVE_TEXT_TERMS,
    LLMMetadataPayload,
    LLMMetadataTask,
    LLMMetadataTrace,
    sanitize_metadata,
)


PUBLIC_SUMMARY_CONSTRAINT_KEYS = (
    "render_text_in_image",
    "must_not_include_text",
    "text_overlay_pending",
    "copy_required",
    "do_not_invent",
    "no_user_unprovided_claims",
    "preserve_custom_input",
    "preserve_user_copy",
    "no_rewrite",
    "no_new_facts",
    "classify_only",
    "no_copy_rewrite",
)


def build_common_trace_metadata(state: dict[str, Any] | None, node_name: str) -> dict[str, Any]:
    source = state or {}
    return sanitize_metadata(
        {
            "schema_version": source.get("schema_version") or LLM_METADATA_SCHEMA_VERSION,
            "job_id": source.get("job_id"),
            "thread_id": source.get("thread_id"),
            "revision": source.get("revision"),
            "node_name": node_name,
        }
    )


def build_common_constraints_metadata(state: dict[str, Any] | None) -> dict[str, Any]:
    source = state or {}
    tone = _dict(source.get("tone_binding_output"))
    return sanitize_metadata(
        {
            "render_text_in_image": False,
            "must_not_include_text": True,
            "text_overlay_pending": bool(source.get("text_overlay_pending", True)),
            "copy_required": bool(source.get("copy_required", True)),
            "do_not_invent": list(DO_NOT_INVENT_FIELDS),
            "no_user_unprovided_claims": True,
            "forbidden_claims": tone.get("forbidden_claims", []),
            "channel_copy_rules": tone.get("channel_copy_rules", []),
            "copy_constraints": tone.get("copy_constraints", []),
        }
    )


def build_validator_metadata(state: dict[str, Any] | None) -> dict[str, Any]:
    source = state or {}
    return build_metadata_payload(
        source,
        node_name="validator",
        objective="Extract and validate MarketingContext from the current user input and brief.",
        output_schema="ValidatorOutput",
        available_state={
            "user_input": source.get("user_input"),
            "messages": source.get("messages", []),
            "current_brief": source.get("current_brief", {}),
            "context": source.get("context", {}),
            "prompt_json": source.get("prompt_json"),
            "image_features": source.get("image_features"),
            "reference_style_profile": source.get("reference_style_profile"),
        },
    )


def build_tone_binding_metadata(state: dict[str, Any] | None) -> dict[str, Any]:
    source = state or {}
    return build_metadata_payload(
        source,
        node_name="tone_binding",
        objective="Bind brand tone, copy constraints, and channel rules for downstream copy/image nodes.",
        output_schema="ToneBindingOutput",
        available_state={
            "context": source.get("context", {}),
            "ad_format_spec": source.get("ad_format_spec"),
            "layout_spec": source.get("layout_spec"),
            "copy_generation_mode": source.get("copy_generation_mode"),
            "copy_required": source.get("copy_required"),
            "text_overlay_pending": source.get("text_overlay_pending"),
            "selected_reference_template": source.get("selected_reference_template"),
            "reference_style_profile": source.get("reference_style_profile"),
            "product_preserve_spec": source.get("product_preserve_spec"),
        },
    )


def build_copy_mode_inference_metadata(state: dict[str, Any] | None, latest_user_input: str | None = None) -> dict[str, Any]:
    source = state or {}
    return build_metadata_payload(
        source,
        node_name="copy_mode_inference",
        objective="Classify the user's intended copy generation mode without changing copy text.",
        output_schema="CopyModeInferenceOutput",
        available_state={
            "latest_user_input": latest_user_input if latest_user_input is not None else source.get("user_input"),
            "user_input": source.get("user_input"),
            "messages": source.get("messages", []),
            "current_brief": source.get("current_brief", {}),
            "context": source.get("context", {}),
            "entry_mode": source.get("entry_mode"),
            "copy_generation_mode": source.get("copy_generation_mode"),
            "user_custom_headline": source.get("user_custom_headline"),
            "user_custom_subcopy": source.get("user_custom_subcopy"),
        },
        constraints={
            "allowed_copy_generation_modes": ["suggest_candidates", "auto_pilot", "no_copy", "custom_input"],
            "classify_only": True,
            "no_copy_rewrite": True,
        },
    )


def build_copy_generation_metadata(
    state: dict[str, Any] | None,
    node_name: str = "copy_generation",
    output_schema: Any = "CopyCandidateListOutput",
) -> dict[str, Any]:
    source = state or {}
    tone = _dict(source.get("tone_binding_output"))
    plan_policy = _dict(source.get("plan_policy"))
    return build_metadata_payload(
        source,
        node_name=node_name,
        objective="Generate or validate structured Korean advertising copy without inventing unprovided facts.",
        output_schema=output_schema,
        available_state={
            "context": source.get("context", {}),
            "ad_format_spec": source.get("ad_format_spec"),
            "layout_spec": source.get("layout_spec"),
            "tone_binding_output": tone,
            "plan_policy": {"max_candidates": plan_policy.get("max_candidates")},
            "copy_generation_mode": source.get("copy_generation_mode"),
            "current_brief": source.get("current_brief", {}),
            "messages": source.get("messages", []),
            "reference_style_profile": source.get("reference_style_profile"),
            "selected_reference_template": source.get("selected_reference_template"),
            "custom_copy_input": source.get("custom_copy_input"),
        },
        constraints={
            "forbidden_claims": tone.get("forbidden_claims", []),
            "channel_copy_rules": tone.get("channel_copy_rules", []),
            "copy_constraints": tone.get("copy_constraints", []),
            "preserve_custom_input": source.get("copy_generation_mode") == "custom_input",
        },
    )


def build_custom_copy_validation_metadata(state: dict[str, Any] | None) -> dict[str, Any]:
    source = state or {}
    return build_metadata_payload(
        source,
        node_name="custom_copy_validation",
        objective="Validate user-provided copy while preserving the user's original wording.",
        output_schema="MarketingCopy",
        available_state={
            "custom_copy_input": source.get("custom_copy_input"),
            "user_custom_headline": source.get("user_custom_headline"),
            "user_custom_subcopy": source.get("user_custom_subcopy"),
            "context": source.get("context", {}),
            "ad_format_spec": source.get("ad_format_spec"),
            "layout_spec": source.get("layout_spec"),
            "tone_binding_output": source.get("tone_binding_output"),
        },
        constraints={
            "preserve_user_copy": True,
            "no_rewrite": True,
            "no_new_facts": True,
        },
    )


def build_copy_spec_parser_metadata(state: dict[str, Any] | None) -> dict[str, Any]:
    source = state or {}
    return build_metadata_payload(
        source,
        node_name="copy_spec_parser",
        objective="Parse approved marketing copy into CopySpec roles without creating new facts.",
        output_schema="CopySpec",
        available_state={
            "marketing_copy": source.get("marketing_copy"),
            "copy_candidates": source.get("copy_candidates", []),
            "selected_copy_id": source.get("selected_copy_id"),
            "custom_copy_input": source.get("custom_copy_input"),
            "copy_generation_mode": source.get("copy_generation_mode"),
            "copy_required": source.get("copy_required"),
            "text_overlay_pending": source.get("text_overlay_pending"),
            "context": source.get("context", {}),
            "ad_format_spec": source.get("ad_format_spec"),
            "layout_spec": source.get("layout_spec"),
            "tone_binding_output": source.get("tone_binding_output"),
        },
        constraints={"no_new_facts": True},
    )


def build_image_prompt_planner_metadata(state: dict[str, Any] | None) -> dict[str, Any]:
    source = state or {}
    reserved_text_areas = _reserved_text_areas_from_state(source)
    return build_metadata_payload(
        source,
        node_name="image_prompt_planner",
        objective="Plan a text-free commercial background prompt while preserving reserved text areas.",
        output_schema="ImagePromptSpec",
        available_state={
            "context": source.get("context", {}),
            "ad_format_spec": source.get("ad_format_spec"),
            "layout_spec": source.get("layout_spec"),
            "copy_spec": source.get("copy_spec"),
            "text_style_spec": source.get("text_style_spec"),
            "text_layout_spec": source.get("text_layout_spec"),
            "reserved_text_areas": reserved_text_areas,
            "reference_style_profile": source.get("reference_style_profile"),
            "product_preserve_spec": source.get("product_preserve_spec"),
            "selected_reference_template": source.get("selected_reference_template"),
            "reference_template_selection": source.get("reference_template_selection"),
            "vision_pipeline_results": source.get("vision_pipeline_results", []),
            "engine": source.get("engine"),
            "render_profile": source.get("render_profile"),
        },
        constraints={
            "must_not_include_text": True,
            "negative_prompt_required_terms": list(NEGATIVE_TEXT_TERMS),
            "reserved_text_areas": reserved_text_areas,
        },
    )


def build_prompt_renderer_metadata(
    state: dict[str, Any] | None,
    requested_engine: str | None = None,
    effective_engine: str | None = None,
) -> dict[str, Any]:
    source = state or {}
    ad_format = _dict(source.get("ad_format_spec"))
    layout = _dict(source.get("layout_spec"))
    return sanitize_metadata(
        {
            "job_id": source.get("job_id"),
            "thread_id": source.get("thread_id"),
            "requested_engine": requested_engine or source.get("engine"),
            "effective_engine": effective_engine or requested_engine or source.get("engine"),
            "render_profile": source.get("render_profile"),
            "ad_format": ad_format.get("ad_format"),
            "platform": ad_format.get("platform"),
            "aspect_ratio": ad_format.get("aspect_ratio"),
            "copy_space": layout.get("copy_space"),
            "reserved_text_areas": _reserved_text_areas_from_state(source),
            "must_not_include_text": True,
            "negative_prompt_required_terms": list(NEGATIVE_TEXT_TERMS),
            "render_text_in_image": False,
            "text_overlay_pending": bool(source.get("text_overlay_pending", True)),
            "selected_reference_template_id": source.get("selected_reference_template_id"),
            "source_node": "prompt_renderer",
        }
    )


def build_t2i_request_metadata(
    state: dict[str, Any] | None,
    prompt_render_output: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = state or {}
    prompt_render = _dict(prompt_render_output or source.get("prompt_render_output"))
    context = _dict(source.get("context"))
    current_brief = _dict(source.get("current_brief"))
    reference_style_profile = source.get("reference_style_profile")
    product_preserve_spec = source.get("product_preserve_spec")
    selected_reference_template = source.get("selected_reference_template")
    reference_template_selection = source.get("reference_template_selection")
    template_style_hint = _dict(_dict(reference_template_selection).get("style_profile_hint"))
    vision_pipeline_enabled = bool(
        source.get("source_image_path")
        or source.get("reference_image_path")
        or source.get("vision_pipeline_results")
        or reference_style_profile
        or product_preserve_spec
        or selected_reference_template
    )
    input_image_paths = [path for path in [source.get("source_image_path")] if path]
    metadata = {
        "job_id": source.get("job_id"),
        "thread_id": source.get("thread_id"),
        "entry_mode": source.get("entry_mode"),
        "generation_route": source.get("generation_route"),
        "copy_generation_mode": source.get("copy_generation_mode"),
        "ad_format_spec": source.get("ad_format_spec"),
        "layout_spec": source.get("layout_spec"),
        "copy_spec": source.get("copy_spec"),
        "text_layout_spec": source.get("text_layout_spec"),
        "text_style_spec": source.get("text_style_spec"),
        "image_prompt_spec": source.get("image_prompt_spec"),
        "reserved_text_areas": _reserved_text_areas_from_state(source, prompt_render),
        "business_type": context.get("business_type"),
        "item_or_service": context.get("item_or_service"),
        "engine": source.get("engine"),
        "requested_engine": prompt_render.get("engine") or source.get("engine"),
        "render_profile": source.get("render_profile"),
        "must_not_include_text": True,
        "negative_prompt_required_terms": list(NEGATIVE_TEXT_TERMS),
        "render_text_in_image": False,
        "text_overlay_pending": bool(source.get("text_overlay_pending", True)),
        "tlfp_enabled": bool(source.get("image_prompt_spec")),
        "vision_pipeline_enabled": vision_pipeline_enabled,
        "source_image_path": source.get("source_image_path"),
        "reference_image_path": source.get("reference_image_path"),
        "reference_style_profile": reference_style_profile,
        "product_preserve_spec": product_preserve_spec,
        "selected_reference_template_id": source.get("selected_reference_template_id"),
        "selected_reference_template": selected_reference_template,
        "reference_template_selection": reference_template_selection,
        "selected_channel_id": source.get("selected_channel_id") or current_brief.get("selected_channel_id"),
        "selected_tone": source.get("selected_tone") or current_brief.get("selected_tone"),
        "custom_direction": source.get("custom_direction") or current_brief.get("custom_direction"),
        "reference_template_style_keywords": template_style_hint.get("style_keywords"),
        "reference_template_color_palette": template_style_hint.get("color_palette"),
        "reference_template_layout_hint": template_style_hint.get("layout_hint"),
        "reference_template_typography_hint": template_style_hint.get("typography_hint"),
        "source_node": "t2i_request_builder",
    }
    if input_image_paths:
        metadata["input_image_paths"] = input_image_paths
    return sanitize_metadata(metadata)


def build_background_validation_metadata(state: dict[str, Any] | None) -> dict[str, Any]:
    source = state or {}
    t2i_result = _dict(source.get("t2i_result"))
    t2i_request = _dict(source.get("t2i_request"))
    text_layout = _dict(source.get("text_layout_spec"))
    return build_metadata_payload(
        source,
        node_name="background_validation",
        objective="Prepare future VLM background validation inputs without performing OCR or VLM calls.",
        output_schema="BackgroundValidationReport",
        available_state={
            "image_paths": t2i_result.get("image_paths", []),
            "t2i_request_metadata": _dict(t2i_request.get("metadata")),
            "image_prompt_spec": source.get("image_prompt_spec"),
            "reserved_text_areas": text_layout.get("reserved_text_areas", []),
            "ad_format_spec": source.get("ad_format_spec"),
            "copy_generation_mode": source.get("copy_generation_mode"),
            "copy_required": source.get("copy_required"),
            "text_overlay_pending": source.get("text_overlay_pending"),
            "reference_style_profile": source.get("reference_style_profile"),
            "product_preserve_spec": source.get("product_preserve_spec"),
            "selected_reference_template": source.get("selected_reference_template"),
            "validation_questions": [
                "Does the image contain unintended text, numbers, logos, or watermarks?",
                "Are the reserved text areas sufficiently empty?",
                "Does the product invade the reserved text areas?",
                "Is the background quality suitable for a commercial ad?",
            ],
        },
        constraints={"ocr_or_vlm_called": False, "vlm_call_allowed": False},
    )


def build_final_validation_metadata(state: dict[str, Any] | None) -> dict[str, Any]:
    source = state or {}
    tone = _dict(source.get("tone_binding_output"))
    return build_metadata_payload(
        source,
        node_name="final_validation",
        objective="Prepare future VLM final creative validation inputs without performing OCR or VLM calls.",
        output_schema="FinalValidationReport",
        available_state={
            "final_image_path": source.get("final_image_path"),
            "render_result": source.get("render_result"),
            "copy_spec": source.get("copy_spec"),
            "marketing_copy": source.get("marketing_copy"),
            "text_layout_spec": source.get("text_layout_spec"),
            "text_style_spec": source.get("text_style_spec"),
            "ad_format_spec": source.get("ad_format_spec"),
            "background_validation_report": source.get("background_validation_report"),
            "safe_area_report": source.get("safe_area_report"),
            "readability_report": source.get("readability_report"),
            "forbidden_claims": tone.get("forbidden_claims", []),
            "copy_generation_mode": source.get("copy_generation_mode"),
            "validation_questions": [
                "Is the expected copy visible?",
                "Is there any extra or hallucinated text?",
                "Is readability sufficient?",
                "Do the product and text collide?",
                "Does the creative match the target format and channel?",
                "Does it contain any forbidden claim?",
            ],
        },
        constraints={"ocr_or_vlm_called": False, "vlm_call_allowed": False},
    )


def build_metadata_payload(
    state: dict[str, Any],
    node_name: str,
    objective: str,
    output_schema: Any,
    available_state: dict[str, Any],
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trace = LLMMetadataTrace(**build_common_trace_metadata(state, node_name))
    task = LLMMetadataTask(objective=objective, output_schema=_schema_name(output_schema))
    payload = LLMMetadataPayload(
        trace=trace,
        task=task,
        available_state=sanitize_metadata(available_state),
        constraints={**build_common_constraints_metadata(state), **sanitize_metadata(constraints or {})},
    )
    return sanitize_metadata(payload.to_metadata_dict())


def metadata_contract_to_prompt_json(metadata_contract: dict[str, Any] | None) -> str:
    """Serialize metadata contracts as stable JSON before embedding them in prompts."""
    sanitized = sanitize_metadata(metadata_contract or {})
    if not isinstance(sanitized, dict):
        sanitized = {}
    return json.dumps(sanitized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_metadata_contract_summary(metadata_contract: dict[str, Any] | None) -> dict[str, Any]:
    """Return a compact public-safe summary for domain output metadata."""
    contract = sanitize_metadata(metadata_contract or {})
    if not isinstance(contract, dict):
        contract = {}
    trace = _dict(contract.get("trace"))
    task = _dict(contract.get("task"))
    output_rules = _dict(contract.get("output_rules"))
    constraints = _dict(contract.get("constraints"))
    constraint_summary = {
        key: constraints[key]
        for key in PUBLIC_SUMMARY_CONSTRAINT_KEYS
        if key in constraints
    }
    return sanitize_metadata(
        {
            "schema_version": trace.get("schema_version"),
            "node_name": trace.get("node_name"),
            "output_schema": task.get("output_schema"),
            "structured_output_only": output_rules.get("structured_output_only"),
            "no_chain_of_thought": output_rules.get("no_chain_of_thought"),
            "constraints": constraint_summary,
        }
    )


def _schema_name(output_schema: Any) -> str:
    if isinstance(output_schema, str):
        return output_schema
    return getattr(output_schema, "__name__", str(output_schema))


def _dict(value: Any) -> dict[str, Any]:
    sanitized = sanitize_metadata(value or {})
    return sanitized if isinstance(sanitized, dict) else {}


def _reserved_text_areas_from_state(
    source: dict[str, Any],
    prompt_render_output: dict[str, Any] | None = None,
) -> list[Any]:
    prompt_render_metadata = _dict(_dict(prompt_render_output).get("metadata"))
    text_layout = _dict(source.get("text_layout_spec"))
    image_prompt = _dict(source.get("image_prompt_spec"))
    return (
        text_layout.get("reserved_text_areas")
        or prompt_render_metadata.get("reserved_text_areas")
        or image_prompt.get("reserved_text_areas")
        or []
    )
