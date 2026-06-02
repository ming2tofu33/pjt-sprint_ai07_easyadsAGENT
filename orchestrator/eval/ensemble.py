"""Ensemble scoring: combines auto-gate + LLM-judge + VLM-judge + human evaluator scores.

Formula (all four present):
    final = human_q*(0.6/1.1) + llm_q*(0.3/1.1) + vlm_q*(0.2/1.1) + gate_term
    where gate_term = gate_fraction * 5.0 * GATE_FRACTION_WEIGHT (0-0.5)

Graceful degradation when evaluators absent — quality weights normalize so
max achievable score is always 5.0 regardless of which evaluators ran.
"""

from __future__ import annotations

import sqlite3
from orchestrator.eval.config import EVAL_DB_PATH
from orchestrator.eval.eval_db import (
    DOMAIN_ITEMS,
    DOMAIN_WEIGHTS,
    GATE_FRACTION_WEIGHT,
    VERDICT_THRESHOLDS,
    EvalDBWriter,
)

# Base quality weights; must sum < 1.0 (remainder = GATE_FRACTION_WEIGHT)
# When all four evaluators present: human≈0.545, llm≈0.273, vlm≈0.182 (normalized from 0.6/0.3/0.2)
QUALITY_BASE_WEIGHTS: dict[str, float] = {
    "human": 0.6,
    "llm": 0.3,
    "vlm": 0.2,
}


# Sum of all domain weights (0.9). Quality side spans 0-4.5; gate adds 0-0.5 → 5.0.
_TOTAL_DOMAIN_WEIGHT: float = sum(DOMAIN_WEIGHTS.values())


def _quality_contribution(scores: dict[str, float]) -> float | None:
    """Weighted domain avg for one evaluator, normalized to the full 0-4.5 span.

    Each evaluator is a specialist: LLM/human cover all 4 domains (weight sum 0.9),
    but VLM only covers III+IV (weight sum 0.5). Without re-normalizing by the
    covered weight a perfect VLM run maxes at 2.5 instead of 4.5 and silently drags
    the ensemble down even on flawless images. Dividing by covered_weight then
    re-scaling by the total domain weight puts every evaluator on the same 0-4.5
    scale before the cross-evaluator blend in compute_ensemble_score().
    """
    parts: list[float] = []
    covered_weight = 0.0
    for domain, items in DOMAIN_ITEMS.items():
        item_scores = [scores[i] for i in items if i in scores]
        if not item_scores:
            continue
        weight = DOMAIN_WEIGHTS[domain]
        parts.append(sum(item_scores) / len(item_scores) * weight)
        covered_weight += weight
    if not parts:
        return None
    return sum(parts) / covered_weight * _TOTAL_DOMAIN_WEIGHT


def compute_ensemble_score(
    eval_id: str,
    eval_db_path: str = EVAL_DB_PATH,
    quality_weights: dict[str, float] | None = None,
) -> tuple[float | None, str]:
    """Compute ensemble score across all evaluator types for eval_id.

    Reads score_items (by evaluator_type) and gate_results.
    Writes back overall_score + verdict to eval_runs.

    Returns:
        (overall_score, verdict)
        verdict: "ship_ready" | "minor_revision" | "major_revision" | "rejected" | "pending_scores"
    """
    weights = quality_weights or QUALITY_BASE_WEIGHTS

    with sqlite3.connect(eval_db_path) as conn:
        conn.row_factory = sqlite3.Row
        score_rows = conn.execute(
            "SELECT item_id, score, evaluator_type FROM score_items WHERE eval_id=? ORDER BY id",
            (eval_id,),
        ).fetchall()
        gate_rows = conn.execute(
            "SELECT passed FROM gate_results WHERE eval_id=?",
            (eval_id,),
        ).fetchall()

    # Group by evaluator_type; last write wins per item_id (re-score support)
    by_type: dict[str, dict[str, float]] = {}
    for row in score_rows:
        et = row["evaluator_type"]
        if et not in by_type:
            by_type[et] = {}
        by_type[et][row["item_id"]] = float(row["score"])

    # Gate term (0-0.5)
    n_gates = len(gate_rows)
    gates_passed = sum(1 for r in gate_rows if r["passed"])
    gate_fraction = gates_passed / n_gates if n_gates else 0.0
    gate_term = gate_fraction * 5.0 * GATE_FRACTION_WEIGHT
    any_gate_fail = any(r["passed"] == 0 for r in gate_rows)

    # Per-evaluator quality contributions (0-4.5 each)
    q_contribs: dict[str, float] = {}
    for et, scores in by_type.items():
        if et in weights:
            q = _quality_contribution(scores)
            if q is not None:
                q_contribs[et] = q

    # Ensemble quality: normalize available weights so quality side maxes at 4.5
    overall: float | None = None
    if q_contribs:
        avail_w = {et: weights[et] for et in q_contribs}
        total_w = sum(avail_w.values())
        # Weighted avg of quality contributions, then add gate_term
        # avail_w normalized → quality side still spans 0-4.5, gate adds 0-0.5
        weighted_q = sum(
            q_contribs[et] * avail_w[et] / total_w for et in q_contribs
        )
        overall = weighted_q + gate_term

    # Verdict
    if any_gate_fail:
        verdict = "rejected"
    elif overall is None:
        verdict = "pending_scores"
    else:
        verdict = "rejected"
        for threshold, label in VERDICT_THRESHOLDS:
            if overall >= threshold:
                verdict = label
                break

    EvalDBWriter(eval_db_path).update_score(eval_id, overall, verdict, any_gate_fail)
    return overall, verdict
