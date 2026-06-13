import base64
import sys
import types
from types import SimpleNamespace

from PIL import Image

from orchestrator.app.llm.native_copy_policy import build_native_prompt_package
from orchestrator.app.schemas.native_creative import ApprovedNativeCopyBrief
from orchestrator.app.t2i.engines.gpt_image_2 import GPTImage2ActualEngine


def test_gpt_image2_native_single_shot_uses_one_generate_no_retry(monkeypatch, tmp_path):
    image_path = tmp_path / "source.png"
    Image.new("RGB", (32, 32), "#ffffff").save(image_path)
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    captured = {}

    class FakeImages:
        def generate(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(id="req_1", data=[SimpleNamespace(b64_json=encoded)])

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs
            self.images = FakeImages()

    module = types.ModuleType("openai")
    module.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", module)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("EASYADS_ENABLE_EXTERNAL_T2I", "true")
    monkeypatch.setenv("EASYADS_ENABLE_GPT_IMAGE_2", "true")

    brief = ApprovedNativeCopyBrief(
        headline="고급진 된장찌개",
        supporting_copy="진한 구수함 한 그릇",
        language="korean",
        message_role="headline_plus_support",
        allowed_texts=["고급진 된장찌개", "진한 구수함 한 그릇"],
        forbidden_texts=[],
        max_text_blocks=2,
        max_total_characters=48,
        verified_evidence_ids=["e1"],
        unsupported_claim_categories=[],
        compliance_status="approved",
        rejection_reasons=[],
    )
    package = build_native_prompt_package(product_understanding={"product_name": "된장찌개"}, copy_brief=brief)

    result = GPTImage2ActualEngine().generate_native_single_shot(prompt_package=package, output_dir=tmp_path)

    assert captured["client_kwargs"]["max_retries"] == 0
    assert captured["model"] == "gpt-image-2"
    assert captured["n"] == 1
    assert result["image_call_count"] == 1
    assert result["edit_call_count"] == 0
    assert (tmp_path / "final_native_image.png").exists()
