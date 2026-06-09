"""Copy Quality Core v2 ranking and validation."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

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

ANGLE_ORDER = {"product_first": 0, "emotion_first": 1, "benefit_action_first": 2, None: 9}


def generate_copy_candidates_v2(state: dict[str, Any] | Any, max_candidates: int = 3) -> CopyGenerationV2Output:
    context = _context_from_state(state)
    candidates = generate_fallback_candidates(context, max_candidates=max_candidates)
    ranking = rank_copy_candidates(candidates, state=state)
    return CopyGenerationV2Output(
        message_strategy=build_message_strategy(context),
        candidates=candidates,
        ranking=ranking,
        recommended_candidate_id=ranking.recommended_candidate_id,
        metadata={"source": "deterministic_fallback_v2"},
    )


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
    ranked = sorted(
        scorecards,
        key=lambda card: (
            card.hard_blocked,
            -card.final_score,
            ANGLE_ORDER.get(_candidate_angle(candidates, card.candidate_id), 9),
            card.candidate_id,
        ),
    )
    recommended = next((card.candidate_id for card in ranked if not card.hard_blocked), ranked[0].candidate_id if ranked else None)
    return CopyCandidateRankingOutput(
        recommended_candidate_id=recommended,
        scorecards=scorecards,
        blocked_candidate_ids=[card.candidate_id for card in scorecards if card.hard_blocked],
        diversity_warnings=[f"near_duplicate:{left}:{right}" for left, right in sorted(set(duplicate_ids.values()))],
        metadata={"ranker": "copy_quality_v2"},
    )


def select_recommended_copy(candidates: list[CopyCandidate], ranking: CopyCandidateRankingOutput | None = None) -> CopyCandidate | None:
    if not candidates:
        return None
    ranking = ranking or rank_copy_candidates(candidates)
    selected_id = ranking.recommended_candidate_id
    return next((candidate for candidate in candidates if candidate.id == selected_id), candidates[0])


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
    candidates = output.candidates[: max(1, max_candidates)]
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
    if state and _invented_fact_detected(text, state):
        fact_penalty = 0.4
        hard_blocked = True
        warnings.append("unsupported_fact_detected")
        reasons.append("Copy appears to introduce unsupported price, discount, phone, or address facts.")
    length_penalty = _length_penalty(candidate, policy, warnings)
    diversity_penalty = 0.15 if duplicate else 0.0
    if duplicate:
        warnings.append("near_duplicate_candidate")
        reasons.append(f"Near duplicate with {duplicate[0] if duplicate[1] == candidate.id else duplicate[1]}.")
    tone_fit = 0.85 if any(term and term in text for term in policy.get("avoid_terms", [])) else 1.0
    if tone_fit < 1.0:
        warnings.append("business_tone_avoid_term_detected")
    action_clarity = 1.0 if candidate.cta else 0.7
    final = 1.0 - generic_penalty - fact_penalty - length_penalty - diversity_penalty
    final = final * tone_fit * action_clarity
    return CopyCandidateScoreCard(
        candidate_id=candidate.id,
        hard_blocked=hard_blocked,
        final_score=max(0.0, min(1.0, round(final, 3))),
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
    return any(token.lower() in normalized.lower() for token in GENERIC_META_TOKENS)


def find_near_duplicate_candidate_ids(candidates: list[CopyCandidate], threshold: float = 0.82) -> dict[str, tuple[str, str]]:
    duplicates: dict[str, tuple[str, str]] = {}
    for left_index, left in enumerate(candidates):
        for right in candidates[left_index + 1 :]:
            similarity = SequenceMatcher(None, _normalize_text(joined_candidate_text(left)), _normalize_text(joined_candidate_text(right))).ratio()
            if similarity >= threshold or (left.angle and left.angle == right.angle):
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
