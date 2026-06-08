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
PRICING_VERSION = "2026-06-05-gpt5.4+gpu"


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


# ── Self-hosted (GPU-billed) pricing ────────────────────────────────────────
# Self-hosted models (Gemma local LLM via local_openai_compat; FLUX/SD3.5 T2I on
# Modal) are NOT token-billed — you pay for GPU time. The product's native cost
# primitive is gpu_seconds (the Modal worker returns it; modal/service.py emits a
# "modal_gpu_seconds" billing event). So the standard for these lanes is:
#     cost = gpu_seconds * (gpu_$per_hour / 3600)
# when gpu_seconds is surfaced into the call record, else $0 marginal cost
# (source="self_hosted") — never a fabricated per-token price.
#
# GPU_PRICES is USD/hour keyed by gpu_type (T2IResult/worker report e.g. "L40S").
# Left EMPTY by default on purpose: a Modal GPU $/hr rate is deployment-specific
# and was not in any captured source, so we do not hardcode an unverified number.
# Set it per environment via EVAL_GPU_PRICES_JSON, e.g. {"L40S": 1.95, "A100": 3.7}.
# Until a rate is set, GPU lanes record cost as "gpu_unpriced" (NULL), not $0.
SELF_HOSTED_LLM_CLASSES: set[str] = {"local_fast", "local_quality", "local_gemma"}

GPU_PRICES: dict[str, float] = {}


def _apply_gpu_env_overrides() -> None:
    raw = _get_env("EVAL_GPU_PRICES_JSON", "")
    if not raw or not raw.strip():
        return
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return
    if not isinstance(data, dict):
        return
    for gpu_type, rate in data.items():
        try:
            GPU_PRICES[str(gpu_type).strip()] = float(rate)
        except (TypeError, ValueError):
            continue


_apply_gpu_env_overrides()


def gpu_cost(gpu_type: str | None, gpu_seconds: float | int | None) -> tuple[float | None, str]:
    """GPU-time cost: gpu_seconds × (USD/hr ÷ 3600) → (cost_usd, source).

    source: gpu_exact (priced) | self_hosted ($0, no GPU time billed) |
            gpu_unpriced (no rate for this gpu_type) | gpu_seconds_missing.
    """
    if gpu_seconds is None:
        return None, "gpu_seconds_missing"
    try:
        secs = float(gpu_seconds)
    except (TypeError, ValueError):
        return None, "gpu_seconds_missing"
    if secs <= 0:
        return 0.0, "self_hosted"
    rate = GPU_PRICES.get((gpu_type or "").strip())
    if rate is None:
        return None, "gpu_unpriced"
    return round(secs / 3600.0 * rate, 8), "gpu_exact"


def self_hosted_llm_cost(usage: dict | None) -> tuple[float | None, str]:
    """Cost for a self-hosted LLM call. GPU-billed, not token-billed.

    Prices by gpu_seconds/gpu_type when the endpoint or worker surfaces them in the
    usage dict; otherwise returns $0 marginal cost (source="self_hosted") — running
    an owned/self-hosted model has no per-call API charge. Never fabricates a
    per-token price for a model you host.
    """
    gpu_seconds = gpu_type = None
    if isinstance(usage, dict):
        gpu_seconds = usage.get("gpu_seconds")
        gpu_type = usage.get("gpu_type")
    if gpu_seconds is None:
        return 0.0, "self_hosted"
    return gpu_cost(gpu_type, gpu_seconds)


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


# Self-hosted local T2I engines bill by GPU time (gpu_seconds), not per image —
# same standard as the self-hosted LLM lane (#13). The SD3.5/FLUX local engines
# surface gpu_seconds (+gpu_type) in T2IResult.metadata; price via gpu_cost.
SELF_HOSTED_T2I_ENGINES: set[str] = {"sd35_large", "flux"}


def t2i_cost(engine: str | None, n_images: int, metadata: dict | None = None) -> tuple[float | None, str]:
    """T2I 비용 디스패처: 셀프호스트(sd35_large/flux)는 gpu_seconds로, API 엔진(gpt_image_2)은 이미지당 정액으로.

    self-hosted → gpu_cost(metadata.gpu_type, metadata.gpu_seconds):
        gpu_exact(요율 있음) | gpu_unpriced(요율 미설정) | gpu_seconds_missing.
    flat → t2i_image_cost: exact | image_unpriced | engine_unknown.
    """
    if engine in SELF_HOSTED_T2I_ENGINES:
        md = metadata or {}
        return gpu_cost(md.get("gpu_type"), md.get("gpu_seconds"))
    return t2i_image_cost(engine, n_images)


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
