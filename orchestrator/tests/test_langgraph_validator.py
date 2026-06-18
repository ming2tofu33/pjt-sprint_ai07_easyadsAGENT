import pytest
from pydantic import ValidationError

from orchestrator.app.graph.nodes import validator_node
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.intake_question_policy import resolve_intake_question_policy
from orchestrator.app.schemas.campaign_context import CampaignContext
from orchestrator.app.schemas.input_evidence import EvidenceItem
from orchestrator.app.schemas.intake_question_policy import IntakeQuestionPolicyDecision
from orchestrator.app.schemas.intake_understanding import IntakeUnderstandingResult
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def _validated_state(text: str):
    state = create_initial_marketing_state(InitialMarketingRequest(user_input=text))
    update = validator_node(state)
    state.update(update)
    return state


def _evidence(key: str, value: str, confidence: float = 0.9) -> EvidenceItem:
    return EvidenceItem(
        key=key,
        value=value,
        normalized_value=value,
        source="structured_llm",
        evidence_class="verified_fact",
        confidence=confidence,
        usable_for_copy=True,
    )


def _policy_input(
    *,
    business_candidate: str | None = None,
    advertised_subject: str | None = None,
    advertised_subject_type: str | None = None,
    campaign_intent_candidate: str | None = None,
    ad_format_candidate: str | None = None,
    ambiguity_flags: tuple[str, ...] = (),
    confidence_by_field: dict[str, float] | None = None,
) -> IntakeUnderstandingResult:
    evidence_items: list[EvidenceItem] = []
    if business_candidate:
        evidence_items.append(_evidence("business_candidate", business_candidate))
    if advertised_subject:
        evidence_items.append(_evidence("advertised_subject", advertised_subject))
    if advertised_subject_type:
        evidence_items.append(_evidence("advertised_subject_type", advertised_subject_type))
    if campaign_intent_candidate:
        evidence_items.append(_evidence("campaign_intent_candidate", campaign_intent_candidate))
    if ad_format_candidate:
        evidence_items.append(_evidence("ad_format_candidate", ad_format_candidate))
    return IntakeUnderstandingResult(
        business_candidate=business_candidate,
        advertised_subject=advertised_subject,
        advertised_subject_type=advertised_subject_type,
        campaign_intent_candidate=campaign_intent_candidate,
        ad_format_candidate=ad_format_candidate,
        evidence_items=tuple(evidence_items),
        confidence_by_field=confidence_by_field
        or {
            "business_candidate": 0.9,
            "advertised_subject": 0.9,
            "campaign_intent_candidate": 0.9,
            "ad_format_candidate": 0.9,
        },
        ambiguity_flags=ambiguity_flags,
        extraction_mode="structured_llm",
    )


def test_validator_infers_samgyeopsal_instagram_context():
    state = _validated_state("우리 삼겹살집 인스타 광고")

    assert state["context"]["business_type"] == "restaurant"
    assert state["context"]["item_or_service"] == "삼겹살"
    assert state["context"]["extra"]["ad_format"] == "instagram_feed"
    assert "promotion_goal" in state["missing_fields"]


def test_validator_infers_raw_meat_sale_feed_context():
    state = _validated_state("고기집 원육 세일 피드 스타일로 고기99 음식점 광고를 만들어줘")

    assert state["context"]["business_type"] == "restaurant"
    assert state["context"]["item_or_service"] == "원육"
    assert state["context"]["promotion_goal"] == "discount_event"
    assert state["context"]["extra"]["ad_format"] == "instagram_feed"
    assert "business_type" not in state["missing_fields"]
    assert "item_or_service" not in state["missing_fields"]
    assert "promotion_goal" not in state["missing_fields"]
    assert "ad_format" not in state["missing_fields"]


def test_validator_infers_nail_summer_story_context():
    state = _validated_state("네일샵 여름 이벤트 인스타 스토리 만들어줘")

    assert state["context"]["business_type"] == "beauty_nail"
    assert state["context"]["item_or_service"] == "네일 서비스"
    assert state["context"]["promotion_goal"] == "seasonal_limited"
    assert state["context"]["extra"]["ad_format"] == "instagram_story"
    assert "business_type" not in state["missing_fields"]
    assert "item_or_service" not in state["missing_fields"]
    assert "promotion_goal" not in state["missing_fields"]
    assert "ad_format" not in state["missing_fields"]


def test_validator_creates_missing_fields_when_input_is_sparse():
    state = _validated_state("광고 만들어줘")

    assert {"business_type", "item_or_service", "promotion_goal", "ad_format"}.issubset(state["missing_fields"])
    assert state["validator_output"]["needs_user_selection"] is True


def test_validator_waives_item_question_for_business_level_campaign():
    state = _validated_state("우리 카페 오픈 홍보 배너 만들어줘")

    assert state["current_brief"]["advertised_subject"]
    assert state["current_brief"]["campaign_intent"] == "store_opening"
    assert "item_or_service" not in state["missing_fields"]
    assert "item_or_service" in state["intake_question_policy_decision"]["waived_fields"]


def test_validator_keeps_item_question_for_product_level_campaign_without_subject():
    state = _validated_state("우리 카페 할인 홍보 배너 만들어줘")

    assert "item_or_service" in state["missing_fields"]


def test_validator_marks_ready_for_planning_when_required_fields_exist():
    request = InitialMarketingRequest(
        user_input="삼겹살 할인 인스타 광고",
        copy_generation_mode="auto_pilot",
        context=MarketingContext(
            business_type="restaurant",
            item_or_service="삼겹살",
            promotion_goal="discount_event",
            extra={"ad_format": "instagram_feed"},
        ),
    )
    state = create_initial_marketing_state(request)
    state.update(validator_node(state))

    assert state["missing_fields"] == []
    assert state["current_brief"]["ready_for_planning"] is True


def test_validator_does_not_reask_confirmed_ambiguous_business_type():
    request = InitialMarketingRequest(
        user_input="미용실 헤어 커트 할인 이벤트",
        copy_generation_mode="auto_pilot",
        context=MarketingContext(
            business_type="beauty",
            item_or_service="헤어 스타일링",
            promotion_goal="reservation_cta",
            extra={"ad_format": "instagram_feed"},
        ),
    )
    state = create_initial_marketing_state(request)

    update = validator_node(state)

    assert "business_type" in state["confirmed_context_fields"]
    assert "business_type" not in update["missing_fields"]


def test_confirmed_business_type_resolves_business_ambiguity_without_reasking():
    decision = resolve_intake_question_policy(
        context=MarketingContext(business_type="beauty_salon", extra={"ad_format": "banner"}),
        intake=_policy_input(
            business_candidate="beauty",
            advertised_subject="프리미엄 뷰티샵",
            advertised_subject_type="business",
            campaign_intent_candidate="store_opening",
            ad_format_candidate="banner",
            ambiguity_flags=("beauty_subtype_ambiguous",),
        ),
        campaign=CampaignContext(campaign_intent="store_opening", evidence_refs=("campaign:intent",), confidence=0.9),
        requested_ad_format="banner",
        input_conflicts=(),
        confirmed_fields=("business_type",),
    )

    assert "business_type" not in decision.missing_fields


def test_campaign_ambiguity_does_not_reopen_business_type():
    decision = resolve_intake_question_policy(
        context=MarketingContext(business_type="cafe", extra={"ad_format": "banner"}),
        intake=_policy_input(
            business_candidate="cafe",
            advertised_subject="우리 카페",
            advertised_subject_type="business",
            campaign_intent_candidate="store_opening",
            ad_format_candidate="banner",
            ambiguity_flags=("campaign_intent_ambiguous",),
        ),
        campaign=CampaignContext(campaign_intent="store_opening", evidence_refs=("campaign:intent",), confidence=0.9),
        requested_ad_format="banner",
        input_conflicts=(),
    )

    assert "business_type" not in decision.missing_fields
    assert "promotion_goal" in decision.missing_fields


def test_non_field_ambiguity_does_not_block_business_subject_item_waiver():
    decision = resolve_intake_question_policy(
        context=MarketingContext(business_type="cafe", extra={"ad_format": "banner"}),
        intake=_policy_input(
            business_candidate="cafe",
            advertised_subject="우리 카페",
            advertised_subject_type="business",
            campaign_intent_candidate="store_opening",
            ad_format_candidate="banner",
            ambiguity_flags=("tone_ambiguous",),
        ),
        campaign=CampaignContext(campaign_intent="store_opening", evidence_refs=("campaign:intent",), confidence=0.9),
        requested_ad_format="banner",
        input_conflicts=(),
    )

    assert "item_or_service" in decision.waived_fields
    assert "item_or_service" not in decision.missing_fields


def test_service_subject_satisfies_item_requirement_without_marking_it_waived():
    decision = resolve_intake_question_policy(
        context=MarketingContext(business_type="beauty_salon", extra={"ad_format": "banner"}),
        intake=_policy_input(
            business_candidate="beauty",
            advertised_subject="프리미엄 네일 케어",
            advertised_subject_type="service",
            campaign_intent_candidate="product_promotion",
            ad_format_candidate="banner",
        ),
        campaign=CampaignContext(campaign_intent="product_promotion", evidence_refs=("campaign:intent",), confidence=0.9),
        requested_ad_format="banner",
        input_conflicts=(),
    )

    assert "item_or_service" in decision.satisfied_fields
    assert "item_or_service" not in decision.waived_fields
    assert next(item for item in decision.field_decisions if item.field == "item_or_service").resolution_kind == "satisfied"


def test_product_launch_without_subject_keeps_item_question_open():
    decision = resolve_intake_question_policy(
        context=MarketingContext(business_type="cafe", extra={"ad_format": "banner"}),
        intake=_policy_input(
            business_candidate="cafe",
            advertised_subject="우리 카페",
            advertised_subject_type="business",
            campaign_intent_candidate="new_product_launch",
            ad_format_candidate="banner",
        ),
        campaign=CampaignContext(campaign_intent="new_product_launch", evidence_refs=("campaign:intent",), confidence=0.9),
        requested_ad_format="banner",
        input_conflicts=(),
    )

    assert "item_or_service" in decision.missing_fields


def test_new_menu_launch_without_subject_keeps_item_question_open():
    decision = resolve_intake_question_policy(
        context=MarketingContext(business_type="cafe", extra={"ad_format": "banner"}),
        intake=_policy_input(
            business_candidate="cafe",
            advertised_subject="우리 카페",
            advertised_subject_type="business",
            campaign_intent_candidate="new_menu_launch",
            ad_format_candidate="banner",
        ),
        campaign=CampaignContext(campaign_intent="new_menu_launch", evidence_refs=("campaign:intent",), confidence=0.9),
        requested_ad_format="banner",
        input_conflicts=(),
    )

    assert "item_or_service" in decision.missing_fields


def test_service_launch_without_service_subject_keeps_item_question_open():
    decision = resolve_intake_question_policy(
        context=MarketingContext(business_type="beauty_salon", extra={"ad_format": "banner"}),
        intake=_policy_input(
            business_candidate="beauty",
            advertised_subject="프리미엄 뷰티샵",
            advertised_subject_type="business",
            campaign_intent_candidate="service_launch",
            ad_format_candidate="banner",
        ),
        campaign=CampaignContext(campaign_intent="service_launch", evidence_refs=("campaign:intent",), confidence=0.9),
        requested_ad_format="banner",
        input_conflicts=(),
    )

    assert "item_or_service" in decision.missing_fields


def test_new_product_launch_with_product_subject_satisfies_item_requirement():
    decision = resolve_intake_question_policy(
        context=MarketingContext(business_type="store", extra={"ad_format": "banner"}),
        intake=_policy_input(
            business_candidate="store",
            advertised_subject="세럼",
            advertised_subject_type="product",
            campaign_intent_candidate="new_product_launch",
            ad_format_candidate="banner",
        ),
        campaign=CampaignContext(campaign_intent="new_product_launch", evidence_refs=("campaign:intent",), confidence=0.9),
        requested_ad_format="banner",
        input_conflicts=(),
    )

    assert "item_or_service" in decision.satisfied_fields
    assert "item_or_service" not in decision.missing_fields


def test_policy_schema_rejects_inconsistent_summary_fields():
    with pytest.raises(ValidationError):
        IntakeQuestionPolicyDecision(
            required_fields=("business_type",),
            missing_fields=("business_type",),
            satisfied_fields=("business_type",),
            field_decisions=(
                {
                    "field": "business_type",
                    "required": True,
                    "satisfied": True,
                    "satisfaction_source": "context.business_type",
                    "reason_code": "context_business_type",
                    "resolution_kind": "satisfied",
                },
            ),
            policy_version="v1",
        )
