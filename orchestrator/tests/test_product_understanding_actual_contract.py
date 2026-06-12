from __future__ import annotations

import argparse
import json
from types import SimpleNamespace

from scripts import run_final_composite_quality_actual as runner


def test_product_understanding_benchmark_stop_after_writes_artifacts(monkeypatch, tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "desk_lamp",
                        "input_mode": "text_only",
                        "user_text": "promote a desk lamp",
                        "expected_broad_category": "home_and_living",
                        "expected_category_prefix": ["home_and_living"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    class Adapter:
        def normalize_input_evidence(self, *, request, model):
            return {
                "input_mode": request.input_mode,
                "user_text": request.user_text,
                "explicit_product_mentions": ["desk lamp"],
                "explicit_user_facts": [
                    {"key": "product_name", "value": "desk lamp", "source": "user_text", "evidence_class": "verified_fact", "confidence": 1.0, "usable_for_copy": True}
                ],
                "visual_observations": [],
                "unknown_fields": [],
                "unresolved_questions": [],
                "input_conflicts": [],
                "overall_confidence": 0.95,
                "provider_metadata": {"normalizer": {"provider": "openai", "model": "gpt-5.4", "fallback_used": False, "token_usage": {"input_tokens": 1, "output_tokens": 1}}},
            }

        def understand_product(self, *, request, evidence, model):
            fact = evidence["explicit_user_facts"][0]
            return {
                "product_understanding": {
                    "product_name": "desk lamp",
                    "normalized_product_type": "desk_lamp",
                    "broad_category": "home_and_living",
                    "category_path": ["home_and_living", "lighting", "desk_lamp"],
                    "verified_facts": [fact],
                    "product_name_evidence_ids": [fact["evidence_id"]],
                    "confidence": 0.9,
                },
                "provider_metadata": {"provider": "openai", "model": model, "fallback_used": False, "token_usage": {"input_tokens": 1, "output_tokens": 1}},
            }

    monkeypatch.setattr(
        runner,
        "_canonical_runtime",
        lambda args: SimpleNamespace(copy_model="gpt-5.4", vision_model="gpt-5.4", openai_adapter=Adapter(), call_budget=None),
    )
    args = argparse.Namespace(benchmark_manifest=str(manifest), seed=62, copy_model="gpt-5.4", vlm_model="gpt-5.4", stop_after="product_understanding")

    summary = runner.run_product_understanding_benchmark(args=args, output_dir=tmp_path / "out")

    assert summary["status"] == "completed"
    assert (tmp_path / "out" / "cases" / "desk_lamp" / "product_understanding.json").exists()
    assert summary["image_generation_performed"] is False
