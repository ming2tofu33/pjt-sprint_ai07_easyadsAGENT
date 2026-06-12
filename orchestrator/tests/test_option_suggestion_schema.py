"""Tests for P7-1: OptionSuggestionOutput schema, slug guards, and merge helpers."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from orchestrator.app.schemas.llm_marketing import OptionItem
from orchestrator.app.schemas.option_suggestion import (
    ELIGIBLE_FIELDS,
    MAX_OPTIONS_AFTER_MERGE,
    OPTION_SUGGESTION_CONFIDENCE_THRESHOLD,
    OptionSuggestionItem,
    OptionSuggestionOutput,
    is_field_eligible,
    is_slug_safe,
    label_for_dynamic_value,
    merge_options,
    passes_confidence_threshold,
    slugify,
    suggestion_to_option_item,
)


# ── slugify / is_slug_safe ───────────────────────────────────────────────

class TestSlugify:
    def test_ascii_passthrough(self):
        assert slugify("discount_event") == "discount_event"

    def test_uppercase_lowered(self):
        assert slugify("New_Launch") == "new_launch"

    def test_spaces_to_underscores(self):
        assert slugify("happy hour special") == "happy_hour_special"

    def test_hyphens_to_underscores(self):
        assert slugify("hair-cut-discount") == "hair_cut_discount"

    def test_korean_stripped(self):
        # Korean chars are not ASCII → stripped; only ASCII remnants survive.
        assert slugify("할인이벤트") == ""

    def test_mixed_korean_ascii(self):
        assert slugify("event_할인") == "event"

    def test_collapse_underscores(self):
        assert slugify("a___b") == "a_b"

    def test_strip_leading_trailing(self):
        assert slugify("__hello__") == "hello"

    def test_empty_string(self):
        assert slugify("") == ""

    def test_max_length(self):
        long = "a" * 100
        assert len(slugify(long)) == 64

    def test_special_chars(self):
        assert slugify("10% off!") == "10_off"


class TestIsSlugSafe:
    def test_valid_slug(self):
        assert is_slug_safe("discount_event") is True

    def test_valid_with_hyphens(self):
        assert is_slug_safe("hair-cut") is True

    def test_starts_with_digit(self):
        assert is_slug_safe("2for1_deal") is True

    def test_uppercase_rejected(self):
        assert is_slug_safe("Discount") is False

    def test_spaces_rejected(self):
        assert is_slug_safe("hello world") is False

    def test_korean_rejected(self):
        assert is_slug_safe("할인") is False

    def test_empty_rejected(self):
        assert is_slug_safe("") is False

    def test_starts_with_underscore_rejected(self):
        assert is_slug_safe("_leading") is False


# ── OptionSuggestionItem ─────────────────────────────────────────────────

class TestOptionSuggestionItem:
    def test_valid_item(self):
        item = OptionSuggestionItem(label="여름 한정 음료", value="summer_drink")
        assert item.label == "여름 한정 음료"
        assert item.value == "summer_drink"

    def test_slug_auto_sanitised(self):
        """A value with uppercase/spaces is auto-slugified by the validator."""
        item = OptionSuggestionItem(label="테스트", value="Hello World")
        assert item.value == "hello_world"

    def test_pure_korean_value_rejected(self):
        """A pure-Korean value slugifies to '' → rejected."""
        with pytest.raises(ValidationError, match="cannot be sanitized"):
            OptionSuggestionItem(label="테스트", value="할인이벤트")

    def test_empty_label_rejected(self):
        with pytest.raises(ValidationError):
            OptionSuggestionItem(label="", value="valid_slug")

    def test_empty_value_rejected(self):
        with pytest.raises(ValidationError):
            OptionSuggestionItem(label="라벨", value="")

    def test_long_label_rejected(self):
        with pytest.raises(ValidationError):
            OptionSuggestionItem(label="가" * 41, value="ok")

    def test_already_valid_slug_unchanged(self):
        item = OptionSuggestionItem(label="라벨", value="already_valid")
        assert item.value == "already_valid"


# ── OptionSuggestionOutput ───────────────────────────────────────────────

class TestOptionSuggestionOutput:
    def test_empty_output(self):
        out = OptionSuggestionOutput()
        assert out.options == []
        assert out.confidence == 0.0

    def test_valid_output(self):
        out = OptionSuggestionOutput(
            options=[
                OptionSuggestionItem(label="여름 음료", value="summer_drink"),
                OptionSuggestionItem(label="아이스크림", value="ice_cream"),
            ],
            confidence=0.85,
        )
        assert len(out.options) == 2
        assert out.confidence == 0.85

    def test_confidence_clamped_low(self):
        with pytest.raises(ValidationError):
            OptionSuggestionOutput(confidence=-0.1)

    def test_confidence_clamped_high(self):
        with pytest.raises(ValidationError):
            OptionSuggestionOutput(confidence=1.1)

    def test_max_options_exceeded(self):
        items = [
            OptionSuggestionItem(label=f"옵션{i}", value=f"opt_{i}")
            for i in range(7)
        ]
        with pytest.raises(ValidationError):
            OptionSuggestionOutput(options=items, confidence=0.8)

    def test_max_options_at_limit(self):
        items = [
            OptionSuggestionItem(label=f"옵션{i}", value=f"opt_{i}")
            for i in range(6)
        ]
        out = OptionSuggestionOutput(options=items, confidence=0.8)
        assert len(out.options) == 6


# ── is_field_eligible ────────────────────────────────────────────────────

class TestIsFieldEligible:
    @pytest.mark.parametrize("field", ["item_or_service", "promotion_goal", "target_persona"])
    def test_eligible(self, field):
        assert is_field_eligible(field) is True

    @pytest.mark.parametrize("field", [
        "business_type", "ad_format", "copy_generation_mode",
        "brand_tone", "region_type", "usp", "custom_request",
    ])
    def test_not_eligible(self, field):
        assert is_field_eligible(field) is False


# ── passes_confidence_threshold ──────────────────────────────────────────

class TestPassesConfidenceThreshold:
    def test_above_threshold(self):
        out = OptionSuggestionOutput(confidence=0.8)
        assert passes_confidence_threshold(out) is True

    def test_at_threshold(self):
        out = OptionSuggestionOutput(confidence=OPTION_SUGGESTION_CONFIDENCE_THRESHOLD)
        assert passes_confidence_threshold(out) is True

    def test_below_threshold(self):
        out = OptionSuggestionOutput(confidence=0.3)
        assert passes_confidence_threshold(out) is False


# ── suggestion_to_option_item ────────────────────────────────────────────

class TestSuggestionToOptionItem:
    def test_conversion(self):
        item = OptionSuggestionItem(label="펌 시술", value="perm_service")
        opt = suggestion_to_option_item(item, item_id=5)
        assert isinstance(opt, OptionItem)
        assert opt.id == 5
        assert opt.label == "펌 시술"
        assert opt.value == "perm_service"
        assert opt.description is None
        assert opt.recommended is False


# ── merge_options ────────────────────────────────────────────────────────

def _make_static() -> list[OptionItem]:
    """Minimal static options resembling item_or_service registry."""
    return [
        OptionItem(id=1, label="대표 메뉴", value="signature_item"),
        OptionItem(id=2, label="신상품", value="new_item"),
        OptionItem(id=3, label="패키지/세트", value="bundle"),
        OptionItem(id=4, label="직접 입력", value="custom"),
    ]


def _make_dynamic() -> list[OptionSuggestionItem]:
    return [
        OptionSuggestionItem(label="여름 한정 음료", value="summer_drink"),
        OptionSuggestionItem(label="시그니처 라떼", value="signature_latte"),
    ]


class TestMergeOptions:
    def test_basic_merge(self):
        result = merge_options(_make_static(), _make_dynamic())
        values = [o.value for o in result]
        # Static first (minus custom), then dynamic, then custom last
        assert values == [
            "signature_item", "new_item", "bundle",
            "summer_drink", "signature_latte",
            "custom",
        ]

    def test_ids_sequential(self):
        result = merge_options(_make_static(), _make_dynamic())
        assert [o.id for o in result] == list(range(1, len(result) + 1))

    def test_custom_always_last(self):
        result = merge_options(_make_static(), _make_dynamic())
        assert result[-1].value == "custom"
        assert result[-1].label == "직접 입력"

    def test_dedup_by_value(self):
        """Dynamic option with same value as static → skipped."""
        dups = [OptionSuggestionItem(label="대표 메뉴 (특별)", value="signature_item")]
        result = merge_options(_make_static(), dups)
        values = [o.value for o in result]
        assert values.count("signature_item") == 1

    def test_dedup_by_label(self):
        """Dynamic option with same label as static → skipped."""
        dups = [OptionSuggestionItem(label="대표 메뉴", value="main_dish")]
        result = merge_options(_make_static(), dups)
        labels = [o.label for o in result]
        assert labels.count("대표 메뉴") == 1

    def test_dynamic_custom_skipped(self):
        """LLM suggesting value='custom' is silently dropped."""
        bad = [OptionSuggestionItem(label="기타", value="custom")]
        result = merge_options(_make_static(), bad)
        custom_items = [o for o in result if o.value == "custom"]
        assert len(custom_items) == 1
        assert custom_items[0].label == "직접 입력"  # the original

    def test_cap_respected(self):
        many = [
            OptionSuggestionItem(label=f"추가{i}", value=f"extra_{i}")
            for i in range(10)
        ]
        result = merge_options(_make_static(), many, max_total=6)
        assert len(result) == 6
        assert result[-1].value == "custom"

    def test_empty_dynamic(self):
        """Empty dynamic list → result identical to static (re-indexed)."""
        result = merge_options(_make_static(), [])
        assert [o.value for o in result] == [
            "signature_item", "new_item", "bundle", "custom",
        ]
        assert [o.id for o in result] == [1, 2, 3, 4]

    def test_no_static_custom(self):
        """If static list has no custom option, none is added."""
        static_no_custom = [
            OptionItem(id=1, label="A", value="a"),
            OptionItem(id=2, label="B", value="b"),
        ]
        dyn = [OptionSuggestionItem(label="C", value="c")]
        result = merge_options(static_no_custom, dyn)
        assert result[-1].value == "c"  # no custom appended

    def test_max_total_default(self):
        """Default cap is MAX_OPTIONS_AFTER_MERGE."""
        assert MAX_OPTIONS_AFTER_MERGE == 8


# ── label_for_dynamic_value ──────────────────────────────────────────────

class TestLabelForDynamicValue:
    def test_found(self):
        cache = {
            "item_or_service": [
                {"label": "여름 한정 음료", "value": "summer_drink"},
                {"label": "시그니처 라떼", "value": "signature_latte"},
            ]
        }
        assert label_for_dynamic_value("item_or_service", "summer_drink", cache) == "여름 한정 음료"

    def test_not_found_value(self):
        cache = {"item_or_service": [{"label": "A", "value": "a"}]}
        assert label_for_dynamic_value("item_or_service", "nonexistent", cache) is None

    def test_not_found_field(self):
        cache = {"other_field": [{"label": "A", "value": "a"}]}
        assert label_for_dynamic_value("item_or_service", "a", cache) is None

    def test_none_cache(self):
        assert label_for_dynamic_value("item_or_service", "a", None) is None

    def test_empty_cache(self):
        assert label_for_dynamic_value("item_or_service", "a", {}) is None
