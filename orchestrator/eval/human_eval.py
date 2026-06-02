"""Interactive CLI human evaluator — gold-standard 1-5 scoring.

Shows text evidence from ops DB, prompts user per scoring item.
Run inside Docker or any env with sqlite3 access to the ops DB.

Usage:
    uv run python -c "
    from orchestrator.eval.human_eval import run_human_eval
    run_human_eval('eval_abc123', 'job_xyz')
    "
Or via: make eval-human EVAL_ID=<id> JOB_ID=<id>
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Generator

from orchestrator.eval.config import OPS_DB_PATH, EVAL_DB_PATH
from orchestrator.eval.eval_db import EvalDBWriter

# Ordered item list for the CLI walk-through
# Image items (IV-8, IV-9) require viewing the final ad image shown in the context section above
_ITEMS: list[tuple[str, str]] = [
    ("II-1",  "컨텍스트 이해 정확도: 추출된 업종/상품/타겟/목표가 올바른가?"),
    ("II-2",  "누락 필드 탐지: 실제로 없는 정보만 missing으로 분류했는가?"),
    ("II-3",  "컨텍스트 업데이트 일관성: 사용자 답변 반영 후 context가 일관적인가?"),
    ("III-3", "카피 어조 적합성: 요청 어조와 타겟에 맞는 어조인가?"),
    ("III-4", "CTA 명확성: 행동 유도 문구가 구체적이고 명확한가?"),
    ("III-5", "브랜드 톤 일관성: 브랜드 정체성과 카피가 일치하는가?"),
    ("IV-3",  "레이아웃 슬롯 수 적합성: 광고 포맷에 맞는 텍스트 슬롯 수인가?"),
    ("IV-4",  "타이포 계층 일관성: 폰트 크기/굵기가 헤드라인>서브>본문 순서인가?"),
    ("IV-5",  "카피 배치 적합성: 텍스트 슬롯 위치가 광고 포맷에 자연스러운가?"),
    ("IV-8",  "[최종 광고 이미지 확인] 가독성 및 침범 (Readability): PIL 합성 텍스트가 핵심 오브젝트를 가리지 않고 배경색에 묻히지 않는가?"),
    ("IV-9",  "[최종 광고 이미지 확인] 상용화 완성도 (Commercial Viability): 최종 광고가 인스타그램/배너 등 실제 마케팅 채널에 즉시 집행 가능한 수준인가?"),
    ("V-3",   "비용 효율: plan 대비 LLM 사용량이 적절한가?"),
    ("V-4",   "재시도 없이 완료: 실패 노드 없이 한 번에 완료됐는가?"),
]

_DIVIDER = "-" * 60


@contextmanager
def _ops_conn(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _fetch_snapshot(conn: sqlite3.Connection, job_id: str, node_name: str) -> dict[str, Any] | None:
    row = conn.execute(
        """SELECT nso.output_snapshot FROM node_state_outputs nso
           JOIN node_executions ne ON ne.id=nso.node_exec_id
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


def _display_context(job_id: str, conn: sqlite3.Connection) -> None:
    """Print human-readable summary of job context, copy, layout, and result."""
    print(f"\n{'='*60}")
    print(f"JOB: {job_id}")
    print("=" * 60)

    # Job metadata
    job = conn.execute(
        "SELECT user_plan, entry_mode, status, created_at FROM jobs WHERE job_id=?", (job_id,)
    ).fetchone()
    if job:
        print(f"Plan: {job['user_plan']}  |  Mode: {job['entry_mode']}  |  Status: {job['status']}")

    # Context
    validator_out = _fetch_snapshot(conn, job_id, "validator")
    if validator_out:
        ctx = validator_out.get("context") or {}
        missing = validator_out.get("missing_fields") or []
        print(f"\n[컨텍스트]")
        for k, v in ctx.items():
            if v:
                print(f"  {k}: {v}")
        if missing:
            print(f"  missing_fields: {missing}")

    # Copy
    for node in ("auto_pilot_copywriting", "state_update_selected_copy"):
        copy_out = _fetch_snapshot(conn, job_id, node)
        if copy_out and copy_out.get("marketing_copy"):
            mc = copy_out["marketing_copy"]
            print(f"\n[카피] (from {node})")
            if isinstance(mc, dict):
                for k, v in mc.items():
                    if v:
                        print(f"  {k}: {v}")
            break

    # Layout
    layout_out = _fetch_snapshot(conn, job_id, "text_layout_planner")
    if layout_out and layout_out.get("text_layout_spec"):
        spec = layout_out["text_layout_spec"]
        slots = spec.get("slots") or []
        print(f"\n[레이아웃] 슬롯 {len(slots)}개")
        for s in slots[:4]:
            if isinstance(s, dict):
                print(f"  slot role={s.get('role')} bbox={s.get('bbox')}")

    # Result payload (image paths — background + final ad)
    result_out = _fetch_snapshot(conn, job_id, "result")
    if result_out and result_out.get("result_payload"):
        rp = result_out["result_payload"]
        if isinstance(rp, dict):
            bg_img = rp.get("background_image_path")
            final_img = rp.get("output_path") or rp.get("final_image_path")
            if bg_img:
                print(f"\n[배경 이미지 (T2I)] {bg_img}")
            if final_img:
                print(f"[최종 광고 (PIL 합성)] {final_img}")
                print("  ← 위 경로를 직접 열어 최종 광고 품질 확인 후 IV-8/IV-9 채점")
            elif bg_img:
                print("  ← 배경 이미지를 직접 열어 시각적 품질 확인")

    # Cost / reliability
    cost = conn.execute(
        "SELECT total_api_calls, fallback_calls, total_tokens, total_cost_usd, cost_estimated "
        "FROM job_cost_summary WHERE job_id=?",
        (job_id,),
    ).fetchone()
    if cost:
        print(f"\n[비용] api호출={cost['total_api_calls']} fallback={cost['fallback_calls']} "
              f"토큰={cost['total_tokens']} 비용=${cost['total_cost_usd'] or 0:.6f}"
              f"{' (불완전)' if cost['cost_estimated'] else ''}")
    failed = conn.execute(
        "SELECT COUNT(*) AS cnt FROM node_executions WHERE job_id=? AND status='failed'", (job_id,)
    ).fetchone()
    if failed:
        print(f"[신뢰성] 실패 노드={failed['cnt']}개")

    print(_DIVIDER)


def _prompt_score(item_id: str, description: str) -> tuple[int, str]:
    """Prompt user for 1-5 score and optional notes. Loops until valid input."""
    print(f"\n[{item_id}] {description}")
    while True:
        try:
            raw = input("  점수 (1-5, 건너뛰려면 Enter): ").strip()
            if not raw:
                return 0, ""
            score = int(raw)
            if 1 <= score <= 5:
                note = input("  메모 (선택, Enter 건너뜀): ").strip()
                return score, note
            print("  1-5 사이 숫자를 입력하세요.")
        except (ValueError, EOFError):
            print("  유효한 숫자를 입력하세요.")


def run_human_eval(
    eval_id: str,
    job_id: str,
    ops_db_path: str = OPS_DB_PATH,
    eval_db_path: str = EVAL_DB_PATH,
) -> list[str]:
    """Interactive CLI: display job context, collect 1-5 scores per item.

    Returns list of scored item_ids (skipped items not included).
    """
    writer = EvalDBWriter(eval_db_path)
    scored: list[str] = []

    with _ops_conn(ops_db_path) as conn:
        _display_context(job_id, conn)

    print("\n항목별 점수를 입력하세요. Enter 건너뛰면 해당 항목 미채점 처리됩니다.")
    print(_DIVIDER)

    for item_id, description in _ITEMS:
        score, note = _prompt_score(item_id, description)
        if score == 0:
            print(f"  [{item_id}] 건너뜀")
            continue
        writer.write_score_item(eval_id, item_id, score, notes=note or None, evaluator_type="human")
        scored.append(item_id)
        print(f"  [{item_id}] {score}점 기록됨.")

    print(f"\n{_DIVIDER}")
    print(f"채점 완료: {len(scored)}개 항목 ({', '.join(scored)})")
    return scored
