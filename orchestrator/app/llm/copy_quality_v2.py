"""Copy Quality Core v2 ranking and validation."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Callable

from orchestrator.app.llm.copy_fallbacks import build_message_strategy, generate_fallback_candidates
from orchestrator.app.llm.copy_tone_policy import get_copy_tone_policy, normalize_copy_for_business
from orchestrator.app.schemas.llm_marketing import (
    CopyCandidate,
    CopyCandidateListOutput,
    CopyCandidateRankingOutput,
    CopyCandidateScoreCard,
    CopyGenerationV2Output,
    MarketingContext,
)


GENERIC_META_PHRASES = (
    "상품의 장점을 쉽게 확인해보세요",
    "필요한 정보를 간결하게 안내",
    "지금 확인하기",
    "자세히 보기",
    "생성된 이미지만 확인하고 다운로드할 수 있어요",
    "best menu",
    "check now",
    "learn more",
)

GENERIC_META_TOKENS = (
    "placeholder",
    "lorem",
    "광고 문구",
    "카피 문구",
    "이미지 생성",
    "다운로드",
)

GENERIC_PATTERNS = (
    r"(정보|내용|상품|메뉴).{0,10}확인",
    r"(간결하게|쉽게).{0,10}(안내|전달)",
    r"필요한.{0,12}(안내|정보|내용)",
    r"(자세히|지금).{0,5}(보기|확인)",
)

HIGH_RISK_CLAIM_TERMS = (
    "프리미엄",
    "맞춤",
    "수제",
    "당일 생산",
    "시그니처",
    "개인별",
    "효과",
    "개선",
    "보장",
    "완성",
)


def build_deterministic_copy_output_v2(state: dict[str, Any] | Any, max_candidates: int = 3) -> CopyGenerationV2Output:
    context = _context_from_state(state)
    candidates = generate_fallback_candidates(context, max_candidates=min(3, max(1, max_candidates)))
    ranking = rank_copy_candidates(candidates, state=state)
    return CopyGenerationV2Output(
        message_strategy=build_message_strategy(context),
        candidates=candidates,
        ranking=ranking,
        recommended_candidate_id=ranking.recommended_candidate_id,
        metadata={"source": "deterministic_fallback_v2"},
    )


def generate_fallback_candidates_v2(state: dict[str, Any] | Any, max_candidates: int = 3) -> CopyGenerationV2Output:
    return build_deterministic_copy_output_v2(state, max_candidates=max_candidates)


def generate_copy_candidates_v2(state: dict[str, Any] | Any, max_candidates: int = 3) -> CopyGenerationV2Output:
    """Compatibility alias for deterministic v2 generation."""

    return build_deterministic_copy_output_v2(state, max_candidates=max_candidates)


def generate_copy_candidates_v2_actual(
    state: dict[str, Any],
    *,
    run_structured_node_fn: Callable[..., tuple[Any, dict[str, Any]]],
    prompt: str,
    max_candidates: int = 3,
) -> tuple[CopyGenerationV2Output, dict[str, Any]]:
    fallback = lambda: build_deterministic_copy_output_v2(state, max_candidates=max_candidates)
    output, metadata = run_structured_node_fn(
        state,
        node_name="copy_generation_v2_actual",
        output_schema=CopyCandidateListOutput,
        prompt=prompt,
        fallback_fn=fallback,
        risk_level="medium",
        confidence=0.6,
        latency_budget="standard",
        metadata={"schema_version": "copy_generation_v2_actual"},
    )
    if isinstance(output, CopyGenerationV2Output):
        output = CopyCandidateListOutput(candidates=output.candidates, recommended_candidate_id=output.recommended_candidate_id, metadata=output.metadata)
    elif not isinstance(output, CopyCandidateListOutput):
        fallback_output = fallback()
        output = CopyCandidateListOutput(candidates=fallback_output.candidates, recommended_candidate_id=fallback_output.recommended_candidate_id, metadata=fallback_output.metadata)
    ranked = annotate_and_rank_candidate_output(
        CopyCandidateListOutput(candidates=output.candidates, recommended_candidate_id=output.recommended_candidate_id),
        state=state,
        max_candidates=max_candidates,
    )
    ranking = CopyCandidateRankingOutput(**ranked.metadata["copy_quality_v2_ranking"])
    result = CopyGenerationV2Output(
        message_strategy=build_message_strategy(_context_from_state(state)),
        candidates=ranked.candidates,
        ranking=ranking,
        recommended_candidate_id=ranking.recommended_candidate_id,
        metadata={**output.metadata, "source": "actual_llm_or_fallback_v2"},
    )
    return result, metadata


def rank_copy_candidates(
    candidates: list[CopyCandidate],
    *,
    state: dict[str, Any] | None = None,
    business_type: str | None = None,
) -> CopyCandidateRankingOutput:
    context = _context_from_state(state)
    business = business_type or (context.business_type if context else None)
    policy = get_copy_tone_policy(business)
    duplicate_ids = find_near_duplicate_candidate_ids(candidates)
    scorecards = [
        score_copy_candidate_v2(candidate, policy=policy, duplicate=duplicate_ids.get(candidate.id), state=state)
        for candidate in candidates
    ]
    valid_cards = [card for card in scorecards if not card.hard_blocked]
    ranked = sorted(
        scorecards,
        key=lambda card: (
            card.hard_blocked,
            -card.final_score,
            -card.business_fit_score,
            -card.specificity_score,
            -card.clarity_score,
            card.candidate_id,
        ),
    )
    recommended = ranked[0].candidate_id if ranked and valid_cards and not ranked[0].hard_blocked else None
    return CopyCandidateRankingOutput(
        recommended_candidate_id=recommended,
        requires_regeneration=bool(scorecards and not valid_cards),
        scorecards=scorecards,
        blocked_candidate_ids=[card.candidate_id for card in scorecards if card.hard_blocked],
        diversity_warnings=[f"near_duplicate:{left}:{right}" for left, right in sorted(set(duplicate_ids.values()))],
        metadata={"ranker": "copy_quality_v2", "candidate_count": len(candidates)},
    )


def select_recommended_copy(candidates: list[CopyCandidate], ranking: CopyCandidateRankingOutput | None = None) -> CopyCandidate | None:
    if not candidates:
        return None
    ranking = ranking or rank_copy_candidates(candidates)
    if ranking.requires_regeneration or not ranking.recommended_candidate_id:
        return None
    selected_id = ranking.recommended_candidate_id
    return next((candidate for candidate in candidates if candidate.id == selected_id), None)


def validate_candidate_diversity(candidates: list[CopyCandidate], threshold: float = 0.82) -> dict[str, Any]:
    duplicates = find_near_duplicate_candidate_ids(candidates, threshold=threshold)
    angles = {candidate.angle for candidate in candidates if candidate.angle}
    return {
        "distinct_angle_count": len(angles),
        "near_duplicate_pairs": sorted(set(duplicates.values())),
        "overall_pass": len(angles) >= min(3, len(candidates)) and not duplicates,
    }


def annotate_and_rank_candidate_output(
    output: CopyCandidateListOutput,
    *,
    state: dict[str, Any],
    max_candidates: int,
) -> CopyCandidateListOutput:
    candidates = output.candidates[: min(3, max(1, max_candidates))]
    context = _context_from_state(state)
    normalized: list[CopyCandidate] = []
    for index, candidate in enumerate(candidates, start=1):
        angle = candidate.angle or ("product_first", "emotion_first", "benefit_action_first")[(index - 1) % 3]
        policy = normalize_copy_for_business(
            {"headline": candidate.headline, "subcopy": candidate.subcopy, "cta": candidate.cta},
            context.business_type,
            mode="generated",
        )
        copy = policy["normalized_copy"]
        normalized.append(
            candidate.model_copy(
                update={
                    "id": candidate.id or f"copy_{index}",
                    "headline": copy["headline"],
                    "subcopy": copy["subcopy"],
                    "cta": copy["cta"],
                    "angle": angle,
                    "strategy_summary": candidate.strategy_summary or build_message_strategy(context).strategy_summary,
                    "metadata": {**candidate.metadata, "copy_tone_policy": policy, "copy_quality_v2": True},
                }
            )
        )
    ranking = rank_copy_candidates(normalized, state=state)
    score_by_id = {card.candidate_id: card.model_dump() for card in ranking.scorecards}
    annotated = [
        candidate.model_copy(update={"metadata": {**candidate.metadata, "copy_quality_v2_score": score_by_id.get(candidate.id)}})
        for candidate in normalized
    ]
    return CopyCandidateListOutput(
        candidates=annotated,
        recommended_candidate_id=ranking.recommended_candidate_id,
        metadata={**output.metadata, "copy_quality_v2_ranking": ranking.model_dump()},
    )


def score_copy_candidate_v2(
    candidate: CopyCandidate,
    *,
    policy: dict[str, Any] | None = None,
    duplicate: tuple[str, str] | None = None,
    state: dict[str, Any] | None = None,
) -> CopyCandidateScoreCard:
    policy = policy or get_copy_tone_policy(None)
    text = joined_candidate_text(candidate)
    warnings: list[str] = []
    reasons: list[str] = []
    hard_blocked = False
    generic_penalty = 0.0
    if contains_generic_meta_phrase(text):
        generic_penalty = 0.45
        hard_blocked = True
        warnings.append("generic_or_meta_phrase_detected")
        reasons.append("Generated copy contains generic/meta placeholder wording.")
    fact_penalty = 0.0
    unsupported_claims = _unsupported_claims(text, state or {})
    if state and (_invented_fact_detected(text, state) or unsupported_claims):
        fact_penalty = 0.4
        hard_blocked = True
        warnings.append("unsupported_fact_detected")
        reasons.append("Copy appears to introduce unsupported facts or high-risk claims.")
        if unsupported_claims:
            warnings.extend(f"unsupported_claim:{claim}" for claim in unsupported_claims)
    length_penalty = _length_penalty(candidate, policy, warnings)
    diversity_penalty = 0.15 if duplicate else 0.0
    if duplicate:
        warnings.append("near_duplicate_candidate")
        reasons.append(f"Near duplicate with {duplicate[0] if duplicate[1] == candidate.id else duplicate[1]}.")
    tone_fit = 0.85 if any(term and term in text for term in policy.get("avoid_terms", [])) else 1.0
    if tone_fit < 1.0:
        warnings.append("business_tone_avoid_term_detected")
    specificity = _specificity_score(candidate)
    business_fit = _business_fit_score(text, policy)
    emotional_pull = _emotional_pull_score(text)
    clarity = _clarity_score(candidate)
    cta_relevance = _cta_relevance_score(candidate, policy)
    visual_fit = _visual_fit_score(candidate)
    action_clarity = cta_relevance
    semantic = (
        specificity * 0.18
        + business_fit * 0.2
        + emotional_pull * 0.14
        + clarity * 0.18
        + cta_relevance * 0.18
        + visual_fit * 0.12
    )
    final = semantic - generic_penalty - fact_penalty - length_penalty - diversity_penalty
    final = final * tone_fit
    return CopyCandidateScoreCard(
        candidate_id=candidate.id,
        hard_blocked=hard_blocked,
        final_score=max(0.0, min(1.0, round(final, 3))),
        specificity_score=specificity,
        business_fit_score=business_fit,
        emotional_pull_score=emotional_pull,
        clarity_score=clarity,
        cta_relevance_score=cta_relevance,
        visual_fit_score=visual_fit,
        generic_phrase_penalty=generic_penalty,
        fact_penalty=fact_penalty,
        length_penalty=length_penalty,
        diversity_penalty=diversity_penalty,
        tone_fit_score=tone_fit,
        action_clarity_score=action_clarity,
        warnings=warnings,
        reasons=reasons,
    )


def contains_generic_meta_phrase(text: str) -> bool:
    normalized = _normalize_text(text)
    if any(_normalize_text(phrase) in normalized for phrase in GENERIC_META_PHRASES):
        return True
    if any(re.search(pattern, text or "") for pattern in GENERIC_PATTERNS):
        return True
    return any(token.lower() in normalized.lower() for token in GENERIC_META_TOKENS)


def find_near_duplicate_candidate_ids(candidates: list[CopyCandidate], threshold: float = 0.82) -> dict[str, tuple[str, str]]:
    duplicates: dict[str, tuple[str, str]] = {}
    for left_index, left in enumerate(candidates):
        for right in candidates[left_index + 1 :]:
            similarity = SequenceMatcher(None, _normalize_text(joined_candidate_text(left)), _normalize_text(joined_candidate_text(right))).ratio()
            if similarity >= threshold:
                pair = (left.id, right.id)
                duplicates[left.id] = pair
                duplicates[right.id] = pair
    return duplicates


def joined_candidate_text(candidate: CopyCandidate) -> str:
    return " ".join(str(value or "") for value in (candidate.headline, candidate.subcopy, candidate.cta))


def _length_penalty(candidate: CopyCandidate, policy: dict[str, Any], warnings: list[str]) -> float:
    penalty = 0.0
    limits = (
        ("headline", candidate.headline, int(policy.get("headline_max_chars") or 24)),
        ("subcopy", candidate.subcopy or "", int(policy.get("subcopy_max_chars") or 42)),
        ("cta", candidate.cta or "", int(policy.get("cta_max_chars") or 16)),
    )
    for field, value, limit in limits:
        if len(value) > limit:
            warnings.append(f"{field}_longer_than_policy")
            penalty += 0.04
    return min(0.16, penalty)


def _invented_fact_detected(text: str, state: dict[str, Any]) -> bool:
    context = _context_from_state(state)
    provided = " ".join(
        str(value or "")
        for value in (
            context.price_or_discount,
            context.location_text,
            context.contact_or_order_method,
            state.get("user_input"),
        )
    )
    if re.search(r"0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}", text) and not re.search(r"0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}", provided):
        return True
    if "%" in text and "%" not in provided:
        return True
    if re.search(r"(₩\s*\d|[0-9][0-9,]*\s*원)", text) and not re.search(r"(₩\s*\d|[0-9][0-9,]*\s*원)", provided):
        return True
    return False


def _unsupported_claims(text: str, state: dict[str, Any]) -> list[str]:
    context = _context_from_state(state)
    supported = " ".join(
        str(value or "")
        for value in (
            context.item_or_service,
            context.usp,
            context.price_or_discount,
            context.user_input if hasattr(context, "user_input") else None,
            state.get("user_input"),
        )
    )
    claims: list[str] = []
    for term in HIGH_RISK_CLAIM_TERMS:
        if term in text and term not in supported:
            claims.append(term)
    return claims


def _specificity_score(candidate: CopyCandidate) -> float:
    text = joined_candidate_text(candidate)
    if any(char.isdigit() for char in text):
        return 0.8
    if candidate.headline and len(candidate.headline) >= 6:
        return 0.74
    return 0.55


def _business_fit_score(text: str, policy: dict[str, Any]) -> float:
    avoid_terms = policy.get("avoid_terms", [])
    if any(term and term in text for term in avoid_terms):
        return 0.55
    notes = " ".join(str(value) for value in policy.get("visual_fit_notes", []))
    return 0.82 if notes else 0.72


def _emotional_pull_score(text: str) -> float:
    emotional_terms = ("오늘", "시간", "무드", "휴식", "달콤", "따뜻", "차분", "기분")
    return 0.86 if any(term in text for term in emotional_terms) else 0.62


def _clarity_score(candidate: CopyCandidate) -> float:
    text = joined_candidate_text(candidate)
    if len(text) > 80:
        return 0.62
    return 0.86 if candidate.headline and candidate.subcopy else 0.7


def _cta_relevance_score(candidate: CopyCandidate, policy: dict[str, Any]) -> float:
    cta = candidate.cta or ""
    if not cta:
        return 0.45
    if cta in policy.get("cta_candidates", []):
        return 0.92
    if any(token in cta for token in ("예약", "문의", "상담", "보기", "신청")):
        return 0.82
    return 0.65


def _visual_fit_score(candidate: CopyCandidate) -> float:
    if candidate.angle == "emotion_first":
        return 0.86
    if candidate.angle == "product_first":
        return 0.78
    return 0.8


def _candidate_angle(candidates: list[CopyCandidate], candidate_id: str) -> str | None:
    candidate = next((item for item in candidates if item.id == candidate_id), None)
    return candidate.angle if candidate else None


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "").strip()


def _context_from_state(state: dict[str, Any] | Any | None) -> MarketingContext:
    raw = state.get("context") if isinstance(state, dict) else None
    if isinstance(raw, MarketingContext):
        return raw
    if isinstance(raw, dict):
        return MarketingContext(**raw)
    return MarketingContext()
