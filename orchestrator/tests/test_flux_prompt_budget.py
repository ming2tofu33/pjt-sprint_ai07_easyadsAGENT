from __future__ import annotations

from pathlib import Path

from PIL import Image

from orchestrator.app.t2i.engines.base import T2IGenerationInput
from orchestrator.app.t2i.engines.flux_local import (
    FluxPromptTokenBudgetError,
    FluxLocalEngine,
    _build_flux_call_kwargs,
    prepare_flux_prompt_bundle,
)


class FakeTokenizer:
    model_max_length = 77

    def __call__(
        self,
        text,
        *,
        add_special_tokens=True,
        truncation=False,
        max_length=None,
        **kwargs,
    ):
        tokens = text.split()
        ids = list(range(len(tokens) + (2 if add_special_tokens else 0)))
        if truncation and max_length:
            ids = ids[:max_length]
        return {"input_ids": ids}


class FakePipeline:
    tokenizer = FakeTokenizer()
    tokenizer_2 = FakeTokenizer()

    def __init__(self):
        self.calls = []

    def __call__(
        self,
        *,
        prompt,
        prompt_2=None,
        width,
        height,
        num_images_per_prompt,
        num_inference_steps,
        guidance_scale,
        max_sequence_length=None,
    ):
        self.calls.append(
            {
                "prompt": prompt,
                "prompt_2": prompt_2,
                "width": width,
                "height": height,
                "num_images_per_prompt": num_images_per_prompt,
                "num_inference_steps": num_inference_steps,
                "guidance_scale": guidance_scale,
                "max_sequence_length": max_sequence_length,
            }
        )
        return type("FakeResult", (), {"images": [Image.new("RGB", (16, 16), "#FFFFFF")]})()


class TinyBudgetTokenizer(FakeTokenizer):
    model_max_length = 10


class TinyBudgetPipeline(FakePipeline):
    tokenizer = TinyBudgetTokenizer()
    tokenizer_2 = FakeTokenizer()


class FakeClipOnlyPipeline:
    tokenizer = FakeTokenizer()
    tokenizer_2 = FakeTokenizer()

    def __call__(self, *, prompt, width, height, num_images_per_prompt, num_inference_steps, guidance_scale):
        return type("FakeResult", (), {"images": []})()


def _long_flux_prompt() -> str:
    return (
        "Create a clean advertising background for the following request: "
        "Create a premium cafe advertising background for a strawberry latte launch with fresh berries, "
        "soft cream, a glass cup, pastel cafe table styling, realistic commercial photography, "
        "warm morning window light, shallow depth of field, elegant dessert props, and many visual details. "
        "Keep clean blank negative space for later Korean copy overlay in post-processing. "
        "Do not include any text, letters, numbers, Hangul, Korean characters, logos, watermarks, captions, "
        "signage, or typography."
    )


def test_flux_prompt_under_budget_is_preserved():
    pipe = FakePipeline()
    prompt = (
        "Strawberry dessert cafe scene with no readable text, no Korean letters, no logos, "
        "no signage, reserved negative space for copy overlay."
    )

    bundle = prepare_flux_prompt_bundle(pipe=pipe, full_prompt=prompt, metadata={"business_type": "cafe"})

    assert bundle.clip_prompt == prompt
    assert bundle.clip_token_count <= bundle.clip_max_tokens
    assert bundle.clip_truncated is False
    assert bundle.critical_constraints_preserved is True
    assert "no readable text" in bundle.clip_prompt
    assert "strawberry" in bundle.clip_prompt.lower()


def test_flux_prompt_over_budget_uses_clip_budget_and_keeps_t5_full_prompt():
    pipe = FakePipeline()
    prompt = _long_flux_prompt()

    bundle = prepare_flux_prompt_bundle(pipe=pipe, full_prompt=prompt, metadata={"business_type": "cafe"})

    assert bundle.clip_token_count <= 77
    assert bundle.clip_truncated is True
    assert bundle.t5_prompt == prompt
    assert bundle.t5_token_count > bundle.clip_token_count
    assert bundle.critical_constraints_preserved is True
    assert bundle.subject_preserved is True
    assert bundle.business_context_preserved is True
    for phrase in ["no readable text", "no Korean letters", "no logos", "no signage", "reserved negative space"]:
        assert phrase in bundle.clip_prompt


def test_flux_prompt_conservative_fallback_without_tokenizer():
    pipe = object()

    bundle = prepare_flux_prompt_bundle(pipe=pipe, full_prompt=_long_flux_prompt(), metadata={})

    assert bundle.clip_token_count <= 62
    assert bundle.clip_max_tokens == 77
    assert bundle.critical_constraints_preserved is True


def test_flux_call_uses_prompt_2_and_t5_max_sequence_length():
    pipe = FakePipeline()
    bundle = prepare_flux_prompt_bundle(pipe=pipe, full_prompt=_long_flux_prompt(), metadata={})
    request = T2IGenerationInput(
        job_id="job_flux",
        prompt=_long_flux_prompt(),
        width=1024,
        height=1024,
        num_images=1,
        output_dir="data/outputs/job_flux",
    )
    settings = type(
        "Settings",
        (),
        {
            "max_images_per_job": 1,
            "flux_num_inference_steps": 4,
            "flux_guidance_scale": 0.0,
            "flux_max_sequence_length": 256,
        },
    )()

    kwargs = _build_flux_call_kwargs(pipe=pipe, prompt_bundle=bundle, request=request, settings=settings)

    assert kwargs["prompt"] == bundle.clip_prompt
    assert kwargs["prompt_2"] == bundle.t5_prompt
    assert kwargs["max_sequence_length"] == 256
    assert kwargs["num_inference_steps"] == 4
    assert kwargs["guidance_scale"] == 0.0


def test_flux_call_omits_prompt_2_when_pipeline_does_not_support_it():
    pipe = FakeClipOnlyPipeline()
    bundle = prepare_flux_prompt_bundle(pipe=pipe, full_prompt=_long_flux_prompt(), metadata={})
    request = T2IGenerationInput(job_id="job_flux", prompt=_long_flux_prompt(), output_dir="data/outputs/job_flux")
    settings = type(
        "Settings",
        (),
        {
            "max_images_per_job": 1,
            "flux_num_inference_steps": 4,
            "flux_guidance_scale": 0.0,
            "flux_max_sequence_length": 256,
        },
    )()

    kwargs = _build_flux_call_kwargs(pipe=pipe, prompt_bundle=bundle, request=request, settings=settings)

    assert kwargs["prompt"] == bundle.clip_prompt
    assert "prompt_2" not in kwargs
    assert "max_sequence_length" not in kwargs


def test_flux_engine_metadata_excludes_raw_secret_like_metadata(monkeypatch, tmp_path):
    pipe = FakePipeline()
    monkeypatch.setenv("EASYADS_ENABLE_FLUX_LOCAL", "true")
    monkeypatch.setenv("HF_TOKEN", "hf-secret")
    monkeypatch.setattr("orchestrator.app.t2i.engines.flux_local._load_pipeline", lambda model_ref, device: pipe)

    output = FluxLocalEngine().generate(
        T2IGenerationInput(
            job_id="job_flux",
            prompt=_long_flux_prompt(),
            output_dir=tmp_path.as_posix(),
            metadata={"api_key": "sk-should-not-leak", "business_type": "cafe"},
        )
    )

    assert Path(output.image_paths[0]).exists()
    assert output.metadata["clip_token_count"] <= output.metadata["clip_max_tokens"]
    assert output.metadata["prompt_2_used"] is True
    assert output.metadata["critical_constraints_preserved"] is True
    assert "sk-should-not-leak" not in str(output.metadata)


def test_flux_request_metadata_cannot_override_engine_metrics(monkeypatch, tmp_path):
    pipe = FakePipeline()
    monkeypatch.setenv("EASYADS_ENABLE_FLUX_LOCAL", "true")
    monkeypatch.setenv("HF_TOKEN", "hf-secret")
    monkeypatch.setattr("orchestrator.app.t2i.engines.flux_local._load_pipeline", lambda model_ref, device: pipe)

    output = FluxLocalEngine().generate(
        T2IGenerationInput(
            job_id="job_flux",
            prompt=_long_flux_prompt(),
            output_dir=tmp_path.as_posix(),
            metadata={
                "clip_token_count": 999,
                "prompt_2_used": False,
                "critical_constraints_preserved": False,
                "debug": {"api_key": "nested-secret", "safe": "visible"},
            },
        )
    )

    assert output.metadata["clip_token_count"] <= 77
    assert output.metadata["prompt_2_used"] is True
    assert output.metadata["critical_constraints_preserved"] is True
    assert output.metadata["debug"]["safe"] == "visible"
    assert "nested-secret" not in str(output.metadata)


def test_flux_prompt_uses_primary_subject_metadata():
    pipe = FakePipeline()
    prompt = _long_flux_prompt()

    bundle = prepare_flux_prompt_bundle(
        pipe=pipe,
        full_prompt=prompt,
        metadata={"primary_subject": "matcha tiramisu hero dessert", "business_type": "cafe"},
    )

    assert "matcha tiramisu hero dessert" in bundle.clip_prompt
    assert bundle.subject_preserved is True
    assert bundle.business_context_preserved is True


def test_flux_long_subject_does_not_drop_later_optional_context():
    pipe = FakePipeline()
    prompt = _long_flux_prompt()
    long_subject = " ".join(f"subjectword{i}" for i in range(120))

    bundle = prepare_flux_prompt_bundle(
        pipe=pipe,
        full_prompt=prompt,
        metadata={"primary_subject": long_subject, "business_type": "beauty_spa"},
    )

    assert bundle.clip_token_count <= 77
    assert "beauty spa" in bundle.clip_prompt
    assert "clear hero product or subject" in bundle.clip_prompt


def test_flux_prompt_budget_failure_uses_specific_error_code():
    pipe = TinyBudgetPipeline()

    try:
        prepare_flux_prompt_bundle(pipe=pipe, full_prompt=_long_flux_prompt(), metadata={})
    except FluxPromptTokenBudgetError as exc:
        assert exc.error_code == "flux_prompt_token_budget_unresolvable"
    else:
        raise AssertionError("expected FluxPromptTokenBudgetError")
