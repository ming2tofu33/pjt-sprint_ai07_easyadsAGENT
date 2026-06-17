from pathlib import Path

from orchestrator.app.llm.campaign_semantics import (
    campaign_intent_label,
    campaign_intent_subject_requirement,
    campaign_roles_for_intent,
    normalize_campaign_intent,
    project_legacy_promotion_goal,
)


def test_normalize_campaign_intent_requires_business_subject_for_store_opening():
    assert normalize_campaign_intent("store_opening", advertised_subject_type="business") == "store_opening"
    assert normalize_campaign_intent("store_opening", advertised_subject_type="product") is None
    assert normalize_campaign_intent("grand_opening", advertised_subject_type="business") == "store_opening"


def test_normalize_campaign_intent_separates_launch_by_subject_type():
    assert normalize_campaign_intent("new_product", advertised_subject_type="product", campaign_status="new_product") == "new_product_launch"
    assert normalize_campaign_intent("new_product", advertised_subject_type="service", campaign_status="new_product") == "service_launch"
    assert normalize_campaign_intent("new_menu", advertised_subject_type="product", campaign_status="new_menu") == "new_menu_launch"


def test_launch_intents_do_not_collapse_into_legacy_new_launch():
    assert project_legacy_promotion_goal("new_product_launch") is None
    assert project_legacy_promotion_goal("new_menu_launch") is None
    assert project_legacy_promotion_goal("service_launch") is None


def test_campaign_semantics_helpers_expose_labels_requirements_and_roles():
    assert campaign_intent_label("service_launch") == "신규 서비스 시작"
    assert campaign_intent_subject_requirement("new_menu_launch") == "menu_or_product"
    assert campaign_roles_for_intent("store_opening") == frozenset({"announcement"})


def test_frontend_context_presentation_covers_required_canonical_intents():
    source = Path("apps/web/lib/context-presentation.ts").read_text(encoding="utf-8")

    for token in ("store_opening", "new_product_launch", "new_menu_launch", "service_launch"):
        assert f"{token}:" in source
