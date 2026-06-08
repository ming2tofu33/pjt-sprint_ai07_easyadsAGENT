"""Usage pricing helpers.

Pricing is configuration-driven. Missing prices return None rather than zero.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any

from orchestrator.app.core.config import _get_env


PRICING_VERSION = "v1"


def load_usage_pricing_catalog() -> dict[str, Any]:
    raw = _get_env("EASYADS_USAGE_PRICING_JSON", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def calculate_llm_cost(
    *,
    provider: str | None,
    model_name: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    catalog: dict[str, Any] | None = None,
) -> tuple[Decimal | None, dict[str, Any]]:
    catalog = catalog if catalog is not None else load_usage_pricing_catalog()
    key = _pricing_key(provider, model_name)
    rates = ((catalog.get("llm") or {}).get(key) or {}) if key else {}
    input_rate = decimal_or_none(rates.get("input_per_1m_tokens_usd"))
    output_rate = decimal_or_none(rates.get("output_per_1m_tokens_usd"))
    if input_rate is None or output_rate is None or input_tokens is None or output_tokens is None:
        return None, {"cost_source": "unpriced", "pricing_key": key, "pricing_version": PRICING_VERSION}
    cost = (Decimal(input_tokens) * input_rate + Decimal(output_tokens) * output_rate) / Decimal(1_000_000)
    return cost, {"cost_source": "configured_estimate", "pricing_key": key, "pricing_version": PRICING_VERSION}


def calculate_t2i_cost(
    *,
    provider: str | None,
    model_name: str | None,
    image_count: int,
    catalog: dict[str, Any] | None = None,
) -> tuple[Decimal | None, dict[str, Any]]:
    catalog = catalog if catalog is not None else load_usage_pricing_catalog()
    key = _pricing_key(provider, model_name)
    rates = ((catalog.get("t2i") or {}).get(key) or {}) if key else {}
    per_image = decimal_or_none(rates.get("per_image_usd"))
    if per_image is None:
        return None, {"cost_source": "unpriced", "pricing_key": key, "pricing_version": PRICING_VERSION}
    return Decimal(image_count) * per_image, {"cost_source": "configured_estimate", "pricing_key": key, "pricing_version": PRICING_VERSION}


def calculate_modal_cost(
    *,
    gpu_type: str | None,
    runtime_seconds: Decimal | int | float | None,
    catalog: dict[str, Any] | None = None,
) -> tuple[Decimal | None, dict[str, Any]]:
    catalog = catalog if catalog is not None else load_usage_pricing_catalog()
    key = gpu_type or None
    rates = ((catalog.get("modal") or {}).get(key) or {}) if key else {}
    per_second = decimal_or_none(rates.get("per_second_usd"))
    seconds = decimal_or_none(runtime_seconds)
    if per_second is None or seconds is None:
        return None, {"cost_source": "unpriced", "pricing_key": key, "pricing_version": PRICING_VERSION}
    return seconds * per_second, {"cost_source": "configured_estimate", "pricing_key": key, "pricing_version": PRICING_VERSION}


def _pricing_key(provider: str | None, model_name: str | None) -> str | None:
    if not provider or not model_name:
        return None
    return f"{provider}:{model_name}"
