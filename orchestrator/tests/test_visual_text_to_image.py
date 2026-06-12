"""Consolidated tests (real physical merge of source files).

Merged from:
- orchestrator/tests/test_t2i_actual_engine_comparison_script.py
- orchestrator/tests/test_t2i_candidate_check.py
- orchestrator/tests/test_t2i_engine_comparison_script.py
- orchestrator/tests/test_t2i_engine_policy.py
- orchestrator/tests/test_t2i_engine_registry.py
- orchestrator/tests/test_t2i_request_builder_node.py
- orchestrator/tests/test_t2i_service.py
- orchestrator/tests/test_t2i_settings.py
- orchestrator/tests/test_t2i_usage_tracking.py
- orchestrator/tests/test_t2i_wrapper.py
- orchestrator/tests/test_vision_asset_materialization.py
- orchestrator/tests/test_vision_nodes.py
- orchestrator/tests/test_vision_preprocess.py
- orchestrator/tests/test_vision_schema.py
- orchestrator/tests/test_vision_service.py
"""

from __future__ import annotations


# ===== from test_t2i_actual_engine_comparison_script.py =====
import json
from pathlib import Path

import pytest

from scripts import run_t2i_actual_engine_comparison as runner


def test_dry_run_does_not_call_actual_engines(monkeypatch, tmp_path):
    def fail_create_app():
        raise AssertionError("actual app path should not run during dry-run")

    monkeypatch.setattr(runner, "create_app", fail_create_app)

    report = runner.run_comparison(
        plan="premium",
        requested_engines=["gpt_image_2", "sd35_large", "flux"],
        case_ids=["cafe_dessert_001"],
        max_cases=1,
        dry_run=True,
        confirm_actual=False,
        execution_backend="auto",
        require_db_r2=False,
        include_comparison=False,
        output_json=tmp_path / "report.json",
    )

    assert report["status"] == "dry_run"
    assert {run["status"] for run in report["runs"]} == {"dry_run"}


def test_dry_run_writes_report_json(tmp_path):
    path = tmp_path / "comparison.json"

    report = runner.run_comparison(
        plan="premium",
        requested_engines=["flux"],
        case_ids=["cafe_dessert_001"],
        max_cases=1,
        dry_run=True,
        confirm_actual=False,
        execution_backend="auto",
        require_db_r2=False,
        include_comparison=False,
        output_json=path,
    )

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert path.exists()
    assert saved["schema_version"] == "t2i_actual_engine_comparison_v1"
    assert saved["report_path"] == path.as_posix()
    assert report["report_path"] == path.as_posix()


def test_free_plan_resolves_only_sd35_large_and_flux(tmp_path):
    report = runner.run_comparison(
        plan="free",
        requested_engines=["gpt_image_2", "sd35_large", "flux"],
        case_ids=["cafe_dessert_001"],
        max_cases=1,
        dry_run=True,
        confirm_actual=False,
        execution_backend="auto",
        require_db_r2=False,
        include_comparison=False,
        output_json=tmp_path / "report.json",
    )

    assert report["resolved_engines"] == ["sd35_large", "flux2_klein_4b"]


def test_economic_plan_allows_gpt_image_1(tmp_path):
    report = runner.run_comparison(
        plan="economic",
        requested_engines=["gpt_image_1"],
        case_ids=["cafe_dessert_001"],
        max_cases=1,
        dry_run=True,
        confirm_actual=False,
        execution_backend="auto",
        require_db_r2=False,
        include_comparison=False,
        output_json=tmp_path / "report.json",
    )

    assert report["resolved_engines"] == ["gpt_image_1"]


def test_premium_include_comparison_resolves_all_engines(tmp_path):
    report = runner.run_comparison(
        plan="premium",
        requested_engines=None,
        case_ids=["cafe_dessert_001"],
        max_cases=1,
        dry_run=True,
        confirm_actual=False,
        execution_backend="auto",
        require_db_r2=False,
        include_comparison=True,
        output_json=tmp_path / "report.json",
    )

    assert report["resolved_engines"] == ["gpt_image_1", "gpt_image_2", "sd35_large", "flux2_klein_4b"]


def test_report_redacts_secret_env_values(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    monkeypatch.setenv("HF_TOKEN", "hf-secret")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "modal-secret")
    monkeypatch.setenv("EASYADS_R2_SECRET_ACCESS_KEY", "r2-secret")
    path = tmp_path / "report.json"

    runner.run_comparison(
        plan="premium",
        requested_engines=["gpt_image_2", "sd35_large", "flux"],
        case_ids=["cafe_dessert_001"],
        max_cases=1,
        dry_run=True,
        confirm_actual=False,
        execution_backend="auto",
        require_db_r2=False,
        include_comparison=False,
        output_json=path,
    )

    text = path.read_text(encoding="utf-8")
    assert "sk-secret" not in text
    assert "hf-secret" not in text
    assert "modal-secret" not in text
    assert "r2-secret" not in text


def test_blocked_run_has_no_arbitrary_manual_quality_score(tmp_path):
    report = runner.run_comparison(
        plan="premium",
        requested_engines=["gpt_image_2"],
        case_ids=["cafe_dessert_001"],
        max_cases=1,
        dry_run=False,
        confirm_actual=False,
        execution_backend="auto",
        require_db_r2=False,
        include_comparison=False,
        output_json=tmp_path / "report.json",
    )

    assert report["runs"][0]["status"] == "blocked"
    assert report["runs"][0]["manual_review"]["quality"] is None


def test_unknown_engine_is_ignored_without_crash(tmp_path):
    report = runner.run_comparison(
        plan="premium",
        requested_engines=["unknown", "flux"],
        case_ids=["cafe_dessert_001"],
        max_cases=1,
        dry_run=True,
        confirm_actual=False,
        execution_backend="auto",
        require_db_r2=False,
        include_comparison=False,
        output_json=tmp_path / "report.json",
    )

    assert report["resolved_engines"] == ["flux2_klein_4b"]


@pytest.mark.parametrize(
    ("engine", "expected_run_mode"),
    [("sd35_large", "sd35_local"), ("flux", "flux2_klein_4b")],
)
def test_engine_maps_to_actual_run_mode(engine, expected_run_mode, tmp_path):
    report = runner.run_comparison(
        plan="premium",
        requested_engines=[engine],
        case_ids=["cafe_dessert_001"],
        max_cases=1,
        dry_run=False,
        confirm_actual=True,
        execution_backend="auto",
        require_db_r2=False,
        include_comparison=False,
        output_json=tmp_path / "report.json",
    )

    assert report["runs"][0]["run_mode"] == expected_run_mode


def test_auto_execution_backend_uses_modal_readiness_for_flux(monkeypatch):
    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "modal")
    monkeypatch.setenv("EASYADS_ENABLE_MODAL_EXECUTION", "true")
    monkeypatch.setenv("EASYADS_MODAL_APP_NAME", "easyads-t2i")
    monkeypatch.setenv("EASYADS_MODAL_FUNCTION_NAME", "generate_image")
    monkeypatch.setenv("MODAL_TOKEN_ID", "token-id")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "token-secret")
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")

    readiness = runner._engine_readiness(
        "flux2_klein_4b",
        execution_backend="auto",
        require_db_r2=False,
    )

    assert readiness["ready"] is True
    assert readiness["missing_requirements"] == []


def test_auto_execution_backend_uses_modal_readiness_for_sd35(monkeypatch):
    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "modal")
    monkeypatch.setenv("EASYADS_ENABLE_MODAL_EXECUTION", "true")
    monkeypatch.setenv("EASYADS_MODAL_APP_NAME", "easyads-t2i")
    monkeypatch.setenv("EASYADS_MODAL_FUNCTION_NAME", "generate_image")
    monkeypatch.setenv("MODAL_TOKEN_ID", "token-id")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "token-secret")
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")

    readiness = runner._engine_readiness(
        "sd35_large",
        execution_backend="auto",
        require_db_r2=False,
    )

    assert readiness["ready"] is True
    assert readiness["missing_requirements"] == []

def test_report_status_treats_running_as_partial():
    runs = [{"status": "running"}, {"status": "blocked"}]

    assert runner._report_status(runs, dry_run=False) == "partial"

def test_summary_counts_pending_statuses():
    runs = [{"status": "running"}, {"status": "queued"}, {"status": "success"}]

    summary = runner._summary(runs, [{"case_id": "case_1"}])

    assert summary["pending"] == 2
    assert summary["success"] == 1


def test_main_prints_safe_run_summary(monkeypatch, tmp_path, capsys):
    path = tmp_path / "report.json"

    exit_code = runner.main(
        [
            "--dry-run",
            "--plan",
            "premium",
            "--engines",
            "flux",
            "--cases",
            "cafe_dessert_001",
            "--output-json",
            path.as_posix(),
        ]
    )

    printed = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert printed["status"] == "dry_run"
    assert printed["report_path"] == path.as_posix()
    assert printed["runs"][0]["engine"] == "flux2_klein_4b"
    assert "prompt_preview" not in printed["runs"][0]


def test_main_returns_nonzero_for_failed_report(monkeypatch, tmp_path, capsys):
    def fake_run_comparison(**kwargs):
        return {
            "status": "failed",
            "report_path": (tmp_path / "report.json").as_posix(),
            "runs": [
                {
                    "engine": "flux",
                    "case_id": "cafe_dessert_001",
                    "status": "failed",
                    "error_code": "flux_prompt_token_budget_unresolvable",
                    "error_type": "FluxPromptTokenBudgetError",
                    "error_message": "budget failed",
                    "clip_token_count": 77,
                    "clip_max_tokens": 77,
                    "clip_truncated": True,
                    "prompt_2_used": True,
                    "critical_constraints_preserved": False,
                }
            ],
        }

    monkeypatch.setattr(runner, "run_comparison", fake_run_comparison)

    exit_code = runner.main(["--confirm-actual", "--engines", "flux"])

    printed = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert printed["runs"][0]["error_type"] == "FluxPromptTokenBudgetError"


# ===== from test_t2i_candidate_check.py =====
"""Tests for dry-run T2I candidate checks."""

from pathlib import Path

from scripts import check_t2i_candidates


def test_candidate_check_dry_run_writes_json_and_markdown_without_api(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    report = check_t2i_candidates.run_candidate_check(
        engines=["gpt_image_2"],
        include_api=False,
        output_dir=str(tmp_path / "candidate-images"),
    )

    json_path = Path(report["json_report_path"])
    markdown_path = Path(report["markdown_report_path"])

    assert json_path.exists()
    assert markdown_path.exists()
    assert report["include_api"] is False
    assert report["results"][0]["engine"] == "gpt_image_2"
    assert report["results"][0]["can_generate"] is False
    assert report["results"][0]["output_path"] is None


def test_sd35_check_records_missing_packages_without_crashing(monkeypatch, tmp_path):
    monkeypatch.setattr(check_t2i_candidates, "_package_available", lambda name: False)

    result = check_t2i_candidates.check_sd35_large(load_local=False, generate_local=False, output_dir=tmp_path)

    assert result["engine"] == "sd35_large"
    assert result["package_available"] is False
    assert result["torch_available"] is False
    assert result["can_import_pipeline"] is False
    assert result["can_load_model"] is False
    assert result["can_generate"] is False


def test_flux_check_records_missing_packages_without_crashing(monkeypatch, tmp_path):
    monkeypatch.setattr(check_t2i_candidates, "_package_available", lambda name: False)

    result = check_t2i_candidates.check_flux(load_local=False, generate_local=False, output_dir=tmp_path)

    assert result["engine"] == "flux"
    assert result["package_available"] is False
    assert result["torch_available"] is False
    assert result["can_import_pipeline"] is False
    assert result["can_load_model"] is False
    assert result["can_generate"] is False


def test_generate_local_requires_load_local(tmp_path):
    result = check_t2i_candidates.check_sd35_large(load_local=False, generate_local=True, output_dir=tmp_path)

    assert result["can_load_model"] is False
    assert result["can_generate"] is False
    assert result["error"] == "--generate-local requires --load-local"


# ===== from test_t2i_engine_comparison_script.py =====
import json
from pathlib import Path

import pytest

from scripts.run_t2i_engine_comparison import CASES, parse_args, run_comparison

def _read_report(report: dict, kind: str = "json") -> str:
    return Path(report["report_paths"][kind]).read_text(encoding="utf-8")


def test_comparison_dry_run_does_not_call_actual_engines(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret")
    monkeypatch.setenv("HF_TOKEN", "hf-test-secret")

    report = run_comparison(
        engines=["gpt_image_2", "sd35_large", "flux"],
        dry_run=True,
        actual=False,
        confirm_cost=False,
        confirm_heavy=False,
        output_dir=tmp_path,
    )

    assert len(CASES) >= 3
    assert report["summary"]["total_results"] == len(CASES) * 3
    assert all(case["status"] == "dry_run" for case in report["cases"])
    assert "sk-test-secret" not in _read_report(report)
    assert "hf-test-secret" not in _read_report(report)
    assert "sk-test-secret" not in _read_report(report, "md")


def test_comparison_actual_without_confirm_is_blocked(tmp_path):
    report = run_comparison(
        engines=["flux"],
        dry_run=False,
        actual=True,
        confirm_cost=False,
        confirm_heavy=False,
        output_dir=tmp_path,
    )

    assert report["engine_readiness"]["flux"]["ready"] is False
    assert "--confirm-heavy" in report["engine_readiness"]["flux"]["missing_requirements"]
    assert all(case["status"] == "blocked" for case in report["cases"])
    payload = json.loads(_read_report(report))
    assert payload["summary"]["total_blocked"] == len(CASES)

def test_comparison_cli_rejects_dry_run_and_actual_together():
    with pytest.raises(SystemExit):
        parse_args(["--dry-run", "--actual"])


# ===== from test_t2i_engine_policy.py =====
from orchestrator.app.t2i.engine_policy import (
    choose_default_engine_for_plan,
    get_image_engine_policy,
    is_engine_allowed_for_plan,
    normalize_image_plan,
    resolve_requested_engines_for_plan,
)


def test_free_plan_allows_sd35_large_and_flux2_klein():
    policy = get_image_engine_policy("free")

    assert policy.allowed_engines == ["sd35_large", "flux2_klein_4b"]
    assert is_engine_allowed_for_plan("sd35_large", "free") is True
    assert is_engine_allowed_for_plan("flux", "free") is True
    assert is_engine_allowed_for_plan("flux2_klein_4b", "free") is True


def test_free_plan_blocks_openai_image_engines():
    assert is_engine_allowed_for_plan("gpt_image_1", "free") is False
    assert is_engine_allowed_for_plan("gpt_image_2", "free") is False


def test_economic_plan_allows_all_engines():
    policy = get_image_engine_policy("economic")

    assert policy.allowed_engines == ["gpt_image_1", "sd35_large", "flux2_klein_4b"]
    assert policy.allow_external_api is True
    assert policy.allow_parallel_comparison is False


def test_premium_plan_allows_all_engines_and_parallel_comparison():
    policy = get_image_engine_policy("premium")

    assert policy.allowed_engines == ["gpt_image_1", "gpt_image_2", "sd35_large", "flux2_klein_4b"]
    assert policy.allow_parallel_comparison is True
    assert resolve_requested_engines_for_plan(plan="premium", include_comparison=True) == [
        "gpt_image_1",
        "gpt_image_2",
        "sd35_large",
        "flux2_klein_4b",
    ]


def test_unknown_plan_falls_back_to_free():
    assert normalize_image_plan(None) == "free"
    assert normalize_image_plan("") == "free"
    assert normalize_image_plan("unknown") == "free"
    assert get_image_engine_policy("unknown").plan == "free"


def test_unknown_requested_engine_is_ignored():
    assert resolve_requested_engines_for_plan(
        plan="premium",
        requested_engines=["unknown", "flux"],
    ) == ["flux2_klein_4b"]


def test_duplicate_requested_engines_are_deduplicated():
    assert resolve_requested_engines_for_plan(
        plan="premium",
        requested_engines=["flux", "flux", "sd35_large"],
    ) == ["flux2_klein_4b", "sd35_large"]


def test_default_engine_by_plan():
    assert choose_default_engine_for_plan("free") == "flux2_klein_4b"
    assert choose_default_engine_for_plan("economic") == "gpt_image_1"
    assert choose_default_engine_for_plan("premium") == "gpt_image_1"


def test_plan_aliases():
    assert normalize_image_plan("economy") == "economic"
    assert normalize_image_plan("standard") == "economic"
    assert normalize_image_plan("pro") == "premium"
    assert normalize_image_plan("business") == "premium"


# ===== from test_t2i_engine_registry.py =====
import pytest

from orchestrator.app.t2i.engines.gpt_image_2 import GPTImage1ActualEngine, GPTImage2ActualEngine
from orchestrator.app.t2i.engines.flux_local import FluxLocalEngine
from orchestrator.app.t2i.engines.mock import MockGuardedT2IEngine
from orchestrator.app.t2i.engines.registry import get_t2i_engine
from orchestrator.app.t2i.engines.sd35_large import SD35LargeLocalEngine


def test_registry_constructs_engines_without_calls_or_loads():
    assert isinstance(get_t2i_engine("mock"), MockGuardedT2IEngine)
    assert isinstance(get_t2i_engine("gpt_image_1"), GPTImage1ActualEngine)
    assert isinstance(get_t2i_engine("gpt_image_2"), GPTImage2ActualEngine)
    assert isinstance(get_t2i_engine("sd35_large"), SD35LargeLocalEngine)
    assert isinstance(get_t2i_engine("flux"), FluxLocalEngine)
    assert isinstance(get_t2i_engine("flux_local"), FluxLocalEngine)


def test_registry_unknown_engine_raises_clear_error():
    with pytest.raises(ValueError, match="unknown T2I engine"):
        get_t2i_engine("unknown")


# ===== from test_t2i_request_builder_node.py =====
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.nodes.t2i_request_builder import t2i_request_builder_node
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def test_t2i_request_builder_maps_prompt_render_output_to_t2i_request():
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            job_id="builder-job",
            thread_id="builder-thread",
            context=MarketingContext(
                business_type="restaurant",
                item_or_service="삼겹살",
                promotion_goal="reservation_cta",
                extra={"ad_format": "instagram_feed"},
            ),
        )
    )
    state["ad_format_spec"] = {"ad_format": "instagram_feed", "platform": "instagram", "aspect_ratio": "1:1", "width": 1080, "height": 1080}
    state["layout_spec"] = {"layout_type": "single_hero", "copy_space": "bottom"}
    state["image_prompt_spec"] = {"reserved_text_areas": [{"x": 0.05, "y": 0.06, "w": 0.90, "h": 0.18}]}
    state["prompt_render_output"] = {
        "engine": "mock",
        "positive_prompt": "text-free bbq background",
        "negative_prompt": "text, watermark, logo",
        "width": 1080,
        "height": 1080,
    }

    update = t2i_request_builder_node(state)
    request = update["t2i_request"]

    assert request["prompt"] == "text-free bbq background"
    assert request["negative_prompt"] == "text, watermark, logo"
    assert request["metadata"]["job_id"] == "builder-job"
    assert request["metadata"]["thread_id"] == "builder-thread"
    assert request["metadata"]["render_text_in_image"] is False
    assert request["metadata"]["text_overlay_pending"] is True
    assert request["metadata"]["reserved_text_areas"] == [{"x": 0.05, "y": 0.06, "w": 0.90, "h": 0.18}]
    assert request["metadata"]["must_not_include_text"] is True
    assert request["metadata"]["negative_prompt_required_terms"] == ["text", "letters", "numbers", "Hangul", "logo", "watermark"]
    assert request["metadata"]["source_node"] == "t2i_request_builder"


def test_t2i_request_builder_passes_source_image_as_input_image():
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            job_id="photo-builder-job",
            thread_id="photo-builder-thread",
            source_image_path="data/uploads/menu.png",
            context=MarketingContext(
                business_type="cafe",
                item_or_service="딸기라떼",
                promotion_goal="discount_event",
                extra={"ad_format": "instagram_feed"},
            ),
        )
    )
    state["prompt_render_output"] = {
        "engine": "gpt_image_2",
        "positive_prompt": "text-free cafe drink background",
        "negative_prompt": "text, watermark, logo",
        "width": 1080,
        "height": 1080,
    }

    update = t2i_request_builder_node(state)
    request = update["t2i_request"]

    assert request["input_image_paths"] == ["data/uploads/menu.png"]
    assert request["metadata"]["input_image_paths"] == ["data/uploads/menu.png"]
    assert request["metadata"]["source_image_path"] == "data/uploads/menu.png"


def test_t2i_request_metadata_aligns_tlfp_reference_and_product_fields():
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            job_id="builder-contract-job",
            thread_id="builder-contract-thread",
            selected_reference_template_id="ref-1",
            context=MarketingContext(
                business_type="cafe",
                item_or_service="딸기라떼",
                promotion_goal="discount_event",
                extra={"ad_format": "instagram_feed"},
            ),
        )
    )
    state["copy_generation_mode"] = "auto_pilot"
    state["ad_format_spec"] = {"ad_format": "instagram_feed", "platform": "instagram", "aspect_ratio": "1:1", "width": 1080, "height": 1080}
    state["layout_spec"] = {"layout_type": "single_hero", "copy_space": "bottom"}
    state["copy_spec"] = {"copy_mode": "standard", "items": [{"role": "headline", "text": "딸기라떼 출시"}]}
    state["text_style_spec"] = {"profile": "premium"}
    state["text_layout_spec"] = {"reserved_text_areas": [{"x": 0.10, "y": 0.70, "w": 0.80, "h": 0.20}]}
    state["image_prompt_spec"] = {
        "reserved_text_areas": [{"x": 0.10, "y": 0.70, "w": 0.80, "h": 0.20}],
        "must_not_include_text": True,
    }
    state["reference_style_profile"] = {"ad_style_prompt": "reference-inspired"}
    state["product_preserve_spec"] = {"product_bbox": {"x": 0.25, "y": 0.20, "w": 0.50, "h": 0.50}}
    state["selected_reference_template"] = {"template_id": "ref-1", "title": "Cafe Feed"}
    state["reference_template_selection"] = {
        "style_profile_hint": {
            "style_keywords": ["fresh", "clean"],
            "color_palette": ["#F9A8D4"],
            "layout_hint": "bottom text",
            "typography_hint": "rounded",
        }
    }
    state["prompt_render_output"] = {
        "engine": "mock",
        "positive_prompt": "text-free cafe background",
        "negative_prompt": "text, watermark, logo",
        "width": 1080,
        "height": 1080,
        "metadata": {"reserved_text_areas": [{"x": 0.90, "y": 0.90, "w": 0.05, "h": 0.05}]},
    }

    request = t2i_request_builder_node(state)["t2i_request"]
    metadata = request["metadata"]

    assert metadata["copy_generation_mode"] == "auto_pilot"
    assert metadata["copy_spec"]["items"][0]["text"] == "딸기라떼 출시"
    assert metadata["text_layout_spec"]["reserved_text_areas"]
    assert metadata["reserved_text_areas"] == [{"x": 0.10, "y": 0.70, "w": 0.80, "h": 0.20}]
    assert metadata["text_style_spec"]["profile"] == "premium"
    assert metadata["image_prompt_spec"]["must_not_include_text"] is True
    assert metadata["reference_style_profile"]["ad_style_prompt"] == "reference-inspired"
    assert metadata["product_preserve_spec"]["product_bbox"]["w"] == 0.50
    assert metadata["selected_reference_template"]["template_id"] == "ref-1"
    assert metadata["reference_template_style_keywords"] == ["fresh", "clean"]


def test_t2i_request_builder_consumes_regeneration_image_prompt_patch():
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            job_id="regen-builder-job",
            thread_id="regen-builder-thread",
            context=MarketingContext(business_type="cafe", item_or_service="latte", promotion_goal="new_menu"),
        )
    )
    state["prompt_render_output"] = {
        "engine": "mock",
        "positive_prompt": "premium cafe background",
        "negative_prompt": "watermark",
        "width": 1080,
        "height": 1080,
    }
    state["regeneration_patch"] = {
        "scope": "image",
        "patches": {
            "removeFakeText": {
                "target": "image_prompt",
                "addNegativeConstraints": ["no visible writing", "no fake text"],
                "simplifyBackground": True,
                "changeSeed": True,
            }
        },
    }

    request = t2i_request_builder_node(state)["t2i_request"]

    assert "no visible writing" in request["negative_prompt"]
    assert "no fake text" in request["negative_prompt"]
    assert "clean simple background" in request["prompt"]
    assert request["seed"] is not None


# ===== from test_t2i_service.py =====
from pathlib import Path

import pytest

from orchestrator.app.modal.schemas import ModalSubmitResult
from orchestrator.app.t2i import graph_engines
from orchestrator.app.t2i.prompts import resolve_negative_prompt
from orchestrator.app.t2i.service import generate_image_v1


def _phrases(prompt: str) -> list[str]:
    return [item.strip().lower() for item in prompt.split(",")]


def test_common_negative_prompt_applies_when_user_prompt_empty():
    effective = resolve_negative_prompt(None, None)

    assert "text" in effective
    assert "watermark" in effective
    assert "broken typography" in effective
    assert "people where not requested" in effective


def test_restaurant_negative_prompt_merges_from_business_type():
    effective = resolve_negative_prompt(None, {"business_type": "restaurant"})

    assert "text" in effective
    assert "dirty table" in effective
    assert "unappetizing food" in effective


def test_food_alias_maps_to_restaurant_negative_prompt():
    effective = resolve_negative_prompt(None, {"business_type": "food"})

    assert "burnt food" in effective
    assert "rotten ingredients" in effective


def test_user_negative_prompt_appends_after_common_and_industry():
    effective = resolve_negative_prompt("bad lighting, text", {"business_type": "cafe"})

    assert "text" in effective
    assert "spilled drink" in effective
    assert "bad lighting" in effective


def test_duplicate_phrases_are_removed_case_insensitively():
    effective = resolve_negative_prompt("TEXT, text, watermark", {"business_type": "restaurant"})
    phrases = _phrases(effective)

    assert phrases.count("text") == 1
    assert phrases.count("watermark") == 1


def test_generate_image_v1_returns_mock_image_path(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("T2I_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("T2I_DEFAULT_ENGINE", "mock")
    result = generate_image_v1(
        prompt="Korean BBQ campaign poster background",
        width=512,
        height=512,
        metadata={"job_id": "job-1", "business_type": "restaurant"},
    )

    assert result.engine == "mock"
    assert result.error is None
    assert result.image_paths == [str(tmp_path / "job-1" / "mock_0.png")]
    assert Path(result.image_paths[0]).exists()


def test_generate_image_v1_metadata_contains_job_and_effective_negative_prompt(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("T2I_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("T2I_DEFAULT_ENGINE", "mock")
    result = generate_image_v1(
        prompt="Cafe signature drink ad background",
        negative_prompt="bad crop",
        metadata={"job_id": "job-meta", "business_type": "beverage"},
    )

    assert result.metadata["job_id"] == "job-meta"
    assert result.metadata["requested_engine"] == "mock"
    assert result.metadata["effective_engine"] == "mock"
    assert "bad crop" in result.metadata["effective_negative_prompt"]
    assert "industry:cafe" in result.metadata["negative_prompt_sources"]
    assert result.metadata["business_type"] == "beverage"
    assert result.metadata["num_images"] == 1


def test_generate_image_v1_uses_job_scoped_output_path(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("T2I_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("T2I_DEFAULT_ENGINE", "mock")
    result = generate_image_v1(
        prompt="Retail product promo background",
        metadata={"job_id": "job-path", "business_type": "product"},
    )

    assert str(tmp_path / "job-path" / "mock_0.png") == result.image_paths[0]


@pytest.mark.parametrize(
    ("engine", "enable_env", "expected_message"),
    [
        ("flux", "EASYADS_ENABLE_FLUX_LOCAL", "FLUX local lane is disabled."),
        ("sd35_large", "EASYADS_ENABLE_SD35_LOCAL", "SD3.5 local generation is disabled."),
    ],
)
def test_generate_image_v1_returns_engine_error_when_graph_actual_lane_is_not_enabled(
    tmp_path: Path,
    monkeypatch,
    engine: str,
    enable_env: str,
    expected_message: str,
):
    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "local")
    monkeypatch.setenv("EASYADS_ENABLE_MODAL_EXECUTION", "false")
    monkeypatch.setenv(enable_env, "false")

    result = generate_image_v1(
        prompt="Premium cafe summer campaign background",
        engine_preference=engine,
        output_dir=str(tmp_path),
        metadata={"job_id": f"job-{engine}"},
    )

    assert result.engine == engine
    assert result.image_paths == []
    assert result.error == expected_message
    assert result.metadata["execution_backend"] == "local"
    assert result.metadata["error_code"] == "t2i_engine_not_enabled"


def test_generate_image_v1_routes_flux_through_modal_and_returns_pending_call_id(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "modal")
    monkeypatch.setenv("EASYADS_ENABLE_MODAL_EXECUTION", "true")
    monkeypatch.setenv("MODAL_TOKEN_ID", "token-id")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "token-secret")
    captured = {}

    def fake_submit(request):
        captured["request"] = request
        return ModalSubmitResult(
            submitted=True,
            modal_call_id="modal_call_flux",
            status="submitted",
        )

    monkeypatch.setattr(graph_engines, "submit_modal_t2i_job", fake_submit)

    result = generate_image_v1(
        prompt="Premium cafe summer campaign background",
        engine_preference="flux",
        output_dir=str(tmp_path),
        metadata={
            "job_id": "job-modal-flux",
            "thread_id": "thread-public",
            "t2i_params": {"max_sequence_length": 256, "ignored": "nope"},
        },
    )

    assert result.engine == "flux"
    assert result.error is None
    assert result.image_paths == []
    assert result.metadata["execution_backend"] == "modal"
    assert result.metadata["modal_provider"] == "modal"
    assert result.metadata["modal_status"] == "submitted"
    assert result.metadata["modal_call_id"] == "modal_call_flux"
    assert result.metadata["modal_call_id_present"] is True
    assert captured["request"].run_mode == "flux_schnell_real"
    assert captured["request"].engine == "flux"
    assert captured["request"].thread_id == "thread-public"
    assert captured["request"].params["render_mode"] == "flux_schnell"
    assert captured["request"].params["max_sequence_length"] == 256
    assert "ignored" not in captured["request"].params


# ===== from test_t2i_settings.py =====
from orchestrator.app.t2i.settings import (
    is_flux_local_enabled,
    is_gpt_image_1_enabled,
    is_gpt_image_2_enabled,
    is_sd35_local_enabled,
    load_t2i_settings,
)


def test_default_settings_disable_external_t2i(monkeypatch):
    monkeypatch.setenv("EASYADS_ENABLE_EXTERNAL_T2I", "false")
    monkeypatch.setenv("EASYADS_ENABLE_GPT_IMAGE_1", "false")
    monkeypatch.setenv("EASYADS_ENABLE_GPT_IMAGE_2", "false")
    monkeypatch.setenv("EASYADS_ENABLE_SD35_LOCAL", "false")
    monkeypatch.setenv("EASYADS_ENABLE_FLUX_LOCAL", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("HF_TOKEN", "")
    monkeypatch.setenv("HUGGINGFACE_TOKEN", "")

    settings = load_t2i_settings()

    assert settings.enable_external_t2i is False
    assert settings.enable_gpt_image_1 is False
    assert settings.enable_gpt_image_2 is False
    assert settings.enable_sd35_local is False
    assert settings.enable_flux_local is False
    assert is_gpt_image_1_enabled(settings) is False
    assert is_gpt_image_2_enabled(settings) is False
    assert is_sd35_local_enabled(settings) is False
    assert is_flux_local_enabled(settings) is False


def test_settings_do_not_expose_secret_values(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-value")
    monkeypatch.setenv("HF_TOKEN", "hf-secret-value")

    dumped = load_t2i_settings().model_dump(mode="json")

    assert dumped["openai_api_key_present"] is True
    assert dumped["hf_token_present"] is True
    assert "sk-secret-value" not in str(dumped)
    assert "hf-secret-value" not in str(dumped)


def test_gpt_image_1_accepts_legacy_enable_flag(monkeypatch):
    monkeypatch.setenv("EASYADS_ENABLE_EXTERNAL_T2I", "true")
    monkeypatch.delenv("EASYADS_ENABLE_GPT_IMAGE_1", raising=False)
    monkeypatch.setenv("EASYADS_ENABLE_GPT_IMAGE_2", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-value")

    settings = load_t2i_settings()

    assert settings.enable_gpt_image_1 is True
    assert is_gpt_image_1_enabled(settings) is True
    assert settings.gpt_image_1_model == "gpt-image-1"


def test_flux_enabled_only_by_explicit_env(monkeypatch):
    monkeypatch.delenv("EASYADS_ENABLE_FLUX_LOCAL", raising=False)
    assert is_flux_local_enabled(load_t2i_settings()) is False

    monkeypatch.setenv("EASYADS_ENABLE_FLUX_LOCAL", "true")
    settings = load_t2i_settings()

    assert settings.enable_flux_local is True
    assert is_flux_local_enabled(settings) is True
    assert settings.flux_model_id == "black-forest-labs/FLUX.1-schnell"


def test_flux_max_sequence_length_is_clamped(monkeypatch):
    monkeypatch.setenv("EASYADS_FLUX_MAX_SEQUENCE_LENGTH", "999")
    assert load_t2i_settings().flux_max_sequence_length == 512

    monkeypatch.setenv("EASYADS_FLUX_MAX_SEQUENCE_LENGTH", "8")
    assert load_t2i_settings().flux_max_sequence_length == 64


# ===== from test_t2i_usage_tracking.py =====
from types import SimpleNamespace

from orchestrator.app.llm.nodes import t2i_generation


def test_t2i_usage_records_successful_actual_result(monkeypatch):
    calls = []
    result = SimpleNamespace(
        error=None,
        image_paths=["data/outputs/job/final_0.png"],
        engine="gpt_image_2",
        metadata={"model": "gpt-image-2", "quality": "high", "requested_run_mode": "gpt_image_2"},
        width=1024,
        height=1024,
    )
    state = {
        "workspace_id": "ws1",
        "thread_id": "thread1",
        "job_id": "job1",
        "usage_thread_db_id": "thread_uuid",
        "usage_job_db_id": "job_uuid",
        "user_id": "user1",
        "user_plan": "premium",
    }
    monkeypatch.setattr(t2i_generation.usage_service, "record_t2i_usage", lambda **kwargs: calls.append(kwargs))

    t2i_generation._record_t2i_usage(state, result)

    assert calls[0]["workspace_id"] == "ws1"
    assert calls[0]["engine"] == "gpt_image_2"
    assert calls[0]["image_count"] == 1
    assert calls[0]["width"] == 1024
    assert calls[0]["height"] == 1024
    assert calls[0]["thread_id"] == "thread_uuid"
    assert calls[0]["job_id"] == "job_uuid"


def test_t2i_usage_uses_internal_job_and_thread_uuid(monkeypatch):
    calls = []
    result = SimpleNamespace(error=None, image_paths=["x"], engine="flux", metadata={"generation_attempt": 2}, width=512, height=512)
    state = {"workspace_id": "ws1", "thread_id": "thread_public", "job_id": "job_public", "usage_thread_db_id": "thread_uuid", "usage_job_db_id": "job_uuid"}
    monkeypatch.setattr(t2i_generation.usage_service, "record_t2i_usage", lambda **kwargs: calls.append(kwargs))

    t2i_generation._record_t2i_usage(state, result)

    assert calls[0]["thread_id"] == "thread_uuid"
    assert calls[0]["job_id"] == "job_uuid"
    assert calls[0]["attempt_index"] == 2


def test_t2i_usage_skips_failed_or_mock_result(monkeypatch):
    calls = []
    monkeypatch.setattr(t2i_generation.usage_service, "record_t2i_usage", lambda **kwargs: calls.append(kwargs))

    t2i_generation._record_t2i_usage({"workspace_id": "ws1"}, SimpleNamespace(error="failed", image_paths=[], engine="gpt_image_2"))
    t2i_generation._record_t2i_usage({"workspace_id": "ws1"}, SimpleNamespace(error=None, image_paths=["x"], engine="mock"))

    assert calls == []


# ===== from test_t2i_wrapper.py =====
from pathlib import Path

from orchestrator.app.core.config import get_t2i_settings
from orchestrator.app.t2i.mock import MockT2IEngine
from orchestrator.app.t2i.router import get_t2i_engine as get_t2i_engine__test_t2i_wrapper, get_t2i_health
from orchestrator.app.t2i.schemas import T2IRequest, T2IResult


def test_t2i_settings_reads_defaults(monkeypatch):
    monkeypatch.setenv("T2I_DEFAULT_ENGINE", "mock")
    monkeypatch.setenv("T2I_ALLOW_API_CALLS", "false")
    monkeypatch.setenv("T2I_GPT_IMAGE_MODEL", "gpt-image-1")

    settings = get_t2i_settings()

    assert settings.default_engine == "mock"
    assert settings.allow_api_calls is False
    assert settings.gpt_image_model == "gpt-image-1"
    assert settings.sd35_model_id == "stabilityai/stable-diffusion-3.5-large"
    assert settings.flux_model_id == "black-forest-labs/FLUX.1-schnell"


def test_mock_engine_generates_placeholder(tmp_path: Path):
    engine = MockT2IEngine()
    request = T2IRequest(
        prompt="Korean BBQ restaurant campaign poster background",
        negative_prompt="text, watermark, logo",
        width=512,
        height=512,
        output_dir=str(tmp_path),
        metadata={"case": "unit"},
    )

    result = engine.generate(request)

    assert isinstance(result, T2IResult)
    assert result.engine == "mock"
    assert result.error is None
    assert result.image_paths == [str(tmp_path / "mock_0.png")]
    assert Path(result.image_paths[0]).exists()
    assert result.metadata["case"] == "unit"


def test_t2i_health_reports_mock_and_graph_actual_engine_status(monkeypatch):
    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "local")
    monkeypatch.setenv("EASYADS_ENABLE_MODAL_EXECUTION", "false")
    monkeypatch.setenv("EASYADS_ENABLE_SD35_LOCAL", "false")
    monkeypatch.setenv("EASYADS_ENABLE_FLUX_LOCAL", "false")

    health = get_t2i_health()

    assert health["mock"]["available"] is True
    assert health["mock"]["loaded"] is True
    assert health["sd35_large"]["available"] is False
    assert health["flux"]["available"] is False
    assert "reason" in health["gpt_image_1"]
    assert "reason" in health["gpt_image_2"]


def test_router_returns_graph_actual_engine_adapters(monkeypatch):
    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "local")
    monkeypatch.setenv("EASYADS_ENABLE_MODAL_EXECUTION", "false")

    assert get_t2i_engine__test_t2i_wrapper("flux").name == "flux"
    assert get_t2i_engine__test_t2i_wrapper("sd35_large").name == "sd35_large"


def test_router_returns_default_mock_engine(monkeypatch):
    monkeypatch.setenv("T2I_DEFAULT_ENGINE", "mock")

    engine = get_t2i_engine__test_t2i_wrapper()

    assert engine.name == "mock"


# ===== from test_vision_asset_materialization.py =====
import pytest
from orchestrator.app.vision.nodes import _resolve_asset_to_local_file

def test_resolve_and_download_asset_not_found(monkeypatch):
    class MockRepo:
        def get_asset_by_public_id(self, *a, **k):
            return None
    monkeypatch.setattr("orchestrator.app.db.repositories.assets.get_asset_by_public_id", MockRepo().get_asset_by_public_id)
    
    state = {
        "workspace_id": "ws1",
        "source_asset_id": "asset_123"
    }
    
    with pytest.raises(ValueError, match="Asset not found"):
        _resolve_asset_to_local_file(
            state=state,
            asset_key="source_asset_id",
            image_key="source_image_path"
        )

def test_resolve_and_download_asset_success(monkeypatch):
    mock_row = {
        "id": "internal-uuid",
        "kind": "source",
        "metadata": {"upload": {"status": "ready"}},
        "bucket": "b",
        "object_key": "k",
        "storage_provider": "r2",
        "public_asset_id": "asset_123"
    }
    class MockRepo:
        def get_asset_by_public_id(self, *a, **k):
            return mock_row
    monkeypatch.setattr("orchestrator.app.db.repositories.assets.get_asset_by_public_id", MockRepo().get_asset_by_public_id)
    def fake_download(*args, **kwargs):
        from pathlib import Path
        target = kwargs.get('target_path') or kwargs.get('local_path')
        Path(target).write_bytes(b"fake")
        
    monkeypatch.setattr("orchestrator.app.storage.r2_service.download_file_from_r2", fake_download)

    state = {
        "workspace_id": "ws1",
        "source_asset_id": "asset_123",
        "job_id": "job_123"
    }
    
    local_path = _resolve_asset_to_local_file(
        state=state,
        asset_key="source_asset_id",
        image_key="source_image_path"
    )
    assert local_path is not None
    assert "downloaded.k" in local_path or "asset_123" in local_path or local_path.endswith(".k") or local_path.endswith(".tmp") or "source_asset_id" in local_path
    from pathlib import Path
    assert Path(local_path).exists()


# ===== from test_vision_nodes.py =====
from pathlib import Path

from PIL import Image

from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest
from orchestrator.app.vision.nodes import product_preprocess_node, reference_preprocess_node


def _image(path: Path) -> Path:
    Image.new("RGB", (80, 80), (200, 140, 120)).save(path)
    return path


def _state(tmp_path: Path):
    return create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            job_id="vision-node-test",
            thread_id="vision-node-test",
            source_image_path=str(_image(tmp_path / "source.png")),
            reference_image_path=str(_image(tmp_path / "reference.png")),
        )
    )


def test_reference_preprocess_node_updates_state_fields(tmp_path):
    update = reference_preprocess_node(_state(tmp_path))

    assert update["status"] == "preprocessing_reference_image"
    assert update["reference_style_profile"]["metadata"]["vlm_used"] is False
    assert update["current_brief"]["reference_style_ready"] is True
    assert update["artifact_refs"]


def test_product_preprocess_node_updates_state_fields(tmp_path):
    update = product_preprocess_node(_state(tmp_path))

    assert update["status"] == "preprocessing_product_image"
    assert update["product_preserve_spec"]["preserve_strategy"] == "center_bbox_stub"
    assert update["current_brief"]["product_preserve_ready"] is True
    assert update["artifact_refs"]


def test_preprocess_node_invalid_path_returns_clear_error():
    state = create_initial_marketing_state(
        InitialMarketingRequest(user_input="ready", job_id="vision-node-invalid", thread_id="vision-node-invalid", source_image_path="missing.png")
    )

    update = product_preprocess_node(state)

    assert update["status"] == "failed"
    assert "vision_preprocess_failed" in update["error_message"]


# ===== from test_vision_preprocess.py =====
from pathlib import Path

import pytest
from PIL import Image

from orchestrator.app.schemas.vision import ImageInputSpec
from orchestrator.app.vision.preprocess import preprocess_image
from orchestrator.app.vision.settings import VisionSettings


def _settings(tmp_path: Path) -> VisionSettings:
    return VisionSettings(upload_dir=tmp_path / "uploads", processed_dir=tmp_path / "processed")


def _image__test_vision_preprocess(path: Path, size=(120, 80), mode="RGB") -> Path:
    color = (200, 120, 80, 180) if mode == "RGBA" else (200, 120, 80)
    Image.new(mode, size, color).save(path)
    return path


def test_preprocess_resize_saves_original_preprocessed_and_preview(tmp_path):
    path = _image__test_vision_preprocess(tmp_path / "source.png", size=(600, 400))

    result = preprocess_image(ImageInputSpec(image_path=str(path), max_side=300), "vision-preprocess", settings=_settings(tmp_path))

    assert result.width == 300
    assert result.height == 200
    assert result.mode == "RGB"
    assert result.original_artifact_path
    assert Path(result.original_artifact_path).exists()
    assert Path(result.preprocessed_artifact_path).exists()
    assert result.preview_path and Path(result.preview_path).exists()
    assert tmp_path / "processed" in Path(result.preprocessed_artifact_path).parents


def test_preprocess_converts_rgba_to_rgb(tmp_path):
    path = _image__test_vision_preprocess(tmp_path / "source.png", size=(40, 40), mode="RGBA")

    result = preprocess_image(ImageInputSpec(image_path=str(path)), "vision-rgba", settings=_settings(tmp_path))

    assert result.mode == "RGB"
    assert result.metadata.has_alpha is True


@pytest.mark.parametrize("suffix", [".jpg", ".jpeg", ".png", ".webp"])
def test_allowed_extensions(tmp_path, suffix):
    path = _image__test_vision_preprocess(tmp_path / f"source{suffix}", size=(40, 40))

    result = preprocess_image(ImageInputSpec(image_path=str(path)), f"vision-ext-{suffix[1:]}", settings=_settings(tmp_path))

    assert Path(result.preprocessed_artifact_path).exists()


def test_invalid_extension_and_missing_file_raise(tmp_path):
    bad = tmp_path / "source.gif"
    bad.write_bytes(b"not-an-image")

    with pytest.raises(ValueError):
        preprocess_image(ImageInputSpec(image_path=str(bad)), "vision-bad-ext", settings=_settings(tmp_path))

    with pytest.raises(FileNotFoundError):
        preprocess_image(ImageInputSpec(image_path=str(tmp_path / "missing.png")), "vision-missing", settings=_settings(tmp_path))


def test_relative_input_paths_resolve_from_project_root(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    upload_dir = project_root / "data" / "uploads"
    upload_dir.mkdir(parents=True)
    path = _image__test_vision_preprocess(upload_dir / "source.png", size=(40, 40))
    monkeypatch.setattr("orchestrator.app.vision.preprocess.PROJECT_ROOT", project_root)
    monkeypatch.chdir(tmp_path)

    result = preprocess_image(
        ImageInputSpec(image_path="data/uploads/source.png"),
        "vision-relative",
        settings=_settings(tmp_path),
    )

    assert result.metadata.original_path == str(path.resolve())
    assert Path(result.preprocessed_artifact_path).exists()


def test_center_crop_and_fit_with_padding(tmp_path):
    path = _image__test_vision_preprocess(tmp_path / "wide.png", size=(200, 100))
    settings = _settings(tmp_path)

    cropped = preprocess_image(
        ImageInputSpec(image_path=str(path), preprocess_mode="center_crop", target_width=80, target_height=80),
        "vision-crop",
        settings=settings,
    )
    padded = preprocess_image(
        ImageInputSpec(image_path=str(path), preprocess_mode="fit_with_padding", target_width=80, target_height=80),
        "vision-pad",
        settings=settings,
    )

    assert (cropped.width, cropped.height) == (80, 80)
    assert (padded.width, padded.height) == (80, 80)


# ===== from test_vision_schema.py =====
import pytest
from pydantic import ValidationError
from typing import get_args

from orchestrator.app.schemas.vision import (
    ImageInputSpec,
    ImageMetadata,
    ImagePreprocessResult,
    ProductPreserveSpec,
    ReferenceStyleProfile,
    VisionArtifactType,
    VisionPipelineResult,
)


def _preprocess_result() -> ImagePreprocessResult:
    metadata = ImageMetadata(
        original_path="input.png",
        original_filename="input.png",
        format="PNG",
        mode="RGBA",
        width=100,
        height=80,
        file_size_bytes=123,
        has_alpha=True,
    )
    return ImagePreprocessResult(
        original_artifact_path="processed/original.png",
        preprocessed_artifact_path="processed/preprocessed.png",
        preview_path="processed/preview.png",
        width=100,
        height=80,
        mode="RGB",
        metadata=metadata,
    )


def test_vision_schemas_are_json_serializable():
    input_spec = ImageInputSpec(image_path="input.png", kind="source_product", max_side=512)
    style = ReferenceStyleProfile(
        color_palette=["#FFFFFF"],
        dominant_colors_rgb=[(255, 255, 255)],
        brightness=0.9,
        contrast_hint="low",
        mood_keywords=["bright"],
    )
    product = ProductPreserveSpec(
        source_image_path="input.png",
        preprocessed_image_path="processed/preprocessed.png",
        product_bbox={"x": 0.2, "y": 0.2, "w": 0.6, "h": 0.6},
    )
    result = VisionPipelineResult(
        input_spec=input_spec,
        preprocess_result=_preprocess_result(),
        reference_style_profile=style,
        product_preserve_spec=product,
    )

    dumped = result.model_dump(mode="json")

    assert dumped["input_spec"]["kind"] == "source_product"
    assert dumped["reference_style_profile"]["dominant_colors_rgb"] == [[255, 255, 255]]


def test_product_bbox_and_confidence_are_validated():
    with pytest.raises(ValidationError):
        ProductPreserveSpec(
            source_image_path="input.png",
            preprocessed_image_path="processed/preprocessed.png",
            product_bbox={"x": 0.7, "y": 0.2, "w": 0.5, "h": 0.6},
        )

    with pytest.raises(ValidationError):
        ProductPreserveSpec(
            source_image_path="input.png",
            preprocessed_image_path="processed/preprocessed.png",
            product_bbox={"x": 0.2, "y": 0.2, "w": 0.6, "h": 0.6},
            confidence=1.2,
        )


def test_input_spec_validates_target_size_and_max_side():
    with pytest.raises(ValidationError):
        ImageInputSpec(image_path="input.png", max_side=128)
    with pytest.raises(ValidationError):
        ImageInputSpec(image_path="input.png", target_width=0)


def test_vision_artifact_type_includes_preprocessed_preview():
    assert "preprocessed_preview" in get_args(VisionArtifactType)


# ===== from test_vision_service.py =====
from pathlib import Path

from PIL import Image

from orchestrator.app.vision.service import run_vision_pipeline_mvp
from orchestrator.app.vision.settings import VisionSettings


def _settings__test_vision_service(tmp_path: Path) -> VisionSettings:
    return VisionSettings(upload_dir=tmp_path / "uploads", processed_dir=tmp_path / "processed")


def _image__test_vision_service(path: Path) -> Path:
    Image.new("RGB", (100, 80), (220, 180, 120)).save(path)
    return path


def test_vision_service_reference_style_result(tmp_path):
    result = run_vision_pipeline_mvp(str(_image__test_vision_service(tmp_path / "ref.png")), "svc-ref", kind="reference_style", settings=_settings__test_vision_service(tmp_path))

    assert result.reference_style_profile is not None
    assert result.product_preserve_spec is None
    assert any(artifact["type"] == "reference_style_profile" for artifact in result.artifact_refs)
    assert result.metadata["external_model_called"] is False


def test_vision_service_product_preserve_result(tmp_path):
    result = run_vision_pipeline_mvp(str(_image__test_vision_service(tmp_path / "product.png")), "svc-product", kind="source_product", settings=_settings__test_vision_service(tmp_path))

    assert result.product_preserve_spec is not None
    assert result.reference_style_profile is None
    assert any(artifact["type"] == "product_mask" for artifact in result.artifact_refs)
    assert any(artifact["type"] == "product_preview" for artifact in result.artifact_refs)
