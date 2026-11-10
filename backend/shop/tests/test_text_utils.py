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

import random
import re
import unicodedata

import pytest
from django.utils.text import slugify
from shop.text_utils import LOANWORD_GLOSSARY, normalize_persian_text, persian_slugify

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


# ─────────────────────────────────────────────────────────────────────────────
# persian_slugify  (Task 14.4.1.2 / ADR 0002)
# ─────────────────────────────────────────────────────────────────────────────
# `glossary={}` disables the loanword glossary and exposes the pure letter-table
# output; the default glossary is what products actually get.

VALID_SLUG = re.compile(r"^[a-z0-9_]+(-[a-z0-9_]+)*$")
NO_GLOSSARY = {}

# Every Persian test input below that is NOT deliberately Arabic. A guard test
# asserts they are already canonical, so a lookalike letter pasted into this
# file fails loudly instead of quietly testing the wrong string.
PERSIAN_INPUTS = [
    "سرم ویتامین سی",
    "سرم ویتامین C",
    "ماسک مو کراتین",
    "مرطوب" + ZWNJ + "کننده",
    "ضدآفتاب بی" + ZWNJ + "رنگ SPF50+ مناسب پوست چرب",
    "رژ لب مایع ۱۵۰ میلی" + ZWNJ + "لیتر",
]


class TestPersianSlugifyInputsAreCanonical:
    @pytest.mark.parametrize("text", PERSIAN_INPUTS)
    def test_inputs_survive_normalisation_unchanged(self, text):
        assert normalize_persian_text(text.replace(ZWNJ, " ")) == text.replace(
            ZWNJ, " "
        )

    def test_glossary_keys_are_canonical_and_values_slug_safe(self):
        for key, value in LOANWORD_GLOSSARY.items():
            assert (
                normalize_persian_text(key) == key
            ), f"non-canonical glossary key {key!r}"
            assert ZWNJ not in key
            assert VALID_SLUG.match(value), f"bad glossary value {value!r}"


class TestPersianSlugifyHeadlineCases:
    """The cases the task is judged by."""

    def test_purely_persian_name(self):
        # Glossary: سرم=serum, "ویتامین سی"=vitamin-c.
        assert persian_slugify("سرم ویتامین سی") == "serum-vitamin-c"

    def test_purely_persian_name_letter_table_only(self):
        # What the hand-built table alone produces (no vocabulary knowledge):
        # short vowels are unwritten in Persian, so سرم -> "srm", never "serum".
        assert (
            persian_slugify("سرم ویتامین سی", glossary=NO_GLOSSARY) == "srm-vitamin-si"
        )

    def test_mixed_script_keeps_the_latin_C(self):
        """THE key test (Task 14.4.1.1's mixed-script requirement)."""
        assert persian_slugify("سرم ویتامین C") == "serum-vitamin-c"

    def test_mixed_script_latin_part_is_not_run_through_the_letter_table(self):
        # With no glossary the Persian words fall back to the table, and the
        # Latin "C" is still exactly "c" (lower-cased by slug convention), not
        # mangled and not dropped.
        out = persian_slugify("سرم ویتامین C", glossary=NO_GLOSSARY)
        assert out == "srm-vitamin-c"
        assert out.split("-")[-1] == "c"

    def test_persian_and_latin_spellings_of_the_same_name_agree(self):
        assert persian_slugify("سرم ویتامین سی") == persian_slugify("سرم ویتامین C")

    def test_persian_numerals_become_western_digits(self):
        assert (
            persian_slugify("رژ لب مایع ۱۵۰ میلی" + ZWNJ + "لیتر")
            == "rzh-lb-may-150-mili-litr"
        )
        assert persian_slugify("۱۲۳۴۵۶۷۸۹۰") == "1234567890"

    def test_arabic_indic_numerals_too(self):
        assert persian_slugify("٠١٢٣٤٥٦٧٨٩") == "0123456789"


class TestPersianSlugifyMixedScript:
    def test_ascii_brand_and_digits_pass_through_lowercased(self):
        assert persian_slugify("ضدآفتاب SPF50+ PA++++") == "zdaftab-spf50-pa"

    def test_latin_brand_with_apostrophe_and_accent(self):
        assert (
            persian_slugify("L'Oréal Paris کرم پودر مات")
            == "loreal-paris-cream-powder-mat"
        )

    def test_glued_script_boundary_is_split(self):
        assert persian_slugify("ویتامینC") == "vitamin-c"
        assert persian_slugify("ماسک۲۵۰ml") == "mask-250ml"
        assert persian_slugify("سرم C۱۰") == "serum-c10"

    def test_realistic_long_name(self):
        name = "ضدآفتاب بی" + ZWNJ + "رنگ SPF50+ مناسب پوست چرب"
        assert persian_slugify(name) == "zdaftab-bi-rng-spf50-mnasb-pust-chrb"


class TestPersianSlugifyZwnj:
    def test_zwnj_is_a_word_boundary_not_deleted(self):
        joined = persian_slugify("مرطوب" + ZWNJ + "کننده")
        assert joined == "mrtub-knnde"
        assert joined == persian_slugify("مرطوب کننده")  # same as the spaced spelling

    def test_other_zero_width_characters_are_stripped(self):
        assert persian_slugify("سرم" + ZWSP + "کرم") == "srmkrm"
        assert persian_slugify("سرم" + ZWJ + "کرم") == "srmkrm"

    def test_arabic_letter_variants_normalised_first(self):
        # ك/ي (Arabic) must give the same slug as ک/ی (Persian): reuses
        # normalize_persian_text, not a second normaliser.
        assert (
            persian_slugify(ARABIC_KAF + "رم")
            == persian_slugify(PERSIAN_KEHEH + "رم")
            == "cream"
        )
        arabic_ali = "عل" + ARABIC_YEH
        assert (
            persian_slugify(arabic_ali) == persian_slugify("عل" + PERSIAN_YEH) == "ali"
        )


class TestPersianSlugifyLetterTable:
    @pytest.mark.parametrize(
        "word, expected",
        [
            ("چشم", "chshm"),  # digraphs
            ("خ", "kh"),
            ("ژ", "zh"),
            ("غ", "gh"),
            ("ق", "q"),
            ("ویتامین", "vitamin"),  # و initial = v ...
            ("پوست", "pust"),  # ... elsewhere = u
            ("مو", "mu"),
            ("و", "va"),  # the conjunction "and"
            ("سی", "si"),  # ی = i ...
            ("میلی", "mili"),
            ("مایع", "may"),  # ... but y after ا
            ("یک", "yk"),  # ... and word-initially
            ("ماه", "mah"),  # final ه = h after a vowel letter ...
            ("روزانه", "ruzane"),  # ... e after a consonant
            ("کننده", "knnde"),
            ("ه", "h"),
            ("عطر", "atr"),  # initial ع = a ...
            ("معمولی", "mmuli"),  # ... dropped elsewhere
        ],
    )
    def test_rules(self, word, expected):
        assert persian_slugify(word, glossary=NO_GLOSSARY) == expected

    @pytest.mark.parametrize("letter", "ابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی")
    def test_every_persian_letter_transliterates_to_something(self, letter):
        out = persian_slugify(letter, glossary=NO_GLOSSARY)
        assert out and VALID_SLUG.match(out)


class TestPersianSlugifyGlossary:
    def test_phrase_beats_single_words(self):
        assert persian_slugify("ویتامین سی") == "vitamin-c"
        assert persian_slugify("ویتامین سی", glossary=NO_GLOSSARY) == "vitamin-si"

    def test_ambiguous_word_alone_is_not_the_letter_c(self):
        # "سی" means both the letter C and the number thirty; only the phrase
        # "ویتامین سی" may become "c".
        assert persian_slugify("سی") == "si"
        assert persian_slugify("سی ساله") == "si-sale"

    def test_loanwords_and_brands(self):
        assert persian_slugify("ماسک مو کراتین") == "mask-mu-keratin"
        assert persian_slugify("نیوآ") == persian_slugify("نیویا") == "nivea"


class TestPersianSlugifyLatinParityWithDjango:
    """For Latin input the result must match Django's slugify (existing tests pin this)."""

    @pytest.mark.parametrize(
        "text",
        [
            "Home & Kitchen",
            "Smart Watch Pro",
            "Under Armour",
            "Cool Shoes",
            "Men's T-Shirts",
            "iPhone 15 Pro Max",
            "  spaced   out  ",
            "Already-a-slug",
            "snake_case_name",
            "UPPER lower",
        ],
    )
    def test_matches_django_slugify(self, text):
        assert persian_slugify(text) == slugify(text)


class TestPersianSlugifyEdgeCases:
    @pytest.mark.parametrize("text", [None, "", "   ", "!!!", "!!! 😀", "،؛؟«»"])
    def test_nothing_usable_returns_empty_string(self, text):
        assert persian_slugify(text) == ""

    def test_max_length_cuts_at_a_word_boundary(self):
        out = persian_slugify("ماسک " * 60, max_length=20)
        assert out == "mask-mask-mask-mask"

    def test_max_length_on_one_long_word_hard_cuts(self):
        assert persian_slugify("ا" * 100, max_length=10) == "a" * 10

    def test_max_length_never_leaves_a_dangling_hyphen(self):
        for n in range(1, 40):
            out = persian_slugify("ماسک ماسک ماسک ماسک", max_length=n)
            assert len(out) <= n and not out.startswith("-") and not out.endswith("-")

    def test_idempotent_on_valid_slugs(self):
        for slug in ("serum-vitamin-c", "spf50", "a_b-c", "loreal-paris"):
            assert persian_slugify(slug) == slug


class TestPersianSlugifyAlwaysSafe:
    """Fuzz: whatever goes in, the output is empty or a valid ASCII slug."""

    ALPHABET = list(
        "ابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهیآأإءئؤةكيى"
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩ABCabc xyz019 -_'.,+/()&!؟،"
    ) + [ZWNJ, ZWSP, ZWJ, "\u064e", "\u0640", "é", "ñ", "😀", "中"]

    def test_random_inputs(self):
        rng = random.Random(14_4_1_2)
        for _ in range(3000):
            text = "".join(rng.choice(self.ALPHABET) for _ in range(rng.randint(1, 40)))
            out = persian_slugify(text)
            assert out == "" or VALID_SLUG.match(out), (text, out)
            assert out.isascii()
            assert out == out.lower()
