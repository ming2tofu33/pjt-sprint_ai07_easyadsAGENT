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


# ===== Task 9: web-shaped request -> native typography pipeline regression =====
import sys as _sys
import types as _types
from types import SimpleNamespace as _SNS

import pytest

from orchestrator.app.llm.nodes.creative_execution_planner import creative_execution_planner_node
from orchestrator.app.llm.nodes.native_copy_brief import native_copy_brief_node
from orchestrator.app.llm.nodes.native_creative_preflight import native_creative_preflight_node
from orchestrator.app.schemas.native_creative import NativeCreativePromptPackage, NativeCreativePreflightReview


class _ApprovedCopyAdapter:
    def generate_native_copy_brief(self, **kwargs):
        return {
            "headline": "자동 헤드라인", "supporting_copy": "자동 서브카피", "language": "korean",
            "message_role": "headline_plus_support",
            "allowed_texts": ["자동 헤드라인", "자동 서브카피"], "forbidden_texts": [],
            "max_text_blocks": 2, "max_total_characters": 48, "verified_evidence_ids": ["e1"],
            "unsupported_claim_categories": [], "compliance_status": "approved", "rejection_reasons": [],
        }


class _FormatPlanAdapter:
    def __init__(self, payload):
        self.payload = payload

    def generate_format_approved_plan(self, **kwargs):
        return self.payload


def _evidence_dict(user_text, mentions):
    return {
        "schema_version": "input_evidence_bundle_v1", "input_mode": "text_only",
        "user_text": user_text, "explicit_product_mentions": mentions, "overall_confidence": 0.9,
    }


def _product_dict(name="시카 세럼"):
    return {
        "product_name": name, "normalized_product_type": "cica_serum",
        "broad_category": "beauty_and_personal_care",
        "category_path": ["beauty_and_personal_care", "cica_serum"],
        "product_name_evidence_ids": ["e1"], "confidence": 0.9,
    }


def _web_state(*, ad_format, user_text, mentions, format_adapter=None, custom_headline="시카 진정 세럼", custom_subcopy="민감 피부 진정 케어", engine="gpt_image_2"):
    # Only existing web request fields drive the backend; no new plan fields.
    state = {
        "engine": engine,
        "selected_ad_format": ad_format,
        "user_input": user_text,
        "user_custom_headline": custom_headline,
        "user_custom_subcopy": custom_subcopy,
        "input_evidence_bundle": _evidence_dict(user_text, mentions),
        "product_understanding": _product_dict(),
        "native_copy_adapter": _ApprovedCopyAdapter(),
    }
    if format_adapter is not None:
        state["format_approved_plan_adapter"] = format_adapter
    return state


def _run_to_preflight(state, monkeypatch):
    monkeypatch.setattr(
        "orchestrator.app.llm.nodes.native_creative_preflight.review_native_creative_preflight",
        lambda **kwargs: NativeCreativePreflightReview(
            decision="approved", copy_grounded=True, claims_supported=True, language_natural=True,
            generic_cta_absent=True, text_budget_valid=True, native_typography_suitable=True,
            product_visual_direction_valid=True, failure_reasons=[], revision_instructions=[],
        ),
    )
    state = dict(state)
    state.update(creative_execution_planner_node(state))
    state.update(native_copy_brief_node(state))
    state.update(native_creative_preflight_node(state))
    return state


def _install_fake_openai(monkeypatch, tmp_path):
    import base64
    img = tmp_path / "src.png"
    Image.new("RGB", (32, 32), "#ffffff").save(img)
    encoded = base64.b64encode(img.read_bytes()).decode("ascii")
    captured = {}

    class FakeImages:
        def generate(self, **kwargs):
            captured.update(kwargs)
            return _SNS(id="req_1", data=[_SNS(b64_json=encoded)])

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs
            self.images = FakeImages()

    module = _types.ModuleType("openai")
    module.OpenAI = FakeOpenAI
    monkeypatch.setitem(_sys.modules, "openai", module)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("EASYADS_ENABLE_EXTERNAL_T2I", "true")
    monkeypatch.setenv("EASYADS_ENABLE_GPT_IMAGE_2", "true")
    return captured


def test_pipeline_gpt_image_2_routes_to_native_single_shot(monkeypatch):
    state = _web_state(ad_format="banner", user_text="시카 세럼 광고", mentions=["시카 세럼"])
    planned = creative_execution_planner_node(state)
    plan = planned["creative_execution_plan"]
    # item 1 + 2: gpt_image_2 stays selected and routes to the native single-shot lane.
    assert plan["image_engine"] == "gpt_image_2"
    assert plan["execution_lane"] == "gpt_native_single_shot"
    assert plan["image_call_limit"] == 1
    assert plan["automatic_edit_allowed"] is False
    assert plan["automatic_retry_allowed"] is False
    assert plan["external_renderer_fallback_allowed"] is False


@pytest.mark.parametrize("ad_format,profile", [("banner", "banner"), ("poster", "poster")])
def test_pipeline_banner_poster_two_block_profile(monkeypatch, ad_format, profile):
    state = _web_state(ad_format=ad_format, user_text="시카 세럼 광고", mentions=["시카 세럼"])
    final = _run_to_preflight(state, monkeypatch)
    pkg = final["native_creative_prompt_package"]
    assert final["native_generation_status"] == "preflight_approved"
    assert f"FORMAT PROFILE: {profile}" in pkg["final_prompt"]
    assert pkg["exact_allowed_texts"] == ["시카 진정 세럼", "민감 피부 진정 케어"]
    assert pkg["product_detail_approved_feature_plan"] is None
    assert pkg["flyer_approved_copy_plan"] is None
    assert pkg["flyer_promotional_approved_copy_plan"] is None


def test_pipeline_product_detail_plan_reaches_prompt_package(monkeypatch):
    adapter = _FormatPlanAdapter({"decision": "approved", "plan": {"feature_labels": ["피부 진정", "수분 충전"]}})
    state = _web_state(ad_format="product_detail", user_text="시카 세럼 상세. 피부 진정, 수분 충전 강조.", mentions=["시카 세럼"], format_adapter=adapter)
    final = _run_to_preflight(state, monkeypatch)
    pkg = final["native_creative_prompt_package"]
    assert final["native_generation_status"] == "preflight_approved"
    assert "FORMAT PROFILE: product_detail" in pkg["final_prompt"]
    assert pkg["product_detail_approved_feature_plan"] is not None
    assert pkg["exact_allowed_texts"] == ["시카 진정 세럼", "민감 피부 진정 케어", "피부 진정", "수분 충전"]
    assert pkg["flyer_approved_copy_plan"] is None


def test_pipeline_editorial_flyer_plan_reaches_prompt_package(monkeypatch):
    adapter = _FormatPlanAdapter({"decision": "approved", "flyer_mode": "editorial", "plan": {"info_cards": ["토요 모임", "자유 토론"]}})
    # editorial flyer text is grounded; the info-card phrases appear in the request.
    state = _web_state(
        ad_format="flyer", user_text="동네 독서 모임 안내 전단지. 토요 모임, 자유 토론. 책 읽는 즐거움 소개.", mentions=["독서 모임"],
        format_adapter=adapter, custom_headline="독서 모임 초대", custom_subcopy="함께 읽는 즐거움",
    )
    final = _run_to_preflight(state, monkeypatch)
    pkg = final["native_creative_prompt_package"]
    assert final["native_generation_status"] == "preflight_approved"
    assert "FORMAT PROFILE: flyer_editorial" in pkg["final_prompt"]
    assert 4 <= len(pkg["exact_allowed_texts"]) <= 6
    assert pkg["flyer_approved_copy_plan"] is not None
    assert pkg["flyer_promotional_approved_copy_plan"] is None
    assert pkg["product_detail_approved_feature_plan"] is None


def test_pipeline_promotional_flyer_plan_reaches_prompt_package(monkeypatch):
    gym_text = ("프리미엄 헬스장 오픈. GRAND OPEN. 1:1 PT 상담 가능, 유산소·웨이트존 운영, 초보자 맞춤 지도. "
                "문의 000-0000-0000. OO역 3번 출구 앞. 상담은 예약제로 운영됩니다.")
    adapter = _FormatPlanAdapter({
        "decision": "approved", "flyer_mode": "promotional",
        "plan": {
            "promo_badge": "GRAND OPEN",
            "info_items": ["1:1 PT 상담 가능", "유산소·웨이트존 운영", "초보자 맞춤 지도"],
            "contact_line": "문의 000-0000-0000", "location_line": "OO역 3번 출구 앞",
            "notice_line": "상담은 예약제로 운영됩니다",
        },
    })
    state = _web_state(ad_format="flyer", user_text=gym_text, mentions=["헬스장"], format_adapter=adapter,
                       custom_headline="프리미엄 헬스장 오픈", custom_subcopy="신규 회원 모집")
    final = _run_to_preflight(state, monkeypatch)
    pkg = final["native_creative_prompt_package"]
    assert final["native_generation_status"] == "preflight_approved"
    assert "FORMAT PROFILE: flyer_promotional" in pkg["final_prompt"]
    assert 7 <= len(pkg["exact_allowed_texts"]) <= 10
    assert "문의 000-0000-0000" in pkg["exact_allowed_texts"]
    assert pkg["product_detail_approved_feature_plan"] is None
    assert pkg["flyer_approved_copy_plan"] is None


def test_pipeline_invented_operational_text_fails_closed_before_preflight(monkeypatch):
    gym_text = "프리미엄 헬스장 오픈. GRAND OPEN. 문의 000-0000-0000."
    adapter = _FormatPlanAdapter({
        "decision": "approved", "flyer_mode": "promotional",
        "plan": {
            "promo_badge": "GRAND OPEN",
            "info_items": ["PT 상담", "웨이트존", "초보 지도"],
            "contact_line": "문의 010-9999-8888",  # not grounded in evidence
        },
    })
    state = _web_state(ad_format="flyer", user_text=gym_text, mentions=["헬스장"], format_adapter=adapter,
                       custom_headline="프리미엄 헬스장 오픈", custom_subcopy="신규 회원 모집")
    update = native_copy_brief_node({**state, **creative_execution_planner_node(state)})
    # fails closed at the bundle stage (before preflight); no plan leaks.
    assert update["native_generation_status"] == "rejected"
    assert update["format_approved_plan_bundle"]["decision"] == "rejected"
    assert "invented_operational_text" in update["format_approved_plan_bundle"]["reason_codes"]
    assert update["flyer_promotional_approved_copy_plan"] is None


def test_pipeline_single_shot_one_image_call_no_edit_no_retry(monkeypatch, tmp_path):
    captured = _install_fake_openai(monkeypatch, tmp_path)
    adapter = _FormatPlanAdapter({"decision": "approved", "plan": {"feature_labels": ["피부 진정", "수분 충전"]}})
    state = _web_state(ad_format="product_detail", user_text="시카 세럼 상세. 피부 진정, 수분 충전 강조.", mentions=["시카 세럼"], format_adapter=adapter)
    final = _run_to_preflight(state, monkeypatch)
    package = NativeCreativePromptPackage(**final["native_creative_prompt_package"])

    result = GPTImage2ActualEngine().generate_native_single_shot(prompt_package=package, output_dir=tmp_path)

    # items 8 + 9: exactly one image call, no edit/retry, external renderer unused.
    assert package.image_call_limit == 1
    assert package.automatic_edit_allowed is False
    assert package.automatic_retry_allowed is False
    assert result["image_call_count"] == 1
    assert result["edit_call_count"] == 0
    assert result["retry_call_count"] == 0
    assert captured["client_kwargs"]["max_retries"] == 0
    assert captured["n"] == 1


def test_no_new_frontend_request_field_for_format_plans():
    # item 10: backend planner generates plans from existing inputs; web schema
    # must not carry any format-plan field.
    from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest
    fields = set(GenerationJobCreateRequest.model_fields)
    for forbidden in ("format_approved_plan_bundle", "flyer_approved_copy_plan",
                      "flyer_promotional_approved_copy_plan", "product_detail_approved_feature_plan",
                      "feature_labels"):
        assert forbidden not in fields
    # existing web fields remain available.
    for existing in ("user_input", "ad_format", "user_custom_headline", "user_custom_subcopy"):
        assert existing in fields
