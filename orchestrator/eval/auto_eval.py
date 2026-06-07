"""Auto-evaluable gate runners — derive pass/fail from ops DB without human input."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Generator

from orchestrator.eval.eval_db import EvalDBWriter
from orchestrator.eval.config import OPS_DB_PATH, EVAL_DB_PATH


@contextmanager
def _ops_conn(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _get_node_output(conn: sqlite3.Connection, job_id: str, node_name: str) -> dict[str, Any] | None:
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
            return json.loads(row["output_snapshot"])
        except Exception:
            return None
    return None


def eval_gate_iii2(
    job_id: str,
    eval_id: str,
    eval_writer: EvalDBWriter,
    ops_db_path: str = OPS_DB_PATH,
) -> bool:
    """III-2: image_prompt_planner enforces TLFP safety (no text in T2I image)."""
    with _ops_conn(ops_db_path) as conn:
        output = _get_node_output(conn, job_id, "image_prompt_planner")

    evidence: dict[str, Any] = {}
    passed = False

    if output is None:
        failure_reason = "image_prompt_planner output not found in DB"
    else:
        spec = output.get("image_prompt_spec") or {}
        must_not_include = spec.get("must_not_include_text")
        meta = spec.get("metadata") or {}
        safety_enforced = meta.get("safety_enforced")
        neg_prompt = spec.get("negative_prompt_en") or ""
        has_no_text_terms = any(
            kw in neg_prompt.lower() for kw in ["text", "letter", "word", "caption", "typography"]
        )
        evidence = {
            "must_not_include_text": must_not_include,
            "safety_enforced": safety_enforced,
            "negative_prompt_has_no_text_terms": has_no_text_terms,
        }
        if must_not_include is True and has_no_text_terms:
            passed = True
            failure_reason = None
        else:
            failure_reason = f"safety not enforced: must_not_include_text={must_not_include}, neg_prompt_ok={has_no_text_terms}"

    eval_writer.write_gate_result(eval_id, "III-2", passed, failure_reason, evidence, auto_evaluated=True)
    return passed


def eval_gate_v1(
    job_id: str,
    eval_id: str,
    eval_writer: EvalDBWriter,
    ops_db_path: str = OPS_DB_PATH,
) -> bool:
    """V-1: all fallback LLMCallResults have valid schema (success=False but schema intact)."""
    with _ops_conn(ops_db_path) as conn:
        rows = conn.execute(
            "SELECT success, error_code FROM llm_calls WHERE job_id=? AND fallback_used=1",
            (job_id,),
        ).fetchall()

    evidence: dict[str, Any] = {"fallback_count": len(rows)}
    # Gate passes if all fallback calls have a recorded error_code (schema intact)
    invalid = [r for r in rows if not r["error_code"]]
    passed = len(invalid) == 0
    failure_reason = None if passed else f"{len(invalid)} fallback calls missing error_code"
    evidence["invalid_fallback_count"] = len(invalid)

    eval_writer.write_gate_result(eval_id, "V-1", passed, failure_reason, evidence, auto_evaluated=True)
    return passed


def eval_gate_v2(
    job_id: str,
    eval_id: str,
    eval_writer: EvalDBWriter,
    ops_db_path: str = OPS_DB_PATH,
) -> bool:
    """V-2: api_* call count does not exceed plan_policy.max_api_calls_per_job."""
    with _ops_conn(ops_db_path) as conn:
        job_row = conn.execute(
            "SELECT user_plan FROM jobs WHERE job_id=?", (job_id,)
        ).fetchone()
        api_count = conn.execute(
            """SELECT COUNT(*) as cnt FROM llm_calls
               WHERE job_id=? AND model_class LIKE 'api_%' AND llm_attempted=1""",
            (job_id,),
        ).fetchone()

    _plan_limits = {"free": 0, "economic": 3, "premium": 10, "internal_benchmark": 999}
    user_plan = job_row["user_plan"] if job_row else "free"
    max_allowed = _plan_limits.get(user_plan, 0)
    actual = api_count["cnt"] if api_count else 0

    passed = actual <= max_allowed
    evidence = {"user_plan": user_plan, "max_allowed": max_allowed, "actual_api_calls": actual}
    failure_reason = None if passed else f"{actual} api calls > limit {max_allowed} for plan {user_plan}"

    eval_writer.write_gate_result(eval_id, "V-2", passed, failure_reason, evidence, auto_evaluated=True)
    return passed


def eval_gate_vi1(
    job_id: str,
    eval_id: str,
    eval_writer: EvalDBWriter,
    ops_db_path: str = OPS_DB_PATH,
) -> bool:
    """VI-1: render_text_in_image=False everywhere in node_state_outputs."""
    with _ops_conn(ops_db_path) as conn:
        rows = conn.execute(
            """SELECT ne.node_name, nso.output_snapshot
               FROM node_state_outputs nso
               JOIN node_executions ne ON ne.id = nso.node_exec_id
               WHERE ne.job_id=?""",
            (job_id,),
        ).fetchall()

    violations: list[str] = []
    for row in rows:
        snap = row["output_snapshot"]
        if not snap:
            continue
        try:
            data = json.loads(snap)
        except Exception:
            continue
        # Check top-level and nested current_brief
        if data.get("render_text_in_image") is True:
            violations.append(row["node_name"])
        brief = data.get("current_brief") or {}
        if isinstance(brief, dict) and brief.get("render_text_in_image") is True:
            violations.append(f"{row['node_name']}.current_brief")

    passed = len(violations) == 0
    evidence = {"violations": violations}
    failure_reason = None if passed else f"render_text_in_image=True in nodes: {violations}"

    eval_writer.write_gate_result(eval_id, "VI-1", passed, failure_reason, evidence, auto_evaluated=True)
    return passed


def eval_gate_vi3(
    job_id: str,
    eval_id: str,
    eval_writer: EvalDBWriter,
    ops_db_path: str = OPS_DB_PATH,
) -> bool:
    """VI-3: each node used a model_class allowed by plan_policy.node_policies."""
    _plan_allowed: dict[str, list[str]] = {
        "free": ["mock", "local_fast", "local_quality"],
        "economic": ["mock", "local_fast", "local_quality", "api_nano"],
        "premium": ["mock", "local_fast", "local_quality", "api_nano", "api_mini", "api_full", "api_vision"],
        "internal_benchmark": ["mock", "local_fast", "local_quality", "api_nano", "api_mini", "api_full", "api_vision"],
    }
    with _ops_conn(ops_db_path) as conn:
        job_row = conn.execute("SELECT user_plan FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        call_rows = conn.execute(
            "SELECT node_name, model_class FROM llm_calls WHERE job_id=?", (job_id,)
        ).fetchall()

    user_plan = job_row["user_plan"] if job_row else "free"
    allowed = _plan_allowed.get(user_plan, ["mock"])
    violations: list[dict] = []
    for row in call_rows:
        if row["model_class"] not in allowed:
            violations.append({"node": row["node_name"], "model_class": row["model_class"]})

    passed = len(violations) == 0
    evidence = {"user_plan": user_plan, "allowed": allowed, "violations": violations}
    failure_reason = None if passed else f"disallowed model_class used: {violations}"

    eval_writer.write_gate_result(eval_id, "VI-3", passed, failure_reason, evidence, auto_evaluated=True)
    return passed


def run_auto_eval(
    job_id: str,
    thread_id: str,
    ops_db_path: str = OPS_DB_PATH,
    eval_db_path: str = EVAL_DB_PATH,
) -> str:
    """Run all auto-evaluable gates for a completed job. Returns eval_id."""
    eval_writer = EvalDBWriter(eval_db_path)
    eval_id = eval_writer.create_eval_run(job_id, thread_id, evaluator_type="auto")

    eval_gate_iii2(job_id, eval_id, eval_writer, ops_db_path)
    eval_gate_v1(job_id, eval_id, eval_writer, ops_db_path)
    eval_gate_v2(job_id, eval_id, eval_writer, ops_db_path)
    eval_gate_vi1(job_id, eval_id, eval_writer, ops_db_path)
    eval_gate_vi3(job_id, eval_id, eval_writer, ops_db_path)

    return eval_id
