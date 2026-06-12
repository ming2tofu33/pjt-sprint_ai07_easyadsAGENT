"""Tests for the canonical ad_format resolver and write-through setter."""

from orchestrator.app.graph.state import resolve_requested_ad_format, set_requested_ad_format


def _state(*, selected=None, brief=None, extra=None):
    state: dict = {"current_brief": dict(brief or {}), "context": {"extra": dict(extra or {})}}
    if selected is not None:
        state["selected_ad_format"] = selected
    return state


def test_returns_none_when_nothing_is_set():
    assert resolve_requested_ad_format(_state()) is None


def test_selected_ad_format_wins_over_everything():
    state = _state(
        selected="kakao_feed",
        brief={"requested_ad_format": "instagram_feed", "ad_format": "naver_blog"},
        extra={"ad_format": "instagram_story"},
    )
    assert resolve_requested_ad_format(state) == "kakao_feed"


def test_brief_requested_beats_context_extra():
    state = _state(brief={"requested_ad_format": "instagram_feed"}, extra={"ad_format": "instagram_story"})
    assert resolve_requested_ad_format(state) == "instagram_feed"


def test_context_extra_beats_legacy_brief_ad_format():
    state = _state(brief={"ad_format": "naver_blog"}, extra={"ad_format": "instagram_story"})
    assert resolve_requested_ad_format(state) == "instagram_story"


def test_legacy_brief_ad_format_is_last_resort():
    state = _state(brief={"ad_format": "naver_blog"})
    assert resolve_requested_ad_format(state) == "naver_blog"


def test_handles_missing_context_and_brief_keys():
    assert resolve_requested_ad_format({}) is None
    assert resolve_requested_ad_format({"context": None, "current_brief": None}) is None


def test_set_writes_both_mirrors():
    brief: dict = {}
    extra: dict = {}
    set_requested_ad_format(brief, extra, "instagram_feed")
    assert brief["requested_ad_format"] == "instagram_feed"
    assert extra["ad_format"] == "instagram_feed"


def test_set_overwrites_divergent_mirrors():
    brief = {"requested_ad_format": "naver_blog"}
    extra = {"ad_format": "instagram_story"}
    set_requested_ad_format(brief, extra, "kakao_feed")
    assert brief["requested_ad_format"] == "kakao_feed"
    assert extra["ad_format"] == "kakao_feed"
