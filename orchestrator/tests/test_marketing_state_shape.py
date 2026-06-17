"""Characterization guard for the MarketingState field surface.

Locks the exact set of 173 fields so the sub-state reorganization cannot
silently drop, rename, duplicate, or re-type a field.
"""

from orchestrator.app.graph.state import MarketingState

EXPECTED_FIELDS = frozenset({
    # job meta / routing / accounting
    "schema_version", "job_id", "thread_id", "usage_job_db_id", "usage_thread_db_id",
    "workspace_id", "project_id", "user_id", "organization_id", "user_plan",
    "plan_policy", "model_selections", "llm_call_results", "revision", "status",
    "entry_mode", "generation_route", "engine", "render_profile", "progress_state",
    # intake / brief / product understanding
    "user_input", "prompt_json", "messages", "conversation_summary", "current_brief",
    "dirty_fields", "user_selection", "image_input", "reference_input", "source_asset_id",
    "reference_asset_id", "source_image_path", "reference_image_path", "input_evidence_bundle",
    "input_normalization_status", "input_conflicts", "unresolved_questions", "intake_understanding_result",
    "intake_extraction_trace", "product_understanding",
    "product_understanding_status", "product_understanding_confidence",
    "product_understanding_provider_metadata", "vision_preprocess_mode",
    # reference templates / vision preprocess
    "selected_reference_template_id", "selected_reference_template", "reference_template_selection",
    "vision_pipeline_results", "image_preprocess_result", "image_features",
    "reference_style_profile", "product_preserve_spec", "reference_style",
    # context / validation / options
    "context", "campaign_context", "intake_question_policy_decision", "validator_output", "missing_fields", "option_question",
    # copy
    "ad_format_spec", "layout_spec", "marketing_copy", "copywriting_output", "copy_generation_mode",
    "copy_candidates", "copy_candidate_origin", "selected_copy_id", "selected_channel_id",
    "selected_ad_format", "selected_tone", "custom_direction", "user_custom_headline",
    "user_custom_subcopy", "copy_required", "text_overlay_pending", "tone_binding_output",
    "copy_mode_inference_output", "copy_selection", "input_compliance_risk", "copy_compliance",
    "copy_compliance_status", "copy_compliance_publication_ready", "copy_compliance_gate",
    "copy_compliance_resolution", "custom_copy_input", "copy_spec", "text_layout_spec",
    "text_style_spec", "copy_visual_intent", "product_copy_context", "copy_presence_plan",
    "language_policy", "interaction_copy_plan", "minimal_copy_candidates",
    "selected_minimal_copy_candidate_id",
    # native creative
    "creative_execution_plan", "native_typography_eligibility", "approved_native_copy_brief",
    "format_approved_plan_bundle", "flyer_approved_copy_plan",
    "flyer_promotional_approved_copy_plan", "product_detail_approved_feature_plan",
    "native_source_visual_analysis", "native_creative_prompt_package",
    "native_creative_preflight_review", "native_generation_budget", "native_generation_result",
    "native_generation_review", "native_generation_status",
    # typography / layout refinement
    "typography_art_direction", "font_catalog_summary", "adaptive_typography_report",
    "image_layout_analysis", "layout_candidate_scores", "layout_refinement_result",
    "layout_copy_fit_report", "layout_revision_attempts",
    # image prompt / t2i
    "image_prompt_spec", "image_prompt", "prompt_optimization_output", "user_readable_image_guide",
    "prompt_render_output", "t2i_request", "t2i_result",
    # quality / ocr gates / candidates
    "background_quality_gate", "final_quality_gate", "quality_gate_attempts",
    "quality_gate_decision", "quality_gate_status", "quality_gate_retry_feedback",
    "background_ocr_gate", "final_ocr_gate", "ocr_gate_decision", "ocr_gate_status",
    "ocr_gate_retry_feedback", "ocr_revision_action", "ocr_revision_attempts",
    "regeneration_patch", "candidates", "selected_candidate_id",
    # render / validation / finalize
    "background_validation_report", "safe_area_report", "readability_report", "render_result",
    "text_overlay_config", "final_image_path", "final_validation_report",
    "final_composite_quality_report", "final_composite_revision_plan", "final_composite_revision_patch",
    "final_composite_retry_feedback", "final_composite_partial_rerun", "final_composite_rerun_action",
    "reuse_existing_background", "final_copy_revision_result", "final_composite_attempts",
    "final_copy_revision_attempts", "final_layout_revision_attempts", "final_style_revision_attempts",
    "final_background_regeneration_attempts", "validation_report", "result_payload", "artifact_refs",
    "error_message", "error_info", "created_at", "updated_at", "latency_ms", "route",
    "image_analysis", "poster_layout_spec", "render_options", "renderer_mode",
})


def test_marketing_state_has_exactly_expected_fields():
    actual = set(MarketingState.__annotations__.keys())
    assert actual == EXPECTED_FIELDS, {
        "missing": EXPECTED_FIELDS - actual,
        "unexpected": actual - EXPECTED_FIELDS,
    }


def test_marketing_state_field_count_is_173():
    assert len(MarketingState.__annotations__) == 173


def test_marketing_state_all_keys_optional_under_total_false():
    # total=False semantics must survive the inheritance reassembly.
    assert MarketingState.__optional_keys__ == frozenset(MarketingState.__annotations__)
    assert MarketingState.__required_keys__ == frozenset()
