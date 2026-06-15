"""Format-aware approved-plan builder service.

Turns the format-neutral ApprovedNativeCopyBrief into at most one format-specific
extended plan (flyer editorial, flyer promotional, or product-detail features)
before typography planning. Banner/poster keep the two-block brief only.

The provider proposes candidate fields only. A graph-state adapter may override
it for tests, while production resolves a lazy default provider. Deterministic
validation in this module remains authoritative and fail-closed.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from orchestrator.app.llm.format_approved_plan_provider import (
    get_default_format_approved_plan_provider,
)
from orchestrator.app.llm.native_copy_brief_service import (
    front_load_allowed_texts,
    resolve_approved_primary_copy,
)
from orchestrator.app.schemas.input_evidence import InputEvidenceBundle
from orchestrator.app.schemas.native_creative import (
    ApprovedNativeCopyBrief,
    FlyerApprovedCopyPlan,
    FlyerPromotionalApprovedCopyPlan,
    FormatApprovedPlanBundle,
    ProductDetailApprovedFeaturePlan,
)
from orchestrator.app.schemas.product_understanding import ProductUnderstanding

_NOT_REQUIRED_FORMATS = {"banner", "poster", "instagram_feed", "instagram_story"}
_EXTENDED_FORMATS = {"flyer", "product_detail"}

_PRODUCT_DETAIL_MIN_FEATURES = 2
_PRODUCT_DETAIL_MAX_FEATURES = 4
_FEATURE_LABEL_MAX_CHARS = 16

# Operational / sensitive copy that must never enter a grounded feature label.
# Prices, dates, phone numbers, and the like always carry digits; the keyword
# set covers digit-free CTA / contact / location / discount phrasing.
_OPERATIONAL_KEYWORDS = (
    "지금", "클릭", "구매", "주문", "신청", "예약", "방문", "바로", "오픈", "문의", "연락", "전화",
    "할인", "세일", "무료", "이벤트", "쿠폰", "증정", "원", "₩", "%",
    "buy", "order", "click", "call", "now", "sale", "off", "free",
    "역", "출구", "번지", "번길", "층", "동 ", "구 ", "시 ",
)


def _normalize_for_grounding(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def _grounding_corpus(input_evidence, product_understanding) -> str:
    parts: list[str] = []

    def _add(value: Any) -> None:
        if value:
            parts.append(str(value))

    def _add_items(items) -> None:
        for item in items or []:
            _add(getattr(item, "value", None))
            _add(getattr(item, "normalized_value", None))
            _add(getattr(item, "key", None))

    _add(input_evidence.user_text)
    _add(input_evidence.user_request_utterance)
    _add(input_evidence.campaign_intent)
    for value in input_evidence.explicit_product_mentions:
        _add(value)
    for value in input_evidence.desired_positioning:
        _add(value)
    _add_items(input_evidence.explicit_user_facts)
    _add_items(input_evidence.visual_observations)

    _add(product_understanding.product_name)
    _add(product_understanding.product_variant)
    _add(product_understanding.normalized_product_type)
    for value in product_understanding.campaign_modifiers:
        _add(value)
    for value in product_understanding.use_contexts:
        _add(value)
    for value in product_understanding.desired_positioning:
        _add(value)
    for value in product_understanding.category_path:
        _add(value)
    _add_items(product_understanding.verified_facts)
    _add_items(product_understanding.visual_observations)
    _add_items(product_understanding.permissible_inferences)

    return _normalize_for_grounding(" ".join(parts))


def _grounding_corpus_text(input_evidence) -> str:
    """Normalized grounding corpus from user evidence only (no product model)."""
    parts: list[str] = []

    def _add(value: Any) -> None:
        if value:
            parts.append(str(value))

    _add(input_evidence.user_text)
    _add(input_evidence.user_request_utterance)
    _add(input_evidence.campaign_intent)
    _add(input_evidence.promotion_goal)
    _add(input_evidence.placement)
    for value in input_evidence.explicit_product_mentions:
        _add(value)
    for value in input_evidence.desired_positioning:
        _add(value)
    for value in input_evidence.user_exact_display_copy:
        _add(value)
    for item in input_evidence.explicit_user_facts:
        _add(getattr(item, "value", None))
        _add(getattr(item, "normalized_value", None))
        _add(getattr(item, "key", None))
    for item in input_evidence.visual_observations:
        _add(getattr(item, "value", None))
    return _normalize_for_grounding(" ".join(parts))


def _label_is_operational(label: str) -> bool:
    if re.search(r"\d", label):
        return True
    lowered = label.lower()
    return any(keyword.strip() and keyword.lower() in lowered for keyword in _OPERATIONAL_KEYWORDS)


def validate_product_detail_feature_labels(
    raw_labels: list[Any],
    *,
    input_evidence,
    product_understanding,
) -> tuple[str, list[str], list[str]]:
    """Deterministically validate and ground product-detail feature labels.

    Returns (decision, labels, reason_codes). The provider may only propose
    labels; grounding, sensitivity, length, uniqueness, and count rules are
    enforced here. No silent fallback to generic labels.
    """
    labels = [str(label).strip() for label in (raw_labels or []) if str(label).strip()]
    reason_codes: list[str] = []

    # Hard rejects: operational text, over-length, duplicates.
    if any(_label_is_operational(label) for label in labels):
        return "rejected", [], ["feature_label_contains_operational_text"]
    if any(len(label) > _FEATURE_LABEL_MAX_CHARS for label in labels):
        return "rejected", [], ["feature_label_too_long"]
    if len(labels) != len(dict.fromkeys(labels)):
        return "rejected", [], ["duplicate_feature_label"]

    # Grounding: every label must trace to user input or verified evidence.
    corpus = _grounding_corpus(input_evidence, product_understanding)
    ungrounded = [label for label in labels if _normalize_for_grounding(label) not in corpus]
    if ungrounded:
        return "rejected", [], ["feature_label_not_grounded"]

    if len(labels) < _PRODUCT_DETAIL_MIN_FEATURES:
        return "manual_review", [], ["insufficient_grounded_features"]

    if len(labels) > _PRODUCT_DETAIL_MAX_FEATURES:
        labels = labels[:_PRODUCT_DETAIL_MAX_FEATURES]
        reason_codes.append("feature_labels_truncated")

    return "approved", labels, reason_codes


def build_format_approved_plan_bundle(
    *,
    ad_format: str,
    input_evidence: InputEvidenceBundle,
    product_understanding: ProductUnderstanding,
    approved_copy: ApprovedNativeCopyBrief,
    state: dict[str, Any],
) -> FormatApprovedPlanBundle:
    fmt = (ad_format or "").strip()
    if fmt in _NOT_REQUIRED_FORMATS:
        return FormatApprovedPlanBundle(decision="not_required", reason_codes=[f"{fmt}_two_block_brief_only"])
    if fmt not in _EXTENDED_FORMATS:
        return FormatApprovedPlanBundle(decision="manual_review", reason_codes=["unsupported_ad_format"])

    try:
        adapter = state.get("format_approved_plan_adapter") or get_default_format_approved_plan_provider()
        payload = adapter.generate_format_approved_plan(
            ad_format=fmt,
            input_evidence=input_evidence,
            product_understanding=product_understanding,
            approved_copy=approved_copy,
            state=state,
        )
    except Exception as exc:  # provider construction/call failure -> fail closed
        return FormatApprovedPlanBundle(decision="rejected", reason_codes=["provider_error"], provider_metadata={"error": str(exc)})

    if not isinstance(payload, dict):
        return FormatApprovedPlanBundle(decision="rejected", reason_codes=["provider_payload_invalid"])
    plan_payload = payload.get("plan") or {}
    reason_payload = payload.get("reason_codes") or []
    metadata_payload = payload.get("provider_metadata") or {}
    if not isinstance(plan_payload, dict) or not isinstance(reason_payload, list) or not isinstance(metadata_payload, dict):
        return FormatApprovedPlanBundle(decision="rejected", reason_codes=["provider_payload_schema_invalid"])
    if fmt == "product_detail" and not isinstance(plan_payload.get("feature_labels") or [], list):
        return FormatApprovedPlanBundle(decision="rejected", reason_codes=["provider_payload_schema_invalid"])

    decision = str(payload.get("decision") or "approved")
    if decision not in {"approved", "manual_review", "rejected"}:
        return FormatApprovedPlanBundle(decision="rejected", reason_codes=["provider_decision_invalid"])
    reason_codes = list(reason_payload)
    provider_metadata = dict(metadata_payload)
    if decision in {"manual_review", "rejected"}:
        return FormatApprovedPlanBundle(decision=decision, reason_codes=reason_codes, provider_metadata=provider_metadata)

    headline, supporting, _mode = resolve_approved_primary_copy(state=state, approved_copy=approved_copy)
    plan_fields = dict(plan_payload)

    if fmt == "product_detail":
        return _build_product_detail_bundle(plan_fields, headline, supporting, input_evidence, product_understanding, reason_codes, provider_metadata)
    return _build_flyer_bundle(payload.get("flyer_mode"), plan_fields, headline, supporting, input_evidence, reason_codes, provider_metadata)


def _build_product_detail_bundle(
    plan_fields: dict[str, Any],
    headline: str | None,
    supporting: str | None,
    input_evidence,
    product_understanding,
    reason_codes: list[str],
    provider_metadata: dict[str, Any],
) -> FormatApprovedPlanBundle:
    if not headline or not supporting:
        return FormatApprovedPlanBundle(decision="rejected", reason_codes=[*reason_codes, "missing_primary_copy"], provider_metadata=provider_metadata)

    decision, feature_labels, feature_reason_codes = validate_product_detail_feature_labels(
        plan_fields.get("feature_labels") or [],
        input_evidence=input_evidence,
        product_understanding=product_understanding,
    )
    if decision != "approved":
        return FormatApprovedPlanBundle(decision=decision, reason_codes=[*reason_codes, *feature_reason_codes], provider_metadata=provider_metadata)
    reason_codes = [*reason_codes, *feature_reason_codes]

    allowed_texts = front_load_allowed_texts([headline, supporting], feature_labels)
    try:
        plan = ProductDetailApprovedFeaturePlan(
            headline=headline,
            supporting_copy=supporting,
            feature_labels=feature_labels,
            allowed_texts=allowed_texts,
        )
    except ValidationError as exc:
        return FormatApprovedPlanBundle(decision="rejected", reason_codes=[*reason_codes, "product_detail_schema_invalid"], provider_metadata={**provider_metadata, "validation_error": exc.errors()})
    return FormatApprovedPlanBundle(product_detail_approved_feature_plan=plan, decision="approved", reason_codes=reason_codes, provider_metadata=provider_metadata)


# Structured/explicit promotional intent signals: offers, recruitment, benefits,
# contact, location, operation notice, opening, sale. A generic informational
# request carrying none of these stays editorial.
_PROMOTIONAL_SIGNAL_KEYWORDS = (
    "오픈", "그랜드", "open", "할인", "세일", "특가", "프로모션", "promotion",
    "이벤트", "쿠폰", "증정", "사은품", "혜택", "모집", "채용", "구인",
    "문의", "연락", "전화", "예약", "상담", "오시는", "찾아오", "위치", "주소",
    "영업", "운영", "오픈일", "멤버십", "등록", "신청", "할인율", "%",
)

# Operational fields that may enter a promotional plan only with exact evidence.
_PROMOTIONAL_OPERATIONAL_FIELDS = ("promo_badge", "offer_line", "contact_line", "location_line", "notice_line")


def classify_flyer_mode(input_evidence) -> str:
    corpus = _flyer_signal_corpus(input_evidence)
    return "promotional" if any(keyword in corpus for keyword in _PROMOTIONAL_SIGNAL_KEYWORDS) else "editorial"


def _flyer_signal_corpus(input_evidence) -> str:
    parts: list[str] = []

    def _add(value: Any) -> None:
        if value:
            parts.append(str(value))

    _add(input_evidence.user_text)
    _add(input_evidence.user_request_utterance)
    _add(input_evidence.campaign_intent)
    _add(input_evidence.promotion_goal)
    _add(input_evidence.user_intent)
    for value in input_evidence.desired_positioning:
        _add(value)
    for value in input_evidence.explicit_product_mentions:
        _add(value)
    for item in input_evidence.explicit_user_facts:
        _add(getattr(item, "value", None))
        _add(getattr(item, "key", None))
    return " ".join(parts).lower()


def _build_flyer_bundle(
    flyer_mode: Any,
    plan_fields: dict[str, Any],
    headline: str | None,
    supporting: str | None,
    input_evidence,
    reason_codes: list[str],
    provider_metadata: dict[str, Any],
) -> FormatApprovedPlanBundle:
    if not headline:
        return FormatApprovedPlanBundle(decision="rejected", reason_codes=[*reason_codes, "missing_primary_copy"], provider_metadata=provider_metadata)

    # Mode is decided from user evidence, never invented. A provider proposal that
    # conflicts with the evidence-derived mode is ambiguous -> manual_review, so we
    # never emit an arbitrary promotional plan.
    evidence_mode = classify_flyer_mode(input_evidence)
    proposed = str(flyer_mode or "").strip()
    if proposed and proposed in {"editorial", "promotional"} and proposed != evidence_mode:
        return FormatApprovedPlanBundle(decision="manual_review", reason_codes=[*reason_codes, "flyer_mode_conflict"], provider_metadata=provider_metadata)
    mode = evidence_mode

    if mode == "editorial":
        return _build_editorial_flyer(plan_fields, headline, supporting, input_evidence, reason_codes, provider_metadata)
    return _build_promotional_flyer(plan_fields, headline, supporting, input_evidence, reason_codes, provider_metadata)


def _build_editorial_flyer(
    plan_fields: dict[str, Any],
    headline: str,
    supporting: str | None,
    input_evidence,
    reason_codes: list[str],
    provider_metadata: dict[str, Any],
) -> FormatApprovedPlanBundle:
    subtitle = supporting if supporting is not None else plan_fields.get("subtitle")
    body_copy = plan_fields.get("body_copy")
    info_cards = [c for c in (plan_fields.get("info_cards") or []) if c]
    bottom_notice = plan_fields.get("bottom_notice")
    proposed_values = [body_copy, *info_cards, bottom_notice]
    if supporting is None:
        proposed_values.insert(0, subtitle)
    if _has_ungrounded_flyer_values(proposed_values, input_evidence):
        return FormatApprovedPlanBundle(decision="rejected", reason_codes=[*reason_codes, "invented_flyer_text"], provider_metadata=provider_metadata)

    # Visible structured fields in display order.
    allowed_texts = _ordered_unique([headline, subtitle, body_copy, *info_cards, bottom_notice])
    try:
        plan = FlyerApprovedCopyPlan(
            headline=headline,
            subtitle=subtitle,
            body_copy=body_copy,
            info_cards=info_cards,
            bottom_notice=bottom_notice,
            allowed_texts=allowed_texts,
        )
    except ValidationError as exc:
        return FormatApprovedPlanBundle(decision="rejected", reason_codes=[*reason_codes, "editorial_flyer_schema_invalid"], provider_metadata={**provider_metadata, "validation_error": exc.errors()})
    return FormatApprovedPlanBundle(flyer_approved_copy_plan=plan, decision="approved", reason_codes=reason_codes, provider_metadata=provider_metadata)


def _build_promotional_flyer(
    plan_fields: dict[str, Any],
    headline: str,
    supporting: str | None,
    input_evidence,
    reason_codes: list[str],
    provider_metadata: dict[str, Any],
) -> FormatApprovedPlanBundle:
    corpus = _grounding_corpus_text(input_evidence)

    # Operational fields require exact evidence. Omitted fields stay absent;
    # an invented (ungrounded) operational value fails closed.
    operational_values: dict[str, str] = {}
    for field in _PROMOTIONAL_OPERATIONAL_FIELDS:
        value = plan_fields.get(field)
        if value is None or str(value).strip() == "":
            continue
        if _normalize_for_grounding(value) not in corpus:
            return FormatApprovedPlanBundle(decision="rejected", reason_codes=[*reason_codes, "invented_operational_text"], provider_metadata=provider_metadata)
        operational_values[field] = str(value)

    subheadline = supporting if supporting is not None else plan_fields.get("subheadline")
    info_items = [i for i in (plan_fields.get("info_items") or []) if i]
    proposed_values = list(info_items)
    if supporting is None:
        proposed_values.insert(0, subheadline)
    if _has_ungrounded_flyer_values(proposed_values, input_evidence):
        return FormatApprovedPlanBundle(decision="rejected", reason_codes=[*reason_codes, "invented_flyer_text"], provider_metadata=provider_metadata)

    promo_badge = operational_values.get("promo_badge")
    offer_line = operational_values.get("offer_line")
    contact_line = operational_values.get("contact_line")
    location_line = operational_values.get("location_line")
    notice_line = operational_values.get("notice_line")

    # Visible structured fields in display order.
    allowed_texts = _ordered_unique([
        promo_badge, headline, subheadline, offer_line, *info_items, contact_line, location_line, notice_line,
    ])
    approved_operational_texts = _ordered_unique([promo_badge, offer_line, contact_line, location_line, notice_line])

    try:
        plan = FlyerPromotionalApprovedCopyPlan(
            promo_badge=promo_badge,
            headline=headline,
            subheadline=subheadline,
            offer_line=offer_line,
            info_items=info_items,
            contact_line=contact_line,
            location_line=location_line,
            notice_line=notice_line,
            allowed_texts=allowed_texts,
            approved_operational_texts=approved_operational_texts,
        )
    except ValidationError as exc:
        return FormatApprovedPlanBundle(decision="rejected", reason_codes=[*reason_codes, "promotional_flyer_schema_invalid"], provider_metadata={**provider_metadata, "validation_error": exc.errors()})
    return FormatApprovedPlanBundle(flyer_promotional_approved_copy_plan=plan, decision="approved", reason_codes=reason_codes, provider_metadata=provider_metadata)


def _has_ungrounded_flyer_values(values: list[Any], input_evidence) -> bool:
    corpus = _grounding_corpus_text(input_evidence)
    return any(
        _normalize_for_grounding(value) not in corpus
        for value in values
        if value is not None and str(value).strip()
    )


def _ordered_unique(values: list[Any]) -> list[str]:
    ordered: list[str] = []
    for value in values:
        text = str(value).strip() if value is not None else ""
        if text and text not in ordered:
            ordered.append(text)
    return ordered
