"""Field-aware normalization for intake item/service candidates."""

from __future__ import annotations

import re
from dataclasses import dataclass


_TRAILING_ARTIFACT_RE = re.compile(
    r"(?:\s+|^)(?P<fragment>"
    r"(?:광고|홍보|포스터|배너|전단지|인스타|상세페이지)\s*(?:이미지|사진|시안|홍보물)?"
    r"|(?:모집|오픈|출시)\s*(?:광고|홍보|포스터|배너|전단지|이미지|사진|홍보물)"
    r"|이미지|사진|포스터|배너|전단지|홍보물|시안"
    r")$",
    re.IGNORECASE,
)

_REQUEST_TAIL_RE = re.compile(
    r"\s*(?:로|으로)?\s*(?:광고|홍보)?\s*(?:만들어\s*줘|만들어줘|제작해\s*줘|제작해줘|추천해\s*줘|추천해줘)\s*$",
    re.IGNORECASE,
)

_ARTIFACT_CONNECTOR_RE = re.compile(
    r"(?:\s+|^)(?P<artifact>이미지|사진|포스터|배너|전단지|홍보물|시안)(?:으)?로\s+(?P<clause>[^,.!?]{1,20})$",
    re.IGNORECASE,
)

_CONFIRMED_SOURCES = frozenset({"confirmed_context", "confirmed_user_answer"})


@dataclass(frozen=True)
class ItemCandidateNormalization:
    raw_value: str | None
    normalized_value: str | None
    removed_fragments: tuple[str, ...]
    reason_codes: tuple[str, ...]
    changed: bool
    confidence: float


def normalize_item_or_service_candidate(
    candidate: str | None,
    *,
    source_text: str,
    candidate_source: str,
    ad_format: str | None,
) -> ItemCandidateNormalization:
    del ad_format
    raw = _clean(candidate)
    if not raw:
        return ItemCandidateNormalization(raw, None, (), (), False, 1.0)

    if candidate_source in _CONFIRMED_SOURCES:
        has_artifact = bool(_TRAILING_ARTIFACT_RE.search(raw))
        return ItemCandidateNormalization(
            raw,
            raw,
            (),
            ("confirmed_value_contains_artifact_term",) if has_artifact else (),
            False,
            1.0,
        )

    value = raw
    removed: list[str] = []
    reasons: list[str] = []

    request_match = _REQUEST_TAIL_RE.search(value)
    if request_match:
        fragment = value[request_match.start() :].strip()
        value = value[: request_match.start()].strip()
        if fragment:
            removed.append(fragment)
            reasons.append("removed_request_tail")

    connector_match = _ARTIFACT_CONNECTOR_RE.search(value)
    if connector_match and _connector_clause_is_context(connector_match.group("clause"), source_text):
        subject = value[: connector_match.start()].strip(" ,.!?:;-/")
        if subject and _has_semantic_subject(subject):
            value = subject
            removed.append(connector_match.group("artifact").strip())
            reasons.append("removed_creative_artifact_connector")

    artifact_match = _TRAILING_ARTIFACT_RE.search(value)
    if artifact_match:
        subject = value[: artifact_match.start()].strip(" ,.!?:;-/")
        fragment = artifact_match.group("fragment").strip()
        if subject and _has_semantic_subject(subject) and _artifact_is_output_request(fragment, source_text):
            value = subject
            removed.append(fragment)
            reasons.append("removed_trailing_creative_artifact")

    normalized = _clean(value)
    changed = normalized != raw
    return ItemCandidateNormalization(
        raw,
        normalized,
        tuple(removed),
        tuple(dict.fromkeys(reasons)),
        changed,
        0.96 if changed else 1.0,
    )


def _artifact_is_output_request(fragment: str, source_text: str) -> bool:
    source = _clean(source_text) or ""
    if not source:
        return True
    return fragment in source and bool(
        re.search(r"(?:만들어|제작|광고|홍보|모집|오픈|출시|추천)", source, re.IGNORECASE)
    )


def _connector_clause_is_context(clause: str, source_text: str) -> bool:
    if re.search(r"(?:서비스|솔루션|컨설팅|메이킹|촬영|디자인|수업|강의|상담)$", clause):
        return False
    return bool(re.search(r"(?:만들어|제작|광고|홍보|추천)", source_text, re.IGNORECASE))


def _has_semantic_subject(value: str) -> bool:
    return bool(re.search(r"[가-힣A-Za-z0-9]", value)) and len(value.strip()) >= 2


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", " ", str(value)).strip(" ,.!?:;")
    return normalized or None
