"""Judge phase — run LLM/VLM/Human judges over already-logged jobs.

Decoupled from generation. `scenario.py` (eval-test / eval-sample) is the *log*
phase: it drives the tracked graph, writes ops-DB rows + auto gates, and stops —
no paid judge tokens. This module is the *judge* phase: it reads those logged
artifacts and scores them, on demand or as a resumable queue.

Design rules:
    - A human types only the **test ID** (job_id). thread_id and eval_id are
      resolved from the DBs (thread_id from ops `jobs`, eval_id = latest eval_run
      for the job, created if absent). No fragile id reconstruction.
    - Judging is **idempotent**: an evaluator already present in score_items is
      skipped unless force=True.
    - A judge that errors is recorded in judge_status with an attempt count; once
      attempts >= MAX_JUDGE_ATTEMPTS it is treated as exhausted and skipped by the
      queue (unless retry_failed=True). Stops a broken job draining API budget.

CLI:
    python -m orchestrator.eval.judge auto    <job_id>
    python -m orchestrator.eval.judge judge   <job_id> [--judges=llm,vlm] [--force] [--retry-failed]
    python -m orchestrator.eval.judge pending [--n=10] [--judges=llm,vlm] [--retry-failed]
    python -m orchestrator.eval.judge ensemble <job_id>
    python -m orchestrator.eval.judge human          <job_id>
    python -m orchestrator.eval.judge human-pending  [--n=5] [--retry-failed]
"""

from __future__ import annotations

import sqlite3
import sys
from typing import Any, Callable

from orchestrator.eval.config import EVAL_DB_PATH, OPS_DB_PATH
from orchestrator.eval.ensemble import compute_ensemble_score
from orchestrator.eval.eval import run_full_eval
from orchestrator.eval.eval_db import EvalDBWriter
from orchestrator.eval.human_eval import run_human_eval
from orchestrator.eval.llm_eval import run_llm_eval
from orchestrator.eval.vlm_eval import run_vlm_eval

MAX_JUDGE_ATTEMPTS = 2
DEFAULT_JUDGES = ["llm", "vlm"]

# Each judge: (eval_id, job_id) -> list[scored item_id]. Raises on hard failure.
_JUDGE_FNS: dict[str, Callable[..., list[str]]] = {
    "llm": run_llm_eval,
    "vlm": run_vlm_eval,
    "human": run_human_eval,
}


# ----------------------------------------------------------------------------- #
# Resolution helpers — turn a job_id into thread_id / eval_id via the DBs.
# ----------------------------------------------------------------------------- #
def resolve_thread_id(job_id: str, ops_db_path: str = OPS_DB_PATH) -> str | None:
    """thread_id for a logged job, from the ops `jobs` table. None if not logged."""
    conn = sqlite3.connect(ops_db_path)
    try:
        row = conn.execute("SELECT thread_id FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def resolve_or_create_eval_id(
    job_id: str,
    ops_db_path: str = OPS_DB_PATH,
    eval_db_path: str = EVAL_DB_PATH,
) -> str:
    """Latest eval_run for the job, or create one (auto gates) if none exists."""
    conn = sqlite3.connect(eval_db_path)
    try:
        row = conn.execute(
            "SELECT eval_id FROM eval_runs WHERE job_id=? "
            "ORDER BY evaluated_at DESC, eval_id DESC LIMIT 1",
            (job_id,),
        ).fetchone()
    finally:
        conn.close()
    if row:
        return row[0]
    thread_id = resolve_thread_id(job_id, ops_db_path)
    if thread_id is None:
        raise RuntimeError(
            f"job '{job_id}' not found in ops DB — run `make eval-test`/`eval-sample` first"
        )
    eval_id, _, _ = run_full_eval(job_id, thread_id)
    return eval_id


def judged_evaluators(eval_id: str, eval_db_path: str = EVAL_DB_PATH) -> set[str]:
    """Evaluator types that already have score_items for this eval_id."""
    conn = sqlite3.connect(eval_db_path)
    try:
        rows = conn.execute(
            "SELECT DISTINCT evaluator_type FROM score_items WHERE eval_id=?",
            (eval_id,),
        ).fetchall()
    finally:
        conn.close()
    return {r[0] for r in rows}


def _is_exhausted(status: tuple[str, int] | None) -> bool:
    """True if this evaluator failed and used up its retry budget."""
    return bool(status and status[0] == "failed" and status[1] >= MAX_JUDGE_ATTEMPTS)


# ----------------------------------------------------------------------------- #
# Single-job judging.
# ----------------------------------------------------------------------------- #
def run_judges(
    job_id: str,
    judges: list[str] | None = None,
    force: bool = False,
    retry_failed: bool = False,
    ops_db_path: str = OPS_DB_PATH,
    eval_db_path: str = EVAL_DB_PATH,
) -> dict[str, Any]:
    """Run the given judges for one job, then recompute the ensemble.

    Skips evaluators already scored (unless force) and exhausted-failed ones
    (unless retry_failed/force). Never raises per-judge — failures are recorded.
    """
    judges = judges or list(DEFAULT_JUDGES)
    eval_id = resolve_or_create_eval_id(job_id, ops_db_path, eval_db_path)
    writer = EvalDBWriter(eval_db_path)
    done = judged_evaluators(eval_id, eval_db_path)
    status = writer.get_judge_status(eval_id)

    out: dict[str, Any] = {"job_id": job_id, "eval_id": eval_id}
    for j in judges:
        if j not in _JUDGE_FNS:
            out[j] = "skip:unknown"
            continue
        if j in done and not force:
            out[j] = "skip:done"
            continue
        if _is_exhausted(status.get(j)) and not (retry_failed or force):
            out[j] = f"skip:failed({status[j][1]})"
            continue
        try:
            scored = _JUDGE_FNS[j](eval_id, job_id)
            if scored:
                writer.record_judge_result(eval_id, j, "done")
                out[j] = len(scored)
            else:
                writer.record_judge_result(eval_id, j, "failed", "0 items scored")
                out[j] = "0"
        except Exception as exc:  # noqa: BLE001 — one judge must not abort the rest
            writer.record_judge_result(eval_id, j, "failed", f"{type(exc).__name__}: {exc}")
            out[j] = f"err:{type(exc).__name__}"

    try:
        score, verdict = compute_ensemble_score(eval_id)
        out["score"], out["verdict"] = score, verdict
    except Exception as exc:  # noqa: BLE001
        out["score"], out["verdict"] = None, f"ensemble_err:{type(exc).__name__}"
    return out


# ----------------------------------------------------------------------------- #
# Queue — recent jobs needing at least one of the requested judges.
# ----------------------------------------------------------------------------- #
def select_pending(
    n: int,
    judges: list[str] | None = None,
    retry_failed: bool = False,
    eval_db_path: str = EVAL_DB_PATH,
) -> list[str]:
    """Up to n recent job_ids still missing >=1 of `judges` (newest first).

    One eval_run per job is considered (the latest). Ordering is deterministic:
    evaluated_at DESC, then eval_id DESC as tiebreaker so repeated calls are stable.
    """
    judges = judges or list(DEFAULT_JUDGES)
    conn = sqlite3.connect(eval_db_path)
    try:
        runs = conn.execute(
            "SELECT eval_id, job_id FROM eval_runs ORDER BY evaluated_at DESC, eval_id DESC"
        ).fetchall()
    finally:
        conn.close()

    writer = EvalDBWriter(eval_db_path)
    pending: list[str] = []
    seen: set[str] = set()
    for eval_id, job_id in runs:
        if job_id in seen:  # only the latest eval_run per job
            continue
        seen.add(job_id)
        done = judged_evaluators(eval_id, eval_db_path)
        status = writer.get_judge_status(eval_id)
        needs = any(
            j in _JUDGE_FNS
            and j not in done
            and not (_is_exhausted(status.get(j)) and not retry_failed)
            for j in judges
        )
        if needs:
            pending.append(job_id)
        if len(pending) >= n:
            break
    return pending


def run_pending(
    n: int = 10,
    judges: list[str] | None = None,
    retry_failed: bool = False,
    ops_db_path: str = OPS_DB_PATH,
    eval_db_path: str = EVAL_DB_PATH,
) -> list[dict[str, Any]]:
    """Judge up to n recent un-judged jobs. Non-interactive (llm/vlm)."""
    judges = judges or list(DEFAULT_JUDGES)
    jobs = select_pending(n, judges, retry_failed, eval_db_path)
    print(f"eval-pending: {len(jobs)} job(s) need {judges} (n={n}, retry_failed={retry_failed})\n")
    results: list[dict[str, Any]] = []
    for i, job_id in enumerate(jobs, 1):
        res = run_judges(job_id, judges, retry_failed=retry_failed,
                         ops_db_path=ops_db_path, eval_db_path=eval_db_path)
        results.append(res)
        scored = ",".join(f"{j}={res.get(j)}" for j in judges)
        score_txt = "-" if res.get("score") is None else f"{res['score']:.2f}"
        print(f"[{i}/{len(jobs)}] {job_id}  {scored}  score={score_txt} verdict={res.get('verdict')}")
    return results


# ----------------------------------------------------------------------------- #
# Human — interactive, with up-front guidance. Excluded from the auto queue.
# ----------------------------------------------------------------------------- #
_HUMAN_GUIDE = """\
================ 인간 평가 안내 (Human Evaluation Guide) ================
- 1~5점 척도: 1=매우 나쁨 / 2=나쁨 / 3=보통 / 4=좋음 / 5=매우 좋음.
- Enter만 누르면 해당 항목 '미채점'(건너뜀) — 모르면 비워 두세요.
- 이미지 항목(IV-8 가독성, IV-9 상용화)은 표시된 '최종 광고 이미지' 경로를
  직접 열어 보고 채점하세요. 더미 PNG(fast 렌더)면 신뢰하지 마세요.
- 메모는 선택입니다. 점수 근거를 남기면 LLM 보정(eval-calibrate)에 쓰입니다.
- job_id만 입력하면 thread_id/eval_id는 자동 해석됩니다.
========================================================================"""


def run_human_one(
    job_id: str,
    ops_db_path: str = OPS_DB_PATH,
    eval_db_path: str = EVAL_DB_PATH,
) -> dict[str, Any]:
    """Guided single-job human scoring."""
    print(_HUMAN_GUIDE)
    return run_judges(job_id, ["human"], ops_db_path=ops_db_path, eval_db_path=eval_db_path)


def run_human_pending(
    n: int = 5,
    retry_failed: bool = False,
    ops_db_path: str = OPS_DB_PATH,
    eval_db_path: str = EVAL_DB_PATH,
) -> list[dict[str, Any]]:
    """Walk recent jobs missing human scores, one at a time, with guidance."""
    jobs = select_pending(n, ["human"], retry_failed, eval_db_path)
    if not jobs:
        print("인간 평가 대기 job 없음 (모두 채점됨).")
        return []
    print(_HUMAN_GUIDE)
    print(f"\n대기 {len(jobs)}건. 중단하려면 Ctrl-C.\n")
    results: list[dict[str, Any]] = []
    for i, job_id in enumerate(jobs, 1):
        print(f"\n===== [{i}/{len(jobs)}] {job_id} =====")
        results.append(
            run_judges(job_id, ["human"], retry_failed=retry_failed,
                       ops_db_path=ops_db_path, eval_db_path=eval_db_path)
        )
    return results


# ----------------------------------------------------------------------------- #
# CLI.
# ----------------------------------------------------------------------------- #
def _flag(args: list[str], name: str) -> bool:
    return name in args


def _opt(args: list[str], name: str, default: str | None = None) -> str | None:
    prefix = f"--{name}="
    for a in args:
        if a.startswith(prefix):
            return a[len(prefix):]
    return default


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    positionals = [a for a in rest if not a.startswith("--")]
    judges_opt = _opt(rest, "judges")
    judges = judges_opt.split(",") if judges_opt else list(DEFAULT_JUDGES)
    n = int(_opt(rest, "n", "10") or "10")
    retry_failed = _flag(rest, "--retry-failed")
    force = _flag(rest, "--force")

    if cmd == "auto":
        job_id = positionals[0]
        eval_id = resolve_or_create_eval_id(job_id)
        score, verdict = compute_ensemble_score(eval_id)
        print(f"{job_id}  eval_id={eval_id}  score={score} verdict={verdict}")
    elif cmd == "judge":
        print(run_judges(positionals[0], judges, force=force, retry_failed=retry_failed))
    elif cmd == "pending":
        run_pending(n=n, judges=judges, retry_failed=retry_failed)
    elif cmd == "ensemble":
        eval_id = resolve_or_create_eval_id(positionals[0])
        score, verdict = compute_ensemble_score(eval_id)
        print(f"{positionals[0]}  eval_id={eval_id}  score={score} verdict={verdict}")
    elif cmd == "human":
        print(run_human_one(positionals[0]))
    elif cmd == "human-pending":
        run_human_pending(n=int(_opt(rest, "n", "5") or "5"), retry_failed=retry_failed)
    else:
        print(f"unknown command: {cmd}")
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
