"""Final composite copy revision node."""

from __future__ import annotations

from typing import Any

from orchestrator.app.graph.state import MarketingState


GENERIC_PHRASES = {"best quality", "limited time", "special offer", "amazing", "premium experience"}


def final_copy_revision_node(state: MarketingState) -> dict[str, Any]:
    plan = state.get("final_composite_revision_plan") or {}
    action = str(plan.get("action") or state.get("final_composite_rerun_action") or "shorten_copy")
    marketing_copy = dict(state.get("marketing_copy") or {})
    if state.get("copy_generation_mode") == "custom_input":
        return {
            "final_copy_revision_result": {
                "status": "manual_review",
                "reason": "custom_input_not_rewritten",
                "suggested_copy": _shortened_copy(marketing_copy),
            },
            "status": "manual_review",
        }

    revised = _rewritten_copy(marketing_copy) if action == "rewrite_copy" else _shortened_copy(marketing_copy)
    return {
        "marketing_copy": revised,
        "final_copy_revision_result": {
            "status": "revised",
            "action": action,
            "preserved_claims": _preserved_claims(marketing_copy, revised),
            "removed_phrases": _removed_phrases(marketing_copy, revised),
            "t2i_bypass": True,
        },
        "final_composite_partial_rerun": True,
        "final_composite_rerun_action": action,
        "reuse_existing_background": True,
        "status": "final_copy_revised",
    }


def _shortened_copy(copy: dict[str, Any]) -> dict[str, Any]:
    return {
        **copy,
        "headline": _compress(str(copy.get("headline") or ""), max_chars=22),
        "subcopy": _compress(str(copy.get("subcopy") or copy.get("body") or ""), max_chars=34),
        "cta": _compress(str(copy.get("cta") or ""), max_chars=12),
    }


def _rewritten_copy(copy: dict[str, Any]) -> dict[str, Any]:
    headline = str(copy.get("headline") or "Macaron Collection")
    subcopy = str(copy.get("subcopy") or copy.get("body") or "부드러운 색감의 마카롱 컬렉션")
    cta = str(copy.get("cta") or "메뉴 보기")
    cleaned = {
        **copy,
        "headline": _compress(_remove_generic(headline) or "Macaron Collection", max_chars=24),
        "subcopy": _compress(_remove_generic(subcopy) or "부드러운 색감의 마카롱 컬렉션", max_chars=36),
        "cta": _compress(_remove_generic(cta) or "메뉴 보기", max_chars=12),
    }
    return cleaned


def _compress(value: str, *, max_chars: int) -> str:
    text = " ".join(value.replace("…", "").replace("...", "").split())
    if len(text) <= max_chars:
        return text
    words = text.split()
    output = ""
    for word in words:
        candidate = f"{output} {word}".strip()
        if len(candidate) > max_chars:
            break
        output = candidate
    return output or text[:max_chars].rstrip()


def _remove_generic(value: str) -> str:
    text = value
    for phrase in GENERIC_PHRASES:
        text = text.replace(phrase, "").replace(phrase.title(), "")
    return " ".join(text.split())


def _removed_phrases(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    removed = []
    before_text = " ".join(str(before.get(key) or "") for key in ("headline", "subcopy", "cta"))
    after_text = " ".join(str(after.get(key) or "") for key in ("headline", "subcopy", "cta"))
    for phrase in GENERIC_PHRASES:
        if phrase in before_text.lower() and phrase not in after_text.lower():
            removed.append(phrase)
    return removed


def _preserved_claims(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    before_text = " ".join(str(before.get(key) or "") for key in ("headline", "subcopy", "cta"))
    after_text = " ".join(str(after.get(key) or "") for key in ("headline", "subcopy", "cta"))
    return [word for word in before_text.split() if len(word) > 3 and word in after_text][:5]
