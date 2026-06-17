"""Open-domain intake understanding service."""

from __future__ import annotations

import re
from typing import Any, Callable

from orchestrator.app.llm.domain_routing import normalize_business_type
from orchestrator.app.llm.native_campaign_copy_rules import clean_product_identity, detect_campaign_status, strip_generic_request_language
from orchestrator.app.schemas.brief_llm import BriefInterpreterOutput
from orchestrator.app.schemas.input_evidence import EvidenceItem
from orchestrator.app.schemas.intake_understanding import IntakeUnderstandingResult

BusinessInterpreter = Callable[[dict[str, Any], str], tuple[BriefInterpreterOutput | None, dict[str, Any]]]
BriefProjector = Callable[[BriefInterpreterOutput, str], tuple[dict[str, Any], list[str]]]

_PHONE_RE = re.compile(r"01\d[-\s]?\d{3,4}[-\s]?\d{4}")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PRICE_RE = re.compile(r"\d[\d,]*\s*(?:원|%|만원)")
_DISTRICT_RE = re.compile(r"([가-힣A-Za-z0-9]+(?:구|동|역|시))")
_OPENING_PATTERNS = (r"오픈", r"개업", r"새로\s+문", r"opening", r"grand\s+open")
_RECRUIT_PATTERNS = (r"모집", r"수강생", r"신청", r"등록")
_SERVICE_PATTERNS = (r"수업", r"강의", r"레슨", r"클래스", r"회화반", r"상담", r"서비스")
_PRODUCT_PATTERNS = (r"라떼", r"메뉴", r"음료", r"제품", r"상품", r"케이크")
_GENERIC_BEAUTY_PATTERNS = (r"뷰티", r"미용")
_FORMAT_TERMS = (r"포스터", r"배너", r"전단지", r"스토리", r"피드", r"상세\s*페이지")
_TONE_MARKERS = {
    "premium": (r"프리미엄", r"고급"),
    "elegant": (r"우아", r"세련"),
    "friendly": (r"친근", r"편안"),
    "clean": (r"깔끔", r"미니멀"),
}
_TIME_MARKERS = {
    "weekday_evening": (r"평일\s*저녁",),
    "weekday": (r"평일",),
    "evening": (r"저녁",),
    "weekend": (r"주말",),
    "lunch": (r"점심",),
}
_TARGET_MARKERS = {
    "office_workers": (r"직장인",),
    "students": (r"학생", r"수강생"),
}


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
        "field_sources": _field_sources_for(deterministic, source="deterministic_parser"),
        "candidate_counts": _candidate_counts_for(deterministic),
        "brief_interpreter": {"used": False, "llm_metadata": {"llm_attempted": False}, "warnings": []},
    }

    if not _should_attempt_structured_intake(deterministic) or brief_interpreter is None or brief_projector is None:
        return deterministic, trace

    llm_output, llm_metadata = brief_interpreter(state, text)
    warnings: list[str] = []
    suggested_copy_mode: str | None = None
    merged = deterministic
    if llm_output is not None:
        llm_updates, warnings = brief_projector(llm_output, source_text=text)
        suggested_copy_mode = llm_updates.pop("copy_generation_mode", None)
        merged = _merge_structured_intake(deterministic, llm_output, llm_updates, text)

    trace["mode"] = merged.extraction_mode
    trace["fallback_used"] = merged.fallback_used
    trace["fallback_reason"] = merged.fallback_reason
    trace["field_sources"] = _field_sources_for(merged, source="structured_llm" if llm_output is not None else "deterministic_parser")
    trace["candidate_counts"] = _candidate_counts_for(merged)
    trace["copy_generation_mode_candidate"] = suggested_copy_mode
    trace["brief_interpreter"] = {
        "used": llm_output is not None,
        "llm_metadata": llm_metadata,
        "warnings": warnings,
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
    product_candidate = _product_or_service_candidate(bundle, hints, user_text)
    business_candidate = _business_candidate(hints, user_text, product_candidate)
    advertised_subject, advertised_subject_type = _advertised_subject(user_text, product_candidate)
    campaign_candidate = _campaign_intent_candidate(user_text, hints)
    ad_format_candidate = hints.get("ad_format")
    tone_candidates = _keyword_candidates(user_text, _TONE_MARKERS)
    mood_candidates = _mood_candidates(user_text)
    target_candidates = _keyword_candidates(user_text, _TARGET_MARKERS)
    time_context = _keyword_candidates(user_text, _TIME_MARKERS)
    location_context = _location_candidates(user_text)
    contact_context = _contact_candidates(user_text)
    price_context = _price_candidates(user_text)
    ambiguity_flags = _ambiguity_flags(business_candidate, user_text)

    evidence_items: list[EvidenceItem] = []
    confidence_by_field: dict[str, float] = {}

    def add_scalar(field: str, value: str | None, *, confidence: float = 0.9) -> None:
        if not value:
            return
        evidence_items.append(_evidence_item(field, value, source="deterministic_parser", confidence=confidence))
        confidence_by_field[field] = confidence

    def add_many(field: str, values: tuple[str, ...], *, confidence: float = 0.85) -> None:
        if not values:
            return
        evidence_items.append(_evidence_item(field, ", ".join(values), source="deterministic_parser", confidence=confidence))
        confidence_by_field[field] = confidence

    add_scalar("business_candidate", business_candidate, confidence=0.92 if business_candidate else 0.0)
    add_scalar("venue_type_candidate", advertised_subject if advertised_subject_type == "business" else None, confidence=0.78)
    add_scalar("advertised_subject", advertised_subject, confidence=0.88)
    add_scalar("advertised_subject_type", advertised_subject_type, confidence=0.88)
    add_scalar("product_or_service_candidate", product_candidate, confidence=0.9)
    add_scalar("campaign_intent_candidate", campaign_candidate, confidence=0.82)
    add_scalar("ad_format_candidate", ad_format_candidate, confidence=0.95)
    add_many("tone_candidates", tone_candidates)
    add_many("mood_candidates", mood_candidates)
    add_many("target_candidates", target_candidates)
    add_many("time_context", time_context)
    add_many("location_context", location_context)
    add_many("contact_context", contact_context, confidence=0.99)
    add_many("price_context", price_context, confidence=0.99)

    return IntakeUnderstandingResult(
        business_candidate=business_candidate,
        venue_type_candidate=advertised_subject if advertised_subject_type == "business" else None,
        advertised_subject=advertised_subject,
        advertised_subject_type=advertised_subject_type,
        product_or_service_candidate=product_candidate,
        campaign_intent_candidate=campaign_candidate,
        ad_format_candidate=ad_format_candidate,
        tone_candidates=tone_candidates,
        mood_candidates=mood_candidates,
        target_candidates=target_candidates,
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
    if normalized.business_type:
        updates["business_type"] = normalized.business_type
    projected_item = _projectable_item_or_service(result.product_or_service_candidate)
    if projected_item is None and result.extraction_mode == "hybrid_structured_llm":
        projected_item = _normalize_phrase(result.product_or_service_candidate)
    if projected_item and result.advertised_subject_type in {"product", "service"}:
        updates["item_or_service"] = projected_item
    promotion_goal = _promotion_goal_from_candidate(result.campaign_intent_candidate)
    if promotion_goal:
        updates["promotion_goal"] = promotion_goal
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
    if "beauty_subtype_ambiguous" in result.ambiguity_flags:
        return True
    return False


def _merge_structured_intake(
    deterministic: IntakeUnderstandingResult,
    llm_output: BriefInterpreterOutput,
    llm_updates: dict[str, Any],
    source_text: str,
) -> IntakeUnderstandingResult:
    product_candidate = llm_updates.get("item_or_service") or deterministic.product_or_service_candidate
    business_candidate = llm_output.business_type or deterministic.business_candidate
    if product_candidate:
        advertised_subject = product_candidate
        advertised_subject_type = "service" if _looks_like_service_phrase(product_candidate) else "product"
    else:
        advertised_subject = deterministic.advertised_subject or _business_subject_phrase(source_text)
        advertised_subject_type = deterministic.advertised_subject_type
    campaign_candidate = str(llm_output.promotion_goal or deterministic.campaign_intent_candidate or "").strip() or None
    evidence_items = list(deterministic.evidence_items)

    def add_if_present(key: str, value: str | None, *, confidence: float | None = None) -> None:
        if not value:
            return
        evidence_items.append(
            _evidence_item(
                key,
                value,
                source="structured_llm",
                confidence=confidence if confidence is not None else max(0.65, llm_output.confidence),
            )
        )

    add_if_present("business_candidate", business_candidate)
    add_if_present("advertised_subject", advertised_subject)
    add_if_present("advertised_subject_type", advertised_subject_type)
    add_if_present("product_or_service_candidate", product_candidate)
    add_if_present("campaign_intent_candidate", campaign_candidate)
    if deterministic.ad_format_candidate:
        add_if_present("ad_format_candidate", deterministic.ad_format_candidate, confidence=0.95)
    if llm_updates.get("brand_tone"):
        add_if_present("tone_candidates", llm_updates["brand_tone"])
    if llm_output.target_persona:
        add_if_present("target_candidates", llm_output.target_persona)

    confidence_map = dict(deterministic.confidence_by_field)
    if business_candidate:
        confidence_map["business_candidate"] = llm_output.confidence
    if product_candidate:
        confidence_map["product_or_service_candidate"] = llm_output.confidence
    if campaign_candidate:
        confidence_map["campaign_intent_candidate"] = llm_output.confidence

    tone_candidates = deterministic.tone_candidates
    if llm_updates.get("brand_tone"):
        tone_candidates = tuple(dict.fromkeys([*deterministic.tone_candidates, llm_updates["brand_tone"]]))
    target_candidates = deterministic.target_candidates
    if llm_output.target_persona:
        target_candidates = tuple(dict.fromkeys([*deterministic.target_candidates, llm_output.target_persona]))
        confidence_map["target_candidates"] = llm_output.confidence
    ambiguity_flags = tuple(
        dict.fromkeys(
            [
                *deterministic.ambiguity_flags,
                *_ambiguity_flags(business_candidate, source_text),
            ]
        )
    )

    return IntakeUnderstandingResult(
        business_candidate=business_candidate,
        venue_type_candidate=deterministic.venue_type_candidate,
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


def _field_sources_for(result: IntakeUnderstandingResult, *, source: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for field in (
        "business_candidate",
        "venue_type_candidate",
        "advertised_subject",
        "advertised_subject_type",
        "product_or_service_candidate",
        "campaign_intent_candidate",
        "ad_format_candidate",
    ):
        if getattr(result, field):
            fields[field] = source
    for field in (
        "tone_candidates",
        "mood_candidates",
        "target_candidates",
        "time_context",
        "location_context",
        "contact_context",
        "price_context",
    ):
        if getattr(result, field):
            fields[field] = source
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


def _product_or_service_candidate(bundle: dict[str, Any], hints: dict[str, str | None], text: str) -> str | None:
    mentions = bundle.get("explicit_product_mentions") or []
    if mentions:
        candidate = _normalize_phrase(str(mentions[0]))
        if candidate:
            return candidate
    candidate = hints.get("item_or_service")
    if candidate:
        return _normalize_phrase(candidate)
    sentence = text.split(".")[0].strip()
    for pattern in (
        r"([가-힣A-Za-z0-9 ]+?(?:회화반|수업|강의|레슨|클래스|상담|서비스))",
        r"([가-힣A-Za-z0-9 ]+?(?:라떼|메뉴|음료|제품|상품|케이크))",
    ):
        match = re.search(pattern, sentence, re.IGNORECASE)
        if match:
            return _normalize_phrase(match.group(1))
    cleaned = clean_product_identity(sentence)
    if cleaned and (_looks_like_service_phrase(cleaned) or _looks_like_product_phrase(cleaned)):
        return _normalize_phrase(cleaned)
    return None


def _business_candidate(hints: dict[str, str | None], text: str, product_candidate: str | None) -> str | None:
    candidate = hints.get("business_type")
    if candidate:
        return candidate
    if any(re.search(pattern, text, re.IGNORECASE) for pattern in _GENERIC_BEAUTY_PATTERNS):
        return "beauty"
    if _looks_like_education_service(text) or (_looks_like_service_phrase(product_candidate or "") and "영어" in text):
        return "education"
    return None


def _advertised_subject(text: str, product_candidate: str | None) -> tuple[str | None, str | None]:
    if product_candidate:
        return product_candidate, "service" if _looks_like_service_phrase(product_candidate) else "product"
    descriptive_business_subject = _descriptive_business_subject_phrase(text)
    if descriptive_business_subject:
        return descriptive_business_subject, "business"
    business_subject = _business_subject_phrase(text)
    if business_subject:
        return business_subject, "business"
    return None, None


def _descriptive_business_subject_phrase(text: str) -> str | None:
    sentence = strip_generic_request_language(text.split(".")[0]) or text.split(".")[0]
    sentence = re.sub(r"(?:이번에|이번|새로)\s+", " ", sentence)
    sentence = re.sub(r"(?:오픈하는|문을\s+여는|오픈)\s+", " ", sentence)
    sentence = re.sub(r"(?:홍보\s*)?(?:포스터|배너|전단지|광고문|광고)\s*(?:만들어줘|만들어\s*줘)?", " ", sentence)
    sentence = re.sub(r"\s+", " ", sentence).strip(" .,!?:;")
    if not re.search(r"[가-힣]", sentence):
        return None
    return _normalize_phrase(sentence)


def _business_subject_phrase(text: str) -> str | None:
    cleaned = strip_generic_request_language(text.split(".")[0]) or text.split(".")[0]
    cleaned = re.sub(r"(이번에|새로|신규로|곧)\s+", " ", cleaned)
    cleaned = re.sub(r"(오픈하는|문을\s+여는|오픈)\s+", " ", cleaned)
    for pattern in _FORMAT_TERMS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    for markers in _TONE_MARKERS.values():
        for marker in markers:
            cleaned = re.sub(marker, " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(만들어줘|만들어\s*줘|홍보\s*물|광고|포스터|배너|전단지)", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,!?:;")
    if not re.search(r"[가-힣]", cleaned):
        return None
    if not cleaned:
        return None
    return _normalize_phrase(cleaned.split("의")[0].strip())


def _campaign_intent_candidate(text: str, hints: dict[str, str | None]) -> str | None:
    status = detect_campaign_status(text)
    if status:
        return status
    if any(re.search(pattern, text, re.IGNORECASE) for pattern in _OPENING_PATTERNS):
        return "store_opening"
    if any(re.search(pattern, text, re.IGNORECASE) for pattern in _RECRUIT_PATTERNS):
        return "student_recruitment"
    if hints.get("promotion_goal"):
        return hints["promotion_goal"]
    return None


def _promotion_goal_from_candidate(candidate: str | None) -> str | None:
    mapping = {
        "new_menu": "new_launch",
        "new_product": "new_launch",
        "seasonal": "seasonal_limited",
        "seasonal_limited": "seasonal_limited",
        "seasonal_campaign": "seasonal_limited",
        "new_launch": "new_launch",
        "discount_event": "discount_event",
        "reservation": "reservation_cta",
        "reservation_cta": "reservation_cta",
        "review_event": "review_event",
        "brand_awareness": "brand_awareness",
    }
    return mapping.get(str(candidate or "").strip())


def _keyword_candidates(text: str, mapping: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    values: list[str] = []
    for normalized, patterns in mapping.items():
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns):
            values.append(normalized)
    return tuple(dict.fromkeys(values))


def _mood_candidates(text: str) -> tuple[str, ...]:
    candidates: list[str] = []
    if re.search(r"뷰티\s*감성", text, re.IGNORECASE):
        candidates.append("beauty_inspired")
    if re.search(r"우아", text, re.IGNORECASE):
        candidates.append("elegant")
    return tuple(dict.fromkeys(candidates))


def _location_candidates(text: str) -> tuple[str, ...]:
    values = [match.group(1).strip() for match in _DISTRICT_RE.finditer(text)]
    leading_location_match = re.match(r"\s*([가-힣]{2,4})\s+[가-힣A-Za-z0-9]+(?:반|샵|카페|학원|수업|상담|서점)", text)
    if leading_location_match:
        leading_token = leading_location_match.group(1).strip()
        if leading_token not in {"프리미엄", "동네", "이번에", "새로"}:
            values.append(leading_token)
    return tuple(dict.fromkeys(value for value in values if value))


def _contact_candidates(text: str) -> tuple[str, ...]:
    values: list[str] = []
    values.extend(match.group(0).strip() for match in _PHONE_RE.finditer(text))
    values.extend(match.group(0).strip() for match in _EMAIL_RE.finditer(text))
    return tuple(dict.fromkeys(values))


def _price_candidates(text: str) -> tuple[str, ...]:
    values = [match.group(0).strip() for match in _PRICE_RE.finditer(text)]
    return tuple(dict.fromkeys(values))


def _ambiguity_flags(business_candidate: str | None, text: str) -> list[str]:
    flags: list[str] = []
    if business_candidate == "beauty":
        flags.append("beauty_subtype_ambiguous")
    if not business_candidate and re.search(r"홍보물|광고", text):
        flags.append("business_subject_ambiguous")
    return flags


def _looks_like_service_phrase(value: str) -> bool:
    return any(re.search(pattern, value or "", re.IGNORECASE) for pattern in _SERVICE_PATTERNS)


def _looks_like_product_phrase(value: str) -> bool:
    return any(re.search(pattern, value or "", re.IGNORECASE) for pattern in _PRODUCT_PATTERNS)


def _looks_like_education_service(text: str) -> bool:
    lowered = text.lower()
    return "영어회화" in text or "academy" in lowered or "class" in lowered or _looks_like_service_phrase(text)


def _normalize_phrase(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", " ", value).strip(" .,!?:;")
    return normalized or None


def _projectable_item_or_service(value: str | None) -> str | None:
    candidate = _normalize_phrase(value)
    if not candidate:
        return None
    candidate = re.sub(r"^(?:우리|저희|이번|새로|신규)\s+", "", candidate)
    candidate = re.sub(r"^(?:카페|식당|음식점|레스토랑|매장|샵|서점)\s+", "", candidate)
    candidate = _normalize_phrase(candidate)
    if not candidate:
        return None
    if re.search(r"(회화반|수업|강의|레슨|클래스|상담|서비스|라떼|메뉴|음료|제품|상품|케이크)$", candidate):
        return candidate
    if re.fullmatch(r"[A-Za-z0-9 _-]+", candidate):
        return None
    return candidate


def _evidence_item(key: str, value: str, *, source: str, confidence: float) -> EvidenceItem:
    return EvidenceItem(
        key=key,
        value=value,
        normalized_value=value,
        source=source,  # type: ignore[arg-type]
        evidence_class="verified_fact",
        confidence=max(0.0, min(1.0, confidence)),
        usable_for_copy=True,
        source_ref=value[:120],
    )
