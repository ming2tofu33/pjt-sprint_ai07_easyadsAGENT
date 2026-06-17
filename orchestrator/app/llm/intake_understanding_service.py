"""Open-domain intake understanding service."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Callable

from orchestrator.app.llm.campaign_semantics import normalize_campaign_intent, project_legacy_promotion_goal
from orchestrator.app.llm.domain_routing import find_business_alias_span, normalize_business_type
from orchestrator.app.llm.native_campaign_copy_rules import detect_campaign_status, strip_generic_request_language
from orchestrator.app.schemas.brief_llm import BriefInterpreterOutput
from orchestrator.app.schemas.input_evidence import EvidenceItem
from orchestrator.app.schemas.intake_understanding import IntakeUnderstandingResult

BusinessInterpreter = Callable[[dict[str, Any], str], tuple[BriefInterpreterOutput | None, dict[str, Any]]]
BriefProjector = Callable[[BriefInterpreterOutput, str], tuple[dict[str, Any], list[str]]]

_PHONE_RE = re.compile(r"01\d[-\s]?\d{3,4}[-\s]?\d{4}")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PRICE_RE = re.compile(r"\d[\d,]*\s*(?:원|만원|%|퍼센트)")
_TIME_TOKEN_RE = re.compile(r"(평일\s*저녁|평일|저녁|주말|점심)")
_LOCATION_TOKEN_RE = re.compile(r"([가-힣A-Za-z0-9]+(?:구|동|역|시|군))")
_FORMAT_TOKEN_RE = re.compile(r"(포스터|배너|전단지|인스타\s*스토리|인스타\s*피드|상세\s*페이지)", re.IGNORECASE)
_OPENING_PATTERNS = (r"오픈", r"개업", r"새로\s+문", r"opening", r"grand\s+open")
_RECRUIT_PATTERNS = (r"모집", r"수강생", r"채용", r"등록")
_PRODUCT_SERVICE_SUFFIX_RE = re.compile(
    r"(회화반|수업|강의|레슨|클래스|상담|서비스|라떼|메뉴|음료|제품|상품|케이크)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class StructuredIntakeOutput:
    business_candidate_phrase: str | None = None
    venue_candidate_phrase: str | None = None
    advertised_subject: str | None = None
    advertised_subject_type: str | None = None
    product_or_service_phrase: str | None = None
    campaign_intent_phrase: str | None = None
    tone_phrases: tuple[str, ...] = ()
    target_phrases: tuple[str, ...] = ()


def understand_intake(
    state: dict[str, Any],
    text: str,
    *,
    deterministic_hints: dict[str, str | None],
    brief_interpreter: BusinessInterpreter | None = None,
    brief_projector: BriefProjector | None = None,
) -> tuple[IntakeUnderstandingResult, dict[str, Any]]:
    deterministic = build_deterministic_intake_understanding(state, text, hints=deterministic_hints)
    trace: dict[str, Any] = {
        "mode": deterministic.extraction_mode,
        "fallback_used": deterministic.fallback_used,
        "fallback_reason": deterministic.fallback_reason,
        "field_sources": _field_sources_for(deterministic),
        "candidate_counts": _candidate_counts_for(deterministic),
        "source_text_hash": _source_text_hash(text),
        "brief_interpreter": {
            "used": False,
            "llm_metadata": {"llm_attempted": False},
            "warnings": [],
            "projected_context_updates": {},
        },
    }

    if not _should_attempt_structured_intake(deterministic) or brief_interpreter is None or brief_projector is None:
        return deterministic, trace

    llm_output, llm_metadata = brief_interpreter(state, text)
    warnings: list[str] = []
    suggested_copy_mode: str | None = None
    projected_context_updates: dict[str, Any] = {}
    merged = deterministic
    if llm_output is None:
        merged = deterministic.model_copy(
            update={
                "fallback_used": bool(llm_metadata.get("fallback_used") or llm_metadata.get("fallback_reason")),
                "fallback_reason": llm_metadata.get("fallback_reason"),
            }
        )
    else:
        llm_updates, warnings = brief_projector(llm_output, source_text=text)
        suggested_copy_mode = llm_updates.pop("copy_generation_mode", None)
        projected_context_updates = dict(llm_updates)
        structured = _brief_output_to_structured_intake(llm_output, llm_updates, text)
        merged = _merge_structured_intake(deterministic, structured, text, llm_output.confidence)

    trace["mode"] = merged.extraction_mode
    trace["fallback_used"] = merged.fallback_used
    trace["fallback_reason"] = merged.fallback_reason
    trace["field_sources"] = _field_sources_for(merged)
    trace["candidate_counts"] = _candidate_counts_for(merged)
    trace["copy_generation_mode_candidate"] = suggested_copy_mode
    trace["brief_interpreter"] = {
        "used": llm_output is not None,
        "llm_metadata": llm_metadata,
        "warnings": warnings,
        "projected_context_updates": projected_context_updates,
    }
    return merged, trace


def build_deterministic_intake_understanding(
    state: dict[str, Any],
    text: str,
    *,
    hints: dict[str, str | None],
) -> IntakeUnderstandingResult:
    bundle = state.get("input_evidence_bundle") or {}
    user_text = str(bundle.get("user_text") or text or "").strip()
    confirmed_context = ((state.get("context") or {}) if isinstance(state.get("context"), dict) else {}) or {}
    business_phrase, routed_business_alias = find_business_alias_span(user_text)
    business_candidate = _first_non_empty(
        confirmed_context.get("business_type"),
        routed_business_alias,
        hints.get("business_type"),
    )
    product_candidate = _first_non_empty(
        confirmed_context.get("item_or_service"),
        _first_explicit_product_mention(bundle),
        hints.get("item_or_service"),
    )
    advertised_subject, advertised_subject_type = _advertised_subject(
        user_text,
        product_candidate,
        business_phrase=business_phrase,
    )
    campaign_candidate = _campaign_intent_candidate(
        user_text,
        confirmed_context.get("promotion_goal") or hints.get("promotion_goal"),
        advertised_subject_type=advertised_subject_type,
    )
    ad_format_candidate = _explicit_format_candidate(
        user_text,
        confirmed_context.get("extra", {}).get("ad_format") if isinstance(confirmed_context.get("extra"), dict) else None,
        hints.get("ad_format"),
    )
    time_context = _time_context(user_text)
    location_context = _location_context(user_text)
    contact_context = _contact_context(user_text)
    price_context = _price_context(user_text)
    ambiguity_flags = _ambiguity_flags(business_candidate, user_text)

    evidence_items: list[EvidenceItem] = []
    confidence_by_field: dict[str, float] = {}

    def add_scalar(field: str, value: str | None, *, confidence: float, exact_span: str | None = None) -> None:
        if not value:
            return
        item = _evidence_item(field, value, user_text=user_text, source="deterministic_parser", confidence=confidence, exact_span=exact_span)
        evidence_items.append(item)
        confidence_by_field[field] = confidence

    def add_many(field: str, values: tuple[str, ...], *, confidence: float) -> None:
        if not values:
            return
        span = next((value for value in values if value in user_text), user_text or ", ".join(values))
        evidence_items.append(
            _evidence_item(field, ", ".join(values), user_text=user_text, source="deterministic_parser", confidence=confidence, exact_span=span)
        )
        confidence_by_field[field] = confidence

    add_scalar("business_candidate", business_candidate, confidence=0.75, exact_span=_span_if_present(user_text, business_candidate))
    add_scalar("venue_type_candidate", business_phrase or (advertised_subject if advertised_subject_type == "business" else None), confidence=0.7, exact_span=_span_if_present(user_text, business_phrase or advertised_subject))
    add_scalar("advertised_subject", advertised_subject, confidence=0.72, exact_span=_span_if_present(user_text, advertised_subject))
    add_scalar("advertised_subject_type", advertised_subject_type, confidence=0.7, exact_span=_span_if_present(user_text, advertised_subject))
    add_scalar("product_or_service_candidate", product_candidate, confidence=0.78, exact_span=_span_if_present(user_text, product_candidate))
    add_scalar("campaign_intent_candidate", campaign_candidate, confidence=0.8, exact_span=_campaign_span(user_text, campaign_candidate))
    add_scalar("ad_format_candidate", ad_format_candidate, confidence=0.9, exact_span=_format_span(user_text, ad_format_candidate))
    add_many("time_context", time_context, confidence=0.84)
    add_many("location_context", location_context, confidence=0.84)
    add_many("contact_context", contact_context, confidence=0.99)
    add_many("price_context", price_context, confidence=0.99)

    return IntakeUnderstandingResult(
        business_candidate=business_candidate,
        venue_type_candidate=business_phrase or (advertised_subject if advertised_subject_type == "business" else None),
        advertised_subject=advertised_subject,
        advertised_subject_type=advertised_subject_type,
        product_or_service_candidate=product_candidate,
        campaign_intent_candidate=campaign_candidate,
        ad_format_candidate=ad_format_candidate,
        tone_candidates=(),
        mood_candidates=(),
        target_candidates=(),
        time_context=time_context,
        location_context=location_context,
        contact_context=contact_context,
        price_context=price_context,
        evidence_items=tuple(evidence_items),
        confidence_by_field=confidence_by_field,
        ambiguity_flags=tuple(ambiguity_flags),
        extraction_mode="deterministic_only",
        fallback_used=False,
    )


def project_intake_to_context(result: IntakeUnderstandingResult) -> tuple[dict[str, Any], dict[str, Any]]:
    updates: dict[str, Any] = {}
    metadata: dict[str, Any] = {
        "ambiguity_flags": list(result.ambiguity_flags),
        "confidence_by_field": dict(result.confidence_by_field),
        "evidence_refs": [item.source_ref or item.evidence_id for item in result.evidence_items],
    }

    normalized = normalize_business_type(result.business_candidate)
    metadata["domain_routing_result"] = normalized.model_dump()
    if normalized.business_type and _should_project_business_type(result):
        updates["business_type"] = normalized.business_type
    elif _should_project_business_type(result) and normalized.canonical_domain.value in {"food_and_beverage", "beauty", "retail"}:
        updates["business_type"] = normalized.canonical_domain.value
    projected_item, rejection_reason = _project_item_candidate(
        result.product_or_service_candidate,
        source_text=_source_text_proxy(result),
    )
    if rejection_reason:
        metadata["rejected_item_candidate"] = _normalize_phrase(result.product_or_service_candidate)
        metadata["rejection_reason"] = rejection_reason
    if projected_item and result.advertised_subject_type in {"product", "service"}:
        updates["item_or_service"] = projected_item
    promotion_goal = _promotion_goal_from_candidate(result.campaign_intent_candidate)
    if promotion_goal:
        updates["promotion_goal"] = promotion_goal
    elif result.campaign_intent_candidate:
        metadata["unprojected_campaign_intent_candidate"] = result.campaign_intent_candidate
    if result.target_candidates:
        updates["target_persona"] = result.target_candidates[0]
    if result.time_context:
        updates["time_context"] = result.time_context[0]
    if result.tone_candidates:
        updates["brand_tone"] = result.tone_candidates[0]
    elif result.mood_candidates:
        updates["brand_tone"] = result.mood_candidates[0]
    if result.ad_format_candidate:
        updates["ad_format"] = result.ad_format_candidate
    return updates, metadata


def _should_attempt_structured_intake(result: IntakeUnderstandingResult) -> bool:
    if not result.advertised_subject:
        return True
    if not result.business_candidate:
        return True
    if not result.campaign_intent_candidate:
        return True
    if result.advertised_subject_type == "business" and result.product_or_service_candidate is None:
        return True
    if "beauty_subtype_ambiguous" in result.ambiguity_flags:
        return True
    return False


def _brief_output_to_structured_intake(
    llm_output: BriefInterpreterOutput,
    llm_updates: dict[str, Any],
    source_text: str,
) -> StructuredIntakeOutput:
    exact_business_phrase, _ = find_business_alias_span(source_text)
    business_phrase = exact_business_phrase or _normalize_phrase(llm_output.business_type) or _business_subject_phrase(source_text)
    product_phrase = _normalize_phrase(llm_updates.get("item_or_service") or llm_output.item_or_service)
    advertised_subject = product_phrase or _business_subject_phrase(source_text)
    if product_phrase:
        advertised_subject_type = "service" if _looks_like_service_phrase(product_phrase) else "product"
    else:
        advertised_subject_type = "business" if advertised_subject else None
    tone_phrases = tuple(
        value
        for value in (
            _normalize_phrase(llm_updates.get("brand_tone")),
            _normalize_phrase(llm_output.tone),
        )
        if value
    )
    target_phrases = tuple(value for value in (_normalize_phrase(llm_output.target_persona),) if value)
    return StructuredIntakeOutput(
        business_candidate_phrase=business_phrase,
        venue_candidate_phrase=exact_business_phrase or _normalize_phrase(_business_subject_phrase(source_text)),
        advertised_subject=advertised_subject,
        advertised_subject_type=advertised_subject_type,
        product_or_service_phrase=product_phrase,
        campaign_intent_phrase=_normalize_phrase(llm_updates.get("promotion_goal") or llm_output.promotion_goal),
        tone_phrases=tone_phrases,
        target_phrases=target_phrases,
    )


def _merge_structured_intake(
    deterministic: IntakeUnderstandingResult,
    structured: StructuredIntakeOutput,
    source_text: str,
    llm_confidence: float,
) -> IntakeUnderstandingResult:
    business_candidate = structured.business_candidate_phrase or deterministic.business_candidate
    product_candidate, _ = _project_item_candidate(
        structured.product_or_service_phrase or deterministic.product_or_service_candidate,
        source_text=source_text,
    )
    advertised_subject = structured.advertised_subject or deterministic.advertised_subject
    advertised_subject_type = structured.advertised_subject_type or deterministic.advertised_subject_type
    if product_candidate is None and advertised_subject_type in {"product", "service"}:
        advertised_subject = structured.business_candidate_phrase or structured.venue_candidate_phrase or deterministic.advertised_subject
        advertised_subject_type = "business" if advertised_subject else None
    campaign_candidate = normalize_campaign_intent(
        structured.campaign_intent_phrase or deterministic.campaign_intent_candidate,
        advertised_subject_type=advertised_subject_type,
    )
    tone_candidates = tuple(dict.fromkeys([*deterministic.tone_candidates, *structured.tone_phrases]))
    target_candidates = tuple(dict.fromkeys([*deterministic.target_candidates, *structured.target_phrases]))
    evidence_items = list(deterministic.evidence_items)

    def add_if_present(key: str, value: str | None) -> None:
        if not value:
            return
        evidence_items.append(
            _evidence_item(
                key,
                value,
                user_text=source_text,
                source="structured_llm",
                confidence=max(0.65, llm_confidence),
                exact_span=_span_if_present(source_text, value),
            )
        )

    add_if_present("business_candidate", business_candidate)
    add_if_present("advertised_subject", advertised_subject)
    add_if_present("advertised_subject_type", advertised_subject_type)
    add_if_present("product_or_service_candidate", product_candidate)
    add_if_present("campaign_intent_candidate", campaign_candidate)
    if deterministic.ad_format_candidate:
        add_if_present("ad_format_candidate", deterministic.ad_format_candidate)
    if tone_candidates:
        add_if_present("tone_candidates", tone_candidates[0])
    if target_candidates:
        add_if_present("target_candidates", target_candidates[0])

    confidence_map = dict(deterministic.confidence_by_field)
    if product_candidate:
        confidence_map["product_or_service_candidate"] = llm_confidence
    if business_candidate:
        confidence_map["business_candidate"] = llm_confidence
    if campaign_candidate:
        confidence_map["campaign_intent_candidate"] = llm_confidence
    if tone_candidates:
        confidence_map["tone_candidates"] = llm_confidence
    if target_candidates:
        confidence_map["target_candidates"] = llm_confidence

    ambiguity_flags = tuple(dict.fromkeys([*deterministic.ambiguity_flags, *_ambiguity_flags(business_candidate, source_text)]))
    return IntakeUnderstandingResult(
        business_candidate=business_candidate,
        venue_type_candidate=structured.venue_candidate_phrase or deterministic.venue_type_candidate,
        advertised_subject=advertised_subject,
        advertised_subject_type=advertised_subject_type,
        product_or_service_candidate=product_candidate,
        campaign_intent_candidate=campaign_candidate,
        ad_format_candidate=deterministic.ad_format_candidate,
        tone_candidates=tone_candidates,
        mood_candidates=deterministic.mood_candidates,
        target_candidates=target_candidates,
        time_context=deterministic.time_context,
        location_context=deterministic.location_context,
        contact_context=deterministic.contact_context,
        price_context=deterministic.price_context,
        evidence_items=tuple(evidence_items),
        confidence_by_field=confidence_map,
        ambiguity_flags=ambiguity_flags,
        input_conflicts=deterministic.input_conflicts,
        extraction_mode="hybrid_structured_llm",
        fallback_used=False,
    )


def _field_sources_for(result: IntakeUnderstandingResult) -> dict[str, str]:
    fields: dict[str, str] = {}
    for item in result.evidence_items:
        if item.key not in fields:
            fields[item.key] = item.source
    return fields


def _candidate_counts_for(result: IntakeUnderstandingResult) -> dict[str, int]:
    return {
        "tone_candidates": len(result.tone_candidates),
        "mood_candidates": len(result.mood_candidates),
        "target_candidates": len(result.target_candidates),
        "time_context": len(result.time_context),
        "location_context": len(result.location_context),
        "contact_context": len(result.contact_context),
        "price_context": len(result.price_context),
    }


def _first_explicit_product_mention(bundle: dict[str, Any]) -> str | None:
    mentions = bundle.get("explicit_product_mentions") or []
    if not mentions:
        return None
    return _normalize_phrase(str(mentions[0]))


def _advertised_subject(
    text: str,
    product_candidate: str | None,
    *,
    business_phrase: str | None = None,
) -> tuple[str | None, str | None]:
    if product_candidate:
        return product_candidate, "service" if _looks_like_service_phrase(product_candidate) else "product"
    business_subject = business_phrase or _business_subject_phrase(text)
    if business_subject:
        return business_subject, "business"
    return None, None


def _business_subject_phrase(text: str) -> str | None:
    sentence = strip_generic_request_language(text.split(".")[0]) or text.split(".")[0]
    sentence = re.sub(r"(이번에|이번|새로)\s+", " ", sentence)
    sentence = re.sub(r"(오픈하는|문을\s+여는|오픈|홍보)\s+", " ", sentence)
    sentence = re.sub(r"(포스터|배너|전단지|광고문|광고)\s*(만들어줘|만들어\s*줘)?", " ", sentence)
    sentence = re.sub(r"\s+", " ", sentence).strip(" .,!?:;")
    if not re.search(r"[가-힣A-Za-z0-9]", sentence):
        return None
    return _normalize_phrase(sentence)


def _campaign_intent_candidate(
    text: str,
    confirmed_or_hint: str | None,
    *,
    advertised_subject_type: str | None,
) -> str | None:
    status = detect_campaign_status(text)
    if status:
        return normalize_campaign_intent(status, advertised_subject_type=advertised_subject_type, campaign_status=status)
    if any(re.search(pattern, text, re.IGNORECASE) for pattern in _OPENING_PATTERNS):
        return normalize_campaign_intent("store_opening", advertised_subject_type=advertised_subject_type)
    if any(re.search(pattern, text, re.IGNORECASE) for pattern in _RECRUIT_PATTERNS):
        return "student_recruitment"
    return normalize_campaign_intent(_normalize_phrase(confirmed_or_hint), advertised_subject_type=advertised_subject_type)


def _promotion_goal_from_candidate(candidate: str | None) -> str | None:
    return project_legacy_promotion_goal(candidate)


def _explicit_format_candidate(text: str, confirmed_ad_format: str | None, hinted_ad_format: str | None) -> str | None:
    explicit_match = _FORMAT_TOKEN_RE.search(text)
    if explicit_match:
        lowered = explicit_match.group(1).lower().replace(" ", "")
        if "스토리" in lowered:
            return "instagram_story"
        if "피드" in lowered:
            return "instagram_feed"
        if "포스터" in lowered:
            return "poster"
        if "배너" in lowered:
            return "banner"
        if "전단지" in lowered:
            return "flyer"
        if "상세" in lowered:
            return "product_detail"
    return _normalize_phrase(confirmed_ad_format) or _normalize_phrase(hinted_ad_format)


def _time_context(text: str) -> tuple[str, ...]:
    matches = [match.group(1).replace(" ", "_") for match in _TIME_TOKEN_RE.finditer(text)]
    return tuple(dict.fromkeys(matches))


def _location_context(text: str) -> tuple[str, ...]:
    values = [match.group(1).strip() for match in _LOCATION_TOKEN_RE.finditer(text)]
    return tuple(dict.fromkeys(value for value in values if value))


def _contact_context(text: str) -> tuple[str, ...]:
    values: list[str] = []
    values.extend(match.group(0).strip() for match in _PHONE_RE.finditer(text))
    values.extend(match.group(0).strip() for match in _EMAIL_RE.finditer(text))
    return tuple(dict.fromkeys(values))


def _price_context(text: str) -> tuple[str, ...]:
    values = [match.group(0).strip() for match in _PRICE_RE.finditer(text)]
    return tuple(dict.fromkeys(values))


def _ambiguity_flags(business_candidate: str | None, text: str) -> list[str]:
    flags: list[str] = []
    lowered = text.lower()
    if business_candidate in {"beauty", "beauty_salon"} or "뷰티" in text or "beauty" in lowered:
        flags.append("beauty_subtype_ambiguous")
    if not business_candidate and ("홍보물" in text or "advertisement" in lowered):
        flags.append("business_subject_ambiguous")
    return flags


def _looks_like_service_phrase(value: str) -> bool:
    normalized = _normalize_phrase(value) or ""
    return bool(_PRODUCT_SERVICE_SUFFIX_RE.search(normalized)) and normalized.endswith(
        ("회화반", "수업", "강의", "레슨", "클래스", "상담", "서비스")
    )


def _projectable_item_or_service(value: str | None) -> str | None:
    candidate = _normalize_phrase(value)
    if not candidate:
        return None
    candidate = re.sub(r"^(우리|저희|이번|새로|신규)\s+", "", candidate)
    candidate = re.sub(r"^(카페|식당|음식점|레스토랑|매장|샵|서점)\s+", "", candidate)
    candidate = _normalize_phrase(candidate)
    if not candidate:
        return None
    if _PRODUCT_SERVICE_SUFFIX_RE.search(candidate):
        return candidate
    if re.fullmatch(r"[A-Za-z0-9 _-]+", candidate):
        return None
    return candidate


def _project_item_candidate(
    value: str | None,
    *,
    source_text: str | None = None,
) -> tuple[str | None, str | None]:
    candidate = _normalize_phrase(value)
    if not candidate:
        return None, None
    source = _normalize_phrase(source_text)
    if source:
        if candidate == source:
            return None, "whole_prompt_candidate"
        if len(candidate) >= 40 and len(candidate) / max(len(source), 1) >= 0.55:
            return None, "whole_prompt_candidate"
        if candidate in source and len(candidate) >= 40:
            return None, "instruction_residue_or_whole_prompt"
    if _contains_request_or_brief_residue(candidate):
        return None, "instruction_residue_or_whole_prompt"
    projected = _projectable_item_or_service(candidate)
    if projected is None and re.fullmatch(r"[A-Za-z0-9 _-]+", candidate):
        if len(candidate.split()) >= 2:
            return candidate, None
        return None, "non_specific_ascii_phrase"
    return projected, None


def _contains_request_or_brief_residue(value: str) -> bool:
    lowered = value.lower()
    if re.search(r"\b(?:create|make|poster|banner|flyer|advertisement|ad)\b", lowered):
        return True
    return any(
        token in value
        for token in (
            "만들어",
            "제작",
            "광고",
            "포스터",
            "배너",
            "전단지",
            "상세페이지",
            "분위기",
            "느낌",
            "타깃",
            "대상",
            "타겟",
            "직장인",
            "여성",
        )
    )


def _source_text_proxy(result: IntakeUnderstandingResult) -> str | None:
    source_refs = [item.source_ref for item in result.evidence_items if isinstance(item.source_ref, str) and item.source_ref.strip()]
    if not source_refs:
        return None
    return max(source_refs, key=len)


def _should_project_business_type(result: IntakeUnderstandingResult) -> bool:
    for item in result.evidence_items:
        if item.key == "business_candidate" and item.source != "structured_llm":
            return True
    return False


def _normalize_phrase(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", " ", value).strip(" .,!?:;")
    return normalized or None


def _evidence_item(
    key: str,
    value: str,
    *,
    user_text: str,
    source: str,
    confidence: float,
    exact_span: str | None,
) -> EvidenceItem:
    source_ref = exact_span if exact_span and exact_span in user_text else (user_text[:120] or value[:120])
    exact = bool(exact_span and exact_span in user_text)
    evidence_class = "verified_fact" if exact else "creative_inference"
    return EvidenceItem(
        key=key,
        value=value,
        normalized_value=value,
        source=source,  # type: ignore[arg-type]
        evidence_class=evidence_class,
        confidence=max(0.0, min(1.0, confidence)),
        usable_for_copy=exact,
        source_ref=source_ref,
        rationale=None if exact else "derived_from_prompt_context",
    )


def _span_if_present(text: str, value: str | None) -> str | None:
    candidate = _normalize_phrase(value)
    if not candidate:
        return None
    return candidate if candidate in text else None


def _campaign_span(text: str, candidate: str | None) -> str | None:
    if not candidate:
        return None
    if candidate == "store_opening":
        for token in ("오픈", "개업", "새로 문"):
            if token in text:
                return token
    if candidate == "student_recruitment":
        for token in ("모집", "수강생", "등록"):
            if token in text:
                return token
    return _span_if_present(text, candidate)


def _format_span(text: str, candidate: str | None) -> str | None:
    if not candidate:
        return None
    mapping = {
        "poster": "포스터",
        "banner": "배너",
        "flyer": "전단지",
        "instagram_story": "스토리",
        "instagram_feed": "피드",
        "product_detail": "상세 페이지",
    }
    token = mapping.get(candidate)
    return token if token and token in text else _span_if_present(text, candidate)


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        normalized = _normalize_phrase(str(value)) if isinstance(value, str) else None
        if normalized:
            return normalized
    return None


def _source_text_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()
