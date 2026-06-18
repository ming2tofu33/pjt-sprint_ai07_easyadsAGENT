import subprocess
import sys
from pathlib import Path

from scripts.diagnose_generation_analysis_latency import graph_inventory, mock_run


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/diagnose_generation_analysis_latency.py"


def test_graph_inventory_has_real_nodes_and_edges():
    nodes, edges = graph_inventory()
    assert any(row["node_name"] == "product_understanding" for row in nodes)
    assert any(row["source"] == "input" for row in edges)


def test_mock_latency_fixture_and_no_external_image_calls():
    report, spans = mock_run(0, "anonymous")
    assert [span.duration_ms for span in spans if span.kind == "llm"] == [100, 150, 200]
    assert report["llm_call_count"] == 3
    assert all(span.kind != "external_io" for span in spans)


def test_actual_call_budget_preflight_blocks_before_execution(tmp_path):
    result = subprocess.run([sys.executable, str(SCRIPT), "--mode", "actual", "--cold-runs", "2", "--warm-runs", "2",
                             "--confirm-paid-calls", "--max-actual-graph-runs", "2", "--max-actual-llm-calls", "8",
                             "--output-dir", str(tmp_path)], capture_output=True, text=True, check=False)
    assert result.returncode != 0
    assert "blocked by budget" in result.stderr


def test_self_check_writes_required_artifacts(tmp_path):
    result = subprocess.run([sys.executable, str(SCRIPT), "--mode", "self-check", "--output-dir", str(tmp_path)],
                             capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    required = {"summary.json", "run_matrix.json", "graph_topology.json", "node_inventory.json", "span_tree.json",
                "critical_path.json", "llm_calls.json", "comparison.json", "report.md", "railway_checklist.md"}
    assert required <= {path.name for path in tmp_path.iterdir()}
