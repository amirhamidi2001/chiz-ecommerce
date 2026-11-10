"""
shop/text_utils.py
───────────────────
Text normalisation for Persian/Arabic-script product text and search input.

The SAME function is applied on both sides of search — to stored text at save
time (Product / Brand / Category .save(), which then feeds search_vector) and
to the customer's query (ProductListView.get_queryset) — so equivalent text
always produces equivalent lexemes.

Code points below were checked against the Unicode character database
(names via Python's unicodedata, Unicode 15.0) and against published
references (Unicode mailing-list statement that ISIRI 6219 requires U+06A9
for the Persian kaf; Apache Lucene's Persian/Sorani normalisers use the same
letters).
"""

import re
import unicodedata

# Arabic-script variant -> canonical Persian-script character
_CHAR_NORMALIZATION_MAP = {
    "\u0643": "\u06a9",  # ARABIC LETTER KAF           -> ARABIC LETTER KEHEH     (ك -> ک)
    "\u064a": "\u06cc",  # ARABIC LETTER YEH           -> ARABIC LETTER FARSI YEH (ي -> ی)
    "\u0649": "\u06cc",  # ARABIC LETTER ALEF MAKSURA  -> ARABIC LETTER FARSI YEH (ى -> ی)
    "\u06c0": "\u0647",  # ARABIC LETTER HEH WITH YEH ABOVE -> ARABIC LETTER HEH  (ۀ -> ه)
}
_CHAR_TRANSLATION_TABLE = str.maketrans(_CHAR_NORMALIZATION_MAP)

# ZWSP, ZWNJ, ZWJ, BOM / ZWNBSP
_ZERO_WIDTH_CHARS = re.compile("[\u200b\u200c\u200d\ufeff]")


def normalize_persian_text(text):
    """
    Normalise Persian/Arabic script variants and strip zero-width characters
    so equivalent text matches consistently regardless of input-method
    quirks. A no-op for text containing none of the targeted characters
    (so safe on Latin text), and falsy input (None, "") is returned as-is.

    NOTE: this is lossy by design. U+06C0 -> U+0647 drops the ezafe mark,
    and removing ZWNJ removes information that affects how Persian text is
    *displayed* (e.g. "می‌خواهم" becomes "میخواهم"). That is why it is also
    applied to the stored text: stored and queried text must be reduced the
    same way.
    """
    if not text:
        return text
    return _ZERO_WIDTH_CHARS.sub("", text.translate(_CHAR_TRANSLATION_TABLE))


# ─────────────────────────────────────────────────────────────────────────────
# persian_slugify  (Task 14.4.1.2 / ADR 0002)
# ─────────────────────────────────────────────────────────────────────────────
#
# WHY THIS EXISTS. Django's slugify() without allow_unicode deletes every
# non-ASCII character, so a Persian name produced an EMPTY slug ("سرم ویتامین
# سی" -> ""), a second such Brand/Category crashed with IntegrityError, and
# Product slugs came out as "", "-1", "-2". ADR 0002 chose Latin-script slugs.
#
# WHY A HAND-BUILT TABLE AND NOT A LIBRARY (evaluated 2026-11-09 on cosmetics
# names; maintenance from PyPI release dates):
#   * `trans`  (last release 2016, has a Farsi table): outright broken, it has
#     no mapping for ک پ چ گ ژ and emits "_" ("کرم" -> "_rm").
#   * `transliterate` (2018): no Persian support. `finglish`: converts the
#     opposite direction. `parstalk`: 2.5 kB toy whose documented API is absent.
#   * Unidecode / anyascii / python-slugify (all maintained): generic skeletons
#     that disagree with each other (رژ -> "rj" vs "rzh"), drop ع ("عطر" ->
#     "tr") and cannot be tuned. A dependency upgrade would silently change slugs.
#   * PyICU "Persian-Latin/BGN": best of the rest, but needs libicu + a C build,
#     leaves ا / آ untransliterated ("vytاmyn") and emits non-ASCII marks.
#   None of them can treat ZWNJ as a word boundary or know loanword spellings.
#   A ~35-entry letter table is small enough to own, test and keep stable.
#
# WHAT THE OUTPUT IS (and is not). Persian does not write short vowels, so NO
# mechanical transliteration can recover "serum" from سرم. The letter table
# therefore produces a readable CONSONANT-PLUS-LONG-VOWEL form ("srm-vitamin-si"),
# and LOANWORD_GLOSSARY supplies the conventional Latin spelling for known
# vocabulary ("serum-vitamin-c"). The glossary is a seed list, meant to grow.

_ZWNJ = "\u200c"

# Persian (U+06F0..) and Arabic-Indic (U+0660..) digits -> ASCII digits.
_DIGIT_TABLE = {
    **{0x06F0 + i: str(i) for i in range(10)},
    **{0x0660 + i: str(i) for i in range(10)},
}

# Dropped silently: harakat/tanwin/shadda/maddah marks, dagger alef, Quranic
# marks, tatweel; and the characters that are DELETED rather than treated as
# separators so "L'Oréal" stays one word (as Django's slugify does): ' ’ ʼ ` .
_DROPPED = re.compile("[\u064b-\u065f\u0670\u06d6-\u06ed\u0640'\u2019\u02bc`.]")

# Arabic-script block ranges (letters; punctuation inside them is not \w, so it
# already acts as a separator).
_ARABIC_SCRIPT = "\u0600-\u06ff\u0750-\u077f\ufb50-\ufdff\ufe70-\ufeff"
_SCRIPT_RUN = re.compile(f"[{_ARABIC_SCRIPT}]+|[^{_ARABIC_SCRIPT}]+")
_HAS_ARABIC_SCRIPT = re.compile(f"[{_ARABIC_SCRIPT}]")

# Context-free letters. و ی ه ع have positional rules in _transliterate_word.
_LETTERS = {
    "ا": "a", "آ": "a", "أ": "a", "إ": "a",
    "ب": "b", "پ": "p", "ت": "t", "ث": "s", "ج": "j", "چ": "ch",
    "ح": "h", "خ": "kh", "د": "d", "ذ": "z", "ر": "r", "ز": "z",
    "ژ": "zh", "س": "s", "ش": "sh", "ص": "s", "ض": "z", "ط": "t",
    "ظ": "z", "غ": "gh", "ف": "f", "ق": "q", "ک": "k", "گ": "g",
    "ل": "l", "م": "m", "ن": "n", "ة": "h", "ھ": "h", "ہ": "h",
    "ء": "", "ئ": "", "ؤ": "",
}  # fmt: skip
_VOWEL_LETTERS = "اآوی"

# Conventional Latin spelling of Persian-script LOANWORDS and brand names.
# Keys are matched whole-word, longest phrase first (up to 3 words), after
# normalisation (so they use ک/ی, never ك/ي, and contain no ZWNJ - a test
# enforces this). Phrases are needed because some words are ambiguous alone:
# "سی" is both the letter C and the number thirty, so only "ویتامین سی" maps.
# Values must be lowercase [a-z0-9_-]. Extend freely; keep entries to words with
# one well-known Latin spelling (do NOT add translations of native words).
LOANWORD_GLOSSARY = {
    "ویتامین سی": "vitamin-c",
    "ویتامین ای": "vitamin-e",
    "ویتامین دی": "vitamin-d",
    "ویتامین بی": "vitamin-b",
    "ویتامین آ": "vitamin-a",
    "ویتامین": "vitamin",
    "سرم": "serum",
    "کرم": "cream",
    "لوسیون": "lotion",
    "شامپو": "shampoo",
    "ماسک": "mask",
    "ژل": "gel",
    "اسپری": "spray",
    "تونر": "toner",
    "پودر": "powder",
    "ادکلن": "cologne",
    "اسید": "acid",
    "کراتین": "keratin",
    "پروتئین": "protein",
    "کلاژن": "collagen",
    "رتینول": "retinol",
    "نیاسینامید": "niacinamide",
    "هیالورونیک": "hyaluronic",
    "لورآل": "loreal",
    "لورال": "loreal",
    "نیوآ": "nivea",
    "نیویا": "nivea",
    "گارنیر": "garnier",
    "ایزادورا": "isadora",
    "بیودرما": "bioderma",
    "نوتروژینا": "neutrogena",
    "ویشی": "vichy",
    "اوسرین": "eucerin",
    "سراوی": "cerave",
    "میبلین": "maybelline",
    "گلدن رز": "golden-rose",
}


def _transliterate_word(word):
    """
    Letter-table transliteration of ONE Arabic-script word (already normalised,
    digits converted, no ZWNJ). Four letters depend on position because Persian
    writes long vowels and consonants with the same letters:

    * و  alone -> "va" (the conjunction "and"); word-initial -> "v"; else "u"
         (پوست -> "pust", مو -> "mu", but ویتامین -> "vitamin").
    * ی  word-initial, or right after ا/آ -> "y" (مایع -> "may"); else "i"
         (سی -> "si", میلی -> "mili").
    * ه  word-final after a consonant -> "e" (روزانه -> "ruzane"); after a
         vowel letter, or anywhere else -> "h" (ماه -> "mah").
    * ع  word-initial -> "a" (عطر -> "atr"); elsewhere dropped.
    Letters outside the table (rare Urdu/Pashto forms) are dropped.
    """
    n = len(word)
    out = []
    for i, ch in enumerate(word):
        prev = word[i - 1] if i else ""
        if ch == "و":
            out.append("va" if n == 1 else "v" if i == 0 else "u")
        elif ch == "ی":
            out.append("y" if i == 0 or prev in "اآ" else "i")
        elif ch == "ه":
            out.append(
                "e" if i == n - 1 and n > 1 and prev not in _VOWEL_LETTERS else "h"
            )
        elif ch == "ع":
            out.append("a" if i == 0 else "")
        else:
            out.append(_LETTERS.get(ch, ""))
    return "".join(out)


def persian_slugify(text, *, max_length=None, glossary=None):
    """
    Transliterate Persian text into a clean, URL-safe, lowercase Latin slug.

    Mixed Persian/Latin input is handled per word: Latin/ASCII text and digits
    pass through (case-folded, diacritics folded, as Django's slugify does) and
    are NEVER fed to the Persian letter table; Persian words are transliterated;
    the two are joined with hyphens ("سرم ویتامین C" -> "serum-vitamin-c").

    Steps: ZWNJ -> word boundary (BEFORE normalisation, which would otherwise
    strip it); normalize_persian_text(); Persian/Arabic digits -> ASCII; drop
    diacritics and apostrophes; split on anything that is not a letter, digit or
    underscore; split glued Persian/Latin words at the script boundary; glossary
    (longest phrase first) else letter table; join with "-".

    ``max_length`` truncates at a hyphen boundary (leave room for a "-N"
    collision suffix). ``glossary=None`` uses LOANWORD_GLOSSARY, ``{}`` disables
    it (pure letter-table output). Returns "" when nothing usable remains -
    callers supply a model-specific fallback.
    """
    if not text:
        return ""
    glossary = LOANWORD_GLOSSARY if glossary is None else glossary

    # ZWNJ is a word boundary in Persian (مرطوب‌کننده = مرطوب + کننده).
    # normalize_persian_text() strips it, so convert it to a space first.
    text = normalize_persian_text(text.replace(_ZWNJ, " "))
    text = _DROPPED.sub("", text.translate(_DIGIT_TABLE))

    # Ordered items: ("fa", word) | ("lat", ascii). Hyphens and any
    # non-word character separate tokens; a token glued across scripts
    # (ویتامینC, ۱۵۰میلی) is split at the boundary.
    items = []
    for token in re.split(r"[^\w]+", text):
        for run in _SCRIPT_RUN.findall(token):
            if _HAS_ARABIC_SCRIPT.match(run):
                items.append(("fa", run))
            else:
                ascii_run = (
                    unicodedata.normalize("NFKD", run)
                    .encode("ascii", "ignore")
                    .decode()
                )
                if ascii_run:
                    items.append(("lat", ascii_run.lower()))

    parts = []
    i = 0
    while i < len(items):
        kind, value = items[i]
        if kind == "lat":
            parts.append(value)
            i += 1
            continue
        for span in (3, 2, 1):  # longest phrase first
            window = items[i : i + span]
            if len(window) == span and all(k == "fa" for k, _ in window):
                key = " ".join(v for _, v in window)
                if key in glossary:
                    parts.append(glossary[key])
                    i += span
                    break
        else:
            parts.append(_transliterate_word(value))
            i += 1

    slug = re.sub(r"-{2,}", "-", "-".join(p for p in parts if p)).strip("-_")
    if max_length is not None and len(slug) > max_length:
        cut = slug[:max_length]
        # Prefer to cut at a word boundary, unless that would throw away most of it.
        slug = (cut.rsplit("-", 1)[0] if "-" in cut[max_length // 2 :] else cut).strip(
            "-_"
        )
    return slug


def unique_slug(model, base_slug, *, pk=None):
    """
    Collision-avoiding slug: ``base``, ``base-1``, ``base-2`` ... This is the
    SAME loop Product.save() has always used (kept inline there, unchanged);
    Category, Brand and the blog models previously had no collision handling.
    """
    slug = base_slug
    counter = 1
    while model.objects.filter(slug=slug).exclude(pk=pk).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


def slug_base_length(model, reserve=8):
    """Max base-slug length for ``model``, leaving room for a "-NNNNNN" collision suffix."""
    return model._meta.get_field("slug").max_length - reserve


def regenerate_legacy_slugs(model, name_field, *, fallback, normalize=True):
    """
    Data-migration helper (Task 14.4.1.2). Rewrites slugs that the OLD generator
    (Django's slugify, no allow_unicode) produced from a Persian/Arabic-script
    name, using persian_slugify instead, and returns ``[(pk, old, new), ...]``.

    A row is rewritten ONLY if its slug is exactly what the old code would have
    generated for its current name (the bare result, or that result plus the old
    "-N" collision suffix). Slugs are read-only in the admin API, so every slug
    in a live database came from that generator, EXCEPT ones set by hand or by
    a seed script; those never match and are left alone. Rows with Latin-only
    names are never touched. Idempotent: a second run changes nothing.

    CAVEATS: no redirects are created (a bare "" slug was never reachable and
    "-N" slugs are meaningless, but lossy valid slugs such as "spf50" change URL).
    Names already had ZWNJ stripped when they were saved, so word boundaries
    cannot be recovered for EXISTING rows ("مرطوبکننده" -> one word).
    Do not edit this function's behaviour after the migrations have shipped.
    """
    from django.utils.text import slugify  # the OLD generator, for matching only

    max_base = slug_base_length(model)
    rows = list(model.objects.order_by("pk").values_list("pk", name_field, "slug"))
    changed = []
    for pk, name, slug in rows:
        if not name or not _HAS_ARABIC_SCRIPT.search(name):
            continue
        legacy_base = slugify(normalize_persian_text(name) if normalize else name)
        if slug != legacy_base and not re.fullmatch(
            re.escape(legacy_base) + r"-\d+", slug
        ):
            continue
        new_slug = unique_slug(
            model, persian_slugify(name, max_length=max_base) or fallback, pk=pk
        )
        if new_slug != slug:
            model.objects.filter(pk=pk).update(slug=new_slug)
            changed.append((pk, slug, new_slug))
    return changed
