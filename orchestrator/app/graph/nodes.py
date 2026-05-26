"""Rule-based intake nodes for the LLM/LangGraph mini graph."""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from orchestrator.app.graph.state import (
    OPTIONAL_CONTEXT_FIELDS,
    REQUIRED_CONTEXT_FIELDS,
    MarketingState,
    append_message,
    calculate_dirty_fields,
    context_to_model,
    create_initial_marketing_state,
    update_current_brief,
)
from orchestrator.app.llm.ad_format_presets import build_ad_format_spec
from orchestrator.app.llm.option_registry import get_next_missing_field, get_option_question
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext, ProgressState, UserSelectionRequest, ValidatorOutput


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
    updates = infer_marketing_context(text)
    context_data = context.model_dump()
    extra = dict(context_data.get("extra") or {})
    if updates.pop("ad_format", None):
        extra["ad_format"] = infer_ad_format(text)
    for key, value in updates.items():
        if value and not context_data.get(key):
            context_data[key] = value
    requested_ad_format = state.get("current_brief", {}).get("requested_ad_format") or infer_ad_format(text) or extra.get("ad_format")
    if requested_ad_format:
        extra["ad_format"] = requested_ad_format
    context_data["extra"] = extra
    context = MarketingContext(**context_data)

    missing_fields = calculate_missing_fields(context)
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
        reasoning_summary="Rule-based v1 validator; no LLM call was made.",
    )
    current_brief_updates = {"ready_for_planning": not bool(missing_fields)}
    if requested_ad_format:
        current_brief_updates["requested_ad_format"] = requested_ad_format
    update_current_brief(state, current_brief_updates)
    return {
        "context": context.model_dump(),
        "validator_output": validator_output.model_dump(),
        "missing_fields": missing_fields,
        "progress_state": progress_state.model_dump(),
        "current_brief": state.get("current_brief", {}),
        "status": "validating_context",
        "option_question": None,
    }


def options_node(state: MarketingState) -> dict[str, Any]:
    field = get_next_missing_field(state.get("missing_fields", []))
    if field is None:
        return {"status": state.get("status", "validating_context"), "option_question": None}
    question = get_option_question(field).model_copy(update={"progress_state": build_progress_state(state.get("missing_fields", []) )})
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
    }


def state_update_node(state: MarketingState) -> dict[str, Any]:
    raw_selection = state.get("user_selection")
    if raw_selection is None:
        return {"status": "updating_state"}
    selection = raw_selection if isinstance(raw_selection, UserSelectionRequest) else UserSelectionRequest(**raw_selection)
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

    if field == "ad_format":
        extra["ad_format"] = value
        context_data["extra"] = extra
        update_current_brief(state, {"requested_ad_format": value})
        updated = True
    elif field in context_data:
        context_data[field] = value
        updated = True
    else:
        extra[field] = value
        context_data["extra"] = extra
        updated = True

    missing_fields = [item for item in state.get("missing_fields", []) if item != field] if updated else list(state.get("missing_fields", []))
    append_message(state, "user", str(value), {"field": field, "source": "user_selection"})
    update_current_brief(state, {field: value})
    dirty_fields = calculate_dirty_fields(state, [field])
    return {
        "context": MarketingContext(**context_data).model_dump(),
        "missing_fields": missing_fields,
        "dirty_fields": dirty_fields,
        "revision": int(state.get("revision", 0)) + 1,
        "status": "updating_state",
        "user_selection": None,
    }


def infer_marketing_context(text: str) -> dict[str, Any]:
    return {
        "business_type": infer_business_type(text),
        "item_or_service": infer_item_or_service(text),
        "promotion_goal": infer_promotion_goal(text),
        "ad_format": infer_ad_format(text),
    }


def infer_business_type(text: str) -> str | None:
    rules = [
        (("카페", "라떼", "디저트", "커피"), "cafe"),
        (("삼겹살", "고기", "한우", "식당", "레스토랑"), "restaurant"),
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
    total = len(REQUIRED_CONTEXT_FIELDS)
    remaining = [field for field in missing_fields if field in REQUIRED_CONTEXT_FIELDS + OPTIONAL_CONTEXT_FIELDS]
    current_step = max(0, total - len([field for field in REQUIRED_CONTEXT_FIELDS if field in remaining]))
    return ProgressState(
        current_step=current_step,
        total_steps=total,
        current_label="필수 정보 확인" if remaining else "기획 준비 완료",
        remaining_fields=remaining,
        can_skip_question_screen=not any(field in REQUIRED_CONTEXT_FIELDS for field in remaining),
    )
