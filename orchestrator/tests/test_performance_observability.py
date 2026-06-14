from __future__ import annotations

import json

from orchestrator.app.observability import performance


def test_perf_trace_disabled_by_default(monkeypatch):
    monkeypatch.delenv("EASYADS_PERF_TRACE", raising=False)
    assert performance.perf_trace_enabled() is False


def test_sql_fingerprint_redacts_literals():
    left = performance.sql_fingerprint("select * from jobs where id = 123 and name = 'abc'")
    right = performance.sql_fingerprint("select * from jobs where id = 456 and name = 'xyz'")
    assert left == right


def test_estimate_json_size_bytes_handles_unserializable():
    class X:
        pass

    assert performance.estimate_json_size_bytes({"x": X()}) is not None


def test_record_perf_event_writes_jsonl(monkeypatch, tmp_path):
    monkeypatch.setenv("EASYADS_PERF_TRACE", "1")
    monkeypatch.setenv("EASYADS_PERF_TRACE_OUTPUT_DIR", str(tmp_path))
    performance.record_perf_event(
        performance.build_event(
            "benchmark_marker",
            operation="self-check",
            duration_ms=1.2,
            metadata={"status": "ok"},
        )
    )
    rows = list(tmp_path.glob("events-*.jsonl"))
    assert len(rows) == 1
    payload = json.loads(rows[0].read_text(encoding="utf-8").splitlines()[0])
    assert payload["event_type"] == "benchmark_marker"
