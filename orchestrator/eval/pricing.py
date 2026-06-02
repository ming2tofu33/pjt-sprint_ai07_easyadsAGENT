"""Model price book + usage-based USD cost — the Langfuse/LangSmith costing model, local.

Hosted LLM-observability tools (Langfuse, LangSmith) compute spend the same way:
keep a static price book keyed by model, then multiply the call's token usage by
the per-token unit price. There is no magic — the value is the price table plus
clean usage ingestion. This module reproduces exactly that, with zero external
SDK and zero network egress, so it fits this project's offline / mock-first and
secret-hygiene posture (no traces or keys ever leave the box).

Cost = (billable_input * input_price)
     + (cached_input    * cached_price)
     + (output          * output_price)   ... all per 1,000,000 tokens.

Token usage comes from LLMCallResult.token_usage (a dict). The OpenAI adapter must
populate it from response.usage — see fix.md. Until then real calls record
source="usage_missing" and a NULL cost (we never fabricate a number); mock/local
calls report 0 tokens and therefore an exact $0.00.

╔══════════════════════════════════════════════════════════════════════════════╗
║  REAL RATE CARD (OpenAI GPT-5.4 family, per 1M tokens, captured 2026-06-02).   ║
║  api_full=gpt-5.4 (2.50/15.00, cached 0.25), api_nano=gpt-5.4-nano             ║
║  (0.20/1.25, cached 0.02), api_mini=gpt-5.4-mini (0.75 input, cached 0.075).   ║
║  NOTE: gpt-5.4-mini *output* price was not published in the captured source —  ║
║  output_per_1m=4.50 is an interpolation (≈6× input, matching nano/full ratio). ║
║  Replace it (or set EVAL_MODEL_PRICES_JSON) once the official mini output rate  ║
║  is known, and bump PRICING_VERSION so stored rows stay auditable.             ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from orchestrator.app.core.config import _get_env

# Bump whenever PRICES changes so every llm_calls / job_cost_summary row records
# which rate card produced its cost (Langfuse calls this the "price version").
PRICING_VERSION = "2026-06-02-gpt5.4"


@dataclass(frozen=True)
class ModelPrice:
    """USD per 1,000,000 tokens. cached_input_per_1m=None ⇒ cached billed as input."""

    input_per_1m: float
    output_per_1m: float
    cached_input_per_1m: float | None = None


# Keyed by INTERNAL model_class (what ModelSelection carries) so lookup needs no
# concrete model name. Concrete OpenAI names are added as aliases below.
PRICES: dict[str, ModelPrice] = {
    # Non-API engines are free to run locally → exact $0.00 (not "unpriced").
    "mock": ModelPrice(0.0, 0.0, 0.0),
    "local_gemma": ModelPrice(0.0, 0.0, 0.0),
    # Real OpenAI GPT-5.4 rate card (USD per 1M tokens, captured 2026-06-02).
    "api_nano": ModelPrice(input_per_1m=0.20, output_per_1m=1.25, cached_input_per_1m=0.02),
    "api_mini": ModelPrice(input_per_1m=0.75, output_per_1m=4.50, cached_input_per_1m=0.075),  # output interpolated, see header
    "api_full": ModelPrice(input_per_1m=2.50, output_per_1m=15.00, cached_input_per_1m=0.25),
    # Vision shares the full-class gpt-5.4 model (text+image in, text out).
    "api_vision": ModelPrice(input_per_1m=2.50, output_per_1m=15.00, cached_input_per_1m=0.25),
}

# Concrete model name → internal class, so a row tagged "gpt-5.4-nano" still prices.
_ALIASES: dict[str, str] = {
    "gpt-5.4-nano": "api_nano",
    "gpt-5.4-mini": "api_mini",
    "gpt-5.4": "api_full",
}


def _apply_env_overrides() -> None:
    """Merge EVAL_MODEL_PRICES_JSON over PRICES (Langfuse-style configurable prices).

    Format: {"api_nano": {"input_per_1m": 0.05, "output_per_1m": 0.4,
                          "cached_input_per_1m": 0.005}, ...}
    Malformed JSON or entries are ignored so a bad env var can never crash eval.
    """
    raw = _get_env("EVAL_MODEL_PRICES_JSON", "")
    if not raw or not raw.strip():
        return
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return
    if not isinstance(data, dict):
        return
    for key, spec in data.items():
        if not isinstance(spec, dict):
            continue
        try:
            PRICES[key] = ModelPrice(
                input_per_1m=float(spec["input_per_1m"]),
                output_per_1m=float(spec["output_per_1m"]),
                cached_input_per_1m=(
                    float(spec["cached_input_per_1m"]) if spec.get("cached_input_per_1m") is not None else None
                ),
            )
        except (KeyError, TypeError, ValueError):
            continue


_apply_env_overrides()


# ── T2I (image) pricing ─────────────────────────────────────────────────────
# Image models bill PER IMAGE (by size/quality), not per token, so they have a
# separate flat-rate book keyed by the t2i engine name (T2IResult.engine).
# gpt_image_2 → OpenAI gpt-image-1. The exact per-image USD rate was NOT in the
# captured price source, so the default is None (→ count stored, cost recorded as
# "unpriced", never fabricated). Set the real rate via T2I_IMAGE_PRICE_USD (flat,
# applies to gpt_image_2) or T2I_IMAGE_PRICES_JSON ({"gpt_image_2": 0.04, ...}).
T2I_IMAGE_PRICES: dict[str, float | None] = {
    "mock": 0.0,          # local dummy PNG → exact $0
    "gpt_image_2": None,  # real gpt-image-1 — set via env once the rate is known
}


def _apply_t2i_env_overrides() -> None:
    flat = _get_env("T2I_IMAGE_PRICE_USD", "")
    if flat and flat.strip():
        try:
            T2I_IMAGE_PRICES["gpt_image_2"] = float(flat)
        except (TypeError, ValueError):
            pass
    raw = _get_env("T2I_IMAGE_PRICES_JSON", "")
    if raw and raw.strip():
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                for k, v in data.items():
                    try:
                        T2I_IMAGE_PRICES[k] = float(v) if v is not None else None
                    except (TypeError, ValueError):
                        continue
        except (ValueError, TypeError):
            pass


_apply_t2i_env_overrides()


def t2i_image_cost(engine: str | None, n_images: int) -> tuple[float | None, str]:
    """Per-image flat rate × image count → (cost_usd, source).

    source: exact (priced) | image_unpriced (no rate for this engine) | engine_unknown.
    """
    if not engine:
        return None, "engine_unknown"
    if engine not in T2I_IMAGE_PRICES:
        return None, "engine_unknown"
    rate = T2I_IMAGE_PRICES[engine]
    if rate is None:
        return None, "image_unpriced"
    return round(rate * max(0, n_images), 8), "exact"


def price_for(model_key: str | None) -> ModelPrice | None:
    """Resolve a price by internal class or concrete model name. None if unpriced."""
    if not model_key:
        return None
    key = model_key.strip()
    if key in PRICES:
        return PRICES[key]
    return PRICES.get(_ALIASES.get(key, ""))


def _tok(usage: dict, *names: str) -> int:
    """First present, non-null token count among aliases (Responses vs ChatCompletions)."""
    for name in names:
        val = usage.get(name)
        if val is not None:
            try:
                return max(0, int(val))
            except (TypeError, ValueError):
                return 0
    return 0


@dataclass(frozen=True)
class CostResult:
    cost_usd: float | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    # exact        → priced from real usage against the price book
    # usage_missing → model is priced but the call carried no token usage
    # model_unpriced→ no price book entry for this model
    source: str


def compute_cost_usd(model_key: str | None, token_usage: dict | None) -> CostResult:
    """Usage × price book → USD. Mirrors Langfuse/LangSmith cost computation.

    Accepts both OpenAI Responses API keys (input_tokens/output_tokens) and
    ChatCompletions keys (prompt_tokens/completion_tokens), plus a cached-token
    field for the cached-input discount.
    """
    price = price_for(model_key)
    if price is None:
        return CostResult(None, None, None, None, "model_unpriced")
    if not token_usage or not isinstance(token_usage, dict):
        return CostResult(None, None, None, None, "usage_missing")

    prompt = _tok(token_usage, "prompt_tokens", "input_tokens")
    completion = _tok(token_usage, "completion_tokens", "output_tokens")
    cached = _tok(token_usage, "cached_tokens", "cached_input_tokens")
    cached = min(cached, prompt)  # cached is a subset of prompt/input tokens
    total = _tok(token_usage, "total_tokens") or (prompt + completion)

    cached_rate = price.cached_input_per_1m if price.cached_input_per_1m is not None else price.input_per_1m
    cost = (
        (prompt - cached) * price.input_per_1m
        + cached * cached_rate
        + completion * price.output_per_1m
    ) / 1_000_000.0
    return CostResult(round(cost, 8), prompt, completion, total, "exact")
