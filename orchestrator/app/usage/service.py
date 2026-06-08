"""Usage recording and summary service."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from orchestrator.app.db import settings as db_settings
from orchestrator.app.db.repositories import usage_events as usage_repo
from orchestrator.app.llm.plan_policy import normalize_user_plan
from orchestrator.app.usage.errors import InvalidUsagePlan, InvalidUsageRange, InvalidUsageScope
from orchestrator.app.usage.pricing import calculate_llm_cost, calculate_modal_cost, calculate_t2i_cost, decimal_or_none
from orchestrator.app.usage.quota_policy import current_utc_month_window, evaluate_plan_quota
from orchestrator.app.usage.types import USAGE_EVENT_TYPES, USAGE_PLANS, USAGE_UNITS


_MEMORY_USAGE_EVENTS: list[dict[str, Any]] = []
_BLOCKED_METADATA_KEYS = {"bucket", "chain_of_thought", "object_key", "presigned_url", "prompt", "raw_prompt", "raw_response"}
_SENSITIVE_METADATA_FRAGMENTS = {"api_key", "access_key", "access_token", "refresh_token", "secret", "password", "authorization", "credential"}


def reset_usage_store_for_tests() -> None:
    _MEMORY_USAGE_EVENTS.clear()


def record_usage_event(
    *,
    workspace_id: str,
    event_type: str,
    unit: str,
    quantity: Decimal | int | str | None = 1,
    created_by: str | None = None,
    thread_id: str | None = None,
    job_id: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    plan: str | None = None,
    cost_usd: Decimal | int | str | None = None,
    idempotency_key: str | None = None,
    metadata: dict | None = None,
    connection: object | None = None,
) -> dict | None:
    if event_type not in USAGE_EVENT_TYPES:
        raise ValueError(f"Unsupported usage event type: {event_type}")
    if unit not in USAGE_UNITS:
        raise ValueError(f"Unsupported usage unit: {unit}")
    safe_metadata = sanitize_usage_metadata(metadata)
    normalized_plan = normalize_usage_event_plan(plan)
    normalized_quantity = _positive_decimal(quantity, field_name="quantity", default=Decimal("1"))
    normalized_cost = _positive_decimal(cost_usd, field_name="cost_usd", default=None)
    if db_settings.get_db_backend() == "postgres":
        return usage_repo.record_usage_event_once(
            workspace_id=workspace_id,
            event_type=event_type,
            created_by=created_by,
            thread_id=thread_id,
            job_id=job_id,
            provider=provider,
            model_name=model_name,
            plan=normalized_plan,
            quantity=normalized_quantity,
            unit=unit,
            cost_usd=normalized_cost,
            idempotency_key=idempotency_key,
            metadata=safe_metadata,
            connection=connection,
        )
    return _record_memory_usage_event(
        workspace_id=workspace_id,
        event_type=event_type,
        created_by=created_by,
        thread_id=thread_id,
        job_id=job_id,
        provider=provider,
        model_name=model_name,
        plan=normalized_plan,
        quantity=normalized_quantity,
        unit=unit,
        cost_usd=normalized_cost,
        idempotency_key=idempotency_key,
        metadata=safe_metadata,
    )


def record_llm_usage(
    *,
    workspace_id: str,
    provider: str,
    model_name: str,
    plan: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    total_tokens: int | None = None,
    cached_input_tokens: int | None = None,
    created_by: str | None = None,
    thread_id: str | None = None,
    job_id: str | None = None,
    task_name: str | None = None,
    node_name: str | None = None,
    provider_request_id: str | None = None,
    call_index: int | None = None,
    request_status: str = "succeeded",
    parse_status: str | None = None,
) -> dict | None:
    cost, cost_metadata = calculate_llm_cost(
        provider=provider,
        model_name=model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    metadata = {
        **cost_metadata,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_input_tokens": cached_input_tokens or 0,
        "total_tokens": total_tokens if total_tokens is not None else _token_total(input_tokens, output_tokens),
        "task_name": task_name,
        "node_name": node_name,
        "provider_request_id_present": bool(provider_request_id),
        "request_status": request_status,
        "parse_status": parse_status,
    }
    return record_usage_event(
        workspace_id=workspace_id,
        event_type="llm_call",
        quantity=1,
        unit="call",
        created_by=created_by,
        thread_id=thread_id,
        job_id=job_id,
        provider=provider,
        model_name=model_name,
        plan=plan,
        cost_usd=cost,
        idempotency_key=_usage_call_idempotency_key("llm", provider_request_id, job_id, node_name, call_index),
        metadata=metadata,
    )


def record_t2i_usage(
    *,
    workspace_id: str,
    engine: str,
    model_name: str | None,
    image_count: int,
    plan: str | None,
    created_by: str | None = None,
    thread_id: str | None = None,
    job_id: str | None = None,
    width: int | None = None,
    height: int | None = None,
    quality: str | None = None,
    request_mode: str | None = None,
    provider_request_id: str | None = None,
    attempt_index: int | None = None,
    generation_status: str = "succeeded",
) -> dict | None:
    if engine in {"mock", "dry_run"} or image_count <= 0:
        return None
    cost, cost_metadata = calculate_t2i_cost(provider=_provider_for_engine(engine), model_name=model_name or engine, image_count=image_count)
    return record_usage_event(
        workspace_id=workspace_id,
        event_type="t2i_generation",
        quantity=image_count,
        unit="image",
        created_by=created_by,
        thread_id=thread_id,
        job_id=job_id,
        provider=_provider_for_engine(engine),
        model_name=model_name or engine,
        plan=plan,
        cost_usd=cost,
        idempotency_key=_usage_call_idempotency_key("t2i", provider_request_id, job_id, engine, attempt_index),
        metadata={
            **cost_metadata,
            "engine": engine,
            "width": width,
            "height": height,
            "quality": quality,
            "variant_count": image_count,
            "request_mode": request_mode,
            "provider_request_id_present": bool(provider_request_id),
            "generation_status": generation_status,
        },
    )


def record_r2_upload_usage(**kwargs) -> tuple[dict | None, dict | None]:
    return (
        record_usage_event(event_type="r2_upload", unit="byte", **kwargs),
        record_usage_event(event_type="r2_storage_added", unit="byte", **{**kwargs, "idempotency_key": _storage_added_key(kwargs.get("idempotency_key"))}),
    )


def record_r2_storage_removed(**kwargs) -> dict | None:
    return record_usage_event(event_type="r2_storage_removed", unit="byte", **kwargs)


def record_modal_gpu_usage(
    *,
    workspace_id: str,
    runtime_seconds: Decimal | int | float | str | None,
    plan: str | None,
    created_by: str | None = None,
    thread_id: str | None = None,
    job_id: str | None = None,
    model_name: str | None = None,
    gpu_type: str | None = None,
    modal_call_id: str | None = None,
    completion_status: str | None = None,
    metadata: dict | None = None,
) -> dict | None:
    seconds = decimal_or_none(runtime_seconds)
    if seconds is None or seconds <= 0:
        return None
    cost, cost_metadata = calculate_modal_cost(gpu_type=gpu_type, runtime_seconds=seconds)
    return record_usage_event(
        workspace_id=workspace_id,
        event_type="modal_gpu_runtime",
        quantity=seconds,
        unit="second",
        created_by=created_by,
        thread_id=thread_id,
        job_id=job_id,
        provider="modal",
        model_name=model_name,
        plan=plan,
        cost_usd=cost,
        idempotency_key=_idempotency_key("modal", modal_call_id or job_id, "runtime"),
        metadata={
            **cost_metadata,
            **(metadata or {}),
            "gpu_type": gpu_type,
            "runtime_seconds": str(seconds),
            "modal_call_id_present": bool(modal_call_id),
            "completion_status": completion_status,
        },
    )


def get_usage_summary(
    *,
    workspace_id: str,
    scope: str = "workspace",
    created_by: str | None = None,
    plan: str | None = None,
    quota_plan: str | None = None,
    event_plan_filter: str | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> dict:
    if scope not in {"workspace", "user"}:
        raise InvalidUsageScope("Usage scope must be workspace or user.")
    if scope == "user" and not created_by:
        raise InvalidUsageScope("User scope requires a resolved user.")
    if (start_at is None) != (end_at is None):
        raise InvalidUsageRange("startAt and endAt must be provided together.")
    if start_at is None and end_at is None:
        start_at, end_at = current_utc_month_window()
    _validate_range(start_at, end_at)
    normalized_quota_plan = normalize_usage_quota_plan(quota_plan if quota_plan is not None else plan)
    normalized_event_plan_filter = normalize_usage_event_plan(event_plan_filter)
    if db_settings.get_db_backend() == "postgres":
        totals = usage_repo.aggregate_usage_summary(
            workspace_id=workspace_id,
            created_by=created_by if scope == "user" else None,
            start_at=start_at,
            end_at=end_at,
            plan=normalized_event_plan_filter,
        )
    else:
        totals = _aggregate_memory_usage(
            workspace_id=workspace_id,
            created_by=created_by if scope == "user" else None,
            start_at=start_at,
            end_at=end_at,
            plan=normalized_event_plan_filter,
        )
    normalized_totals = normalize_summary_totals(totals)
    return {
        "scope": scope,
        "plan": normalized_quota_plan,
        "window": {
            "startAt": _iso_z(start_at),
            "endAt": _iso_z(end_at),
            "timezone": "UTC",
        },
        "totals": normalized_totals,
        "quota": evaluate_plan_quota(plan=normalized_quota_plan, totals=normalized_totals),
        "byEventType": _normalize_breakdown(totals.get("by_event_type") or []),
        "byProvider": _normalize_breakdown(totals.get("by_provider") or []),
        "byModel": _normalize_breakdown(totals.get("by_model") or []),
        "byEventPlan": _normalize_breakdown(totals.get("by_event_plan") or []),
    }


def normalize_summary_totals(totals: dict[str, Any]) -> dict[str, Any]:
    estimated_cost = Decimal(str(totals.get("estimated_cost_usd") or 0))
    return {
        "llmCalls": int(Decimal(str(totals.get("llm_calls") or 0))),
        "llmInputTokens": int(Decimal(str(totals.get("llm_input_tokens") or 0))),
        "llmOutputTokens": int(Decimal(str(totals.get("llm_output_tokens") or 0))),
        "llmTotalTokens": int(Decimal(str(totals.get("llm_total_tokens") or 0))),
        "t2iImages": int(Decimal(str(totals.get("t2i_images") or 0))),
        "r2UploadBytes": int(Decimal(str(totals.get("r2_upload_bytes") or 0))),
        "r2StorageBytesAdded": int(Decimal(str(totals.get("r2_storage_bytes_added") or 0))),
        "r2StorageBytesRemoved": int(Decimal(str(totals.get("r2_storage_bytes_removed") or 0))),
        "estimatedNetStorageBytes": int(Decimal(str(totals.get("estimated_net_storage_bytes") or 0))),
        "modalGpuSeconds": str(Decimal(str(totals.get("modal_gpu_seconds") or 0))),
        "estimatedCostUsd": f"{estimated_cost:.8f}",
        "unpricedEventCount": int(Decimal(str(totals.get("unpriced_event_count") or 0))),
    }


def _normalize_breakdown(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        cost = Decimal(str(row.get("estimated_cost_usd") or 0))
        quantity = Decimal(str(row.get("quantity") or 0))
        normalized.append(
            {
                "key": row.get("key"),
                "unit": row.get("unit"),
                "quantity": str(quantity),
                "estimatedCostUsd": f"{cost:.8f}",
            }
        )
    return normalized


def sanitize_usage_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        output = {}
        for key, item in value.items():
            normalized = str(key).lower()
            if normalized in _BLOCKED_METADATA_KEYS or any(fragment in normalized for fragment in _SENSITIVE_METADATA_FRAGMENTS):
                continue
            output[str(key)] = sanitize_usage_metadata(item)
        return output
    if isinstance(value, list):
        return [sanitize_usage_metadata(item) for item in value[:50]]
    if isinstance(value, str):
        if _looks_like_local_or_object_path(value):
            return "hidden"
        return value[:300]
    return value


def _record_memory_usage_event(**kwargs) -> dict:
    idempotency_key = kwargs.get("idempotency_key")
    workspace_id = kwargs["workspace_id"]
    if idempotency_key:
        for row in _MEMORY_USAGE_EVENTS:
            if row.get("workspace_id") == workspace_id and row.get("idempotency_key") == idempotency_key:
                return row
    row = {
        "id": f"usage_{len(_MEMORY_USAGE_EVENTS) + 1}",
        "created_at": datetime.now(timezone.utc),
        **kwargs,
        "quantity": Decimal(str(kwargs.get("quantity") if kwargs.get("quantity") is not None else 1)),
        "cost_usd": decimal_or_none(kwargs.get("cost_usd")),
    }
    _MEMORY_USAGE_EVENTS.append(row)
    return row


def _aggregate_memory_usage(*, workspace_id: str, created_by: str | None, start_at: datetime, end_at: datetime, plan: str | None) -> dict:
    rows = [
        row for row in _MEMORY_USAGE_EVENTS
        if row.get("workspace_id") == workspace_id
        and (not created_by or row.get("created_by") == created_by)
        and (not plan or row.get("plan") == plan)
        and start_at <= _as_dt(row.get("created_at")) < end_at
    ]
    totals: dict[str, Any] = {
        "llm_calls": Decimal("0"),
        "llm_input_tokens": Decimal("0"),
        "llm_output_tokens": Decimal("0"),
        "llm_total_tokens": Decimal("0"),
        "t2i_images": Decimal("0"),
        "r2_upload_bytes": Decimal("0"),
        "r2_storage_bytes_added": Decimal("0"),
        "r2_storage_bytes_removed": Decimal("0"),
        "modal_gpu_seconds": Decimal("0"),
        "estimated_cost_usd": Decimal("0"),
        "unpriced_event_count": 0,
    }
    for row in rows:
        quantity = Decimal(str(row.get("quantity") or 0))
        event_type = row.get("event_type")
        metadata = row.get("metadata") or {}
        if event_type == "llm_call":
            totals["llm_calls"] += quantity
            totals["llm_input_tokens"] += Decimal(str(metadata.get("input_tokens") or 0))
            totals["llm_output_tokens"] += Decimal(str(metadata.get("output_tokens") or 0))
            totals["llm_total_tokens"] += Decimal(str(metadata.get("total_tokens") or 0))
        elif event_type == "t2i_generation":
            totals["t2i_images"] += quantity
        elif event_type == "r2_upload":
            totals["r2_upload_bytes"] += quantity
        elif event_type == "r2_storage_added":
            totals["r2_storage_bytes_added"] += quantity
        elif event_type == "r2_storage_removed":
            totals["r2_storage_bytes_removed"] += quantity
        elif event_type == "modal_gpu_runtime":
            totals["modal_gpu_seconds"] += quantity
        if row.get("cost_usd") is None:
            totals["unpriced_event_count"] += 1
        else:
            totals["estimated_cost_usd"] += Decimal(str(row.get("cost_usd")))
    totals["estimated_net_storage_bytes"] = totals["r2_storage_bytes_added"] - totals["r2_storage_bytes_removed"]
    totals["by_event_type"] = _group_memory(rows, "event_type")
    totals["by_provider"] = _group_memory(rows, "provider")
    totals["by_model"] = _group_memory(rows, "model_name")
    totals["by_event_plan"] = _group_memory(rows, "plan")
    return totals


def _group_memory(rows: list[dict], key: str) -> list[dict]:
    grouped: dict[Any, dict[str, Any]] = {}
    for row in rows:
        value = row.get(key)
        group_key = (value, row.get("unit"))
        bucket = grouped.setdefault(group_key, {"key": value, "unit": row.get("unit"), "quantity": Decimal("0"), "estimated_cost_usd": Decimal("0")})
        bucket["quantity"] += Decimal(str(row.get("quantity") or 0))
        if row.get("cost_usd") is not None:
            bucket["estimated_cost_usd"] += Decimal(str(row.get("cost_usd")))
    return list(grouped.values())


def _validate_range(start_at: datetime, end_at: datetime) -> None:
    if start_at >= end_at:
        raise InvalidUsageRange("startAt must be before endAt.")
    if end_at - start_at > timedelta(days=366):
        raise InvalidUsageRange("Usage range cannot exceed 366 days.")


def normalize_usage_event_plan(plan: str | None) -> str | None:
    if plan is None or plan == "":
        return None
    if plan in USAGE_PLANS:
        return plan
    raise InvalidUsagePlan("Invalid usage plan.")


def normalize_usage_quota_plan(plan: str | None) -> str:
    if plan is None or plan == "":
        return normalize_user_plan(None)
    if plan in USAGE_PLANS:
        return str(plan)
    raise InvalidUsagePlan("Invalid usage plan.")


def _positive_decimal(value: Any, *, field_name: str, default: Decimal | None) -> Decimal | None:
    if value is None or value == "":
        return default
    try:
        normalized = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric.") from exc
    if normalized < 0:
        raise ValueError(f"{field_name} must be non-negative.")
    return normalized


def _token_total(input_tokens: int | None, output_tokens: int | None) -> int | None:
    if input_tokens is None and output_tokens is None:
        return None
    return int(input_tokens or 0) + int(output_tokens or 0)


def _provider_for_engine(engine: str) -> str:
    if engine == "gpt_image_2":
        return "openai"
    if engine in {"sd35_large", "flux"}:
        return "local"
    return engine


def _idempotency_key(*parts: Any) -> str | None:
    clean = [str(part) for part in parts if part]
    if not clean:
        return None
    digest = hashlib.sha256(":".join(clean).encode("utf-8")).hexdigest()[:32]
    return f"usage:{digest}"


def _usage_call_idempotency_key(prefix: str, provider_request_id: str | None, *fallback_parts: Any) -> str | None:
    if provider_request_id:
        return _idempotency_key(prefix, "provider_request", provider_request_id)
    if any(part is None for part in fallback_parts):
        return None
    return _idempotency_key(prefix, *fallback_parts)


def _storage_added_key(value: Any) -> str | None:
    if not value:
        return None
    return f"{value}:storage_added"


def _as_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _looks_like_local_or_object_path(value: str) -> bool:
    lowered = value.lower()
    return (
        lowered.startswith(("data/", "data\\", "./data", "../data", "/tmp/", "/home/", "c:\\", "file://"))
        or "workspaces/" in lowered
        or "\\" in value
    )
