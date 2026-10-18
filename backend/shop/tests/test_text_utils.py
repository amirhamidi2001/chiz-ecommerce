"""
Tests for shop.text_utils.normalize_persian_text.

The Persian/Arabic letters below are REAL characters, not escapes, so the
test file shows what is being tested. Because lookalike letters are exactly
what this feature is about, the first test class pins every literal to its
intended code point and Unicode name — if an editor, formatter or
copy-paste ever swaps one for its lookalike, THAT test fails loudly instead
of the others quietly testing the wrong thing.

Invisible characters are written as escapes (a literal ZWNJ in source is
unreadable) and pinned the same way.
"""

import unicodedata

import pytest
from shop.text_utils import normalize_persian_text

ARABIC_KAF = "ك"  # U+0643
PERSIAN_KEHEH = "ک"  # U+06A9
ARABIC_YEH = "ي"  # U+064A
PERSIAN_YEH = "ی"  # U+06CC
ALEF_MAKSURA = "ى"  # U+0649
HEH_YEH_ABOVE = "ۀ"  # U+06C0
PLAIN_HEH = "ه"  # U+0647

ZWSP = "\u200b"
ZWNJ = "\u200c"
ZWJ = "\u200d"
BOM = "\ufeff"


class TestFixturesAreTheIntendedCharacters:
    @pytest.mark.parametrize(
        "char, codepoint, name",
        [
            (ARABIC_KAF, 0x0643, "ARABIC LETTER KAF"),
            (PERSIAN_KEHEH, 0x06A9, "ARABIC LETTER KEHEH"),
            (ARABIC_YEH, 0x064A, "ARABIC LETTER YEH"),
            (PERSIAN_YEH, 0x06CC, "ARABIC LETTER FARSI YEH"),
            (ALEF_MAKSURA, 0x0649, "ARABIC LETTER ALEF MAKSURA"),
            (HEH_YEH_ABOVE, 0x06C0, "ARABIC LETTER HEH WITH YEH ABOVE"),
            (PLAIN_HEH, 0x0647, "ARABIC LETTER HEH"),
            (ZWSP, 0x200B, "ZERO WIDTH SPACE"),
            (ZWNJ, 0x200C, "ZERO WIDTH NON-JOINER"),
            (ZWJ, 0x200D, "ZERO WIDTH JOINER"),
            (BOM, 0xFEFF, "ZERO WIDTH NO-BREAK SPACE"),
        ],
    )
    def test_literal_is_the_intended_code_point(self, char, codepoint, name):
        assert len(char) == 1
        assert ord(char) == codepoint
        assert unicodedata.name(char) == name


class TestCharacterMappings:
    def test_arabic_kaf_becomes_persian_keheh(self):
        assert normalize_persian_text(ARABIC_KAF) == PERSIAN_KEHEH

    def test_arabic_yeh_becomes_persian_farsi_yeh(self):
        assert normalize_persian_text(ARABIC_YEH) == PERSIAN_YEH

    def test_alef_maksura_becomes_persian_farsi_yeh(self):
        assert normalize_persian_text(ALEF_MAKSURA) == PERSIAN_YEH

    def test_heh_with_yeh_above_becomes_plain_heh(self):
        assert normalize_persian_text(HEH_YEH_ABOVE) == PLAIN_HEH

    def test_whole_word_with_arabic_variants_matches_persian_spelling(self):
        arabic_typed = "كرم مرطوب كننده آرايشي"
        persian_typed = "کرم مرطوب کننده آرایشی"
        assert arabic_typed != persian_typed  # genuinely different strings
        assert normalize_persian_text(arabic_typed) == persian_typed

    def test_canonical_persian_characters_are_left_alone(self):
        text = "کرم آرایشی"
        assert normalize_persian_text(text) == text

    def test_is_idempotent(self):
        once = normalize_persian_text(f"{ARABIC_KAF}{ARABIC_YEH}{ZWNJ}{HEH_YEH_ABOVE}")
        assert normalize_persian_text(once) == once


class TestZeroWidthStripping:
    @pytest.mark.parametrize(
        "zero_width", [ZWSP, ZWNJ, ZWJ, BOM], ids=["ZWSP", "ZWNJ", "ZWJ", "BOM"]
    )
    def test_each_zero_width_character_is_stripped(self, zero_width):
        assert normalize_persian_text(f"ضد{zero_width}آفتاب") == "ضدآفتاب"

    def test_zero_width_only_string_becomes_empty(self):
        assert normalize_persian_text(f"{ZWSP}{ZWNJ}{ZWJ}{BOM}") == ""

    def test_leading_and_trailing_zero_width_are_stripped(self):
        assert normalize_persian_text(f"{BOM}کرم{ZWNJ}") == "کرم"

    def test_ordinary_space_is_not_touched(self):
        assert normalize_persian_text("کرم  دست") == "کرم  دست"


class TestSafeNoOps:
    @pytest.mark.parametrize(
        "text",
        [
            "Matte Lipstick",
            "L'Oréal Paris — SPF 50+ (100ml)",
            "123 456",
            "ASCII only, with punctuation!?",
            "日本語のテキスト",
            "Привет мир",
        ],
    )
    def test_text_without_targeted_characters_is_unchanged(self, text):
        assert normalize_persian_text(text) == text

    def test_empty_string(self):
        assert normalize_persian_text("") == ""

    def test_none_does_not_raise(self):
        assert normalize_persian_text(None) is None
