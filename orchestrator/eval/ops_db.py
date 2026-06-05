"""Operational DB writer — records per-node execution, state outputs, schema validations, and LLM calls."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Generator

from orchestrator.app.graph.state import now_iso
from orchestrator.eval.config import OPS_DB_PATH
from orchestrator.eval.pricing import (
    PRICING_VERSION,
    SELF_HOSTED_LLM_CLASSES,
    compute_cost_usd,
    self_hosted_llm_cost,
    t2i_image_cost,
)

_SENSITIVE_KEYS = {"prompt", "api_key", "openai_api_key", "OPENAI_API_KEY"}

_DDL = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id              TEXT PRIMARY KEY,
    thread_id           TEXT NOT NULL,
    project_id          TEXT,
    user_id             TEXT,
    organization_id     TEXT,
    user_plan           TEXT NOT NULL,
    status              TEXT NOT NULL,
    entry_mode          TEXT,
    generation_route    TEXT,
    render_profile      TEXT,
    engine              TEXT,
    copy_generation_mode TEXT,
    revision            INTEGER DEFAULT 1,
    schema_version      TEXT DEFAULT 'llm_marketing_v1',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    latency_ms          INTEGER,
    error_message       TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_thread_id ON jobs(thread_id);
CREATE INDEX IF NOT EXISTS idx_jobs_user_plan ON jobs(user_plan);

CREATE TABLE IF NOT EXISTS node_executions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          TEXT REFERENCES jobs(job_id),
    thread_id       TEXT,
    revision        INTEGER NOT NULL DEFAULT 1,
    node_name       TEXT NOT NULL,
    graph           TEXT NOT NULL,
    status          TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    completed_at    TEXT,
    latency_ms      INTEGER,
    error_message   TEXT
);
CREATE INDEX IF NOT EXISTS idx_node_exec_job_id ON node_executions(job_id);
CREATE INDEX IF NOT EXISTS idx_node_exec_node_name ON node_executions(node_name);
CREATE INDEX IF NOT EXISTS idx_node_exec_status ON node_executions(status);

CREATE TABLE IF NOT EXISTS node_state_outputs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    node_exec_id    INTEGER NOT NULL REFERENCES node_executions(id),
    job_id          TEXT,
    node_name       TEXT NOT NULL,
    fields_written  TEXT NOT NULL,
    output_snapshot TEXT,
    recorded_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_state_outputs_node_exec_id ON node_state_outputs(node_exec_id);
CREATE INDEX IF NOT EXISTS idx_state_outputs_job_id ON node_state_outputs(job_id);

CREATE TABLE IF NOT EXISTS schema_validations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    node_exec_id    INTEGER NOT NULL REFERENCES node_executions(id),
    job_id          TEXT,
    node_name       TEXT NOT NULL,
    schema_name     TEXT NOT NULL,
    field_name      TEXT,
    passed          INTEGER NOT NULL,
    error_detail    TEXT,
    checked_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_schema_val_node_exec_id ON schema_validations(node_exec_id);
CREATE INDEX IF NOT EXISTS idx_schema_val_job_id ON schema_validations(job_id);
CREATE INDEX IF NOT EXISTS idx_schema_val_node_name ON schema_validations(node_name);

CREATE TABLE IF NOT EXISTS llm_calls (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    node_exec_id    INTEGER NOT NULL REFERENCES node_executions(id),
    job_id          TEXT REFERENCES jobs(job_id),
    thread_id       TEXT,
    node_name       TEXT NOT NULL,
    model_class     TEXT NOT NULL,
    provider        TEXT NOT NULL,
    cost_tier       TEXT NOT NULL,
    success         INTEGER NOT NULL,
    fallback_used   INTEGER NOT NULL DEFAULT 0,
    llm_attempted   INTEGER NOT NULL DEFAULT 1,
    error_code      TEXT,
    latency_ms      INTEGER,
    model_name        TEXT,
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    total_tokens      INTEGER,
    cost_usd          REAL,
    cost_source       TEXT,
    pricing_version   TEXT,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_llm_calls_job_id ON llm_calls(job_id);
CREATE INDEX IF NOT EXISTS idx_llm_calls_node_exec_id ON llm_calls(node_exec_id);

CREATE TABLE IF NOT EXISTS job_cost_summary (
    job_id              TEXT PRIMARY KEY REFERENCES jobs(job_id),
    total_api_calls     INTEGER DEFAULT 0,
    api_nano_calls      INTEGER DEFAULT 0,
    api_mini_calls      INTEGER DEFAULT 0,
    api_full_calls      INTEGER DEFAULT 0,
    api_vision_calls    INTEGER DEFAULT 0,
    fallback_calls      INTEGER DEFAULT 0,
    t2i_engine          TEXT,
    t2i_image_count     INTEGER DEFAULT 0,
    t2i_cost_usd        REAL,
    t2i_cost_source     TEXT,
    estimated_cost_tier TEXT,
    prompt_tokens       INTEGER DEFAULT 0,
    completion_tokens   INTEGER DEFAULT 0,
    total_tokens        INTEGER DEFAULT 0,
    total_cost_usd      REAL DEFAULT 0.0,
    cost_estimated      INTEGER DEFAULT 0,
    pricing_version     TEXT,
    updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dirty_field_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          TEXT REFERENCES jobs(job_id),
    thread_id       TEXT,
    revision        INTEGER NOT NULL,
    changed_fields  TEXT NOT NULL,
    dirty_fields    TEXT NOT NULL,
    triggered_at    TEXT NOT NULL
);
"""

# Additive cost/token columns for DBs created before cost tracking existed.
# CREATE TABLE above already includes them for fresh DBs; these ALTERs backfill
# existing files. Each runs in its own try/except — a "duplicate column name"
# OperationalError just means the column is already present (idempotent).
_MIGRATIONS: list[str] = [
    "ALTER TABLE llm_calls ADD COLUMN model_name TEXT",
    "ALTER TABLE llm_calls ADD COLUMN prompt_tokens INTEGER",
    "ALTER TABLE llm_calls ADD COLUMN completion_tokens INTEGER",
    "ALTER TABLE llm_calls ADD COLUMN total_tokens INTEGER",
    "ALTER TABLE llm_calls ADD COLUMN cost_usd REAL",
    "ALTER TABLE llm_calls ADD COLUMN cost_source TEXT",
    "ALTER TABLE llm_calls ADD COLUMN pricing_version TEXT",
    "ALTER TABLE job_cost_summary ADD COLUMN prompt_tokens INTEGER DEFAULT 0",
    "ALTER TABLE job_cost_summary ADD COLUMN completion_tokens INTEGER DEFAULT 0",
    "ALTER TABLE job_cost_summary ADD COLUMN total_tokens INTEGER DEFAULT 0",
    "ALTER TABLE job_cost_summary ADD COLUMN total_cost_usd REAL DEFAULT 0.0",
    "ALTER TABLE job_cost_summary ADD COLUMN cost_estimated INTEGER DEFAULT 0",
    "ALTER TABLE job_cost_summary ADD COLUMN pricing_version TEXT",
    "ALTER TABLE job_cost_summary ADD COLUMN t2i_image_count INTEGER DEFAULT 0",
    "ALTER TABLE job_cost_summary ADD COLUMN t2i_cost_usd REAL",
    "ALTER TABLE job_cost_summary ADD COLUMN t2i_cost_source TEXT",
]


def _sanitize(obj: Any, depth: int = 0) -> Any:
    """Recursively strip sensitive keys from dicts. Caps recursion at depth 6."""
    if depth > 6:
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize(v, depth + 1) for k, v in obj.items() if k not in _SENSITIVE_KEYS}
    if isinstance(obj, list):
        return [_sanitize(item, depth + 1) for item in obj]
    return obj


def _to_json(obj: Any) -> str:
    try:
        return json.dumps(_sanitize(obj), ensure_ascii=False, default=str)
    except Exception:
        return json.dumps({"_serialization_error": True})


def _latency_ms(started_at: str, completed_at: str) -> int:
    from datetime import datetime, timezone
    try:
        start = datetime.fromisoformat(started_at).replace(tzinfo=timezone.utc)
        end = datetime.fromisoformat(completed_at).replace(tzinfo=timezone.utc)
        return max(0, int((end - start).total_seconds() * 1000))
    except Exception:
        return 0


class OpsDBWriter:
    def __init__(self, db_path: str = OPS_DB_PATH) -> None:
        self._db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._ensure_tables()

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        # /home/records is a shared write volume across team containers; SQLite allows
        # only one writer at a time. Wait up to 5s on a held lock instead of raising
        # "database is locked" immediately (default busy_timeout is 0).
        conn.execute("PRAGMA busy_timeout=5000")
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
            for stmt in _MIGRATIONS:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    pass  # column already exists — additive migration is idempotent

    def insert_job(self, job_id: str, state: dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO jobs
                   (job_id, thread_id, project_id, user_id, organization_id,
                    user_plan, status, entry_mode, generation_route, render_profile,
                    engine, copy_generation_mode, revision, schema_version,
                    created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    job_id,
                    state.get("thread_id"),
                    state.get("project_id"),
                    state.get("user_id"),
                    state.get("organization_id"),
                    state.get("user_plan", "free"),
                    state.get("status", "created"),
                    state.get("entry_mode"),
                    state.get("generation_route"),
                    state.get("render_profile"),
                    state.get("engine"),
                    state.get("copy_generation_mode"),
                    state.get("revision", 1),
                    state.get("schema_version", "llm_marketing_v1"),
                    state.get("created_at") or now_iso(),
                    state.get("updated_at") or now_iso(),
                ),
            )

    def start_node(
        self,
        job_id: str | None,
        thread_id: str | None,
        revision: int,
        node_name: str,
        graph: str,
        started_at: str,
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO node_executions
                   (job_id, thread_id, revision, node_name, graph, status, started_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (job_id, thread_id, revision, node_name, graph, "started", started_at),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def complete_node(
        self,
        exec_id: int,
        job_id: str | None,
        started_at: str,
        result: dict[str, Any],
    ) -> None:
        completed_at = now_iso()
        lat = _latency_ms(started_at, completed_at)
        with self._conn() as conn:
            conn.execute(
                """UPDATE node_executions
                   SET status=?, completed_at=?, latency_ms=?, job_id=COALESCE(job_id,?)
                   WHERE id=?""",
                ("completed", completed_at, lat, job_id, exec_id),
            )
            conn.execute(
                """INSERT INTO node_state_outputs
                   (node_exec_id, job_id, node_name, fields_written, output_snapshot, recorded_at)
                   SELECT id, job_id, node_name, ?, ?, ?
                   FROM node_executions WHERE id=?""",
                (
                    _to_json(list(result.keys())),
                    _to_json(result),
                    completed_at,
                    exec_id,
                ),
            )

    def relocate_result_images(self, job_id: str, dest_root: str) -> dict[str, str]:
        """Mirror a job's generated images into the shared volume and rewrite the
        logged paths so `make eval-logs` / VLM judge see the shared copy.

        The app writes images to data/outputs/<job_id> (hardcoded in
        t2i_request_builder.py:83 — see fix.md), which is the local source tree,
        not the team-shared volume. This eval-side step copies them under
        dest_root/<job_id>/ and string-replaces old paths with new ones inside the
        result node's output_snapshot. Best-effort: returns {} and never raises into
        the batch if anything is missing/unreadable.
        """
        import shutil

        with self._conn() as conn:
            row = conn.execute(
                """SELECT id, output_snapshot FROM node_state_outputs
                   WHERE job_id=? AND node_name='result' AND output_snapshot IS NOT NULL
                   ORDER BY id DESC LIMIT 1""",
                (job_id,),
            ).fetchone()
            if not row:
                return {}
            snapshot_id, snapshot = row[0], row[1]

        try:
            payload = json.loads(snapshot)
        except (TypeError, ValueError):
            return {}

        # Gather candidate image paths from top level and result_payload.
        rp = payload.get("result_payload") if isinstance(payload.get("result_payload"), dict) else {}
        candidates = [
            payload.get("final_image_path"),
            payload.get("background_image_path"),
            rp.get("output_path"),
            rp.get("final_image_path"),
            rp.get("background_image_path"),
        ]

        dest_dir = os.path.join(dest_root, job_id)
        remap: dict[str, str] = {}
        for src in candidates:
            if not src or src in remap or not os.path.isfile(src):
                continue
            os.makedirs(dest_dir, exist_ok=True)
            dest = os.path.join(dest_dir, os.path.basename(src))
            try:
                shutil.copy2(src, dest)
            except OSError:
                continue
            remap[src] = dest

        if not remap:
            return {}

        new_snapshot = snapshot
        for old, new in remap.items():
            new_snapshot = new_snapshot.replace(old, new)
        with self._conn() as conn:
            conn.execute(
                "UPDATE node_state_outputs SET output_snapshot=? WHERE id=?",
                (new_snapshot, snapshot_id),
            )
        return remap

    def fail_node(
        self,
        exec_id: int,
        job_id: str | None,
        started_at: str,
        error: str,
    ) -> None:
        completed_at = now_iso()
        lat = _latency_ms(started_at, completed_at)
        with self._conn() as conn:
            conn.execute(
                """UPDATE node_executions
                   SET status=?, completed_at=?, latency_ms=?, error_message=?,
                       job_id=COALESCE(job_id,?)
                   WHERE id=?""",
                ("failed", completed_at, lat, error[:2000], job_id, exec_id),
            )

    def validate_outputs(
        self,
        exec_id: int,
        job_id: str | None,
        node_name: str,
        result: dict[str, Any],
        schemas: list[tuple[str, type | None]],
    ) -> None:
        now = now_iso()
        rows: list[tuple] = []
        for field_name, schema_cls in schemas:
            value = result.get(field_name)
            if schema_cls is None:
                passed = 1 if value is not None else 0
                error_detail = None if passed else f"{field_name} is None"
                schema_name = field_name
            else:
                schema_name = schema_cls.__name__
                if value is None:
                    passed = 0
                    error_detail = f"{field_name} is None"
                else:
                    try:
                        if not isinstance(value, schema_cls):
                            schema_cls(**(value if isinstance(value, dict) else {}))
                        passed = 1
                        error_detail = None
                    except Exception as exc:
                        passed = 0
                        error_detail = str(exc)[:500]
            rows.append((exec_id, job_id, node_name, schema_name, field_name, passed, error_detail, now))

        if rows:
            with self._conn() as conn:
                conn.executemany(
                    """INSERT INTO schema_validations
                       (node_exec_id, job_id, node_name, schema_name, field_name,
                        passed, error_detail, checked_at)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    rows,
                )

    def write_llm_calls(
        self,
        exec_id: int,
        job_id: str | None,
        thread_id: str | None,
        node_name: str,
        new_results: list[dict[str, Any]],
    ) -> None:
        now = now_iso()
        rows: list[tuple] = []
        for r in new_results:
            # Entry shape changed on develop: node_runner.safe_llm_call_result now
            # flattens these fields to the top level instead of nesting them under
            # "model_selection". Read flat first, fall back to nested for back-compat.
            ms = r.get("model_selection") or {}
            model_class = r.get("selected_model_class") or ms.get("selected_model_class") or "mock"
            provider = r.get("provider") or ms.get("provider") or "mock"
            cost_tier = r.get("estimated_cost_tier") or ms.get("estimated_cost_tier") or "none"
            model_name = r.get("model_name") or ms.get("model_name") or model_class
            # fallback_used: every fallback path builds an LLMCallResult(success=False),
            # while a real LLM call returns success=True. ModelSelection.fallback_used
            # means something different (router downgraded the model CLASS) and is False
            # for the common free-plan/api-disabled fallbacks — so do NOT read it here.
            fallback_used = 0 if r.get("success") else 1
            # Sub-calls (e.g. prompt_critic, brief_interpreter) run via run_structured_node
            # INSIDE a graph node (image_prompt_planner, validator). The entry carries the
            # real selection node_name; prefer it so per-node cost is attributed correctly
            # instead of being folded into the parent graph node. node_exec_id still ties
            # the row to the graph node that executed it.
            call_node = r.get("node_name") or node_name
            cost, source, p_tok, c_tok, t_tok = self._cost_of(r, model_class)
            rows.append((
                exec_id,
                job_id,
                thread_id,
                call_node,
                model_class,
                provider,
                cost_tier,
                1 if r.get("success") else 0,
                fallback_used,
                0 if r.get("error") in {"api_call_disabled", "free_plan_deterministic_fallback"} else 1,
                r.get("error"),
                r.get("latency_ms"),
                model_name,
                p_tok,
                c_tok,
                t_tok,
                cost,
                source,
                PRICING_VERSION,
                now,
            ))
        if rows:
            with self._conn() as conn:
                conn.executemany(
                    """INSERT INTO llm_calls
                       (node_exec_id, job_id, thread_id, node_name, model_class, provider,
                        cost_tier, success, fallback_used, llm_attempted, error_code,
                        latency_ms, model_name, prompt_tokens, completion_tokens,
                        total_tokens, cost_usd, cost_source, pricing_version, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    rows,
                )

    @staticmethod
    def _cost_of(
        result: dict[str, Any], model_class: str
    ) -> tuple[float | None, str, int | None, int | None, int | None]:
        """Per-call (cost_usd, source, prompt_tok, completion_tok, total_tok).

        Self-hosted models (local Gemma etc.) are GPU-billed, not token-billed →
        priced by gpu_seconds when present, else $0 (source="self_hosted").
        For API models the token price book is authoritative when usage is present;
        if usage is absent but the adapter pre-computed cost_estimate, honor that
        (source="adapter"). Otherwise cost is NULL — never fabricated.
        """
        if model_class in SELF_HOSTED_LLM_CLASSES:
            cost, source = self_hosted_llm_cost(result.get("token_usage"))
            return cost, source, None, None, None
        cr = compute_cost_usd(model_class, result.get("token_usage"))
        if cr.source == "exact":
            return cr.cost_usd, "exact", cr.prompt_tokens, cr.completion_tokens, cr.total_tokens
        est = result.get("cost_estimate")
        if est is not None:
            try:
                return round(float(est), 8), "adapter", None, None, None
            except (TypeError, ValueError):
                pass
        return None, cr.source, None, None, None

    def update_job_status(
        self,
        job_id: str,
        status: str,
        latency_ms: int | None = None,
        error_message: str | None = None,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """UPDATE jobs SET status=?, updated_at=?, latency_ms=COALESCE(?,latency_ms),
                   error_message=COALESCE(?,error_message) WHERE job_id=?""",
                (status, now_iso(), latency_ms, error_message, job_id),
            )

    def insert_cost_summary(self, job_id: str, state: dict[str, Any]) -> None:
        llm_results: list[dict] = state.get("llm_call_results") or []
        total = api_nano = api_mini = api_full = api_vision = fallback = 0
        sum_prompt = sum_completion = sum_total = 0
        sum_cost = 0.0
        cost_estimated = 0  # 1 if any API call could not be priced exactly
        worst_tier = "none"
        _tier_rank = {"none": 0, "low": 1, "medium": 2, "high": 3}

        for r in llm_results:
            # flat shape (develop) first, nested model_selection for back-compat
            ms = r.get("model_selection") or {}
            mc = r.get("selected_model_class") or ms.get("selected_model_class") or "mock"
            tier = r.get("estimated_cost_tier") or ms.get("estimated_cost_tier") or "none"
            if mc.startswith("api_"):
                total += 1
                if mc == "api_nano":
                    api_nano += 1
                elif mc == "api_mini":
                    api_mini += 1
                elif mc == "api_full":
                    api_full += 1
                elif mc == "api_vision":
                    api_vision += 1
            if not r.get("success"):  # fallback occurred (see write_llm_calls note)
                fallback += 1
            if _tier_rank.get(tier, 0) > _tier_rank.get(worst_tier, 0):
                worst_tier = tier

            cost, source, p_tok, c_tok, t_tok = self._cost_of(r, mc)
            sum_prompt += p_tok or 0
            sum_completion += c_tok or 0
            sum_total += t_tok or 0
            if cost is not None:
                sum_cost += cost
            # incomplete pricing: an API call without exact token cost, or a
            # self-hosted call that had GPU time but no rate to price it.
            if mc.startswith("api_") and source != "exact":
                cost_estimated = 1
            elif source in {"gpu_unpriced", "gpu_seconds_missing"}:
                cost_estimated = 1

        t2i_result = state.get("t2i_result") or {}
        t2i_engine = t2i_result.get("engine") if isinstance(t2i_result, dict) else None
        # T2I bills per image (separate book from token-based LLM cost). Count the
        # produced images and price them; fold an exact T2I cost into the grand total.
        n_images = len(t2i_result.get("image_paths") or []) if isinstance(t2i_result, dict) else 0
        t2i_cost, t2i_cost_source = t2i_image_cost(t2i_engine, n_images)
        if t2i_cost is not None:
            sum_cost += t2i_cost
        elif t2i_engine and t2i_engine != "mock" and n_images > 0:
            # real image produced but no rate available → total is incomplete.
            cost_estimated = 1

        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO job_cost_summary
                   (job_id, total_api_calls, api_nano_calls, api_mini_calls,
                    api_full_calls, api_vision_calls, fallback_calls,
                    t2i_engine, t2i_image_count, t2i_cost_usd, t2i_cost_source,
                    estimated_cost_tier, prompt_tokens, completion_tokens,
                    total_tokens, total_cost_usd, cost_estimated, pricing_version, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (job_id, total, api_nano, api_mini, api_full, api_vision,
                 fallback, t2i_engine, n_images, t2i_cost, t2i_cost_source,
                 worst_tier, sum_prompt, sum_completion,
                 sum_total, round(sum_cost, 8), cost_estimated, PRICING_VERSION, now_iso()),
            )

    def insert_dirty_event(
        self,
        job_id: str | None,
        thread_id: str | None,
        revision: int,
        changed_fields: list[str],
        dirty_fields: list[str],
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO dirty_field_events
                   (job_id, thread_id, revision, changed_fields, dirty_fields, triggered_at)
                   VALUES (?,?,?,?,?,?)""",
                (job_id, thread_id, revision,
                 json.dumps(changed_fields), json.dumps(dirty_fields), now_iso()),
            )


def create_ops_writer(db_path: str = OPS_DB_PATH) -> OpsDBWriter:
    return OpsDBWriter(db_path)
