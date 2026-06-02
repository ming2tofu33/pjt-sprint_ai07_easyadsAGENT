"""Compute weighted domain scores and overall verdict for an eval run."""

from __future__ import annotations

from orchestrator.eval.eval_db import EvalDBWriter
from orchestrator.eval.config import EVAL_DB_PATH


def compute_and_finalize(
    eval_id: str,
    eval_db_path: str = EVAL_DB_PATH,
) -> tuple[float | None, str]:
    """Compute domain_scores then finalize eval_run. Returns (overall_score, verdict)."""
    writer = EvalDBWriter(eval_db_path)
    writer.compute_domain_scores(eval_id)
    return writer.finalize_eval_run(eval_id)
