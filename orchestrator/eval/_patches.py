"""Eval-process-only monkeypatches that re-enrich data prod deliberately trims.

Serving keeps `state["llm_call_results"]` lean: develop's
`node_runner.safe_llm_call_result()` whitelists a handful of fields and DROPS
`token_usage`/`cost_estimate` (smaller state through every LangGraph checkpoint).
Serving never bills on those, so that is correct for prod.

Eval *does* bill on them. Rather than push the cost concern back into the serving
hot path (which would bloat every prod request's state), the eval process opts in
to the richer record here — same philosophy as tracked_builder's add_node patch:
observe prod without changing prod. This module is imported only by the eval
runner; production never loads it.

The patch fails LOUD, not silent: if upstream renames/reworks
`safe_llm_call_result`, the cost data silently reverting to NULL would be the worst
outcome, so we warn instead. Eval breaking loudly is fine; prod is untouched.
"""

from __future__ import annotations

import warnings
from typing import Any

_PATCHED = False


def enable_llm_usage_capture() -> bool:
    """Re-inject token_usage/cost_estimate into llm_call_results entries so the
    eval cost pipeline (ops_db._cost_of -> pricing) can price calls 'exact'.

    Idempotent. Returns True if the patch is active, False if it could not be
    applied (and emits a warning) — callers may ignore the result; eval still
    runs, cost just stays NULL as it would without the patch.
    """
    global _PATCHED
    if _PATCHED:
        return True

    try:
        import orchestrator.app.llm.node_runner as node_runner
    except Exception as exc:  # pragma: no cover - import guard
        warnings.warn(
            f"[eval] cannot import node_runner ({exc!r}); LLM cost will be NULL.",
            RuntimeWarning,
            stacklevel=2,
        )
        return False

    original = getattr(node_runner, "safe_llm_call_result", None)
    if not callable(original):
        warnings.warn(
            "[eval] node_runner.safe_llm_call_result not found — upstream may have "
            "renamed it. LLM cost tracking will be NULL until this patch is updated "
            "(see fix.md #12).",
            RuntimeWarning,
            stacklevel=2,
        )
        return False

    def safe_llm_call_result_with_usage(result: Any) -> dict[str, Any]:
        data = original(result)
        if not isinstance(data, dict):  # upstream changed the contract — bail loud
            warnings.warn(
                "[eval] safe_llm_call_result returned non-dict; usage capture "
                "skipped (see fix.md #12).",
                RuntimeWarning,
                stacklevel=2,
            )
            return data
        src = result.model_dump() if hasattr(result, "model_dump") else dict(result or {})
        for key in ("token_usage", "cost_estimate"):
            if src.get(key) is not None and data.get(key) is None:
                data[key] = src[key]
        tier = (src.get("model_selection") or {}).get("estimated_cost_tier")
        if tier and not data.get("estimated_cost_tier"):
            data["estimated_cost_tier"] = tier
        return data

    node_runner.safe_llm_call_result = safe_llm_call_result_with_usage  # type: ignore[assignment]
    _PATCHED = True
    return True
