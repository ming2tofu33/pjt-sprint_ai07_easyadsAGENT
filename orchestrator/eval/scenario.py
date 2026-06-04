"""End-to-end eval test-set runner.

This is the LOG phase. Drives the *tracked* marketing graph in-process (start →
HITL answers → copy selection → final image) and runs auto gates only ($0) —
paid LLM/VLM/Human judging is decoupled into judge.py (`make eval-pending`), so a
batch never spends judge tokens. The tracked graph guarantees ops-DB rows so the
judge phase can read them; the public chat API uses the untracked graph (see
fix.md #5), so HTTP would write nothing — that is why this driver invokes the
graph directly.

Test cases live in scenarios.json (override with EVAL_SCENARIOS_PATH). Each case:
    name, category ("relevant"|"edge"|"copymode"|"nsfw"), user_input,
    answers: {field: <option_value> | {"value": "custom", "custom_text": "..."}},
    optional overrides: render_profile, ad_format, copy_index, tone, channel.

Random sampling (env, both honored by make eval-sample):
    EVAL_SAMPLE_N    — if >0, pick that many random cases TOTAL across selected
                       categories, guaranteeing >=1 from each category.
    EVAL_SAMPLE_SEED — optional int for reproducible sampling (unset = nondeterministic).

Usage:
    uv run python -m orchestrator.eval.scenario              # all
    uv run python -m orchestrator.eval.scenario relevant     # category filter
    uv run python -m orchestrator.eval.scenario edge
    uv run python -m orchestrator.eval.scenario nsfw         # safety cases
    uv run python -m orchestrator.eval.scenario cafe_iced_americano   # one by name
    EVAL_SAMPLE_N=5 uv run python -m orchestrator.eval.scenario all   # 5 random total, >=1/category
Or via: make eval-test SCENARIO=all|relevant|edge|copymode|nsfw|<name>
        make eval-sample [N=10] [SCENARIO=all] [SEED=...]
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from typing import Any

from orchestrator.eval.config import IMAGES_DIR
from orchestrator.eval.eval import run_full_eval
from orchestrator.eval.ops_db import create_ops_writer
from orchestrator.eval.tracked_builder import build_tracked_marketing_graph

# Guard against a malformed answers map (or an unexpected required field) trapping
# the resume loop in an infinite option_question cycle.
MAX_HITL_TURNS = 14

_DEFAULT_SCENARIOS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenarios.json")


def load_scenarios(path: str | None = None) -> dict[str, Any]:
    resolved = path or os.environ.get("EVAL_SCENARIOS_PATH") or _DEFAULT_SCENARIOS_PATH
    with open(resolved, encoding="utf-8") as f:
        data = json.load(f)
    if "scenarios" not in data or not isinstance(data["scenarios"], list):
        raise ValueError(f"{resolved}: missing 'scenarios' list")
    return data


def _interrupt_value(result: dict[str, Any]) -> dict[str, Any] | None:
    interrupts = result.get("__interrupt__") or []
    if not interrupts:
        return None
    return getattr(interrupts[0], "value", None)


def _norm_answer(answer: Any) -> tuple[Any, str | None]:
    """Return (value, custom_text). answer is a plain option value or {value, custom_text}."""
    if isinstance(answer, dict):
        return answer.get("value"), answer.get("custom_text")
    return answer, None


def _resolve_option_answer(
    question: dict[str, Any], answers: dict[str, Any]
) -> tuple[str, Any, str | None]:
    """Pick (field, value, custom_text) for an option_question.

    Falls back to the first non-custom option when the scenario has no canned
    answer for the asked field, so an unexpected required field cannot stall the run.
    """
    field = question.get("field")
    if field in answers:
        value, custom_text = _norm_answer(answers[field])
        return field, value, custom_text
    options = question.get("options") or []
    value = next(
        (o.get("value") for o in options if o.get("value") not in (None, "custom")),
        "custom",
    )
    return field, value, None


def run_one(graph: Any, scenario: dict[str, Any], defaults: dict[str, Any], run_tag: str) -> dict[str, Any]:
    """Run the full pipeline + eval for one scenario. Never raises — errors captured in the row."""
    from langgraph.types import Command  # local import keeps module import cheap for tests

    name = scenario["name"]
    cfg_in = {**defaults, **scenario}
    job_id = f"test_{name}_{run_tag}"
    thread_id = f"{job_id}_thread"
    answers = scenario.get("answers") or {}

    row: dict[str, Any] = {
        "name": name,
        "category": scenario.get("category", "?"),
        "job_id": job_id,
        "status": None,
        "final_image_path": None,
        "eval_id": None,
        "score": None,
        "verdict": None,
        "error": None,
    }

    try:
        state = {
            "entry_mode": "chat_start",
            "user_input": cfg_in["user_input"],
            "job_id": job_id,
            "thread_id": thread_id,
            "render_profile": os.environ.get("EVAL_RENDER_PROFILE") or cfg_in.get("render_profile") or "premium_api",
            # user_plan gates real LLM: node_runner falls back to deterministic copy when
            # plan == "free" (decision step 1), regardless of LLM_ENABLE_API_CALL. Default
            # premium so eval exercises the real GPT-5.4 path; override per-scenario or via
            # EVAL_USER_PLAN (e.g. =free to test the fallback path on purpose).
            "user_plan": os.environ.get("EVAL_USER_PLAN") or cfg_in.get("user_plan") or "premium",
            "copy_generation_mode": cfg_in.get("copy_generation_mode", "suggest_candidates"),
            "context": {"extra": {"ad_format": cfg_in.get("ad_format", "instagram_feed")}},
        }
        config = {"configurable": {"thread_id": thread_id}}

        result = graph.invoke(state, config)
        for _ in range(MAX_HITL_TURNS):
            interrupt = _interrupt_value(result)
            if not interrupt:
                break
            itype = interrupt.get("type")
            if itype == "option_question":
                question = interrupt.get("option_question") or {}
                field, value, custom_text = _resolve_option_answer(question, answers)
                resume: dict[str, Any] = {
                    "job_id": job_id,
                    "thread_id": thread_id,
                    "field": field,
                    "value": value,
                }
                if custom_text:
                    resume["custom_text"] = custom_text
                result = graph.invoke(Command(resume=resume), config)
            elif itype == "copy_candidate_selection":
                candidates = interrupt.get("candidates") or []
                idx = cfg_in.get("copy_index", 0)
                if candidates:
                    chosen = candidates[idx] if 0 <= idx < len(candidates) else candidates[0]
                    selected_id = chosen.get("id", "copy_1")
                else:
                    selected_id = interrupt.get("recommended_candidate_id") or "copy_1"
                resume = {
                    "selected_copy_id": selected_id,
                    "selected_channel_id": cfg_in.get("channel", "instagram-feed"),
                    "selected_ad_format": cfg_in.get("ad_format", "instagram_feed"),
                }
                if cfg_in.get("tone"):
                    resume["selected_tone"] = cfg_in["tone"]
                result = graph.invoke(Command(resume=resume), config)
            elif itype == "custom_copy_input":
                # copy_generation_mode=custom_input branch: supply the user's headline/subcopy.
                cc = cfg_in.get("custom_copy") or {}
                resume = {
                    "user_custom_headline": cc.get("headline") or "지금 만나보세요",
                    "user_custom_subcopy": cc.get("subcopy") or "",
                }
                result = graph.invoke(Command(resume=resume), config)
            else:
                break

        row["status"] = result.get("status")
        row["final_image_path"] = result.get("final_image_path")

        # Mirror generated images into the shared volume (default /app/records/images)
        # so teammates can open them; rewrites the logged path too. Best-effort.
        try:
            remap = create_ops_writer().relocate_result_images(job_id, IMAGES_DIR)
            new_final = remap.get(row["final_image_path"])
            if new_final:
                row["final_image_path"] = new_final
        except Exception:  # noqa: BLE001 — image mirroring must never break the batch
            pass

        # ---- Log-phase eval only: auto gates ($0). Paid LLM/VLM/Human judges are
        # decoupled into the judge phase (judge.py / `make eval-pending`) so a batch
        # never spends judge tokens. Score/verdict here reflect auto gates alone.
        eval_id, score, verdict = run_full_eval(job_id, thread_id)
        row["eval_id"] = eval_id
        row["score"] = score
        row["verdict"] = verdict
    except Exception as exc:  # noqa: BLE001 — batch must continue past a broken case
        row["error"] = f"{type(exc).__name__}: {exc}"
        row["_traceback"] = traceback.format_exc()

    return row


def _select(scenarios: list[dict[str, Any]], selector: str) -> list[dict[str, Any]]:
    if selector in ("all", "", None):
        return scenarios
    by_category = [s for s in scenarios if s.get("category") == selector]
    if by_category:
        return by_category
    by_name = [s for s in scenarios if s.get("name") == selector]
    if by_name:
        return by_name
    raise SystemExit(f"no scenario matches selector '{selector}' (use all|relevant|edge|<name>)")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _sample(scenarios: list[dict[str, Any]], n: int, seed: int | None = None) -> list[dict[str, Any]]:
    """Pick n scenarios TOTAL across all categories, guaranteeing >=1 per category.

    Round 1 takes one random case from each category (so every category that has
    any case is represented). Round 2+ fills the remaining budget by drawing
    randomly from whichever categories still have unused cases. Caps at the total
    number of available scenarios. Result is shuffled so the output order is not
    grouped by category.
    """
    import random

    rng = random.Random(seed)
    groups: dict[str, list[dict[str, Any]]] = {}
    for s in scenarios:
        groups.setdefault(s.get("category", "?"), []).append(s)
    for items in groups.values():
        rng.shuffle(items)

    cats = list(groups)
    rng.shuffle(cats)
    out: list[dict[str, Any]] = []

    # Round 1: one per category (priority order randomized when n < #categories).
    for cat in cats:
        if len(out) >= n:
            break
        if groups[cat]:
            out.append(groups[cat].pop())

    # Round 2+: distribute remaining budget across categories that still have cases.
    while len(out) < n:
        avail = [c for c in cats if groups[c]]
        if not avail:
            break
        out.append(groups[rng.choice(avail)].pop())

    rng.shuffle(out)
    return out


def _fmt(value: Any, width: int) -> str:
    text = "-" if value is None else str(value)
    return text[:width].ljust(width)


def run_batch(selector: str = "all", scenarios_path: str | None = None) -> list[dict[str, Any]]:
    data = load_scenarios(scenarios_path)
    defaults = data.get("defaults") or {}
    selected = _select(data["scenarios"], selector)
    run_tag = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    sample_note = ""
    sample_n = _env_int("EVAL_SAMPLE_N", 0)
    if sample_n > 0:
        seed_raw = os.environ.get("EVAL_SAMPLE_SEED")
        seed = int(seed_raw) if seed_raw and seed_raw.lstrip("-").isdigit() else None
        before = len(selected)
        selected = _sample(selected, sample_n, seed)
        sample_note = f", sampled {len(selected)}/{before} (n={sample_n} total, >=1/cat{'' if seed is None else f', seed={seed}'})"

    render = os.environ.get("EVAL_RENDER_PROFILE") or defaults.get("render_profile") or "premium_api"
    plan = os.environ.get("EVAL_USER_PLAN") or defaults.get("user_plan") or "premium"
    note = "  [NOTE] dummy PNG — VLM/Human judging needs a real render (RENDER=premium_api)" if render in ("fast", "mock") else ""
    if plan == "free":
        note += "  [NOTE] plan=free → copy is deterministic fallback, not real LLM (PLAN=premium for real)"
    print(f"eval-test (LOG phase — auto gates only, $0): {len(selected)} scenario(s), "
          f"selector='{selector}'{sample_note}, render={render}, plan={plan}, run_tag={run_tag}{note}")
    print("  → paid LLM/VLM judging is deferred. After this: make eval-pending  (or eval-llm/eval-vlm/eval-human JOB_ID=<id>)\n")

    # One tracked graph instance serves every scenario (unique thread_id each).
    graph = build_tracked_marketing_graph()

    rows: list[dict[str, Any]] = []
    header = f"{_fmt('NAME', 30)} {_fmt('CAT', 8)} {_fmt('STATUS', 14)} {_fmt('AUTO-VERDICT', 15)} {_fmt('AUTO', 6)} IMG/ERR"
    print(header)
    print("-" * len(header))

    for scenario in selected:
        row = run_one(graph, scenario, defaults, run_tag)
        rows.append(row)
        score_txt = "-" if row["score"] is None else f"{row['score']:.2f}"
        tail = row["error"] or (os.path.basename(row["final_image_path"]) if row["final_image_path"] else "-")
        print(f"{_fmt(row['name'], 30)} {_fmt(row['category'], 8)} {_fmt(row['status'], 14)} "
              f"{_fmt(row['verdict'], 15)} {_fmt(score_txt, 6)} {tail}")

    _print_summary(rows)
    return rows


def _print_summary(rows: list[dict[str, Any]]) -> None:
    import collections

    print("\n" + "=" * 60)
    verdicts = collections.Counter(r["verdict"] for r in rows if r["verdict"])
    errored = [r["name"] for r in rows if r["error"]]
    with_image = sum(1 for r in rows if r["final_image_path"])
    scores = [r["score"] for r in rows if isinstance(r["score"], (int, float))]

    print(f"총 {len(rows)}건 | 이미지 생성 {with_image}건 | 오류 {len(errored)}건")
    if verdicts:
        print("verdict: " + ", ".join(f"{k}={v}" for k, v in verdicts.most_common()))
    if scores:
        print(f"점수 평균 {sum(scores)/len(scores):.2f} (min {min(scores):.2f}, max {max(scores):.2f}, n={len(scores)})")
    if errored:
        print(f"오류 케이스: {', '.join(errored)}")
        print("  (상세: 첫 오류 트레이스백 ↓)")
        first = next(r for r in rows if r["error"])
        print(first.get("_traceback", ""))


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    selector = args[0] if args else "all"
    rows = run_batch(selector)
    # Non-zero exit if any case errored or any verdict is rejected — useful for CI.
    bad = any(r["error"] for r in rows) or any(r["verdict"] == "rejected" for r in rows)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
