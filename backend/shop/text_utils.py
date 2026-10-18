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
