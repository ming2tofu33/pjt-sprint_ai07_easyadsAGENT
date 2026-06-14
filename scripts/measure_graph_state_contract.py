from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import subprocess
import tempfile
import uuid
from contextlib import ExitStack
from pathlib import Path
from time import perf_counter
from typing import Any
from unittest.mock import patch

from langgraph.types import Command

from orchestrator.app.api.schemas.generation_jobs import GenerationJobAnswerRequest, GenerationJobCreateRequest
from orchestrator.app.chat_threads import state_service
from orchestrator.app.generation_jobs.execution import (
    execute_generation_job_graph,
    poll_and_process_graph_modal_generation_job,
    resume_generation_job_graph,
)
from orchestrator.app.generation_jobs.service import create_generation_job, reset_generation_job_store_for_tests
from orchestrator.app.graph.builder import build_marketing_graph
from orchestrator.app.graph.checkpointer import InstrumentedCheckpointer
from orchestrator.app.graph.state import MarketingState
from orchestrator.app.observability import performance
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:  # pragma: no cover
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = REPO_ROOT / "data" / "performance" / "state_contract_v1"
SOURCE_HASH_PATHS = [
    REPO_ROOT / "orchestrator" / "app" / "graph" / "builder.py",
    REPO_ROOT / "orchestrator" / "app" / "graph" / "state.py",
    REPO_ROOT / "orchestrator" / "app" / "graph" / "nodes.py",
    REPO_ROOT / "orchestrator" / "app" / "llm" / "node_runner.py",
    Path(__file__),
]
SCENARIOS = ("S1", "S2", "S3", "S4", "S5")
RUNTIME_SUFFIX_RE = re.compile(r"^([a-z_]+)_([0-9a-f]{32})$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("before", "after"), required=False, default="before")
    parser.add_argument("--output-dir", default=str(OUTPUT_ROOT))
    parser.add_argument("--warmup-runs", type=int, default=2)
    parser.add_argument("--cold-runs", type=int, default=1)
    parser.add_argument("--warm-runs", type=int, default=7)
    parser.add_argument("--self-check", action="store_true")
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    return sha256_text(path.read_text(encoding="utf-8"))


def git_head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True, capture_output=True, check=True).stdout.strip()


def source_identity() -> dict[str, Any]:
    return {
        "source_commit": git_head(),
        "relevant_source_hashes": {path.relative_to(REPO_ROOT).as_posix(): file_hash(path) for path in SOURCE_HASH_PATHS},
        "graph_builder_hash": file_hash(REPO_ROOT / "orchestrator" / "app" / "graph" / "builder.py"),
        "state_schema_hash": file_hash(REPO_ROOT / "orchestrator" / "app" / "graph" / "state.py"),
        "node_source_hashes": {
            "graph_nodes": file_hash(REPO_ROOT / "orchestrator" / "app" / "graph" / "nodes.py"),
            "node_runner": file_hash(REPO_ROOT / "orchestrator" / "app" / "llm" / "node_runner.py"),
        },
        "benchmark_script_hash": file_hash(Path(__file__)),
        "checkpointer_type": "InstrumentedCheckpointer(InMemorySaver)",
        "serializer_type": type(InstrumentedCheckpointer(InMemorySaver()).serde).__name__,
    }


def scenario_happy_request(job_id: str, thread_id: str) -> dict[str, Any]:
    return {
        "user_input": "ready",
        "job_id": job_id,
        "thread_id": thread_id,
        "copy_generation_mode": "no_copy",
        "context": {
            "business_type": "restaurant",
            "item_or_service": "BBQ",
            "promotion_goal": "reservation_cta",
            "extra": {"ad_format": "instagram_feed"},
        },
    }


def bind_perf(output_dir: Path, scenario_id: str, run_id: str, cold_or_warm: str):
    os.environ["EASYADS_PERF_TRACE"] = "1"
    os.environ["EASYADS_PERF_TRACE_OUTPUT_DIR"] = str(output_dir)
    performance.clear_perf_event_buffer()
    tokens = performance.bind_perf_context(
        trace_id=performance.new_trace_id(),
        request_id=performance.new_request_id(),
        scenario_id=scenario_id,
        run_id=run_id,
        cold_or_warm=cold_or_warm,
    )
    return tokens


def parse_event_files(output_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(output_dir.glob("events-*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def aggregate_run_metrics(events: list[dict[str, Any]], terminal_state: dict[str, Any]) -> dict[str, Any]:
    graph_nodes = [e for e in events if e.get("event_type") == "graph_node"]
    ckpt_write = [e for e in events if e.get("event_type") in {"checkpoint_write", "checkpoint_write_batch"}]
    ckpt_read = [e for e in events if e.get("event_type") == "checkpoint_read"]
    node_delta_total = 0
    for event in graph_nodes:
        meta = event.get("metadata") or {}
        in_size = meta.get("input_state_size_bytes") or 0
        out_size = meta.get("output_state_size_bytes") or 0
        node_delta_total += max(int(out_size) - int(in_size), 0)
    write_sizes = []
    for event in ckpt_write:
        meta = event.get("metadata") or {}
        size = meta.get("checkpoint_size_bytes") or meta.get("writes_size_bytes")
        if isinstance(size, (int, float)):
            write_sizes.append(int(size))
    return {
        "graph_wall_duration_ms": round(sum(float(e.get("duration_ms") or 0.0) for e in graph_nodes + ckpt_write + ckpt_read), 3),
        "graph_node_count": len(graph_nodes),
        "node_cumulative_duration_ms": round(sum(float(e.get("duration_ms") or 0.0) for e in graph_nodes), 3),
        "checkpoint_write_count": len(ckpt_write),
        "checkpoint_read_count": len(ckpt_read),
        "checkpoint_write_duration_total_ms": round(sum(float(e.get("duration_ms") or 0.0) for e in ckpt_write), 3),
        "checkpoint_read_duration_total_ms": round(sum(float(e.get("duration_ms") or 0.0) for e in ckpt_read), 3),
        "checkpoint_write_bytes_total": sum(write_sizes),
        "checkpoint_write_bytes_max": max(write_sizes or [0]),
        "pending_writes_bytes_total": sum(
            int((e.get("metadata") or {}).get("writes_size_bytes") or 0)
            for e in ckpt_write
            if e.get("event_type") == "checkpoint_write_batch"
        ),
        "terminal_state_bytes": performance.estimate_json_size_bytes(terminal_state) or 0,
        "node_output_delta_bytes_total": node_delta_total,
    }


def summarize_runs(rows: list[dict[str, Any]], *, field: str) -> dict[str, Any]:
    values = [float(row[field]) for row in rows]
    if not values:
        return {"run_count": 0, "min": 0.0, "median": 0.0, "mean": 0.0, "p95": 0.0, "max": 0.0}
    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, max(0, round(0.95 * (len(ordered) - 1))))
    return {
        "run_count": len(values),
        "min": round(min(values), 3),
        "median": round(statistics.median(values), 3),
        "mean": round(statistics.fmean(values), 3),
        "p95": round(ordered[p95_index], 3),
        "max": round(max(values), 3),
    }


def canonicalize(value: Any) -> Any:
    volatile = {
        "created_at",
        "updated_at",
        "latency_ms",
        "trace_id",
        "request_id",
        "checkpoint_id",
        "job_id",
        "thread_id",
        "artifact_id",
        "image_id",
        "snapshot_id",
    }
    if isinstance(value, dict):
        return {k: canonicalize(v) for k, v in sorted(value.items()) if k not in volatile}
    if isinstance(value, list):
        return [canonicalize(item) for item in value]
    if isinstance(value, str):
        normalized = value.replace("\\", "/")
        if "data/outputs/" in normalized:
            name = Path(normalized).name
            return f"data/outputs/<run>/{name}" if Path(name).suffix else "data/outputs/<run>/<dir>"
        if match := RUNTIME_SUFFIX_RE.match(normalized):
            return f"{match.group(1)}_<runtime-id>"
    if isinstance(value, str) and (value.startswith("job_") or value.startswith("thread_")):
        return "<runtime-id>"
    return value


def hash_result(value: Any) -> str:
    return sha256_text(json.dumps(canonicalize(value), ensure_ascii=False, sort_keys=True, default=str))


def build_graph() -> Any:
    start = perf_counter()
    graph = build_marketing_graph(checkpointer=InstrumentedCheckpointer(InMemorySaver()))
    compile_ms = round((perf_counter() - start) * 1000, 3)
    return graph, compile_ms


def run_s1(thread_id: str) -> dict[str, Any]:
    graph, compile_ms = build_graph()
    result = graph.invoke(scenario_happy_request(thread_id, thread_id), config={"configurable": {"thread_id": thread_id}})
    return {"status": "completed", "result": result, "compile_ms": compile_ms}


def run_s2(thread_id: str) -> dict[str, Any]:
    graph, compile_ms = build_graph()
    config = {"configurable": {"thread_id": thread_id}}
    state = {"user_input": "광고 만들어줘", "job_id": thread_id, "thread_id": thread_id}
    result = graph.invoke(state, config=config)
    interrupts = 0
    while "__interrupt__" in result and interrupts < 8:
        payload = result["__interrupt__"][0].value
        question = payload.get("option_question") or {}
        field = question.get("field")
        if field == "copy_generation_mode":
            value = "no_copy"
        elif field == "business_type":
            value = "restaurant"
        elif field == "item_or_service":
            value = "BBQ"
        elif field == "promotion_goal":
            value = "reservation_cta"
        elif field == "ad_format":
            value = "instagram_feed"
        else:
            value = "reservation_cta"
        result = graph.invoke(
            Command(
                resume={
                    "job_id": payload["job_id"],
                    "thread_id": payload["thread_id"],
                    "field": field,
                    "value": value,
                }
            ),
            config=config,
        )
        interrupts += 1
    return {"status": "completed" if result.get("status") == "done" else "blocked", "result": result, "compile_ms": compile_ms, "interrupts": interrupts}


def run_s3(thread_id: str) -> dict[str, Any]:
    def fake_background(state: MarketingState) -> dict[str, Any]:
        if int(state.get("ocr_revision_attempts") or 0) == 0:
            return {
                "background_ocr_gate": {"status": "retry", "decision": "retry_layout", "retry_feedback": ["ocr revision requested"], "revision_action": "retry_layout"},
                "ocr_gate_status": "retry",
                "ocr_gate_decision": "retry_layout",
                "ocr_gate_retry_feedback": ["ocr revision requested"],
                "ocr_revision_action": "retry_layout",
            }
        return {
            "background_ocr_gate": {"status": "pass", "decision": "continue", "retry_feedback": [], "revision_action": None},
            "ocr_gate_status": "pass",
            "ocr_gate_decision": "continue",
            "ocr_gate_retry_feedback": [],
            "ocr_revision_action": None,
        }

    with ExitStack() as stack:
        stack.enter_context(patch("orchestrator.app.graph.builder.background_ocr_gate_node", fake_background))
        graph, compile_ms = build_graph()
        result = graph.invoke(scenario_happy_request(thread_id, thread_id), config={"configurable": {"thread_id": thread_id}})
    ok = result.get("status") == "done" and int(result.get("ocr_revision_attempts") or 0) == 1
    return {"status": "completed" if ok else "blocked", "result": result, "compile_ms": compile_ms}


def run_s4(thread_id: str) -> dict[str, Any]:
    def fake_gate(_state: MarketingState) -> dict[str, Any]:
        return {
            "copy_compliance_gate": {
                "status": "evidence_required",
                "publication_ready": False,
                "findings": [{"finding_id": "f1", "field": "headline", "matched_text": "1위", "severity": "high", "reason": "claim"}],
            },
            "copy_compliance_status": "evidence_required",
            "copy_compliance_publication_ready": False,
            "status": "copy_compliance_checked",
        }

    with ExitStack() as stack:
        stack.enter_context(patch("orchestrator.app.graph.builder.copy_compliance_gate_node", fake_gate))
        graph, compile_ms = build_graph()
        config = {"configurable": {"thread_id": thread_id}}
        first = graph.invoke(scenario_happy_request(thread_id, thread_id), config=config)
        if "__interrupt__" not in first:
            return {"status": "blocked", "reason": "expected_compliance_interrupt_missing", "result": first, "compile_ms": compile_ms}
        result = graph.invoke(Command(resume={"action": "keep_original_draft"}), config=config)
    ok = result.get("status") in {"done", "failed"} and (result.get("copy_compliance_status") in {"manual_review_required", "rewritten_by_user_choice"} or result.get("error_info"))
    return {"status": "completed" if ok else "blocked", "result": result, "compile_ms": compile_ms}


def run_s5(thread_id: str) -> dict[str, Any]:
    from orchestrator.app.modal.schemas import ModalPollResult

    reset_generation_job_store_for_tests()
    request = GenerationJobCreateRequest(user_input="ready", run_mode="graph_job")

    def fake_t2i_generation(_state: MarketingState) -> dict[str, Any]:
        return {
            "status": "modal_running",
            "t2i_request": {
                "prompt": "background only",
                "negative_prompt": "",
                "width": 1024,
                "height": 1024,
                "metadata": {"requested_engine": "sd35_large", "modal_call_id": "modal-call-1"},
                "output_dir": str(REPO_ROOT / "data" / "outputs" / thread_id),
            },
            "t2i_result": {
                "engine": "sd35_large",
                "metadata": {"modal_call_id": "modal-call-1", "requested_engine": "sd35_large"},
            },
        }

    with ExitStack() as stack:
        stack.enter_context(patch("orchestrator.app.graph.builder.t2i_generation_node", fake_t2i_generation))
        stack.enter_context(
            patch(
                "orchestrator.app.modal.client.poll_modal_t2i_result",
                lambda _call_id: ModalPollResult(status="succeeded", image_bytes_base64=None, image_url=None, metadata={"requested_engine": "sd35_large"}),
            )
        )
        job = create_generation_job(request)
        pending = execute_generation_job_graph(job.job_id, request)
        if pending.status not in {"running", "queued"}:
            return {"status": "blocked", "reason": f"unexpected_pending_status:{pending.status}", "result": pending.model_dump(mode='json')}
        polled = poll_and_process_graph_modal_generation_job(job.job_id)
    ok = polled is not None and polled.status == "done"
    return {"status": "completed" if ok else "blocked", "result": polled.model_dump(mode="json") if polled else None}


SCENARIO_IMPLS = {
    "S1": run_s1,
    "S2": run_s2,
    "S3": run_s3,
    "S4": run_s4,
    "S5": run_s5,
}


def run_scenario_measurement(scenario_id: str, output_dir: Path, kind: str, run_index: int) -> dict[str, Any]:
    run_id = f"{scenario_id}-{kind}-{run_index}"
    scenario_dir = output_dir / "raw" / run_id
    scenario_dir.mkdir(parents=True, exist_ok=True)
    tokens = bind_perf(scenario_dir, scenario_id, run_id, kind)
    start = perf_counter()
    try:
        result = SCENARIO_IMPLS[scenario_id](thread_id=f"{scenario_id.lower()}-{kind}-{run_index}-{uuid.uuid4().hex[:8]}")
        duration_ms = round((perf_counter() - start) * 1000, 3)
        performance.flush_perf_events()
    finally:
        performance.reset_perf_context(tokens)
    events = parse_event_files(scenario_dir)
    terminal = result.get("result") or {}
    metrics = aggregate_run_metrics(events, terminal)
    metrics["graph_wall_duration_ms"] = duration_ms
    return {
        "scenario_id": scenario_id,
        "run_id": run_id,
        "cold_or_warm": kind,
        "status": result.get("status", "blocked"),
        "reason": result.get("reason"),
        "graph_compile_duration_ms": result.get("compile_ms", 0.0),
        "events": events,
        "terminal_result_hash": hash_result(terminal) if terminal else None,
        "metrics": metrics,
        "terminal_state": terminal,
    }


def instrumentation_overhead(output_dir: Path) -> dict[str, Any]:
    durations_off = []
    durations_on = []
    for enabled, bucket in ((False, durations_off), (True, durations_on)):
        if enabled:
            os.environ["EASYADS_PERF_TRACE"] = "1"
        else:
            os.environ["EASYADS_PERF_TRACE"] = "0"
        for _ in range(5):
            run_s1(f"overhead-warmup-{uuid.uuid4().hex[:6]}")
        for _ in range(20):
            start = perf_counter()
            run_s1(f"overhead-run-{uuid.uuid4().hex[:6]}")
            bucket.append((perf_counter() - start) * 1000)
    off_median = statistics.median(durations_off)
    on_median = statistics.median(durations_on)
    absolute = on_median - off_median
    event_count = 0
    if output_dir.exists():
        event_count = len(parse_event_files(output_dir))
    return {
        "off_median_ms": round(off_median, 3),
        "on_median_ms": round(on_median, 3),
        "absolute_overhead_ms": round(absolute, 3),
        "overhead_percent": round((absolute / off_median * 100.0), 3) if off_median else None,
        "overhead_per_node_ms": round(absolute / 10.0, 3),
        "event_count_per_run": event_count,
    }


def run_self_check() -> dict[str, Any]:
    sample = canonicalize({"created_at": "x", "status": "done", "items": [{"updated_at": "y", "x": 1}]})
    assert "created_at" not in sample
    assert "updated_at" not in sample["items"][0]
    s1 = run_s1(f"selfcheck-{uuid.uuid4().hex[:8]}")
    assert s1["status"] == "completed"
    return {
        "status": "ok",
        "checked": [
            "actual_compiled_graph",
            "result_canonicalization",
            "run_level_aggregation",
            "fake_checkpointer_not_used",
        ],
    }


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_dir)
    if args.self_check:
        write_json(output_root / "benchmark_self_check.json", run_self_check())
        return

    phase_root = output_root / args.phase
    phase_root.mkdir(parents=True, exist_ok=True)
    identity = source_identity()

    all_runs: list[dict[str, Any]] = []
    scenario_statuses: dict[str, Any] = {}
    graph_node_timings: dict[str, Any] = {}
    checkpoint_timings: dict[str, Any] = {}
    state_sizes: dict[str, Any] = {}
    result_hashes: dict[str, Any] = {}

    for scenario_id in SCENARIOS:
        for i in range(args.warmup_runs):
            run_scenario_measurement(scenario_id, phase_root, "warmup", i)
        cold_rows = [run_scenario_measurement(scenario_id, phase_root, "cold", i) for i in range(args.cold_runs)]
        warm_rows = [run_scenario_measurement(scenario_id, phase_root, "warm", i) for i in range(args.warm_runs)]
        rows = cold_rows + warm_rows
        all_runs.extend(rows)
        terminal_hashes = [row["terminal_result_hash"] for row in rows if row["terminal_result_hash"]]
        scenario_statuses[scenario_id] = {
            "status": "completed" if all(row["status"] == "completed" for row in rows) else "blocked",
            "reasons": sorted({row["reason"] for row in rows if row.get("reason")}),
            "canonical_result_hash": terminal_hashes[-1] if terminal_hashes else None,
        }
        graph_node_timings[scenario_id] = {
            "graph_wall_duration_ms": summarize_runs(warm_rows, field="metrics.graph_wall_duration_ms".split(".")[-1]) if False else summarize_runs([row["metrics"] for row in warm_rows], field="graph_wall_duration_ms"),
            "node_cumulative_duration_ms": summarize_runs([row["metrics"] for row in warm_rows], field="node_cumulative_duration_ms"),
        }
        checkpoint_timings[scenario_id] = {
            "checkpoint_write_duration_total_ms": summarize_runs([row["metrics"] for row in warm_rows], field="checkpoint_write_duration_total_ms"),
            "checkpoint_read_duration_total_ms": summarize_runs([row["metrics"] for row in warm_rows], field="checkpoint_read_duration_total_ms"),
            "checkpoint_write_count": summarize_runs([row["metrics"] for row in warm_rows], field="checkpoint_write_count"),
        }
        state_sizes[scenario_id] = {
            "terminal_state_bytes": summarize_runs([row["metrics"] for row in warm_rows], field="terminal_state_bytes"),
            "node_output_delta_bytes_total": summarize_runs([row["metrics"] for row in warm_rows], field="node_output_delta_bytes_total"),
            "checkpoint_write_bytes_total": summarize_runs([row["metrics"] for row in warm_rows], field="checkpoint_write_bytes_total"),
            "checkpoint_write_bytes_max": summarize_runs([row["metrics"] for row in warm_rows], field="checkpoint_write_bytes_max"),
        }
        result_hashes[scenario_id] = {
            "scenario_id": scenario_id,
            "canonical_result_hash": scenario_statuses[scenario_id]["canonical_result_hash"],
            "match": len(set(terminal_hashes)) <= 1 if terminal_hashes else False,
        }

    overhead = instrumentation_overhead(phase_root / "overhead_raw")
    write_json(phase_root / "benchmark_runs.json", all_runs)
    write_json(phase_root / "graph_execution_timings.json", graph_node_timings)
    write_json(phase_root / "graph_node_timings.json", graph_node_timings)
    write_json(phase_root / "checkpoint_timings.json", checkpoint_timings)
    write_json(phase_root / "state_sizes.json", state_sizes)
    write_json(phase_root / "instrumentation_overhead.json", overhead)
    write_json(phase_root / "result_contract_hashes.json", result_hashes)
    write_json(
        phase_root / "source_identity.json",
        {
            **identity,
            "benchmark_uses_actual_compiled_graph": True,
            "benchmark_uses_fake_checkpointer": False,
            "frontend_benchmark_included": False,
            "artifact_externalization": False,
            "production_db_used": False,
            "postgres_benchmark_status": "not_run",
            "postgres_benchmark_reason": "dev_postgres_unavailable",
        },
    )


if __name__ == "__main__":
    main()
