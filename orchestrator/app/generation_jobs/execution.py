"""Deterministic GenerationJob execution bridge."""

from __future__ import annotations

from pathlib import Path
from shutil import copyfile
from typing import Any

from PIL import Image, ImageDraw

from orchestrator.app.artifacts.service import (
    build_result_artifact_payload,
    ensure_job_output_dir,
    get_job_output_dir,
    write_json_artifact,
)
from orchestrator.app.api.schemas.generation_jobs import (
    GenerationJobAnswerRequest,
    GenerationJobCreateRequest,
    GenerationJobResponse,
)
from orchestrator.app.generation_jobs.service import (
    append_generation_job_user_answer_message,
    get_generation_job,
    mark_generation_job_done,
    mark_generation_job_failed,
    mark_generation_job_modal_running,
    mark_generation_job_running,
)
from orchestrator.app.t2i.engines.base import T2IGenerationInput
from orchestrator.app.t2i.engines.registry import get_t2i_engine
from orchestrator.app.t2i.execution import TEXT_FREE_NEGATIVE_PROMPT, build_generation_job_prompt, prompt_summary
from orchestrator.app.t2i.settings import T2IEngineNotEnabledError, T2IEngineUnavailableError

_EFFECTIVE_RUN_MODE_BY_ENGINE = {
    "gpt_image_1": "gpt_image_1_actual",
    "gpt_image_2": "gpt_image_2_actual",
    "sd35_large": "sd35_local",
    "flux": "flux_local",
    "flux_local": "flux_local",
    "flux2_klein_4b": "flux2_klein_4b",
}

_CHANNEL_TO_AD_FORMAT = {
    "instagram-feed": "instagram_feed",
    "instagram-story": "instagram_story",
    "poster": "poster",
    "flyer": "flyer",
}
_VALID_AD_FORMATS = {"instagram_feed", "instagram_story", "poster", "flyer", "banner", "product_detail"}


def _clean_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _canonical_ad_format(value: Any) -> str | None:
    normalized = _clean_optional_text(value)
    if not normalized:
        return None
    mapped = _CHANNEL_TO_AD_FORMAT.get(normalized, normalized)
    if mapped in _VALID_AD_FORMATS:
        return mapped
    return mapped.replace("-", "_")


def _seed_generation_job_ui_state(state: dict[str, Any], request: GenerationJobCreateRequest) -> None:
    current_brief = dict(state.get("current_brief") or {})
    context = dict(state.get("context") or {})
    context_extra = dict(context.get("extra") or {})

    selected_channel_id = _clean_optional_text(state.get("selected_channel_id") or request.selected_channel_id)
    selected_ad_format = _canonical_ad_format(
        request.ad_format
        or selected_channel_id
        or state.get("selected_ad_format")
        or current_brief.get("requested_ad_format")
        or context_extra.get("ad_format")
    )
    selected_tone = _clean_optional_text(state.get("selected_tone") or request.selected_tone)
    custom_direction = _clean_optional_text(state.get("custom_direction") or request.custom_direction)

    if selected_channel_id:
        state["selected_channel_id"] = selected_channel_id
        current_brief["selected_channel_id"] = selected_channel_id
        context_extra["selected_channel_id"] = selected_channel_id
    if selected_ad_format:
        state["selected_ad_format"] = selected_ad_format
        current_brief["requested_ad_format"] = selected_ad_format
        context_extra["ad_format"] = selected_ad_format
        context_extra["selected_ad_format"] = selected_ad_format
    if selected_tone:
        state["selected_tone"] = selected_tone
        current_brief["selected_tone"] = selected_tone
        context["brand_tone"] = selected_tone
        context_extra["selected_tone"] = selected_tone
    if custom_direction:
        state["custom_direction"] = custom_direction
        current_brief["custom_direction"] = custom_direction
        context_extra["custom_direction"] = custom_direction

    if current_brief:
        state["current_brief"] = current_brief
    if context_extra or context:
        context["extra"] = context_extra
        state["context"] = context


def _clear_stale_suggest_copy_state(state: dict[str, Any], request: GenerationJobCreateRequest) -> None:
    mode = request.copy_generation_mode or state.get("copy_generation_mode")
    if mode != "suggest_candidates" or _clean_optional_text(request.selected_copy_id):
        return
    state["selected_copy_id"] = None
    state["copy_selection"] = None
    state["marketing_copy"] = None
    state["copy_candidates"] = []
    state["copywriting_output"] = None
    state["copy_candidate_origin"] = None


def _assistant_message_from_interrupt(result_state: dict, fallback: str) -> str:
    interrupts = result_state.get("__interrupt__") or []
    if isinstance(interrupts, (list, tuple)) and interrupts:
        value = getattr(interrupts[0], "value", None)
        if isinstance(value, dict):
            option_question = value.get("option_question")
            if isinstance(option_question, dict):
                question = option_question.get("question")
                if isinstance(question, str) and question.strip():
                    return question.strip()
            question = value.get("question")
            if isinstance(question, str) and question.strip():
                return question.strip()

    for message in reversed(result_state.get("messages", []) or []):
        if message.get("role") == "assistant":
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return fallback


def get_generation_job_output_dir(job_id: str) -> Path:
    return get_job_output_dir(job_id)


def execute_generation_job_immediate(job_id: str, request: GenerationJobCreateRequest) -> GenerationJobResponse:
    job = get_generation_job(job_id)
    if not job:
        raise ValueError("generation job was not found")

    try:
        mark_generation_job_running(job_id, stage="rendering")
        output_dir = ensure_job_output_dir(job_id)

        background_path = output_dir / "background_0.png"
        final_path = output_dir / "final_0.png"
        metadata_path = output_dir / "metadata.json"
        prompt_path = output_dir / "prompt.json"
        validation_path = output_dir / "validation.json"
        copy_path = output_dir / "copy.json"
        layout_path = output_dir / "layout.json"
        render_result_path = output_dir / "render_result.json"

        _write_mock_images(background_path, final_path, request)
        prompt_summary = {"user_input_preview": " ".join(request.user_input.split())[:120]}
        validation_summary = {"overall_pass": True, "checks": ["mock_artifacts_written"]}
        copy_summary = {
            "schema_version": "mock_copy_v1",
            "headline": "EasyAds Mock Result",
            "subcopy": "deterministic mock output",
            "cta": "미리보기",
        }
        layout_summary = {
            "schema_version": "mock_layout_v1",
            "canvas": {"width": 1024, "height": 1024},
            "reserved_text_areas": [],
        }
        render_summary = {"schema_version": "mock_render_result_v1", "rendered_slot_count": 2, "warnings": []}
        write_json_artifact(
            metadata_path,
            {
                "schema_version": "result_artifact_metadata_v1",
                "job_id": job_id,
                "engine": "mock",
                "render_mode": "deterministic_mock",
                "requested_run_mode": request.run_mode,
                "effective_run_mode": "mock_immediate",
                "execution_mode": "deterministic_mock",
            },
        )
        write_json_artifact(prompt_path, prompt_summary)
        write_json_artifact(validation_path, validation_summary)
        write_json_artifact(copy_path, copy_summary)
        write_json_artifact(layout_path, layout_summary)
        write_json_artifact(render_result_path, render_summary)

        result_payload = build_result_artifact_payload(
            job_id=job_id,
            background_image_path=background_path,
            final_image_path=final_path,
            metadata_path=metadata_path,
            prompt_path=prompt_path,
            validation_path=validation_path,
            copy_path=copy_path,
            layout_path=layout_path,
            render_result_path=render_result_path,
            prompt_summary=prompt_summary,
            validation_summary=validation_summary,
            copy_summary=copy_summary,
            layout_summary=layout_summary,
            has_text_overlay=True,
            engine="mock",
            render_mode="deterministic_mock",
        ).model_dump(mode="json")
        done = mark_generation_job_done(
            job_id,
            result_payload=result_payload,
            output_path=_as_posix(final_path),
            metadata={
                "requested_run_mode": request.run_mode,
                "effective_run_mode": "mock_immediate",
                "execution_mode": "deterministic_mock",
            },
        )
        if not done:
            raise ValueError("generation job was not found")
        return done
    except Exception as exc:
        failed = mark_generation_job_failed(
            job_id,
            {
                "error_code": "generation_job_execution_failed",
                "message": "Generation job mock execution failed.",
                "detail": str(exc),
            },
            metadata={"execution_mode": "deterministic_mock_failed"},
        )
        if failed:
            return failed
        raise


def get_generation_job_graph():
    from orchestrator.app.api.marketing_graph import MARKETING_GRAPH

    return MARKETING_GRAPH


def _graph_modal_call_id(result_state: dict) -> str:
    t2i_result = result_state.get("t2i_result") or {}
    metadata = t2i_result.get("metadata") if isinstance(t2i_result, dict) else {}
    value = (metadata or {}).get("modal_call_id")
    return str(value or "").strip()


def _resolve_graph_job_context(job_id: str, job: GenerationJobResponse) -> dict[str, Any]:
    from orchestrator.app.chat_threads import state_service
    from orchestrator.app.db import settings as db_settings
    from orchestrator.app.db.repositories.generation_jobs import get_generation_job_row

    context: dict[str, Any] = {
        "workspace_id": "mem_workspace",
        "public_job_id": job_id,
        "internal_job_id": job_id,
        "public_thread_id": job.thread_id,
        "user_id": job.user_id,
        "modal_call_id": (job.metadata or {}).get("modal_call_id"),
        "metadata": job.metadata or {},
        "parent_snapshot_id": None,
    }
    if db_settings.get_db_backend() == "postgres":
        row = get_generation_job_row(job_id)
        if row:
            context.update(
                {
                    "workspace_id": str(row["workspace_id"]),
                    "public_job_id": str(row["public_job_id"]),
                    "internal_job_id": str(row["id"]),
                    "public_thread_id": row.get("public_thread_id") or job.thread_id,
                    "user_id": row.get("requested_by") or job.user_id,
                    "modal_call_id": row.get("modal_call_id") or (row.get("metadata") or {}).get("modal_call_id"),
                    "metadata": row.get("metadata") or {},
                    "row": row,
                }
            )

    latest_snapshot = state_service.get_latest_thread_state_snapshot(
        public_thread_id=str(context["public_thread_id"]),
        workspace_id=str(context["workspace_id"]),
        user_id=str(context["user_id"]) if context.get("user_id") else None,
    )
    context["parent_snapshot_id"] = latest_snapshot.snapshot_id if latest_snapshot else None
    return context


def _mark_graph_modal_pending(
    *,
    job_id: str,
    job: GenerationJobResponse,
    result_state: dict,
    changed_fields: list[str],
    request_run_mode: str,
    workspace_id: str,
    public_job_id: str,
    internal_job_id: str,
    parent_snapshot_id: str | None,
) -> GenerationJobResponse:
    from orchestrator.app.chat_threads import state_service

    modal_call_id = _graph_modal_call_id(result_state)
    if not modal_call_id:
        failed = mark_generation_job_failed(
            job_id,
            {
                "error_code": "graph_modal_call_id_missing",
                "message": "Graph submitted a Modal generation without a call id.",
            },
            metadata={"execution_mode": "graph_modal_pending_failed"},
        )
        return failed or job

    state_service.save_thread_state_snapshot(
        public_thread_id=str(job.thread_id),
        workspace_id=workspace_id,
        snapshot_kind="graph_modal_pending",
        state_payload=result_state,
        changed_fields=changed_fields,
        generation_job_id=internal_job_id,
        parent_snapshot_id=parent_snapshot_id,
        snapshot_key=f"{public_job_id}:graph_modal_pending",
        created_by=job.user_id,
        user_id=job.user_id,
    )
    running = mark_generation_job_modal_running(
        job_id,
        modal_call_id=modal_call_id,
        result_state=result_state,
        metadata={
            "requested_run_mode": request_run_mode,
            "effective_run_mode": "graph_job",
            "execution_mode": "graph_modal_pending",
            "final_brief": result_state.get("current_brief"),
        },
    )
    return running or job


def execute_generation_job_graph(job_id: str, request: GenerationJobCreateRequest) -> GenerationJobResponse:
    from orchestrator.app.chat_threads import state_service
    from orchestrator.app.chat_threads.state_snapshot import restore_persistent_state, calculate_changed_fields
    from orchestrator.app.db import settings as db_settings
    from orchestrator.app.db.session import db_transaction

    from orchestrator.app.graph.state import create_initial_marketing_state
    from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest
    
    job = get_generation_job(job_id)
    if not job:
        raise ValueError("generation job was not found")

    try:
        mark_generation_job_running(job_id, stage="planning")

        workspace_id = "mem_workspace"
        public_job_id = job_id
        internal_job_id = job_id

        if db_settings.get_db_backend() == "postgres":
            from orchestrator.app.db.repositories.generation_jobs import get_generation_job_row
            with db_transaction() as conn:
                job_row = get_generation_job_row(job_id, connection=conn)
                if job_row:
                    internal_job_id = str(job_row["id"])
                    public_job_id = str(job_row["public_job_id"])
                    workspace_id = str(job_row["workspace_id"])

        input_snapshot = state_service.get_chat_state_snapshot_by_key(
            snapshot_key=f"{public_job_id}:input",
            public_thread_id=job.thread_id,
            workspace_id=workspace_id,
            user_id=job.user_id,
        )
        if not input_snapshot:
            raise ValueError(f"Input snapshot not found for job_id={public_job_id}")

        initial_state = create_initial_marketing_state(
            InitialMarketingRequest(
                user_input=request.user_input,
                job_id=public_job_id,
                thread_id=job.thread_id,
                entry_mode=request.entry_mode,
                copy_generation_mode=request.copy_generation_mode,
                user_plan=request.user_plan,
                source_asset_id=request.source_asset_id,
                reference_asset_id=request.reference_asset_id,
                source_image_path=request.source_image_path,
                reference_image_path=request.reference_image_path,
                selected_reference_template_id=request.selected_reference_template_id,
                renderer_mode=request.renderer_mode,
                # #7 dedup: FE가 보낸 ad_format(기본 instagram_feed)을 시드 → ad_format이
                # missing_fields에 안 들어가 intake에서 중복 질문 안 함. 최종 사이즈는 브리프의
                # CopyChannelStep(selectedChannelId)가 소유(final gen이 channel로 adFormat 전송).
                requested_ad_format=request.ad_format,
            )
        )
        initial_state.update(restore_persistent_state(input_snapshot.state_payload))
        
        # Enforce current context
        initial_state["job_id"] = public_job_id
        initial_state["thread_id"] = job.thread_id
        initial_state["user_input"] = request.user_input
        initial_state["workspace_id"] = workspace_id
        
        if request.source_asset_id is not None:
            initial_state["source_asset_id"] = request.source_asset_id
            initial_state["source_image_path"] = None

        if request.reference_asset_id is not None:
            initial_state["reference_asset_id"] = request.reference_asset_id
            initial_state["reference_image_path"] = None

        if request.selected_reference_template_id is not None:
            initial_state["selected_reference_template_id"] = request.selected_reference_template_id
        _seed_generation_job_ui_state(initial_state, request)
        _clear_stale_suggest_copy_state(initial_state, request)
        regeneration_patch = (request.metadata or {}).get("regeneration_patch")
        if regeneration_patch:
            initial_state["regeneration_patch"] = regeneration_patch

        # Execute
        graph = get_generation_job_graph()
        config = {
            "configurable": {
                "thread_id": job.thread_id,
            }
        }
        result_state = graph.invoke(initial_state, config=config)

        changed_fields = calculate_changed_fields(input_snapshot.state_payload, result_state)

        if "__interrupt__" in result_state:
            from orchestrator.app.generation_jobs.service import mark_generation_job_waiting_user_input
            msg_content = _assistant_message_from_interrupt(result_state, "추가 정보가 필요해요.")
            
            updated = mark_generation_job_waiting_user_input(
                job_id=job_id,
                result_state=result_state,
                changed_fields=changed_fields,
                assistant_message=msg_content,
                workspace_id=workspace_id,
                user_id=job.user_id,
            )
            return updated or job

        elif result_state.get("status") == "modal_running":
            return _mark_graph_modal_pending(
                job_id=job_id,
                job=job,
                result_state=result_state,
                changed_fields=changed_fields,
                request_run_mode=request.run_mode,
                workspace_id=workspace_id,
                public_job_id=public_job_id,
                internal_job_id=internal_job_id,
                parent_snapshot_id=input_snapshot.snapshot_id,
            )

        elif result_state.get("status") == "done":
            state_service.save_thread_state_snapshot(
                public_thread_id=job.thread_id,
                workspace_id=workspace_id,
                snapshot_kind="graph_completed",
                state_payload=result_state,
                changed_fields=changed_fields,
                generation_job_id=internal_job_id,
                parent_snapshot_id=input_snapshot.snapshot_id,
                snapshot_key=f"{public_job_id}:graph_completed",
                created_by=job.user_id,
                user_id=job.user_id,
            )
            result_payload = result_state.get("result_payload") or {}
            done = mark_generation_job_done(
                job_id,
                result_payload=result_payload,
                output_path=result_state.get("final_image_path"),
                metadata={
                    "requested_run_mode": request.run_mode,
                    "effective_run_mode": "graph_job",
                    "execution_mode": "graph_execution",
                    "final_brief": result_state.get("current_brief"),
                },
            )
            return done or job

        elif result_state.get("status") == "failed":
            error_info = result_state.get("error_info") or {}
            # Removed redundant job_failed snapshot here (P1-1)
            failed = mark_generation_job_failed(
                job_id,
                {
                    "error_code": error_info.get("error_code") or "generation_job_execution_failed",
                    "error_type": error_info.get("error_type"),
                    "message": error_info.get("message") or "Graph execution failed",
                    "detail": result_state.get("error_message"),
                },
                metadata={"execution_mode": "graph_execution_failed"},
            )
            return failed or job

        else:
            raise ValueError(f"Unexpected graph result status: {result_state.get('status')}")

    except Exception as exc:
        failed = mark_generation_job_failed(
            job_id,
            {
                "error_code": "generation_job_execution_failed",
                "message": "Generation job graph execution failed.",
                "detail": str(exc),
            },
            metadata={"execution_mode": "graph_execution_failed"},
        )
        return failed or job


def resume_generation_job_graph(
    job_id: str,
    answer: GenerationJobAnswerRequest,
    *,
    allow_running: bool = False,
    workspace_id: str | None = None,
    user_id: str | None = None,
) -> GenerationJobResponse:
    from langgraph.types import Command
    from orchestrator.app.chat_threads.state_snapshot import calculate_changed_fields
    from orchestrator.app.generation_jobs.service import mark_generation_job_done, mark_generation_job_failed, mark_generation_job_running, mark_generation_job_waiting_user_input

    job = get_generation_job(job_id, workspace_id=workspace_id, user_id=user_id) if workspace_id or user_id else get_generation_job(job_id)
    if not job:
        raise ValueError("generation job was not found")
    if job.status != "waiting_user_input" and not (allow_running and job.status == "running"):
        raise ValueError("generation job is not waiting for user input")
    if not job.thread_id:
        raise ValueError("generation job has no thread_id")

    try:
        running = mark_generation_job_running(job_id, stage="planning", workspace_id=workspace_id, user_id=user_id)
        job = running or job

        resume_payload = answer.to_resume_payload(job_id=job_id, thread_id=job.thread_id)
        append_generation_job_user_answer_message(job_id, answer, workspace_id=workspace_id, user_id=user_id)
        graph = get_generation_job_graph()
        result_state = graph.invoke(
            Command(resume=resume_payload),
            config={"configurable": {"thread_id": job.thread_id}},
        )
        changed_fields = calculate_changed_fields(None, result_state)

        if "__interrupt__" in result_state:
            assistant_message = _assistant_message_from_interrupt(result_state, "추가 정보가 필요해요.")
            updated = mark_generation_job_waiting_user_input(
                job_id=job_id,
                result_state=result_state,
                changed_fields=changed_fields,
                assistant_message=assistant_message,
                workspace_id=workspace_id,
                user_id=user_id,
            )
            return updated or job

        if result_state.get("status") == "modal_running":
            context = _resolve_graph_job_context(job_id, job)
            return _mark_graph_modal_pending(
                job_id=job_id,
                job=job,
                result_state=result_state,
                changed_fields=changed_fields,
                request_run_mode="graph_job",
                workspace_id=str(context["workspace_id"]),
                public_job_id=str(context["public_job_id"]),
                internal_job_id=str(context["internal_job_id"]),
                parent_snapshot_id=context.get("parent_snapshot_id"),
            )

        if result_state.get("status") == "done":
            done = mark_generation_job_done(
                job_id,
                result_payload=result_state.get("result_payload") or {},
                output_path=result_state.get("final_image_path"),
                metadata={
                    "requested_run_mode": "graph_job",
                    "effective_run_mode": "graph_job",
                    "execution_mode": "graph_execution",
                    "final_brief": result_state.get("current_brief"),
                },
                workspace_id=workspace_id,
                user_id=user_id,
            )
            return done or job

        if result_state.get("status") == "failed":
            error_info = result_state.get("error_info") or {}
            failed = mark_generation_job_failed(
                job_id,
                {
                    "error_code": error_info.get("error_code") or "generation_job_execution_failed",
                    "error_type": error_info.get("error_type"),
                    "message": error_info.get("message") or "Graph execution failed",
                    "detail": result_state.get("error_message"),
                },
                metadata={"execution_mode": "graph_execution_failed"},
                workspace_id=workspace_id,
                user_id=user_id,
            )
            return failed or job

        raise ValueError(f"Unexpected graph result status: {result_state.get('status')}")
    except Exception as exc:
        failed = mark_generation_job_failed(
            job_id,
            {
                "error_code": "generation_job_execution_failed",
                "message": "Generation job graph resume failed.",
                "detail": str(exc),
            },
            metadata={"execution_mode": "graph_resume_failed"},
            workspace_id=workspace_id,
            user_id=user_id,
        )
        return failed or job


def poll_and_process_graph_modal_generation_job(
    job_id: str,
    *,
    workspace_id: str | None = None,
    user_id: str | None = None,
) -> GenerationJobResponse | None:
    from orchestrator.app.chat_threads import state_service
    from orchestrator.app.chat_threads.state_snapshot import calculate_changed_fields, restore_persistent_state
    from orchestrator.app.modal.client import poll_modal_t2i_result
    from orchestrator.app.t2i.graph_engines import write_modal_graph_result_image

    job = get_generation_job(job_id, workspace_id=workspace_id, user_id=user_id) if workspace_id or user_id else get_generation_job(job_id)
    if not job:
        return None
    if job.status not in {"queued", "running"}:
        return job

    context = _resolve_graph_job_context(job_id, job)
    modal_call_id = str(context.get("modal_call_id") or "").strip()
    if not modal_call_id:
        return mark_generation_job_failed(
            job_id,
            {
                "error_code": "graph_modal_call_id_missing",
                "message": "Graph Modal job is missing its Modal call id.",
            },
            metadata={"execution_mode": "graph_modal_poll_failed"},
            workspace_id=workspace_id,
            user_id=user_id,
        ) or job

    poll_result = poll_modal_t2i_result(modal_call_id)
    if poll_result.status in {"pending", "running", "unknown"}:
        return mark_generation_job_running(job_id, "modal_running", workspace_id=workspace_id, user_id=user_id) or job

    if poll_result.status in {"failed", "canceled"}:
        return mark_generation_job_failed(
            job_id,
            {
                "error_code": "modal_generation_failed",
                "message": "Modal generation failed.",
                "detail": _safe_modal_error(poll_result.error),
            },
            metadata={
                "execution_backend": "modal",
                "execution_mode": "graph_modal_failed",
                "modal_status": poll_result.status,
            },
            workspace_id=workspace_id,
            user_id=user_id,
        ) or job

    if poll_result.status != "succeeded":
        return job

    snapshot = state_service.get_chat_state_snapshot_by_key(
        snapshot_key=f"{context['public_job_id']}:graph_modal_pending",
        public_thread_id=str(context["public_thread_id"]),
        workspace_id=str(context["workspace_id"]),
        user_id=str(context["user_id"]) if context.get("user_id") else None,
    )
    if not snapshot:
        return mark_generation_job_failed(
            job_id,
            {
                "error_code": "graph_modal_snapshot_missing",
                "message": "Graph Modal state snapshot was not found.",
            },
            metadata={"execution_mode": "graph_modal_poll_failed"},
            workspace_id=workspace_id,
            user_id=user_id,
        ) or job

    state = restore_persistent_state(snapshot.state_payload)
    state["job_id"] = str(context["public_job_id"])
    state["thread_id"] = str(context["public_thread_id"])
    state["user_id"] = context.get("user_id")
    t2i_request = state.get("t2i_request") or {}
    output_dir = Path(t2i_request.get("output_dir") or ensure_job_output_dir(job_id))
    background_path = write_modal_graph_result_image(output_dir=output_dir, poll_result=poll_result)
    _inject_modal_graph_t2i_result(state, background_path=background_path, poll_metadata=poll_result.metadata)
    _run_graph_post_t2i_nodes(state)

    changed_fields = calculate_changed_fields(snapshot.state_payload, state)
    state_service.save_thread_state_snapshot(
        public_thread_id=str(context["public_thread_id"]),
        workspace_id=str(context["workspace_id"]),
        snapshot_kind="graph_completed",
        state_payload=state,
        changed_fields=changed_fields,
        generation_job_id=str(context["internal_job_id"]),
        parent_snapshot_id=snapshot.snapshot_id,
        snapshot_key=f"{context['public_job_id']}:graph_completed",
        created_by=context.get("user_id"),
        user_id=str(context["user_id"]) if context.get("user_id") else None,
    )

    if state.get("status") == "done":
        return mark_generation_job_done(
            job_id,
            result_payload=state.get("result_payload") or {},
            output_path=state.get("final_image_path") or (state.get("result_payload") or {}).get("output_path"),
            metadata={
                "requested_run_mode": (context.get("metadata") or {}).get("requested_run_mode") or "graph_job",
                "effective_run_mode": "graph_job",
                "execution_mode": "graph_modal_completed",
                "execution_backend": "modal",
                "modal_status": "succeeded",
                "final_brief": state.get("current_brief"),
            },
            workspace_id=workspace_id,
            user_id=user_id,
        ) or job

    error_info = state.get("error_info") or {}
    return mark_generation_job_failed(
        job_id,
        {
            "error_code": error_info.get("error_code") or "graph_modal_postprocess_failed",
            "error_type": error_info.get("error_type"),
            "message": error_info.get("message") or state.get("error_message") or "Graph Modal post-processing failed.",
        },
        metadata={
            "execution_backend": "modal",
            "execution_mode": "graph_modal_postprocess_failed",
            "modal_status": "succeeded",
        },
        workspace_id=workspace_id,
        user_id=user_id,
    ) or job


def _inject_modal_graph_t2i_result(state: dict, *, background_path: str, poll_metadata: dict | None = None) -> None:
    from orchestrator.app.schemas.llm_marketing import ArtifactRef, GeneratedImageCandidate
    from orchestrator.app.t2i.schemas import T2IResult

    current_result = state.get("t2i_result") or {}
    current_metadata = current_result.get("metadata") or {}
    request = state.get("t2i_request") or {}
    request_metadata = request.get("metadata") or {}
    engine = _normalize_graph_t2i_engine(
        current_result.get("engine")
        or current_metadata.get("requested_engine")
        or request_metadata.get("requested_engine")
        or state.get("engine")
    )
    result = T2IResult(
        engine=engine,
        image_paths=[background_path],
        seed=current_result.get("seed") or request.get("seed"),
        latency_ms=int(current_result.get("latency_ms") or 0),
        width=int(current_result.get("width") or request.get("width") or 1024),
        height=int(current_result.get("height") or request.get("height") or 1024),
        prompt=str(current_result.get("prompt") or request.get("prompt") or ""),
        negative_prompt=str(current_result.get("negative_prompt") or request.get("negative_prompt") or ""),
        metadata={
            **request_metadata,
            **current_metadata,
            **(poll_metadata or {}),
            "execution_backend": "modal",
            "modal_call_id_present": True,
            "modal_status": "succeeded",
            "source_node": "t2i_generation",
        },
        error=None,
    )
    state["t2i_result"] = result.model_dump()
    state["candidates"] = [
        GeneratedImageCandidate(
            image_id=f"{state.get('job_id')}_candidate_0",
            image_path=background_path,
            width=result.width,
            height=result.height,
            engine=result.engine,
            seed=result.seed,
            latency_ms=result.latency_ms,
            metadata={"source_node": "t2i_generation", "text_overlay_pending": True},
        ).model_dump()
    ]
    artifacts = list(state.get("artifact_refs") or [])
    artifacts.append(
        ArtifactRef(
            artifact_id=f"{state.get('job_id')}_image_0",
            artifact_type="generated_background",
            path=background_path,
            label=Path(background_path).name,
            metadata={"engine": result.engine, "text_overlay_pending": True},
        ).model_dump()
    )
    state["artifact_refs"] = artifacts
    state["final_image_path"] = background_path
    state["status"] = "t2i_running"
    state["error_message"] = None


def _run_graph_post_t2i_nodes(state: dict) -> None:
    from orchestrator.app.graph.routers import route_by_copy_presence
    from orchestrator.app.llm.nodes.background_validation import background_validation_node
    from orchestrator.app.llm.nodes.final_validation import final_validation_node
    from orchestrator.app.llm.nodes.ocr_gate import background_ocr_gate_node, final_ocr_gate_node
    from orchestrator.app.llm.nodes.readability_gate import readability_gate_node
    from orchestrator.app.llm.nodes.result import result_node
    from orchestrator.app.llm.nodes.safe_area_gate import safe_area_gate_node
    from orchestrator.app.llm.nodes.text_renderer import text_renderer_node

    for update in (
        background_ocr_gate_node(state),
        background_validation_node(state),
        safe_area_gate_node(state),
    ):
        state.update(update)

    if route_by_copy_presence(state) == "result":
        state.update(result_node(state))
        return

    for update in (
        text_renderer_node(state),
        final_ocr_gate_node(state),
        readability_gate_node(state),
        final_validation_node(state),
        result_node(state),
    ):
        state.update(update)


def _normalize_graph_t2i_engine(value: object) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    if normalized in {"sd35", "sd3_5", "sd3_5_large", "sd35_large"}:
        return "sd35_large"
    if normalized in {"flux", "flux_schnell", "flux_1_schnell", "flux2_klein", "flux2_klein_4b", "flux_2_klein_4b"}:
        return "flux2_klein_4b"
    if normalized in {"gpt_image_1", "gpt_image1"}:
        return "gpt_image_1"
    if normalized in {"gpt_image_2", "gpt_image2"}:
        return "gpt_image_2"
    raise ValueError(f"Unsupported graph T2I engine: {value}")


def _safe_modal_error(error: dict | None) -> dict:
    if not error:
        return {}
    return {key: value for key, value in error.items() if str(key).lower() not in {"token", "secret", "api_key"}}


def execute_generation_job_t2i(job_id: str, request: GenerationJobCreateRequest, engine_name: str) -> GenerationJobResponse:
    job = get_generation_job(job_id)
    if not job:
        raise ValueError("generation job was not found")
    try:
        mark_generation_job_running(job_id, stage="t2i_running")
        output_dir = ensure_job_output_dir(job_id)
        prompt = build_generation_job_prompt(request.user_input)
        negative_prompt = TEXT_FREE_NEGATIVE_PROMPT
        engine = get_t2i_engine(engine_name)
        generation = engine.generate(
            T2IGenerationInput(
                job_id=job_id,
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=1024,
                height=1024,
                num_images=1,
                output_dir=output_dir.as_posix(),
                metadata={
                    **_safe_t2i_request_metadata(request.metadata or {}),
                    "requested_run_mode": request.run_mode,
                    "render_text_in_image": False,
                    "must_not_include_text": True,
                },
            )
        )
        generation_error = getattr(generation, "error", None)
        if generation_error:
            metadata = generation.metadata or {}
            error_code = str(metadata.get("error_code") or "t2i_engine_unavailable")
            if error_code == "t2i_engine_not_enabled":
                raise T2IEngineNotEnabledError(generation_error)
            exc = T2IEngineUnavailableError(generation_error)
            setattr(exc, "error_code", error_code)
            raise exc
        if not generation.image_paths:
            raise T2IEngineUnavailableError(f"{engine_name} did not return an image.")

        background_path = output_dir / "background_0.png"
        final_path = output_dir / "final_0.png"
        _copy_generated_image(Path(generation.image_paths[0]), background_path)
        _copy_generated_image(background_path, final_path)

        metadata_path = output_dir / "metadata.json"
        prompt_path = output_dir / "prompt.json"
        validation_path = output_dir / "validation.json"
        prompt_data = prompt_summary(prompt, negative_prompt, engine_name)
        validation_summary = {"overall_pass": True, "checks": ["t2i_image_saved"], "engine": engine_name}
        write_json_artifact(prompt_path, prompt_data)
        write_json_artifact(validation_path, validation_summary)
        write_json_artifact(
            metadata_path,
            {
                "schema_version": "t2i_actual_metadata_v1",
                "job_id": job_id,
                "engine": engine_name,
                "requested_run_mode": request.run_mode,
                "effective_run_mode": _effective_run_mode(engine_name),
                "execution_mode": "t2i_actual",
                "latency_ms": generation.latency_ms,
                "render_text_in_image": False,
                "must_not_include_text": True,
                "engine_metadata": _safe_engine_metadata(generation.metadata),
            },
        )
        result_payload = build_result_artifact_payload(
            job_id=job_id,
            background_image_path=background_path,
            final_image_path=final_path,
            metadata_path=metadata_path,
            prompt_path=prompt_path,
            validation_path=validation_path,
            prompt_summary=prompt_data,
            validation_summary=validation_summary,
            has_text_overlay=False,
            engine=engine_name,
            render_mode="t2i_actual",
        ).model_dump(mode="json")
        done = mark_generation_job_done(
            job_id,
            result_payload=result_payload,
            output_path=_as_posix(final_path),
            metadata={
                "requested_run_mode": request.run_mode,
                "effective_run_mode": _effective_run_mode(engine_name),
                "execution_mode": "t2i_actual",
                "engine": engine_name,
                "engine_preference": engine_name,
                "t2i_engine": engine_name,
                "render_text_in_image": False,
                "must_not_include_text": True,
                **_safe_engine_metadata(generation.metadata),
            },
        )
        if not done:
            raise ValueError("generation job was not found")
        return done
    except T2IEngineNotEnabledError as exc:
        return _mark_t2i_failed(job_id, "t2i_engine_not_enabled", str(exc), engine_name, request.run_mode)
    except T2IEngineUnavailableError as exc:
        return _mark_t2i_failed(
            job_id,
            getattr(exc, "error_code", "t2i_engine_unavailable"),
            str(exc),
            engine_name,
            request.run_mode,
            error_type=type(exc).__name__,
        )
    except Exception as exc:
        return _mark_t2i_failed(
            job_id,
            "t2i_engine_unavailable",
            "T2I generation failed.",
            engine_name,
            request.run_mode,
            detail=str(exc),
            error_type=type(exc).__name__,
        )


def _write_mock_images(background_path: Path, final_path: Path, request: GenerationJobCreateRequest) -> None:
    width, height = 1024, 1024
    image = Image.new("RGB", (width, height), "#F6F2EA")
    draw = ImageDraw.Draw(image)
    for y in range(height):
        color = (246, max(210, 242 - y // 20), max(190, 234 - y // 18))
        draw.line([(0, y), (width, y)], fill=color)
    image.save(background_path)

    final = image.copy()
    draw = ImageDraw.Draw(final)
    draw.rectangle((96, 760, 928, 920), fill="#111827")
    label = request.ad_format or "mock_ad"
    draw.text((128, 800), f"EasyAds Mock Result - {label}", fill="#FFFFFF")
    draw.text((128, 850), "deterministic mock output", fill="#FDE68A")
    final.save(final_path)


def _copy_generated_image(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)

    source_resolved = source.resolve()
    destination_resolved = destination.resolve()

    if source_resolved == destination_resolved:
        return

    copyfile(source, destination)


def _safe_engine_metadata(metadata: dict) -> dict:
    blocked = {"api_key", "openai_api_key", "hf_token", "huggingface_token", "token"}
    return {key: value for key, value in metadata.items() if key.lower() not in blocked}


_ALLOWED_T2I_REQUEST_METADATA = {
    "comparison_batch_id",
    "case_id",
    "business_type",
    "business_subtype",
    "item_or_service",
    "primary_subject",
    "selected_reference_template_id",
    "reference_template_id",
}

_SECRET_METADATA_KEYS = {
    "api_key",
    "openai_api_key",
    "hf_token",
    "huggingface_token",
    "token",
    "authorization",
    "secret",
    "password",
}


def _safe_t2i_request_metadata(metadata: dict) -> dict:
    sanitized = _sanitize_metadata_recursive(metadata)
    return {
        key: value
        for key, value in sanitized.items()
        if key in _ALLOWED_T2I_REQUEST_METADATA
    }


def _sanitize_metadata_recursive(value):
    if isinstance(value, dict):
        return {
            key: _sanitize_metadata_recursive(item)
            for key, item in value.items()
            if str(key).lower() not in _SECRET_METADATA_KEYS
        }
    if isinstance(value, list):
        return [_sanitize_metadata_recursive(item) for item in value]
    return value


def _mark_t2i_failed(
    job_id: str,
    error_code: str,
    message: str,
    engine_name: str,
    run_mode: str,
    detail: str | None = None,
    error_type: str | None = None,
) -> GenerationJobResponse:
    failed = mark_generation_job_failed(
        job_id,
        {"error_code": error_code, "error_type": error_type, "message": message, "detail": detail},
        metadata={
            "requested_run_mode": run_mode,
            "effective_run_mode": _effective_run_mode(engine_name),
            "execution_mode": "t2i_actual_failed",
            "engine": engine_name,
            "engine_preference": engine_name,
            "t2i_engine": engine_name,
        },
    )
    if not failed:
        raise ValueError("generation job was not found")
    return failed


def _as_posix(path: Path) -> str:
    return path.as_posix()


def _effective_run_mode(engine_name: str) -> str:
    return _EFFECTIVE_RUN_MODE_BY_ENGINE.get(engine_name, engine_name)
