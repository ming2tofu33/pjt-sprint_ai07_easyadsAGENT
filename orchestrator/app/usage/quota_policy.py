"""Plan quota policy helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from orchestrator.app.core.config import _get_env
from orchestrator.app.llm.plan_policy import normalize_user_plan
from orchestrator.app.usage.types import SUMMARY_METRICS


def current_utc_month_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.now(timezone.utc)
    now = now.astimezone(timezone.utc)
    start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    return start, end


def load_usage_quota_config() -> dict[str, dict[str, int | str | None]]:
    raw = _get_env("EASYADS_USAGE_QUOTAS_JSON", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def get_usage_quota_enforcement_enabled() -> bool:
    return str(_get_env("EASYADS_ENFORCE_USAGE_QUOTAS", "false") or "").strip().lower() in {"1", "true", "yes", "on"}


def evaluate_plan_quota(
    *,
    plan: str | None,
    totals: dict[str, Any],
    quota_config: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    normalized_plan = normalize_user_plan(plan)
    config = quota_config if quota_config is not None else load_usage_quota_config()
    limits = config.get(normalized_plan) or {}
    results = []
    for metric in SUMMARY_METRICS:
        if metric == "estimatedNetStorageBytes":
            continue
        used = totals.get(metric) or 0
        limit = limits.get(metric)
        if limit is None:
            results.append(_quota_row(metric, used, None, configured=False))
            continue
        try:
            numeric_limit = Decimal(str(limit))
        except Exception:
            results.append(_quota_row(metric, used, None, configured=False))
            continue
        results.append(_quota_row(metric, used, numeric_limit, configured=True))
    return results


def _quota_row(metric: str, used: Any, limit: Decimal | None, *, configured: bool) -> dict[str, Any]:
    used_decimal = Decimal(str(used or 0))
    enforcement_enabled = get_usage_quota_enforcement_enabled()
    if limit is None:
        return {
            "metric": metric,
            "limit": None,
            "used": _decimal_json(used_decimal),
            "remaining": None,
            "exceeded": False,
            "configured": configured,
            "enforced": False,
        }
    remaining = limit - used_decimal
    if remaining < 0:
        remaining = Decimal("0")
    return {
        "metric": metric,
        "limit": _decimal_json(limit),
        "used": _decimal_json(used_decimal),
        "remaining": _decimal_json(remaining),
        "exceeded": used_decimal > limit,
        "configured": configured,
        "enforced": enforcement_enabled,
    }


def _decimal_json(value: Decimal) -> int | str:
    if value == value.to_integral_value():
        return int(value)
    return str(value)
