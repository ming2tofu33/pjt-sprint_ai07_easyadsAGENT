from orchestrator.app.t2i.engine_policy import (
    choose_default_engine_for_plan,
    get_image_engine_policy,
    is_engine_allowed_for_plan,
    normalize_image_plan,
    resolve_requested_engines_for_plan,
)


def test_free_plan_allows_sd35_large_and_flux2_klein():
    policy = get_image_engine_policy("free")

    assert policy.allowed_engines == ["sd35_large", "flux2_klein_4b"]
    assert is_engine_allowed_for_plan("sd35_large", "free") is True
    assert is_engine_allowed_for_plan("flux", "free") is True
    assert is_engine_allowed_for_plan("flux2_klein_4b", "free") is True


def test_free_plan_blocks_openai_image_engines():
    assert is_engine_allowed_for_plan("gpt_image_1", "free") is False
    assert is_engine_allowed_for_plan("gpt_image_2", "free") is False


def test_economic_plan_allows_all_engines():
    policy = get_image_engine_policy("economic")

    assert policy.allowed_engines == ["gpt_image_1", "sd35_large", "flux2_klein_4b"]
    assert policy.allow_external_api is True
    assert policy.allow_parallel_comparison is False


def test_premium_plan_allows_all_engines_and_parallel_comparison():
    policy = get_image_engine_policy("premium")

    assert policy.allowed_engines == ["gpt_image_1", "gpt_image_2", "sd35_large", "flux2_klein_4b"]
    assert policy.allow_parallel_comparison is True
    assert resolve_requested_engines_for_plan(plan="premium", include_comparison=True) == [
        "gpt_image_1",
        "gpt_image_2",
        "sd35_large",
        "flux2_klein_4b",
    ]


def test_unknown_plan_falls_back_to_free():
    assert normalize_image_plan(None) == "free"
    assert normalize_image_plan("") == "free"
    assert normalize_image_plan("unknown") == "free"
    assert get_image_engine_policy("unknown").plan == "free"


def test_unknown_requested_engine_is_ignored():
    assert resolve_requested_engines_for_plan(
        plan="premium",
        requested_engines=["unknown", "flux"],
    ) == ["flux2_klein_4b"]


def test_duplicate_requested_engines_are_deduplicated():
    assert resolve_requested_engines_for_plan(
        plan="premium",
        requested_engines=["flux", "flux", "sd35_large"],
    ) == ["flux2_klein_4b", "sd35_large"]


def test_default_engine_by_plan():
    assert choose_default_engine_for_plan("free") == "flux2_klein_4b"
    assert choose_default_engine_for_plan("economic") == "gpt_image_1"
    assert choose_default_engine_for_plan("premium") == "gpt_image_1"


def test_plan_aliases():
    assert normalize_image_plan("economy") == "economic"
    assert normalize_image_plan("standard") == "economic"
    assert normalize_image_plan("pro") == "premium"
    assert normalize_image_plan("business") == "premium"
