"""Eval-aware graph runner — entry point for tracked graph execution.

Use instead of builder.py when per-node DB tracking is needed.
DBs write to RECORDS_DIR (default /app/records) via config.py.

Evaluator roles:
    auto  — deterministic P/F gates (run_full_eval)
    llm   — gpt-5.4-nano text quality scoring (run_llm_eval)
    vlm   — gpt-5.4 vision image scoring (run_vlm_eval)
    human — interactive CLI gold-standard scoring (run_human_eval)

Ensemble:
    compute_ensemble_score(eval_id) — combines all available scores.
"""

from __future__ import annotations

from orchestrator.eval.auto_eval import run_auto_eval
from orchestrator.eval.config import EVAL_DB_PATH, OPS_DB_PATH
from orchestrator.eval.ensemble import compute_ensemble_score
from orchestrator.eval.human_eval import run_human_eval
from orchestrator.eval.llm_eval import run_llm_eval
from orchestrator.eval.vlm_eval import run_vlm_eval
from orchestrator.eval.scoring import compute_and_finalize
from orchestrator.eval.tracked_builder import (
    build_tracked_intake_graph,
    build_tracked_marketing_graph,
)

__all__ = [
    "build_tracked_marketing_graph",
    "build_tracked_intake_graph",
    "run_full_eval",
    "run_llm_eval",
    "run_vlm_eval",
    "run_human_eval",
    "compute_ensemble_score",
]


def run_full_eval(job_id: str, thread_id: str) -> tuple[str, float | None, str]:
    """Run all 5 auto-eval gates then compute final score and verdict.

    Returns:
        (eval_id, overall_score, verdict)
        verdict: "ship_ready" | "minor_revision" | "major_revision" | "rejected" | "pending_scores"
    """
    eval_id = run_auto_eval(job_id, thread_id, OPS_DB_PATH, EVAL_DB_PATH)
    score, verdict = compute_and_finalize(eval_id, EVAL_DB_PATH)
    return eval_id, score, verdict
