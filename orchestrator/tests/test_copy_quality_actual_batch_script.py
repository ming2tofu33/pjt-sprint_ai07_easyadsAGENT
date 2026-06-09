from scripts import run_copy_quality_actual_batch as batch
from scripts import run_copy_quality_visual_actual as visual
from orchestrator.app.llm.copy_quality_v2 import build_deterministic_copy_output_v2


def test_copy_quality_actual_batch_dry_run_does_not_require_openai(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    args = type("Args", (), {"actual": False, "max_cases": 2, "max_openai_calls": 2, "mode": "post"})()

    report = batch.build_report(args)

    assert report["status"] == "dry_run"
    assert report["total_cases"] == 2
    assert all(run["actual_openai_call"] is False for run in report["runs"])


def test_copy_quality_actual_batch_blocks_without_guard(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("EASYADS_COPY_QUALITY_ACTUAL", raising=False)
    args = type("Args", (), {"actual": True, "max_cases": 1, "max_openai_calls": 1, "mode": "post"})()

    report = batch.build_report(args)

    assert report["status"] == "blocked"
    assert "OPENAI_API_KEY" in report["runs"][0]["missing_requirements"]
    assert "EASYADS_COPY_QUALITY_ACTUAL=1" in report["runs"][0]["missing_requirements"]


def test_copy_quality_visual_actual_blocks_without_model_or_guard(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("EASYADS_COPY_QUALITY_ACTUAL", raising=False)
    monkeypatch.delenv("EASYADS_ENABLE_FLUX2_KLEIN_LOCAL", raising=False)
    args = type("Args", (), {"actual": True, "max_cases": 1})()

    report = visual.build_report(args)

    assert report["status"] == "blocked"
    assert report["runs"][0]["quality"] is None
    assert "EASYADS_COPY_QUALITY_ACTUAL=1" in report["runs"][0]["missing_requirements"]
    assert "HF_TOKEN_or_HUGGINGFACE_TOKEN" not in report["runs"][0]["missing_requirements"]


def test_copy_quality_actual_batch_calls_actual_runner_when_guarded(monkeypatch):
    calls = []

    def fake_run_actual_copy_generation(state):
        calls.append(state["context"]["business_type"])
        output = build_deterministic_copy_output_v2(state)
        return output, {"llm_attempted": True, "fallback_used": False, "llm_call_result": {"token_usage": {"input_tokens": 3, "output_tokens": 4}}}

    monkeypatch.setattr(batch, "run_actual_copy_generation", fake_run_actual_copy_generation)
    monkeypatch.setenv("EASYADS_COPY_QUALITY_ACTUAL", "1")
    monkeypatch.setenv("EASYADS_ENABLE_LLM_CALLS", "true")
    monkeypatch.setenv("EASYADS_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-redacted")
    args = type("Args", (), {"actual": True, "max_cases": 1, "max_openai_calls": 1, "mode": "post"})()

    report = batch.build_report(args)

    assert calls == ["macaron"]
    assert report["status"] == "completed"
    assert report["call_budget"]["attempted"] == 1
    assert report["call_budget"]["succeeded"] == 1
    assert report["runs"][0]["actual_openai_call"] is True


def test_copy_quality_actual_batch_enforces_call_budget(monkeypatch):
    monkeypatch.setenv("EASYADS_COPY_QUALITY_ACTUAL", "1")
    monkeypatch.setenv("EASYADS_ENABLE_LLM_CALLS", "true")
    monkeypatch.setenv("EASYADS_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-redacted")
    args = type("Args", (), {"actual": True, "max_cases": 1, "max_openai_calls": 0, "mode": "post"})()

    report = batch.build_report(args)

    assert report["status"] == "blocked"
    assert "max_openai_calls_positive" in report["runs"][0]["missing_requirements"]
