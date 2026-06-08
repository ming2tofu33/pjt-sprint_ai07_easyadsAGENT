"""Node tracking wrapper and output schema map for per-node DB observability."""

from __future__ import annotations

from typing import Any, Callable

# LangGraph raises GraphInterrupt (an Exception subclass) when interrupt() fires
# inside an HITL node. This is normal control flow, NOT a node failure, so the
# wrapper must let it propagate without recording a failure row.
try:
    from langgraph.errors import GraphInterrupt as _GraphInterrupt

    _INTERRUPT_EXC: tuple[type[BaseException], ...] = (_GraphInterrupt,)
except Exception:  # pragma: no cover - older/newer langgraph without this path
    _INTERRUPT_EXC = ()

from orchestrator.app.graph.state import MarketingState, now_iso
from orchestrator.app.schemas.llm_marketing import (
    AdFormatSpec,
    CopyCandidateListOutput,
    CopyModeInferenceOutput,
    CopywritingOutput,
    FinalValidationReport as LLMFinalValidationReport,
    ImagePrompt,
    MarketingContext,
    MarketingCopy,
    OptionQuestion,
    PromptRenderOutput,
    ToneBindingOutput,
)
from orchestrator.app.schemas.text_layout import (
    BackgroundValidationReport,
    CopySpec,
    FinalValidationReport,
    ImagePromptSpec,
    ReadabilityReport,
    RenderResult,
    ResultPayload,
    SafeAreaReport,
    TextLayoutSpec,
    TextStyleSpec,
)
from orchestrator.app.t2i.schemas import T2IRequest, T2IResult
from orchestrator.eval.ops_db import OpsDBWriter

# Maps node_name → list of (field_name, SchemaClass | None).
# SchemaClass=None means: just check field is not None (no Pydantic validation).
NODE_OUTPUT_SCHEMAS: dict[str, list[tuple[str, type | None]]] = {
    "input": [
        ("job_id", None),
        ("thread_id", None),
        ("user_plan", None),
    ],
    "product_preprocess": [
        ("status", None),
    ],
    "reference_preprocess": [
        ("status", None),
    ],
    "validator": [
        ("context", MarketingContext),
        ("copy_mode_inference_output", CopyModeInferenceOutput),
        ("missing_fields", None),
    ],
    "options": [
        ("option_question", OptionQuestion),
    ],
    "state_update": [
        ("context", MarketingContext),
        ("revision", None),
    ],
    "format_planner": [
        ("ad_format_spec", AdFormatSpec),
    ],
    "tone_binding": [
        ("tone_binding_output", ToneBindingOutput),
    ],
    "copy_candidate_generation": [
        ("copy_candidates", None),
        # 이 노드는 copywriting_output에 CopyCandidateListOutput(candidates 목록)을 쓴다.
        # auto_pilot/copywriting 노드만 CopywritingOutput(marketing_copy)을 쓴다 — 같은 필드 다른 스키마.
        # 과거엔 CopywritingOutput으로 검증해 marketing_copy 누락으로 4건 실패(실은 정상 출력). fix.md 참고.
        ("copywriting_output", CopyCandidateListOutput),
    ],
    "copy_candidate_selection_interrupt": [
        ("status", None),
    ],
    "state_update_selected_copy": [
        ("marketing_copy", MarketingCopy),
    ],
    "auto_pilot_copywriting": [
        ("marketing_copy", MarketingCopy),
        ("copywriting_output", CopywritingOutput),
    ],
    "custom_copy_input": [
        ("status", None),
    ],
    "custom_copy_validation": [
        ("marketing_copy", MarketingCopy),
    ],
    "no_copy_bypass": [
        ("copy_generation_mode", None),
        ("status", None),
    ],
    "copy_spec_parser": [
        ("copy_spec", CopySpec),
    ],
    "text_style_binder": [
        ("text_style_spec", TextStyleSpec),
    ],
    "text_layout_planner": [
        ("text_layout_spec", TextLayoutSpec),
    ],
    "image_prompt_planner": [
        ("image_prompt_spec", ImagePromptSpec),
        ("image_prompt", ImagePrompt),
    ],
    "prompt_renderer": [
        ("prompt_render_output", PromptRenderOutput),
    ],
    "t2i_request_builder": [
        ("t2i_request", T2IRequest),
    ],
    "t2i_generation": [
        ("t2i_result", T2IResult),
    ],
    "background_validation": [
        ("background_validation_report", BackgroundValidationReport),
    ],
    "safe_area_gate": [
        ("safe_area_report", SafeAreaReport),
    ],
    "text_renderer": [
        ("render_result", RenderResult),
    ],
    "readability_gate": [
        ("readability_report", ReadabilityReport),
    ],
    "final_validation": [
        ("final_validation_report", FinalValidationReport),
    ],
    "reference_template_resolve": [
        ("reference_template_selection", None),
    ],
    "result": [
        ("result_payload", ResultPayload),
        ("status", None),
    ],
}


def make_tracking_wrapper(
    fn: Callable[[Any], dict[str, Any]],
    node_name: str,
    graph_name: str,
    db_writer: OpsDBWriter,
) -> Callable[[Any], dict[str, Any]]:
    schemas = NODE_OUTPUT_SCHEMAS.get(node_name, [])

    def wrapped(state: Any) -> dict[str, Any]:
        raw_state = state if isinstance(state, dict) else {}
        job_id: str | None = raw_state.get("job_id")
        thread_id: str | None = raw_state.get("thread_id")
        revision: int = raw_state.get("revision", 1) or 1
        llm_results_before: int = len(raw_state.get("llm_call_results") or [])

        started_at = now_iso()

        # The input node owns job-row creation. job_id may already be present (caller
        # passed a built MarketingState) or only appear after fn runs (caller passed an
        # InitialMarketingRequest). Either way the jobs row must exist before any
        # node_executions row is written, or the FK (foreign_keys=ON) fails. So for the
        # input node we always defer start_node until after the job row is inserted.
        is_input = node_name == "input"

        exec_id: int | None = None
        if not is_input:
            exec_id = db_writer.start_node(job_id, thread_id, revision, node_name, graph_name, started_at)

        try:
            result = fn(state)
        except _INTERRUPT_EXC:
            # HITL interrupt — normal control flow, not a failure. Leave the row "started".
            raise
        except Exception as exc:
            if exec_id is not None:
                db_writer.fail_node(exec_id, job_id, started_at, str(exc))
            raise

        result_dict = result if isinstance(result, dict) else {}

        # Resolve actual job_id. For the input node the RESULT is the freshly initialized
        # state, so its job_id/thread_id are authoritative (create_initial_marketing_state
        # may mint new ids even when the caller passed some) — and that is what every
        # downstream node will carry, so the jobs row must use it. For all other nodes the
        # incoming state id is the stable one.
        if is_input:
            actual_job_id: str | None = result_dict.get("job_id") or job_id
            actual_thread_id: str | None = result_dict.get("thread_id") or thread_id
        else:
            actual_job_id = job_id or result_dict.get("job_id")
            actual_thread_id = thread_id or result_dict.get("thread_id")

        if is_input and actual_job_id:
            merged = {**raw_state, **result_dict}
            db_writer.insert_job(actual_job_id, merged)
            exec_id = db_writer.start_node(actual_job_id, actual_thread_id, revision, node_name, graph_name, started_at)

        if exec_id is not None:
            db_writer.complete_node(exec_id, actual_job_id, started_at, result_dict)

            if schemas:
                db_writer.validate_outputs(exec_id, actual_job_id, node_name, result_dict, schemas)

            # Diff-detect new LLM call results — no changes to node_runner.py needed
            all_results: list[dict] = result_dict.get("llm_call_results") or []
            new_results = all_results[llm_results_before:]
            if new_results:
                db_writer.write_llm_calls(exec_id, actual_job_id, actual_thread_id, node_name, new_results)

            # Cost summary + final job status on result_node
            if node_name == "result" and actual_job_id:
                merged = {**raw_state, **result_dict}
                db_writer.insert_cost_summary(actual_job_id, merged)
                db_writer.update_job_status(actual_job_id, result_dict.get("status", "done"))

            # Dirty field event on state_update_node
            if node_name == "state_update" and actual_job_id:
                changed = result_dict.get("changed_fields") or []
                if not changed:
                    # state_update_node no longer emits changed_fields — derive from
                    # incoming user_selection which always carries the field name.
                    sel = raw_state.get("user_selection") or {}
                    if isinstance(sel, dict) and sel.get("field"):
                        changed = [sel["field"]]
                    elif hasattr(sel, "field") and sel.field:
                        changed = [sel.field]
                dirty = result_dict.get("dirty_fields") or []
                if changed or dirty:
                    db_writer.insert_dirty_event(actual_job_id, actual_thread_id, revision, changed, dirty)

        return result

    wrapped.__name__ = fn.__name__
    wrapped.__qualname__ = fn.__qualname__
    return wrapped
