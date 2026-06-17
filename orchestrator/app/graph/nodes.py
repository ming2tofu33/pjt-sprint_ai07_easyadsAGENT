"""Rule-based intake nodes for the LLM/LangGraph mini graph."""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from orchestrator.app.graph.state import (
    OPTIONAL_CONTEXT_FIELDS,
    REQUIRED_CONTEXT_FIELDS,
    MarketingState,
    append_message,
    build_message,
    calculate_dirty_fields,
    context_to_model,
    create_initial_marketing_state,
    read_model,
    resolve_requested_ad_format,
    set_requested_ad_format,
    update_current_brief,
)
from orchestrator.app.llm.ad_format_presets import build_ad_format_spec
from orchestrator.app.llm.intake_understanding_service import project_intake_to_context, understand_intake
from orchestrator.app.llm.metadata_builders import build_copy_mode_inference_metadata, metadata_contract_to_prompt_json
from orchestrator.app.llm.nodes.brief_interpreter import build_context_updates_from_brief_interpreter, interpret_brief_with_llm
from orchestrator.app.llm.node_runner import run_structured_node
from orchestrator.app.llm.option_registry import get_next_missing_field, get_option_question, option_label_for_value
from orchestrator.app.schemas.llm_marketing import CopyModeInferenceOutput, InitialMarketingRequest, MarketingContext, ProgressState, UserSelectionRequest, ValidatorOutput


DISPLAY_LABEL_CONTEXT_FIELDS = {"item_or_service"}


def input_node(input_value: MarketingState | InitialMarketingRequest | dict[str, Any]) -> MarketingState:
    if isinstance(input_value, InitialMarketingRequest):
        return create_initial_marketing_state(input_value)
    if isinstance(input_value, dict) and "schema_version" in input_value and "job_id" in input_value:
        return input_value
    if isinstance(input_value, dict):
        return create_initial_marketing_state(InitialMarketingRequest(**input_value))
    raise TypeError(f"Unsupported input type: {type(input_value)!r}")


def validator_node(state: MarketingState) -> dict[str, Any]:
    context = context_to_model(state.get("context"))
    text = " ".join(str(value or "") for value in [state.get("user_input"), state.get("current_brief", {}).get("custom_request")])
    intake_result, intake_trace = _resolve_intake_understanding(state, text)
    updates, intake_projection = project_intake_to_context(intake_result)
    context_data = context.model_dump()
    extra = dict(context_data.get("extra") or {})
    if updates.pop("ad_format", None):
        extra["ad_format"] = intake_result.ad_format_candidate or infer_ad_format(text)
    for key, value in updates.items():
        if value and not context_data.get(key):
            context_data[key] = value
    requested_ad_format = resolve_requested_ad_format(state) or infer_ad_format(text)
    if requested_ad_format:
        extra["ad_format"] = requested_ad_format
    context_data["extra"] = extra
    context = MarketingContext(**context_data)

    missing_fields = calculate_missing_fields(context)
    copy_mode, copy_mode_output = resolve_copy_generation_mode(state, text, track_in_state=False)
    copy_mode_from_brief = intake_trace.get("copy_generation_mode_candidate")
    if copy_mode is None and copy_mode_from_brief:
        copy_mode = copy_mode_from_brief
        copy_mode_output = CopyModeInferenceOutput(
            copy_generation_mode=copy_mode_from_brief,
            confidence=float(intake_trace.get("brief_interpreter", {}).get("llm_metadata", {}).get("confidence") or 0.65),
            source="brief_interpreter_llm",
            reasoning_summary="Copy mode inferred by guarded brief interpreter.",
            metadata={"source": "brief_interpreter_llm", "source_detail": "copy_generation_mode inferred by guarded brief interpreter"},
        )
    # copy_generation_mode is the 4-mode HITL choice (AI 추천 / AI 알아서 / 직접 입력 / 카피 없음).
    # Heuristic/LLM inference only seeds the recommended default and must not satisfy the field;
    # the question is surfaced until the user confirms (or supplied a mode up front).
    copy_mode_confirmed = bool(state.get("current_brief", {}).get("copy_generation_mode_confirmed"))
    if not copy_mode_confirmed and "copy_generation_mode" not in missing_fields:
        missing_fields.append("copy_generation_mode")
    if copy_mode_confirmed and "copy_generation_mode" in missing_fields:
        missing_fields.remove("copy_generation_mode")
    progress_state = build_progress_state(missing_fields)
    inferred_ad_format = build_ad_format_spec(requested_ad_format) if requested_ad_format else None
    validator_output = ValidatorOutput(
        context=context,
        missing_fields=missing_fields,
        confidence=0.7,
        needs_user_selection=bool(missing_fields),
        inferred_entry_mode=state.get("entry_mode"),
        inferred_generation_route=state.get("generation_route"),
        inferred_ad_format=inferred_ad_format,
        progress_state=progress_state,
        reasoning_summary="Rule-based v1 validator with guarded brief interpretation fallback.",
    )
    validator_metadata = {
        "intake_understanding": intake_projection,
        "brief_interpreter": {
            "used": bool(intake_trace.get("brief_interpreter", {}).get("used")),
            "llm_metadata": intake_trace.get("brief_interpreter", {}).get("llm_metadata"),
            "warnings": intake_trace.get("brief_interpreter", {}).get("warnings", []),
        }
    }
    current_brief_updates = {"ready_for_planning": not bool(missing_fields), "copy_generation_mode": copy_mode}
    if requested_ad_format:
        current_brief_updates["requested_ad_format"] = requested_ad_format
    next_brief = update_current_brief(state.get("current_brief"), current_brief_updates)
    copy_required = copy_mode != "no_copy" if copy_mode else state.get("copy_required", True)
    text_overlay_pending = copy_mode != "no_copy" if copy_mode else state.get("text_overlay_pending", True)
    tracking = _merge_llm_tracking(
        intake_trace.get("brief_interpreter", {}).get("llm_metadata"),
        copy_mode_output.metadata.get("llm_metadata") if copy_mode_output else None,
    )
    return {
        "context": context.model_dump(),
        "intake_understanding_result": intake_result.model_dump(),
        "intake_extraction_trace": intake_trace,
        "validator_output": validator_output.model_dump(),
        "validator_metadata": validator_metadata,
        "missing_fields": missing_fields,
        "progress_state": progress_state.model_dump(),
        "current_brief": next_brief,
        "copy_generation_mode": copy_mode,
        "copy_mode_inference_output": copy_mode_output.model_dump() if copy_mode_output else None,
        "copy_required": copy_required,
        "text_overlay_pending": text_overlay_pending,
        **tracking,
        "status": "validating_context",
        "option_question": None,
    }


def options_node(state: MarketingState) -> dict[str, Any]:
    field = get_next_missing_field(state.get("missing_fields", []))
    if field is None:
        return {"status": state.get("status", "validating_context"), "option_question": None}
    question = get_option_question(field)
    next_brief = dict(state.get("current_brief") or {})

    from orchestrator.app.schemas.option_suggestion import is_field_eligible

    if is_field_eligible(field):
        cached = next_brief.get("cached_options", {}).get(field)
        if cached is not None:
            from orchestrator.app.schemas.llm_marketing import OptionItem
            augmented_options = [OptionItem(**o) for o in cached]
            option_tracking = {}
        else:
            augmented_options = _augment_options(state, field, question)
            option_tracking = _llm_tracking_from_metadata(getattr(_augment_options, "_last_llm_metadata", None))
            next_brief = update_current_brief(
                next_brief,
                {"cached_options": {field: [o.model_dump() for o in augmented_options]}},
            )
        question = question.model_copy(update={"options": augmented_options})
    else:
        option_tracking = {}

    question = question.model_copy(update={"progress_state": build_progress_state(state.get("missing_fields", []) )})
    payload = {
        "type": "option_question",
        "job_id": state["job_id"],
        "thread_id": state["thread_id"],
        "option_question": question.model_dump(),
    }
    resume_payload = interrupt(payload)
    return {
        "user_selection": resume_payload,
        "option_question": question.model_dump(),
        "status": "updating_state",
        "current_brief": next_brief,
        **option_tracking,
    }


def _resolve_intake_understanding(state: MarketingState, text: str):
    cached = state.get("intake_understanding_result")
    trace = dict(state.get("intake_extraction_trace") or {})
    if cached:
        from orchestrator.app.schemas.intake_understanding import IntakeUnderstandingResult

        try:
            return IntakeUnderstandingResult(**cached), trace
        except Exception:
            trace = {}
    return understand_intake(
        state,
        text,
        deterministic_hints=infer_marketing_context(text),
        brief_interpreter=interpret_brief_with_llm,
        brief_projector=build_context_updates_from_brief_interpreter,
    )


def _augment_options(state: MarketingState, field: str, question: OptionQuestion):
    from orchestrator.app.llm.nodes.option_suggester import suggest_options
    from orchestrator.app.schemas.option_suggestion import (
        merge_options, passes_confidence_threshold,
    )
    output, _meta = suggest_options(state, field, question)
    _augment_options._last_llm_metadata = _meta  # type: ignore[attr-defined]
    if output is not None and passes_confidence_threshold(output):
        return merge_options(question.options, output.options)
    return list(question.options)


def state_update_node(state: MarketingState) -> dict[str, Any]:
    raw_selection = state.get("user_selection")
    if raw_selection is None:
        return {"status": "updating_state"}
    selection = read_model(state, "user_selection", UserSelectionRequest)
    if selection.job_id != state.get("job_id") or selection.thread_id != state.get("thread_id"):
        return {"status": "failed", "error_message": "user_selection job_id/thread_id mismatch"}

    context = context_to_model(state.get("context"))
    context_data = context.model_dump()
    extra = dict(context_data.get("extra") or {})
    field = selection.field
    value: Any = selection.value
    updated = False
    if value == "custom":
        if selection.custom_text:
            value = selection.custom_text
        else:
            missing = list(state.get("missing_fields", []))
            if field not in missing:
                missing.append(field)
            return {"missing_fields": missing, "status": "updating_state"}

    extra_return: dict[str, Any] = {}
    original_value = value
    value = display_value_for_selection(field, value)

    # P7: Check cached dynamic options for label resolution
    if value == original_value and field in DISPLAY_LABEL_CONTEXT_FIELDS:
        from orchestrator.app.schemas.option_suggestion import label_for_dynamic_value
        cached_options = state.get("current_brief", {}).get("cached_options")
        dyn_label = label_for_dynamic_value(field, original_value, cached_options)
        if dyn_label is not None:
            value = dyn_label

    if value != original_value and field in DISPLAY_LABEL_CONTEXT_FIELDS:
        extra[f"{field}_option_value"] = original_value
        context_data["extra"] = extra
    if field == "copy_generation_mode":
        next_brief = update_current_brief(state.get("current_brief"), {"copy_generation_mode": value, "copy_generation_mode_confirmed": True})
        extra_return.update(
            {
                "copy_generation_mode": value,
                "copy_required": value != "no_copy",
                "text_overlay_pending": value != "no_copy",
            }
        )
        updated = True
    elif field == "user_custom_headline":
        next_brief = update_current_brief(state.get("current_brief"), {"user_custom_headline": value})
        extra_return["user_custom_headline"] = value
        updated = True
    elif field == "user_custom_subcopy":
        next_brief = update_current_brief(state.get("current_brief"), {"user_custom_subcopy": value})
        extra_return["user_custom_subcopy"] = value
        updated = True
    elif field == "ad_format":
        next_brief, extra = set_requested_ad_format(dict(state.get("current_brief") or {}), dict(extra), value)
        context_data["extra"] = extra
        updated = True
    elif field in context_data:
        next_brief = dict(state.get("current_brief") or {})
        context_data[field] = value
        updated = True
    else:
        next_brief = dict(state.get("current_brief") or {})
        extra[field] = value
        context_data["extra"] = extra
        updated = True

    missing_fields = [item for item in state.get("missing_fields", []) if item != field] if updated else list(state.get("missing_fields", []))
    next_brief = update_current_brief(next_brief, {field: value})
    dirty_fields = calculate_dirty_fields(state, [field])
    return {
        "context": MarketingContext(**context_data).model_dump(),
        "current_brief": next_brief,
        "missing_fields": missing_fields,
        "dirty_fields": dirty_fields,
        "revision": int(state.get("revision", 0)) + 1,
        "status": "updating_state",
        "user_selection": None,
        **extra_return,
    }


def _llm_tracking_from_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    metadata = metadata or {}
    update: dict[str, Any] = {}
    selection = metadata.get("model_selection")
    result = metadata.get("llm_call_result")
    update["model_selections"] = [selection] if selection else []
    update["llm_call_results"] = [result] if result else []
    return update


def _merge_llm_tracking(*metadatas: dict[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for metadata in metadatas:
        current = _llm_tracking_from_metadata(metadata)
        if "model_selections" in current:
            merged["model_selections"] = [*(merged.get("model_selections") or []), *current["model_selections"]]
        if "llm_call_results" in current:
            merged["llm_call_results"] = [*(merged.get("llm_call_results") or []), *current["llm_call_results"]]
    return merged


def display_value_for_selection(field: str, value: Any) -> Any:
    if field not in DISPLAY_LABEL_CONTEXT_FIELDS:
        return value
    return option_label_for_value(field, value) or value


def infer_marketing_context(text: str) -> dict[str, Any]:
    return {
        "business_type": infer_business_type(text),
        "item_or_service": infer_item_or_service(text),
        "promotion_goal": infer_promotion_goal(text),
        "ad_format": infer_ad_format(text),
    }


def resolve_copy_generation_mode(state: MarketingState, text: str, *, track_in_state: bool = True):
    if state.get("copy_generation_mode"):
        return state["copy_generation_mode"], CopyModeInferenceOutput(
            copy_generation_mode=state["copy_generation_mode"],
            confidence=1.0,
            source="explicit_user_choice",
            reasoning_summary="User supplied copy generation mode.",
        )
    mode = infer_copy_generation_mode(text)
    if mode:
        return mode, CopyModeInferenceOutput(
            copy_generation_mode=mode,
            confidence=0.8,
            source="heuristic",
            reasoning_summary="Copy generation mode inferred from user wording.",
        )
    metadata_contract = build_copy_mode_inference_metadata(state, text)
    runner_state = state if track_in_state else dict(state)
    output, metadata = run_structured_node(
        runner_state,
        node_name="copy_mode_inference",
        output_schema=CopyModeInferenceOutput,
        prompt=build_copy_mode_prompt(text, state, metadata_contract),
        fallback_fn=lambda: None,
        risk_level="low",
        confidence=0.3,
        latency_budget="interactive",
        metadata=metadata_contract,
    )
    if isinstance(output, CopyModeInferenceOutput) and output.confidence >= 0.6:
        output.metadata.update({"llm_metadata": metadata})
        return output.copy_generation_mode, output
    return None, None


def build_copy_mode_prompt(text: str, state: MarketingState, metadata_contract: dict[str, Any] | None = None) -> str:
    context = state.get("context") or {}
    metadata_contract = metadata_contract or build_copy_mode_inference_metadata(state, text)
    return (
        "Classify the requested copy generation mode for a Korean small-business ad. "
        "Available modes: suggest_candidates, auto_pilot, no_copy, custom_input. "
        f"User input: {text[:500]}. "
        f"Context summary: business_type={context.get('business_type')}, item_or_service={context.get('item_or_service')}. "
        f"metadata_contract={metadata_contract_to_prompt_json(metadata_contract)}."
    )


def infer_copy_generation_mode(text: str) -> str | None:
    rules = [
        (("카피 없이", "문구 없이", "텍스트 없이", "글자 없이", "이미지만", "깔끔한 이미지만"), "no_copy"),
        (("문구는 내가", "내가 쓴 문구", "정해둔 문구", "직접 입력", "내 문구"), "custom_input"),
        (("알아서", "자동으로", "최적의 문구", "하나만 추천", "제일 좋은 문구"), "auto_pilot"),
        (("여러 개", "후보", "추천해줘", "몇 개", "시안 여러 개"), "suggest_candidates"),
    ]
    for keywords, mode in rules:
        if any(keyword in text for keyword in keywords):
            return mode
    return None


def infer_business_type(text: str) -> str | None:
    rules = [
        (("카페", "라떼", "디저트", "커피"), "cafe"),
        (("삼겹살", "고기", "한우", "식당", "레스토랑"), "restaurant"),
        (("네일샵", "네일아트", "젤네일", "네일"), "beauty_nail"),
        (("미용실", "헤어", "염색", "펌"), "beauty_salon"),
        (("헬스", "PT", "pt", "운동", "피트니스"), "fitness"),
        (("꽃", "꽃집", "플라워"), "flower_shop"),
    ]
    for keywords, value in rules:
        if any(keyword in text for keyword in keywords):
            return value
    return None


def infer_item_or_service(text: str) -> str | None:
    rules = [
        ("한우 선물세트", "한우 선물세트"),
        ("원육", "원육"),
        ("네일 아트", "네일 아트"),
        ("네일아트", "네일 아트"),
        ("젤네일", "젤네일"),
        ("네일", "네일 서비스"),
        ("삼겹살집", "삼겹살"),
        ("삼겹살", "삼겹살"),
        ("딸기라떼", "딸기라떼"),
        ("라떼", "라떼"),
        ("염색", "염색"),
        ("한우", "한우"),
        ("PT", "PT"),
        ("pt", "PT"),
    ]
    for keyword, value in rules:
        if keyword in text:
            return value
    return None


def infer_promotion_goal(text: str) -> str | None:
    rules = [
        (("시즌", "계절", "여름", "겨울", "봄", "가을", "한정"), "seasonal_limited"),
        (("할인", "%", "세일", "특가"), "discount_event"),
        (("신메뉴", "신상품", "출시", "오픈"), "new_launch"),
        (("예약", "방문", "문의"), "reservation_cta"),
        (("리뷰",), "review_event"),
    ]
    for keywords, value in rules:
        if any(keyword in text for keyword in keywords):
            return value
    return None


def infer_ad_format(text: str) -> str | None:
    rules = [
        (("스토리",), "instagram_story"),
        (("인스타", "피드"), "instagram_feed"),
        (("포스터",), "poster"),
        (("전단지", "A4", "당근"), "flyer"),
        (("배너", "웹"), "banner"),
        (("상세페이지", "스마트스토어"), "product_detail"),
    ]
    for keywords, value in rules:
        if any(keyword in text for keyword in keywords):
            return value
    return None


def calculate_missing_fields(context: MarketingContext) -> list[str]:
    missing: list[str] = []
    context_data = context.model_dump()
    for field in REQUIRED_CONTEXT_FIELDS:
        if field == "ad_format":
            if not context.extra.get("ad_format"):
                missing.append(field)
        elif not context_data.get(field):
            missing.append(field)
    return missing


def build_progress_state(missing_fields: list[str]) -> ProgressState:
    required = REQUIRED_CONTEXT_FIELDS + ["copy_generation_mode"]
    total = len(required)
    remaining = [field for field in missing_fields if field in required + OPTIONAL_CONTEXT_FIELDS]
    current_step = max(0, total - len([field for field in required if field in remaining]))
    return ProgressState(
        current_step=current_step,
        total_steps=total,
        current_label="필수 정보 확인" if remaining else "기획 준비 완료",
        remaining_fields=remaining,
        can_skip_question_screen=not any(field in REQUIRED_CONTEXT_FIELDS for field in remaining),
    )
