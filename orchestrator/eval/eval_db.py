"""Evaluation DB writer — eval runs, gate results, score items, domain scores."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Generator
from uuid import uuid4

from orchestrator.app.graph.state import now_iso
from orchestrator.eval.config import EVAL_DB_PATH

_DDL = """
CREATE TABLE IF NOT EXISTS eval_runs (
    eval_id         TEXT PRIMARY KEY,
    job_id          TEXT NOT NULL,
    thread_id       TEXT NOT NULL,
    evaluated_at    TEXT NOT NULL,
    evaluator_type  TEXT NOT NULL,
    evaluator_id    TEXT,
    overall_score   REAL,
    verdict         TEXT,
    auto_rejected   INTEGER DEFAULT 0,
    schema_version  TEXT DEFAULT 'llm_marketing_v1',
    model_snapshot  TEXT,
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_eval_runs_job_id ON eval_runs(job_id);
CREATE INDEX IF NOT EXISTS idx_eval_runs_thread_id ON eval_runs(thread_id);
CREATE INDEX IF NOT EXISTS idx_eval_runs_verdict ON eval_runs(verdict);

CREATE TABLE IF NOT EXISTS gate_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    eval_id         TEXT NOT NULL REFERENCES eval_runs(eval_id),
    gate_id         TEXT NOT NULL,
    passed          INTEGER NOT NULL,
    failure_reason  TEXT,
    evidence        TEXT,
    auto_evaluated  INTEGER DEFAULT 0,
    checked_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS score_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    eval_id         TEXT NOT NULL REFERENCES eval_runs(eval_id),
    item_id         TEXT NOT NULL,
    score           INTEGER NOT NULL CHECK (score BETWEEN 1 AND 5),
    notes           TEXT,
    evaluator_type  TEXT NOT NULL,
    scored_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS domain_scores (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    eval_id                 TEXT NOT NULL REFERENCES eval_runs(eval_id),
    domain                  TEXT NOT NULL,
    avg_score               REAL,
    weight                  REAL NOT NULL,
    weighted_contribution   REAL,
    item_count              INTEGER
);

-- Per-evaluator judge bookkeeping for the decoupled judge phase (eval-pending).
-- Lets the queue distinguish "never judged" from "judged-and-failed" so a broken
-- job (e.g. invalid vision model) is not retried forever. attempts caps retries.
CREATE TABLE IF NOT EXISTS judge_status (
    eval_id        TEXT NOT NULL,
    evaluator_type TEXT NOT NULL,
    status         TEXT NOT NULL,        -- done | failed
    attempts       INTEGER NOT NULL DEFAULT 0,
    last_error     TEXT,
    updated_at     TEXT NOT NULL,
    PRIMARY KEY (eval_id, evaluator_type)
);
"""

# Domain weights from EVAL_PLAN §14
DOMAIN_WEIGHTS: dict[str, float] = {
    "II": 0.30,
    "III": 0.20,
    "IV": 0.30,
    "V": 0.10,
}

# Score items per domain (1-5 rated)
DOMAIN_ITEMS: dict[str, list[str]] = {
    "II": ["II-1", "II-2", "II-3"],
    "III": ["III-3", "III-4", "III-5", "III-6"],                          # III-6: VLM brand tone
    "IV": ["IV-3", "IV-4", "IV-5", "IV-6", "IV-7", "IV-8", "IV-9"],     # IV-6: VLM text hallucination, IV-7: VLM composition, IV-8: readability (VLM+Human), IV-9: commercial viability (VLM+Human)
    "V": ["V-3", "V-4"],
}

# P/F gates (not scored 1-5 — pass/fail only)
GATE_FRACTION_WEIGHT = 0.10
ALL_GATES = ["I-1", "I-2", "III-1", "III-2", "IV-1", "IV-2", "V-1", "V-2", "VI-1", "VI-2", "VI-3"]

VERDICT_THRESHOLDS = [
    (4.5, "ship_ready"),
    (4.0, "minor_revision"),
    (3.0, "major_revision"),
]

# Aliases for internal use (keep internal refs working)
_DOMAIN_WEIGHTS = DOMAIN_WEIGHTS
_DOMAIN_ITEMS = DOMAIN_ITEMS
_GATE_FRACTION_WEIGHT = GATE_FRACTION_WEIGHT
_ALL_GATES = ALL_GATES
_VERDICT_THRESHOLDS = VERDICT_THRESHOLDS


class EvalDBWriter:
    def __init__(self, db_path: str = EVAL_DB_PATH) -> None:
        self._db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._ensure_tables()

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_tables(self) -> None:
        with self._conn() as conn:
            conn.executescript(_DDL)

    def create_eval_run(
        self,
        job_id: str,
        thread_id: str,
        evaluator_type: str = "auto",
        evaluator_id: str | None = None,
        model_snapshot: dict[str, Any] | None = None,
        notes: str | None = None,
    ) -> str:
        eval_id = f"eval_{uuid4().hex}"
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO eval_runs
                   (eval_id, job_id, thread_id, evaluated_at, evaluator_type,
                    evaluator_id, schema_version, model_snapshot, notes)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    eval_id, job_id, thread_id, now_iso(),
                    evaluator_type, evaluator_id,
                    "llm_marketing_v1",
                    json.dumps(model_snapshot) if model_snapshot else None,
                    notes,
                ),
            )
        return eval_id

    def write_gate_result(
        self,
        eval_id: str,
        gate_id: str,
        passed: bool,
        failure_reason: str | None = None,
        evidence: dict[str, Any] | None = None,
        auto_evaluated: bool = False,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO gate_results
                   (eval_id, gate_id, passed, failure_reason, evidence, auto_evaluated, checked_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    eval_id, gate_id,
                    1 if passed else 0,
                    failure_reason,
                    json.dumps(evidence) if evidence else None,
                    1 if auto_evaluated else 0,
                    now_iso(),
                ),
            )

    def record_judge_result(
        self,
        eval_id: str,
        evaluator_type: str,
        status: str,
        last_error: str | None = None,
    ) -> None:
        """Upsert a judge attempt for (eval_id, evaluator_type). Increments attempts."""
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO judge_status
                       (eval_id, evaluator_type, status, attempts, last_error, updated_at)
                   VALUES (?,?,?,1,?,?)
                   ON CONFLICT(eval_id, evaluator_type) DO UPDATE SET
                       status=excluded.status,
                       attempts=judge_status.attempts + 1,
                       last_error=excluded.last_error,
                       updated_at=excluded.updated_at""",
                (eval_id, evaluator_type, status, last_error, now_iso()),
            )

    def get_judge_status(self, eval_id: str) -> dict[str, tuple[str, int]]:
        """Return {evaluator_type: (status, attempts)} for an eval_id."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT evaluator_type, status, attempts FROM judge_status WHERE eval_id=?",
                (eval_id,),
            ).fetchall()
        return {r[0]: (r[1], r[2]) for r in rows}

    def write_score_item(
        self,
        eval_id: str,
        item_id: str,
        score: int,
        notes: str | None = None,
        evaluator_type: str = "human",
    ) -> None:
        if not (1 <= score <= 5):
            raise ValueError(f"score must be 1-5, got {score}")
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO score_items (eval_id, item_id, score, notes, evaluator_type, scored_at)
                   VALUES (?,?,?,?,?,?)""",
                (eval_id, item_id, score, notes, evaluator_type, now_iso()),
            )

    def compute_domain_scores(self, eval_id: str) -> None:
        with self._conn() as conn:
            # ORDER BY id so that for a duplicated (eval_id, item_id) the last-inserted
            # row deterministically wins the dict-comprehension below (re-scoring case).
            rows = conn.execute(
                "SELECT item_id, score FROM score_items WHERE eval_id=? ORDER BY id", (eval_id,)
            ).fetchall()

        scores_by_item: dict[str, int] = {row[0]: row[1] for row in rows}
        domain_rows: list[tuple] = []

        for domain, items in _DOMAIN_ITEMS.items():
            item_scores = [scores_by_item[i] for i in items if i in scores_by_item]
            weight = _DOMAIN_WEIGHTS[domain]
            avg = sum(item_scores) / len(item_scores) if item_scores else None
            contribution = avg * weight if avg is not None else None
            domain_rows.append((eval_id, domain, avg, weight, contribution, len(item_scores)))

        with self._conn() as conn:
            conn.execute("DELETE FROM domain_scores WHERE eval_id=?", (eval_id,))
            conn.executemany(
                """INSERT INTO domain_scores
                   (eval_id, domain, avg_score, weight, weighted_contribution, item_count)
                   VALUES (?,?,?,?,?,?)""",
                domain_rows,
            )

    def finalize_eval_run(self, eval_id: str) -> tuple[float | None, str]:
        with self._conn() as conn:
            gate_rows = conn.execute(
                "SELECT gate_id, passed FROM gate_results WHERE eval_id=?", (eval_id,)
            ).fetchall()
            domain_rows = conn.execute(
                "SELECT weighted_contribution FROM domain_scores WHERE eval_id=?", (eval_id,)
            ).fetchall()

        any_gate_fail = any(row[1] == 0 for row in gate_rows)
        # Divide by the gates actually recorded, not len(_ALL_GATES). Only a subset of
        # the 11 gates is ever written (5 auto + any human-entered ones); dividing by 11
        # would cap a clean auto-only run at 5/11 of the gate credit, which contradicts
        # the reject logic above (absent gates don't fail, so they shouldn't penalize).
        recorded_gates = len(gate_rows)
        gates_passed = sum(1 for row in gate_rows if row[1] == 1)
        gate_fraction = gates_passed / recorded_gates if recorded_gates else 0.0

        contributions = [row[0] for row in domain_rows if row[0] is not None]
        overall: float | None = None
        if contributions:
            # gate_fraction is 0-1 while domain contributions are avg(1-5)*weight.
            # Multiply by 5 so the gate slice is also on the 0-5 scale; otherwise the
            # max achievable score is 4.6, not 5.0, making ship_ready (>=4.5) unreachable.
            overall = sum(contributions) + gate_fraction * 5 * _GATE_FRACTION_WEIGHT

        if any_gate_fail:
            verdict = "rejected"
        elif overall is None:
            # Auto gates ran but no 1-5 score items entered yet (e.g. auto-only
            # run_full_eval before LLM/human grading). Not a real rejection — distinguish
            # so the caller knows scores are still pending.
            verdict = "pending_scores"
        else:
            verdict = "rejected"
            for threshold, label in _VERDICT_THRESHOLDS:
                if overall >= threshold:
                    verdict = label
                    break

        with self._conn() as conn:
            conn.execute(
                """UPDATE eval_runs SET overall_score=?, verdict=?, auto_rejected=? WHERE eval_id=?""",
                (overall, verdict, 1 if any_gate_fail else 0, eval_id),
            )

        return overall, verdict


    def update_score(
        self,
        eval_id: str,
        overall: float | None,
        verdict: str,
        any_gate_fail: bool,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE eval_runs SET overall_score=?, verdict=?, auto_rejected=? WHERE eval_id=?",
                (overall, verdict, 1 if any_gate_fail else 0, eval_id),
            )


def create_eval_writer(db_path: str = EVAL_DB_PATH) -> EvalDBWriter:
    return EvalDBWriter(db_path)
