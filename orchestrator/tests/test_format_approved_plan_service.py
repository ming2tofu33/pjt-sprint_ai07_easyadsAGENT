"""Tests for the format-aware approved-plan builder (Tasks 2, 3 & 4, scoped).

Covers the public builder contract / bundle structure, exact custom
headline/subcopy precedence, and grounded product-detail feature extraction.
Flyer mode classification grounding and graph wiring are out of this scope.
"""

from types import SimpleNamespace

from orchestrator.app.llm.format_approved_plan_service import build_format_approved_plan_bundle
from orchestrator.app.llm.format_approved_plan_provider import DefaultFormatApprovedPlanProvider
from orchestrator.app.schemas.input_evidence import InputEvidenceBundle
from orchestrator.app.schemas.native_creative import ApprovedNativeCopyBrief, FormatApprovedPlanBundle
from orchestrator.app.schemas.product_understanding import ProductUnderstanding


def _evidence() -> InputEvidenceBundle:
    return InputEvidenceBundle(
        input_mode="text_only",
        user_text="시카 세럼 상세페이지를 만들어줘. 피부 진정과 수분 충전을 강조해줘.",
        explicit_product_mentions=["시카 세럼"],
        overall_confidence=0.9,
    )


def _product() -> ProductUnderstanding:
    return ProductUnderstanding(
        product_name="시카 세럼",
        normalized_product_type="cica_serum",
        broad_category="beauty_and_personal_care",
        category_path=["beauty_and_personal_care", "cica_serum"],
        confidence=0.9,
    )


def _approved_copy(headline="시카 세럼", supporting="피부 진정 수분 케어") -> ApprovedNativeCopyBrief:
    return ApprovedNativeCopyBrief(
        headline=headline,
        supporting_copy=supporting,
        language="korean",
        message_role="headline_plus_support",
        allowed_texts=[t for t in (headline, supporting) if t],
        max_text_blocks=2,
        max_total_characters=48,
        compliance_status="approved",
    )


class _RecordingAdapter:
    """Fake adapter capturing whether it was called and returning a fixed payload."""

    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def generate_format_approved_plan(self, **kwargs):
        self.calls += 1
        return self.payload


class _RaisingAdapter:
    def generate_format_approved_plan(self, **kwargs):
        raise RuntimeError("provider_down")


def _build(ad_format, *, adapter=None, state=None, approved_copy=None, evidence=None):
    full_state = {"format_approved_plan_adapter": adapter} if adapter is not None else {}
    full_state.update(state or {})
    return build_format_approved_plan_bundle(
        ad_format=ad_format,
        input_evidence=evidence or _evidence(),
        product_understanding=_product(),
        approved_copy=approved_copy or _approved_copy(),
        state=full_state,
    )


def _extended_plans(bundle: FormatApprovedPlanBundle) -> list:
    return [
        plan
        for plan in (
            bundle.flyer_approved_copy_plan,
            bundle.flyer_promotional_approved_copy_plan,
            bundle.product_detail_approved_feature_plan,
        )
        if plan is not None
    ]


# ----- Task 2: builder contract & bundle structure -----

def test_banner_returns_not_required_without_calling_adapter():
    adapter = _RecordingAdapter({"decision": "approved"})
    bundle = _build("banner", adapter=adapter)
    assert bundle.decision == "not_required"
    assert _extended_plans(bundle) == []
    assert adapter.calls == 0


def test_poster_returns_not_required_without_extended_plan():
    bundle = _build("poster", adapter=_RecordingAdapter({"decision": "approved"}))
    assert bundle.decision == "not_required"
    assert _extended_plans(bundle) == []


def test_product_detail_returns_only_product_detail_feature_plan():
    adapter = _RecordingAdapter({
        "decision": "approved",
        "plan": {"feature_labels": ["피부 진정", "수분 충전"]},
    })
    bundle = _build("product_detail", adapter=adapter)
    assert bundle.decision == "approved"
    assert bundle.product_detail_approved_feature_plan is not None
    assert bundle.flyer_approved_copy_plan is None
    assert bundle.flyer_promotional_approved_copy_plan is None
    assert len(_extended_plans(bundle)) == 1


def test_editorial_flyer_returns_only_flyer_approved_copy_plan():
    adapter = _RecordingAdapter({
        "decision": "approved",
        "flyer_mode": "editorial",
        "plan": {
            "subtitle": "데일리 진정 케어",
            "info_cards": ["진정", "수분"],
            "allowed_texts": ["시카 세럼", "데일리 진정 케어", "진정", "수분"],
        },
    })
    bundle = _build("flyer", adapter=adapter)
    assert bundle.decision == "approved"
    assert bundle.flyer_approved_copy_plan is not None
    assert bundle.flyer_promotional_approved_copy_plan is None
    assert bundle.product_detail_approved_feature_plan is None
    assert len(_extended_plans(bundle)) == 1


def _gym_evidence() -> InputEvidenceBundle:
    return InputEvidenceBundle(
        input_mode="text_only",
        user_text=(
            "프리미엄 헬스장 오픈. GRAND OPEN. "
            "1:1 PT 상담 가능, 유산소·웨이트존 운영, 초보자 맞춤 지도. "
            "문의 000-0000-0000. OO역 3번 출구 앞. 상담은 예약제로 운영됩니다."
        ),
        explicit_product_mentions=["헬스장"],
        overall_confidence=0.9,
    )


def _gym_promo_payload() -> dict:
    return {
        "decision": "approved",
        "flyer_mode": "promotional",
        "plan": {
            "promo_badge": "GRAND OPEN",
            "info_items": ["1:1 PT 상담 가능", "유산소·웨이트존 운영", "초보자 맞춤 지도"],
            "contact_line": "문의 000-0000-0000",
            "location_line": "OO역 3번 출구 앞",
            "notice_line": "상담은 예약제로 운영됩니다",
        },
    }


def test_promotional_flyer_returns_only_promotional_plan():
    bundle = _build(
        "flyer",
        adapter=_RecordingAdapter(_gym_promo_payload()),
        evidence=_gym_evidence(),
        approved_copy=_approved_copy("프리미엄 헬스장 오픈", None),
    )
    assert bundle.decision == "approved"
    assert bundle.flyer_promotional_approved_copy_plan is not None
    assert bundle.flyer_approved_copy_plan is None
    assert bundle.product_detail_approved_feature_plan is None
    assert len(_extended_plans(bundle)) == 1


def test_no_request_populates_more_than_one_extended_plan():
    for ad_format, payload in (
        ("product_detail", {"decision": "approved", "plan": {"feature_labels": ["피부 진정", "수분 충전"]}}),
        ("flyer", {"decision": "approved", "flyer_mode": "editorial",
                   "plan": {"subtitle": "데일리 진정 케어", "info_cards": ["진정", "수분"],
                            "allowed_texts": ["시카 세럼", "데일리 진정 케어", "진정", "수분"]}}),
    ):
        bundle = _build(ad_format, adapter=_RecordingAdapter(payload))
        assert len(_extended_plans(bundle)) <= 1


def test_unsupported_format_returns_manual_review():
    bundle = _build("carousel", adapter=_RecordingAdapter({"decision": "approved"}))
    assert bundle.decision == "manual_review"
    assert "unsupported_ad_format" in bundle.reason_codes
    assert _extended_plans(bundle) == []


def test_default_provider_builds_product_detail_without_state_adapter(monkeypatch):
    provider = _RecordingAdapter({
        "decision": "approved",
        "plan": {"feature_labels": ["피부 진정", "수분 충전"]},
    })
    monkeypatch.setattr(
        "orchestrator.app.llm.format_approved_plan_service.get_default_format_approved_plan_provider",
        lambda: provider,
    )
    bundle = build_format_approved_plan_bundle(
        ad_format="product_detail",
        input_evidence=_evidence(),
        product_understanding=_product(),
        approved_copy=_approved_copy(),
        state={},
    )
    assert bundle.decision == "approved"
    assert bundle.product_detail_approved_feature_plan.feature_labels == ["피부 진정", "수분 충전"]
    assert provider.calls == 1


def test_explicit_adapter_failure_returns_rejected():
    bundle = _build("product_detail", adapter=_RaisingAdapter())
    assert bundle.decision == "rejected"
    assert "provider_error" in bundle.reason_codes


def test_default_provider_failure_returns_rejected(monkeypatch):
    monkeypatch.setattr(
        "orchestrator.app.llm.format_approved_plan_service.get_default_format_approved_plan_provider",
        lambda: _RaisingAdapter(),
    )
    bundle = _build("product_detail")
    assert bundle.decision == "rejected"
    assert bundle.reason_codes == ["provider_error"]
    assert bundle.provider_metadata["error"] == "provider_down"


def test_default_provider_schema_error_fails_closed(monkeypatch):
    monkeypatch.setattr(
        "orchestrator.app.llm.format_approved_plan_service.get_default_format_approved_plan_provider",
        lambda: _RecordingAdapter({"decision": "approved", "plan": {"feature_labels": "not-a-list"}}),
    )
    bundle = _build("product_detail")
    assert bundle.decision == "rejected"
    assert "provider_payload_schema_invalid" in bundle.reason_codes


def test_default_provider_builds_promotional_flyer_without_state_adapter(monkeypatch):
    provider = _RecordingAdapter(_gym_promo_payload())
    monkeypatch.setattr(
        "orchestrator.app.llm.format_approved_plan_service.get_default_format_approved_plan_provider",
        lambda: provider,
    )
    bundle = _build(
        "flyer",
        evidence=_gym_evidence(),
        approved_copy=_approved_copy("프리미엄 헬스장 오픈", None),
    )
    assert bundle.decision == "approved"
    assert bundle.flyer_promotional_approved_copy_plan is not None
    assert provider.calls == 1


def test_default_provider_invented_operational_text_fails_closed(monkeypatch):
    payload = _gym_promo_payload()
    payload["plan"] = {**payload["plan"], "contact_line": "문의 010-1234-5678"}
    monkeypatch.setattr(
        "orchestrator.app.llm.format_approved_plan_service.get_default_format_approved_plan_provider",
        lambda: _RecordingAdapter(payload),
    )
    bundle = _build(
        "flyer",
        evidence=_gym_evidence(),
        approved_copy=_approved_copy("프리미엄 헬스장 오픈", None),
    )
    assert bundle.decision == "rejected"
    assert "invented_operational_text" in bundle.reason_codes
    assert bundle.flyer_promotional_approved_copy_plan is None


def test_editorial_flyer_normalizes_grounded_optional_fields_into_schema_budget():
    payload = {
        "decision": "approved",
        "flyer_mode": "editorial",
        "plan": {
            "body_copy": "에스프레소와 우유로 만든 메뉴",
            "info_cards": ["부드러운 맛", "은은한 단맛", "매장에서 편하게 즐길 수 있음"],
            "bottom_notice": "따뜻하게 또는 아이스로 제공",
        },
    }
    evidence = InputEvidenceBundle(
        input_mode="text_only",
        user_text=(
            "라떼 카페 라떼 전단지를 만들어줘. "
            "에스프레소와 우유로 만든 메뉴. 부드러운 맛. 은은한 단맛. "
            "따뜻하게 또는 아이스로 제공. 매장에서 편하게 즐길 수 있음."
        ),
        explicit_product_mentions=["라떼 카페 라떼"],
        overall_confidence=0.9,
    )

    bundle = _build(
        "flyer",
        adapter=_RecordingAdapter(payload),
        evidence=evidence,
        approved_copy=_approved_copy("라떼 카페 라떼", "부드럽고 은은한 단맛의 라떼"),
    )

    assert bundle.decision == "approved"
    assert bundle.flyer_approved_copy_plan is not None
    assert 4 <= len(bundle.flyer_approved_copy_plan.allowed_texts) <= 6


def test_default_provider_uses_llm_adapter_path(monkeypatch):
    captured = {}

    def fake_invoke_structured(self, schema, prompt, model_selection, metadata=None):
        captured["schema_name"] = getattr(schema, "__name__", "")
        captured["provider"] = model_selection.provider
        captured["selected_model_class"] = model_selection.selected_model_class
        captured["metadata"] = metadata
        return SimpleNamespace(
            success=True,
            output={"decision": "approved", "plan": {"feature_labels": ["피부 진정", "수분 충전"]}, "provider_metadata": {}},
            metadata={"provider": "openai", "provider_profile": "openai", "model": "gpt-5.4"},
            error=None,
        )

    monkeypatch.setattr(
        "orchestrator.app.llm.format_approved_plan_provider.OpenAIAdapter.invoke_structured",
        fake_invoke_structured,
    )

    payload = DefaultFormatApprovedPlanProvider().generate_format_approved_plan(
        ad_format="product_detail",
        input_evidence=_evidence(),
        product_understanding=_product(),
        approved_copy=_approved_copy(),
        state={},
    )

    assert payload["decision"] == "approved"
    assert payload["plan"]["feature_labels"] == ["피부 진정", "수분 충전"]
    assert captured["schema_name"] == "_FormatApprovedPlanPayload"
    assert captured["provider"] == "openai"
    assert captured["selected_model_class"] == "api_full"
    assert captured["metadata"] == {"ad_format": "product_detail"}


def test_product_detail_single_label_returns_manual_review():
    # One grounded label is below the 2-feature minimum -> manual_review (Task 4).
    adapter = _RecordingAdapter({"decision": "approved", "plan": {"feature_labels": ["피부 진정"]}})
    bundle = _build("product_detail", adapter=adapter)
    assert bundle.decision == "manual_review"
    assert "insufficient_grounded_features" in bundle.reason_codes
    assert bundle.product_detail_approved_feature_plan is None


# ----- Task 3: exact custom headline/subcopy precedence -----

def test_custom_headline_and_subcopy_preserved_byte_for_byte_in_product_detail():
    custom_headline = "시카 진정 세럼"
    custom_subcopy = "민감한 피부를 편안하게 감싸는 진정 케어"
    adapter = _RecordingAdapter({
        "decision": "approved",
        "plan": {"feature_labels": ["피부 진정", "수분 충전"]},
    })
    bundle = _build(
        "product_detail",
        adapter=adapter,
        approved_copy=_approved_copy("자동 생성 헤드라인", "자동 생성 서브카피"),
        state={"user_custom_headline": custom_headline, "user_custom_subcopy": custom_subcopy},
    )
    plan = bundle.product_detail_approved_feature_plan
    assert plan is not None
    # byte-for-byte: custom values override the generated copy unchanged.
    assert plan.headline == custom_headline
    assert plan.supporting_copy == custom_subcopy
    # both custom strings appear first, in order, ahead of feature labels.
    assert plan.allowed_texts[:2] == [custom_headline, custom_subcopy]
    assert plan.allowed_texts == [custom_headline, custom_subcopy, "피부 진정", "수분 충전"]


def test_custom_copy_not_normalized_or_shortened():
    # Surrounding whitespace and length must survive verbatim.
    custom_headline = "  시카   진정   세럼  "
    adapter = _RecordingAdapter({
        "decision": "approved",
        "plan": {"feature_labels": ["피부 진정", "수분 충전"]},
    })
    bundle = _build(
        "product_detail",
        adapter=adapter,
        state={"user_custom_headline": custom_headline, "user_custom_subcopy": "민감 피부 진정 케어"},
    )
    plan = bundle.product_detail_approved_feature_plan
    assert plan.headline == custom_headline


def test_generated_copy_authoritative_when_no_custom_copy():
    adapter = _RecordingAdapter({
        "decision": "approved",
        "plan": {"feature_labels": ["피부 진정", "수분 충전"]},
    })
    bundle = _build(
        "product_detail",
        adapter=adapter,
        approved_copy=_approved_copy("자동 생성 헤드라인", "자동 생성 서브카피"),
    )
    plan = bundle.product_detail_approved_feature_plan
    assert plan.headline == "자동 생성 헤드라인"
    assert plan.supporting_copy == "자동 생성 서브카피"
    assert plan.allowed_texts[:2] == ["자동 생성 헤드라인", "자동 생성 서브카피"]


# ----- Task 4: grounded product-detail feature extraction -----

def _serum_features_evidence() -> InputEvidenceBundle:
    return InputEvidenceBundle(
        input_mode="text_only",
        user_text="시카 세럼 상세페이지를 만들어줘. 피부 진정, 수분 충전, 산뜻한 흡수, 데일리 케어를 강조해줘.",
        explicit_product_mentions=["시카 세럼"],
        overall_confidence=0.9,
    )


def test_product_detail_generates_grounded_feature_labels():
    adapter = _RecordingAdapter({
        "decision": "approved",
        "plan": {"feature_labels": ["피부 진정", "수분 충전", "산뜻한 흡수", "데일리 케어"]},
    })
    bundle = _build(
        "product_detail",
        adapter=adapter,
        evidence=_serum_features_evidence(),
        approved_copy=_approved_copy("시카 세럼", "피부 진정 데일리 케어"),
    )
    assert bundle.decision == "approved"
    plan = bundle.product_detail_approved_feature_plan
    assert plan.feature_labels == ["피부 진정", "수분 충전", "산뜻한 흡수", "데일리 케어"]
    assert plan.allowed_texts == ["시카 세럼", "피부 진정 데일리 케어", "피부 진정", "수분 충전", "산뜻한 흡수", "데일리 케어"]


def test_product_detail_rejects_operational_text_in_feature_label():
    for bad_label in ("9,000원", "문의 000-0000-0000", "OO역 3번 출구", "지금 구매"):
        adapter = _RecordingAdapter({
            "decision": "approved",
            "plan": {"feature_labels": ["피부 진정", bad_label]},
        })
        bundle = _build("product_detail", adapter=adapter, evidence=_serum_features_evidence())
        assert bundle.decision == "rejected", bad_label
        assert "feature_label_contains_operational_text" in bundle.reason_codes
        assert bundle.product_detail_approved_feature_plan is None


def test_product_detail_rejects_invented_efficacy_claim():
    # "주름 개선" never appears in user input or product evidence.
    adapter = _RecordingAdapter({
        "decision": "approved",
        "plan": {"feature_labels": ["피부 진정", "주름 개선"]},
    })
    bundle = _build("product_detail", adapter=adapter, evidence=_serum_features_evidence())
    assert bundle.decision == "rejected"
    assert "feature_label_not_grounded" in bundle.reason_codes


def test_product_detail_rejects_ungrounded_adapter_output():
    adapter = _RecordingAdapter({
        "decision": "approved",
        "plan": {"feature_labels": ["완전 무관한 라벨", "또다른 무관 라벨"]},
    })
    bundle = _build("product_detail", adapter=adapter, evidence=_serum_features_evidence())
    assert bundle.decision == "rejected"
    assert "feature_label_not_grounded" in bundle.reason_codes


def test_product_detail_manual_review_when_fewer_than_two_grounded():
    adapter = _RecordingAdapter({
        "decision": "approved",
        "plan": {"feature_labels": ["피부 진정"]},
    })
    bundle = _build("product_detail", adapter=adapter, evidence=_serum_features_evidence())
    assert bundle.decision == "manual_review"
    assert "insufficient_grounded_features" in bundle.reason_codes
    assert bundle.product_detail_approved_feature_plan is None


def test_product_detail_truncates_more_than_four_labels_deterministically():
    adapter = _RecordingAdapter({
        "decision": "approved",
        "plan": {"feature_labels": ["피부 진정", "수분 충전", "산뜻한 흡수", "데일리 케어", "민감 케어"]},
    })
    evidence = InputEvidenceBundle(
        input_mode="text_only",
        user_text="시카 세럼. 피부 진정, 수분 충전, 산뜻한 흡수, 데일리 케어, 민감 케어 강조.",
        explicit_product_mentions=["시카 세럼"],
        overall_confidence=0.9,
    )
    bundle = _build("product_detail", adapter=adapter, evidence=evidence)
    assert bundle.decision == "approved"
    plan = bundle.product_detail_approved_feature_plan
    # deterministic: keep the first four labels in order.
    assert plan.feature_labels == ["피부 진정", "수분 충전", "산뜻한 흡수", "데일리 케어"]
    assert "feature_labels_truncated" in bundle.reason_codes


def test_product_detail_rejects_duplicate_feature_labels():
    adapter = _RecordingAdapter({
        "decision": "approved",
        "plan": {"feature_labels": ["피부 진정", "피부 진정"]},
    })
    bundle = _build("product_detail", adapter=adapter, evidence=_serum_features_evidence())
    assert bundle.decision == "rejected"
    assert "duplicate_feature_label" in bundle.reason_codes


def test_product_detail_rejects_feature_label_over_16_chars():
    long_label = "피부 진정 수분 충전 산뜻한 흡수 데일리 케어 추가 라벨"  # > 16 chars
    adapter = _RecordingAdapter({
        "decision": "approved",
        "plan": {"feature_labels": ["피부 진정", long_label]},
    })
    bundle = _build("product_detail", adapter=adapter, evidence=_serum_features_evidence())
    assert bundle.decision == "rejected"
    assert "feature_label_too_long" in bundle.reason_codes


# ----- Task 5: editorial vs promotional flyer planning -----

def _editorial_evidence() -> InputEvidenceBundle:
    # Generic informational flyer request with no promotional signals.
    return InputEvidenceBundle(
        input_mode="text_only",
        user_text="동네 도서관 독서 모임 안내 전단지. 함께 읽고 나누는 시간. 매주 토요일 모임. 자유로운 토론.",
        explicit_product_mentions=["독서 모임"],
        overall_confidence=0.9,
    )


def _editorial_payload() -> dict:
    return {
        "decision": "approved",
        "flyer_mode": "editorial",
        "plan": {
            "body_copy": "함께 읽고 나누는 시간",
            "info_cards": ["매주 토요일 모임", "자유로운 토론"],
        },
    }


def test_editorial_request_selects_editorial_flyer_only():
    bundle = _build(
        "flyer",
        adapter=_RecordingAdapter(_editorial_payload()),
        evidence=_editorial_evidence(),
        approved_copy=_approved_copy("독서 모임에 초대합니다", "함께 읽는 즐거움"),
    )
    assert bundle.decision == "approved"
    assert bundle.flyer_approved_copy_plan is not None
    assert bundle.flyer_promotional_approved_copy_plan is None


def test_business_promotion_request_selects_promotional_flyer_only():
    bundle = _build(
        "flyer",
        adapter=_RecordingAdapter(_gym_promo_payload()),
        evidence=_gym_evidence(),
        approved_copy=_approved_copy("프리미엄 헬스장 오픈", None),
    )
    assert bundle.decision == "approved"
    assert bundle.flyer_promotional_approved_copy_plan is not None
    assert bundle.flyer_approved_copy_plan is None


def test_promotional_mode_inferred_when_adapter_omits_flyer_mode():
    payload = _gym_promo_payload()
    payload.pop("flyer_mode")
    bundle = _build(
        "flyer",
        adapter=_RecordingAdapter(payload),
        evidence=_gym_evidence(),
        approved_copy=_approved_copy("프리미엄 헬스장 오픈", None),
    )
    assert bundle.decision == "approved"
    assert bundle.flyer_promotional_approved_copy_plan is not None


def test_ambiguous_flyer_mode_conflict_returns_manual_review():
    # Provider proposes promotional but evidence carries no promotional signal.
    bundle = _build(
        "flyer",
        adapter=_RecordingAdapter(_gym_promo_payload()),
        evidence=_editorial_evidence(),
        approved_copy=_approved_copy("독서 모임에 초대합니다", "함께 읽는 즐거움"),
    )
    assert bundle.decision == "manual_review"
    assert "flyer_mode_conflict" in bundle.reason_codes
    assert _extended_plans(bundle) == []


def test_promotional_flyer_maps_operational_fields_from_evidence():
    bundle = _build(
        "flyer",
        adapter=_RecordingAdapter(_gym_promo_payload()),
        evidence=_gym_evidence(),
        approved_copy=_approved_copy("프리미엄 헬스장 오픈", None),
    )
    plan = bundle.flyer_promotional_approved_copy_plan
    assert plan.promo_badge == "GRAND OPEN"
    assert plan.headline == "프리미엄 헬스장 오픈"
    assert plan.info_items == ["1:1 PT 상담 가능", "유산소·웨이트존 운영", "초보자 맞춤 지도"]
    assert plan.contact_line == "문의 000-0000-0000"
    assert plan.location_line == "OO역 3번 출구 앞"
    assert plan.notice_line == "상담은 예약제로 운영됩니다"
    # 7-10 visible blocks.
    assert 7 <= len(plan.allowed_texts) <= 10


def test_promotional_flyer_omitted_operational_fields_stay_none():
    bundle = _build(
        "flyer",
        adapter=_RecordingAdapter(_gym_promo_payload()),
        evidence=_gym_evidence(),
        approved_copy=_approved_copy("프리미엄 헬스장 오픈", None),
    )
    plan = bundle.flyer_promotional_approved_copy_plan
    # offer_line / subheadline were never supplied -> not invented.
    assert plan.offer_line is None
    assert plan.subheadline is None


def test_promotional_flyer_rejects_invented_operational_text():
    payload = _gym_promo_payload()
    payload["plan"]["contact_line"] = "문의 010-9999-8888"  # not in evidence
    bundle = _build(
        "flyer",
        adapter=_RecordingAdapter(payload),
        evidence=_gym_evidence(),
        approved_copy=_approved_copy("프리미엄 헬스장 오픈", None),
    )
    assert bundle.decision == "rejected"
    assert "invented_operational_text" in bundle.reason_codes
    assert bundle.flyer_promotional_approved_copy_plan is None


def test_promotional_flyer_rejects_invented_info_item():
    payload = _gym_promo_payload()
    payload["plan"]["info_items"] = ["1:1 PT 상담 가능", "유산소·웨이트존 운영", "전문 영양 상담"]
    bundle = _build(
        "flyer",
        adapter=_RecordingAdapter(payload),
        evidence=_gym_evidence(),
        approved_copy=_approved_copy("프리미엄 헬스장 오픈", None),
    )
    assert bundle.decision == "rejected"
    assert "invented_flyer_text" in bundle.reason_codes


def test_promotional_flyer_rejects_too_few_blocks():
    payload = _gym_promo_payload()
    payload["plan"]["info_items"] = ["1:1 PT 상담 가능"]  # only 5 visible blocks total
    bundle = _build(
        "flyer",
        adapter=_RecordingAdapter(payload),
        evidence=_gym_evidence(),
        approved_copy=_approved_copy("프리미엄 헬스장 오픈", None),
    )
    assert bundle.decision == "rejected"
    assert "promotional_flyer_schema_invalid" in bundle.reason_codes


def test_editorial_flyer_allowed_texts_in_display_order():
    bundle = _build(
        "flyer",
        adapter=_RecordingAdapter(_editorial_payload()),
        evidence=_editorial_evidence(),
        approved_copy=_approved_copy("독서 모임에 초대합니다", "함께 읽는 즐거움"),
    )
    plan = bundle.flyer_approved_copy_plan
    assert plan.allowed_texts == [
        "독서 모임에 초대합니다", "함께 읽는 즐거움", "함께 읽고 나누는 시간",
        "매주 토요일 모임", "자유로운 토론",
    ]
    assert 4 <= len(plan.allowed_texts) <= 6


def test_instagram_formats_keep_two_block_brief_without_adapter():
    for ad_format in ("instagram_feed", "instagram_story"):
        bundle = _build(ad_format)
        assert bundle.decision == "not_required"
        assert bundle.flyer_approved_copy_plan is None
        assert bundle.flyer_promotional_approved_copy_plan is None
        assert bundle.product_detail_approved_feature_plan is None
