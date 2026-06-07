"""LLM-as-Judge evaluator — scores pipeline quality using gpt-5.4-nano.

Reads node outputs from ops DB, calls OpenAI, writes score_items to eval DB.
Requires: LLM_ENABLE_API_CALL=true + OPENAI_API_KEY set in env/.env/api_key.env.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Generator

from orchestrator.app.core.config import _get_env, _get_bool
from orchestrator.eval.config import OPS_DB_PATH, EVAL_DB_PATH
from orchestrator.eval.eval_db import EvalDBWriter

# Map item_id → (description, list of node_names to fetch output from)
_ITEM_SPEC: dict[str, tuple[str, list[str]]] = {
    "II-1": (
        "Marketing context understanding accuracy: "
        "Does the extracted context correctly capture business type, product, target audience, and campaign goal?",
        ["validator"],
    ),
    "II-2": (
        "Missing field detection accuracy: "
        "Are the detected missing fields genuinely missing and relevant?",
        ["validator"],
    ),
    "II-3": (
        "Context update consistency: "
        "After user provides missing info, is the updated context internally consistent?",
        ["state_update", "validator"],
    ),
    "III-3": (
        "Copy tone fit: "
        "Does the ad copy tone match the requested tone profile and target audience?",
        ["auto_pilot_copywriting", "state_update_selected_copy", "tone_binding"],
    ),
    "III-4": (
        "CTA clarity: "
        "Is the call-to-action clear, specific, and actionable?",
        ["auto_pilot_copywriting", "state_update_selected_copy"],
    ),
    "III-5": (
        "Brand tone consistency: "
        "Is the copy consistent with the brand identity described in the context?",
        ["auto_pilot_copywriting", "state_update_selected_copy", "validator"],
    ),
    "IV-3": (
        "Layout slot count fit: "
        "Is the number of text layout slots appropriate for the ad format and copy length?",
        ["text_layout_planner", "format_planner"],
    ),
    "IV-4": (
        "Typography hierarchy consistency: "
        "Do font sizes and weights form a clear visual hierarchy (headline > subhead > body)?",
        ["text_style_binder", "text_layout_planner"],
    ),
    "IV-5": (
        "Copy placement fit: "
        "Are the copy slots positioned sensibly relative to the ad format and safe areas?",
        ["copy_spec_parser", "text_layout_planner"],
    ),
    "V-3": (
        "Cost efficiency: "
        "Given the user plan, was the LLM usage proportionate? Penalize unnecessary api_* calls on free/economic plans.",
        ["result"],
    ),
    "V-4": (
        "Completion without retry: "
        "Did the pipeline complete without failed nodes or partial re-runs?",
        ["result"],
    ),
}

_SYSTEM_PROMPT = (
    "You are an advertising pipeline quality evaluator. "
    "Score the given criterion on a 1-5 scale based only on the evidence provided.\n"
    "Rubric: 5=Excellent, 4=Good minor gap, 3=Acceptable notable gap, 2=Poor significant failure, 1=Very poor/missing.\n"
    "Return JSON only: {\"score\": <int 1-5>, \"reason\": \"<one sentence>\"}"
)


@contextmanager
def _ops_conn(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _fetch_node_outputs(conn: sqlite3.Connection, job_id: str, node_names: list[str]) -> dict[str, Any]:
    """Fetch latest completed output_snapshot per node_name, merged into one dict."""
    merged: dict[str, Any] = {}
    for node_name in node_names:
        row = conn.execute(
            """SELECT nso.output_snapshot
               FROM node_state_outputs nso
               JOIN node_executions ne ON ne.id = nso.node_exec_id
               WHERE ne.job_id=? AND ne.node_name=? AND ne.status='completed'
               ORDER BY ne.id DESC LIMIT 1""",
            (job_id, node_name),
        ).fetchone()
        if row and row["output_snapshot"]:
            try:
                data = json.loads(row["output_snapshot"])
                merged[node_name] = data
            except Exception:
                pass
    return merged


def _fetch_job_stats(conn: sqlite3.Connection, job_id: str) -> dict[str, Any]:
    """Fetch cost summary and failed node count for V-3 / V-4 scoring."""
    stats: dict[str, Any] = {}
    cost_row = conn.execute(
        "SELECT total_api_calls, fallback_calls, total_tokens, total_cost_usd, "
        "cost_estimated, estimated_cost_tier FROM job_cost_summary WHERE job_id=?",
        (job_id,),
    ).fetchone()
    if cost_row:
        stats["cost_summary"] = dict(cost_row)
    fail_row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM node_executions WHERE job_id=? AND status='failed'",
        (job_id,),
    ).fetchone()
    stats["failed_nodes"] = fail_row["cnt"] if fail_row else 0
    plan_row = conn.execute(
        "SELECT user_plan FROM jobs WHERE job_id=?", (job_id,)
    ).fetchone()
    stats["user_plan"] = plan_row["user_plan"] if plan_row else "unknown"
    return stats


def _call_llm(prompt: str, api_key: str, model: str, timeout: int = 30) -> dict[str, Any] | None:
    """Call OpenAI and return parsed JSON or None on any failure."""
    try:
        from openai import OpenAI
    except ImportError:
        return None
    try:
        client = OpenAI(api_key=api_key, timeout=timeout)
        response = client.responses.create(
            model=model,
            input=f"{_SYSTEM_PROMPT}\n\n{prompt}",
            text={"format": {"type": "json_object"}},
        )
        raw = getattr(response, "output_text", None) or ""
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _build_prompt(item_id: str, description: str, evidence: dict[str, Any]) -> str:
    evidence_text = json.dumps(evidence, ensure_ascii=False, indent=2)
    if len(evidence_text) > 3000:
        evidence_text = evidence_text[:3000] + "\n... [truncated]"
    return f"Criterion [{item_id}]: {description}\n\nEvidence:\n{evidence_text}"


def run_llm_eval(
    eval_id: str,
    job_id: str,
    ops_db_path: str = OPS_DB_PATH,
    eval_db_path: str = EVAL_DB_PATH,
    api_key: str | None = None,
    model: str | None = None,
) -> list[str]:
    """Score all LLM-evaluable items for eval_id/job_id using gpt-5.4-nano.

    Returns list of scored item_ids. Skips items where LLM call fails (no partial writes).
    Raises RuntimeError if API call is globally disabled.
    """
    if not _get_bool("LLM_ENABLE_API_CALL", False):
        raise RuntimeError("LLM_ENABLE_API_CALL is false — set to true to run llm eval")

    resolved_key = api_key or _get_env("OPENAI_API_KEY", "")
    if not resolved_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    resolved_model = model or _get_env("LLM_OPENAI_TEXT_MODEL_NANO", "gpt-5.4-nano") or "gpt-5.4-nano"
    timeout = int(_get_env("LLM_REQUEST_TIMEOUT_SECONDS", "30") or "30")

    writer = EvalDBWriter(eval_db_path)
    scored: list[str] = []

    with _ops_conn(ops_db_path) as conn:
        job_stats = _fetch_job_stats(conn, job_id)

        for item_id, (description, node_names) in _ITEM_SPEC.items():
            if item_id in ("V-3", "V-4"):
                evidence = job_stats
            else:
                evidence = _fetch_node_outputs(conn, job_id, node_names)
                if not evidence:
                    continue

            prompt = _build_prompt(item_id, description, evidence)
            result = _call_llm(prompt, resolved_key, resolved_model, timeout)
            if result is None:
                continue

            score = result.get("score")
            reason = result.get("reason", "")
            if not isinstance(score, int) or not (1 <= score <= 5):
                continue

            writer.write_score_item(eval_id, item_id, score, notes=reason, evaluator_type="llm")
            scored.append(item_id)

    return scored
