from __future__ import annotations

from pathlib import Path


PRIMARY_MARKERS = ("unit", "integration", "contract", "e2e")
TRAIT_MARKERS = (
    "regression",
    "external",
    "actual",
    "slow",
    "critical",
    "security",
    "transaction",
    "graph",
)
TAXONOMY_MARKERS = set(PRIMARY_MARKERS) | set(TRAIT_MARKERS)

E2E_FILES = {
    "test_canonical_actual_creative_pipeline.py",
    "test_final_composite_quality_loop.py",
    "test_image_prompt_v3_integration.py",
    "test_marketing_graph.py",
    "test_native_single_shot_graph.py",
    "test_tlfp_final_pipeline.py",
}

INTEGRATION_FILES = {
    "test_api_prefix_aliases.py",
    "test_api_routers.py",
    "test_archive.py",
    "test_asset_upload.py",
    "test_brand_kit_service.py",
    "test_chat_threads.py",
    "test_checkpointer_durable_resume.py",
    "test_final_selection_transaction.py",
    "test_generation_jobs.py",
    "test_generation_output_asset_persistence.py",
    "test_generation_outputs_repository_v1.py",
    "test_generation_outputs_service_v1.py",
    "test_graph_checkpointer.py",
    "test_image_aware_layout_graph.py",
    "test_input_evidence_graph_integration.py",
    "test_internal_auth_middleware.py",
    "test_langgraph_intake_graph.py",
    "test_langgraph_options_interrupt.py",
    "test_marketing_graph_singleton.py",
    "test_marketing_state_model_policy.py",
    "test_modal_services.py",
    "test_multiturn_state_api.py",
    "test_multiturn_state_restore.py",
    "test_product_understanding.py",
    "test_r2_storage.py",
    "test_reference_catalog_service.py",
    "test_regeneration.py",
    "test_usage_tracking.py",
    "test_validation_feedback.py",
    "test_validation_gates.py",
    "test_visual_text_to_image.py",
    "test_workspace_account_type_propagation.py",
    "test_workspaces_repository.py",
}

CONTRACT_FILES = {
    "test_agent_schema_imports.py",
    "test_db_settings.py",
    "test_final_composite_actual_script.py",
    "test_flux2_klein_modal_contract.py",
    "test_flux_local_lane_guard.py",
    "test_generation_interrupt_contract.py",
    "test_generation_stage_contract.py",
    "test_gpt_image_2_actual_lane_guard.py",
    "test_gpt_image2_engine.py",
    "test_gpt_image2_native_single_shot.py",
    "test_gpt_image2_quality_batch_script.py",
    "test_image_aware_layout_actual_script.py",
    "test_input_evidence_schemas.py",
    "test_multimodal_input_normalization_actual.py",
    "test_native_creative_schemas.py",
    "test_native_single_shot_actual_script.py",
    "test_openai_adapter_skeleton.py",
    "test_option_suggestion_schema.py",
    "test_reference_catalog_schema.py",
    "test_result_artifact_contract.py",
    "test_result_artifact_storage_contract.py",
    "test_sd35_adapter.py",
    "test_sd35_local_lane_guard.py",
    "test_smoke_generation_job_t2i_script.py",
    "test_smoke_llm_adapter.py",
    "test_storage_settings.py",
    "test_supabase_migration_schema.py",
    "test_text_layout_schema.py",
}

GRAPH_FILES = {
    "test_brief_interpreter_llm_v1.py",
    "test_canonical_actual_creative_pipeline.py",
    "test_chat_threads.py",
    "test_checkpointer_durable_resume.py",
    "test_dirty_field_propagation.py",
    "test_generation_jobs.py",
    "test_graph_checkpointer.py",
    "test_image_aware_layout_graph.py",
    "test_image_prompt_v3_integration.py",
    "test_input_evidence_graph_integration.py",
    "test_langgraph_intake_graph.py",
    "test_langgraph_options_interrupt.py",
    "test_langgraph_state.py",
    "test_langgraph_state_update.py",
    "test_marketing_graph.py",
    "test_marketing_graph_singleton.py",
    "test_marketing_state_model_policy.py",
    "test_multiturn_state_api.py",
    "test_multiturn_state_restore.py",
    "test_native_single_shot_graph.py",
    "test_regeneration.py",
    "test_tlfp_final_pipeline.py",
    "test_validation_feedback.py",
    "test_validation_gates.py",
    "test_visual_text_to_image.py",
}

SECURITY_FILES = {
    "test_api_prefix_aliases.py",
    "test_api_routers.py",
    "test_archive.py",
    "test_asset_upload.py",
    "test_chat_threads.py",
    "test_internal_auth_middleware.py",
    "test_r2_storage.py",
    "test_validation_feedback.py",
    "test_workspace_account_type_propagation.py",
    "test_workspaces_repository.py",
}

TRANSACTION_FILES = {
    "test_asset_upload.py",
    "test_final_selection_transaction.py",
    "test_generation_jobs.py",
    "test_generation_output_asset_persistence.py",
    "test_generation_outputs_repository_v1.py",
    "test_regeneration.py",
    "test_usage_tracking.py",
}

SLOW_FILES = E2E_FILES | {
    "test_marketing_graph_singleton.py",
    "test_validation_gates.py",
}

CRITICAL_FILES = {
    "test_compliance.py",
    "test_final_selection_transaction.py",
    "test_generation_jobs.py",
    "test_marketing_graph.py",
    "test_r2_storage.py",
    "test_regeneration.py",
    "test_usage_tracking.py",
    "test_validation_feedback.py",
    "test_validation_gates.py",
    "test_workspace_account_type_propagation.py",
}


def classify_primary(file_path: str, node_id: str) -> str:
    del node_id
    basename = Path(file_path).name
    if basename in E2E_FILES:
        return "e2e"
    if basename in INTEGRATION_FILES:
        return "integration"
    if basename in CONTRACT_FILES:
        return "contract"
    if "contract" in basename or "schema" in basename:
        return "contract"
    return "unit"


def classify_traits(file_path: str, node_id: str, primary: str) -> set[str]:
    basename = Path(file_path).name
    node_key = node_id.lower()
    traits: set[str] = set()

    if basename in GRAPH_FILES or any(
        token in node_key
        for token in (
            "graph",
            "resume",
            "interrupt",
            "snapshot",
            "checkpointer",
            "dirty_field",
            "state_restore",
        )
    ):
        traits.add("graph")

    if basename in SECURITY_FILES or any(
        token in node_key
        for token in (
            "workspace",
            "tenant",
            "scope",
            "cross_workspace",
            "secret",
            "auth",
            "path_traversal",
            "sanitize",
            "public_safe",
        )
    ):
        traits.update({"security", "critical"})

    if basename in TRANSACTION_FILES or any(
        token in node_key
        for token in (
            "transaction",
            "rollback",
            "idempot",
            "on_conflict",
            "upsert",
            "mark_final",
            "final_selection",
            "stale",
            "lineage",
        )
    ):
        traits.update({"transaction", "critical"})

    if basename in CRITICAL_FILES or any(
        token in node_key
        for token in (
            "fail_closed",
            "fail-closed",
            "quality_gate",
            "compliance",
            "budget",
            "selection",
            "snapshot",
            "resume",
        )
    ):
        traits.add("critical")

    if basename in SLOW_FILES or primary == "e2e":
        traits.add("slow")

    return traits


def classify_node(file_path: str, node_id: str) -> tuple[str, set[str]]:
    primary = classify_primary(file_path, node_id)
    traits = classify_traits(file_path, node_id, primary)
    return primary, traits


def taxonomy_marker_names(mark_names: list[str]) -> list[str]:
    return [name for name in mark_names if name in TAXONOMY_MARKERS]


def build_invariant_violations(record: dict[str, object]) -> list[str]:
    primary = list(record["primary_markers"])
    traits = set(record["trait_markers"])
    violations: list[str] = []

    if len(primary) == 0:
        violations.append("missing_primary_marker")
    if len(primary) > 1:
        violations.append("multiple_primary_markers")
    if "actual" in traits and "external" not in traits:
        violations.append("actual_without_external")
    if "actual" in traits and "slow" not in traits:
        violations.append("actual_without_slow")
    if "security" in traits and "critical" not in traits:
        violations.append("security_without_critical")
    if "transaction" in traits and "critical" not in traits:
        violations.append("transaction_without_critical")
    if "external" in traits and primary == ["unit"]:
        violations.append("external_marked_unit")
    if "e2e" in primary and "unit" in primary:
        violations.append("e2e_with_unit")
    return violations
