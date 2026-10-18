"""
shop/search.py
───────────────
Postgres full-text search helpers for Product.

Single source of truth for HOW the stored `Product.search_vector` is built
and HOW a customer's search string becomes a tsquery, shared by
Product.save(), the Brand/Category rename signals, the rebuild management
command and the product list view.

Every vector/query uses the "simple" text-search config on purpose: the
language-aware configs ("english", ...) apply stemming/stop-word rules that
are wrong for Persian text, and Postgres ships no Persian config. "simple"
only lower-cases and tokenises — the honest baseline for a Persian-primary,
multi-lingual catalog. (A real Persian analyser would need a custom PG text
search configuration or an external engine; out of scope.)

NOTE: migration 0032 deliberately keeps its OWN frozen copy of the vector
expression instead of importing this module — a migration must keep doing
what it did when it was written even if this module changes later.
"""

import re

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import F, OuterRef, Subquery

from .text_utils import normalize_persian_text

SEARCH_CONFIG = "simple"

# Fields whose change makes Product.search_vector stale. Both the field and
# the attname spelling are listed because callers may pass either in
# save(update_fields=[...]).
SEARCH_VECTOR_SOURCE_FIELDS = frozenset(
    {
        "name",
        "short_description",
        "description",
        "brand",
        "brand_id",
        "category",
        "category_id",
    }
)

# Keep the tsquery we build bounded: a pathological 10 kB search string
# shouldn't become a 10 kB tsquery.
MAX_SEARCH_TERM_LENGTH = 100
MAX_SEARCH_TOKENS = 8

# Letters/digits in any script (Persian included); underscore excluded since
# Postgres's parser treats it as a separator rather than part of a word.
_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


def _related_name(model, fk_column):
    """
    Correlated subquery for the `name` of the related row, or NULL when the
    FK is NULL.

    A subquery rather than SearchVector("brand__name") because
    QuerySet.update() forbids joined-field references ("Joined field
    references are not permitted in this query"). SearchVector wraps every
    input in COALESCE(..., ''), so a missing brand/category contributes
    nothing instead of nulling the whole vector.
    """
    return Subquery(model.objects.filter(pk=OuterRef(fk_column)).values("name")[:1])


def product_search_vector_expression(brand_model, category_model):
    """
    The weighted vector: name/brand = A, category/short_description = B,
    description = C. (ts_rank's default weights are A=1.0, B=0.4, C=0.2,
    D=0.1, so a name hit outranks a description-only hit.)
    """
    cfg = SEARCH_CONFIG
    return (
        SearchVector("name", weight="A", config=cfg)
        + SearchVector(_related_name(brand_model, "brand_id"), weight="A", config=cfg)
        + SearchVector(
            _related_name(category_model, "category_id"), weight="B", config=cfg
        )
        + SearchVector("short_description", weight="B", config=cfg)
        + SearchVector("description", weight="C", config=cfg)
    )


def refresh_product_search_vectors(queryset=None):
    """
    Recompute search_vector for the products in `queryset` (default: all)
    with ONE UPDATE statement. Returns the number of rows updated.
    """
    from .models import Brand, Category, Product

    if queryset is None:
        queryset = Product.objects.all()
    return queryset.update(
        search_vector=product_search_vector_expression(Brand, Category)
    )


def build_search_query(raw_term):
    """
    Turn a customer's search string into a prefix-matching SearchQuery, or
    None if it contains no searchable tokens (e.g. "!!!").

    Each token becomes `token:*` and tokens are ANDed: "wire head" matches
    products containing a word starting "wire" AND a word starting "head"
    (in any field, any order) — the same AND-across-terms semantics DRF's
    SearchFilter had, and it keeps search-as-you-type working ("lipst" finds
    "Lipstick"), which plain `SearchQuery(term)` would NOT: that only matches
    whole lexemes.

    Tokens are reduced to letters/digits before being interpolated into the
    raw tsquery string, so tsquery operators in user input (& | ! ( ) < > : *
    quotes, backslashes) can never reach to_tsquery() and raise a syntax
    error.
    """
    tokens = _TOKEN_RE.findall(raw_term[:MAX_SEARCH_TERM_LENGTH])[:MAX_SEARCH_TOKENS]
    if not tokens:
        return None
    return SearchQuery(
        " & ".join(f"{token}:*" for token in tokens),
        search_type="raw",
        config=SEARCH_CONFIG,
    )


SEARCH_LOG_MAX_LENGTH = 255  # SearchQueryLog.query max_length


def clean_search_term(raw_term):
    """
    Normalised, stripped search term; "" means "not a search" (absent, blank,
    or only whitespace/zero-width characters). The single definition of
    "blank" shared by the search itself and by search logging.
    """
    return normalize_persian_text(raw_term or "").strip()


def search_log_term(raw_term):
    """
    The form of a search term stored in SearchQueryLog, or "" if it isn't a
    search. Collapses whitespace and lower-cases so "Lipstick", "lipstick "
    and "LIPSTICK" aggregate as one term, and truncates to the column width
    (an over-long term would otherwise raise DataError on Postgres).
    """
    term = " ".join(clean_search_term(raw_term).split()).lower()
    return term[:SEARCH_LOG_MAX_LENGTH]


def apply_product_search(queryset, raw_term):
    """
    THE entry point for searching products — used by both the paginated list
    (?search=) and the autocomplete endpoint, so there is exactly one
    implementation of normalisation, prefix tsquery and ranking.

    Returns (queryset, is_ranked):
      * blank / zero-width-only term  -> (queryset unchanged, False)
      * term with nothing searchable  -> (queryset.none(), False)   e.g. "!!!"
      * otherwise                     -> (filtered queryset annotated with
                                          `rank`, True)
    Ordering is left to the caller (the list view lets an explicit
    ?ordering= override rank; autocomplete always orders by rank).
    """
    # Same normalisation the stored text got at save time, done BEFORE the
    # blank check so a term of only zero-width characters counts as blank.
    term = clean_search_term(raw_term)
    if not term:
        return queryset, False
    query = build_search_query(term)
    if query is None:
        return queryset.none(), False
    # F("search_vector"), NOT the string "search_vector": SearchRank wraps a
    # bare string in SearchVector(...), i.e. to_tsvector(search_vector::text),
    # which re-parses the stored vector as plain text, discards the A/B/C
    # weights (every row ranks as D) and recomputes the vector per row.
    return (
        queryset.filter(search_vector=query).annotate(
            rank=SearchRank(F("search_vector"), query)
        ),
        True,
    )


def filter_products_by_search(queryset, raw_term):
    """
    Restrict `queryset` to products matching the search term, WITHOUT the
    `rank` annotation apply_product_search adds — for callers that only need
    the matching set (e.g. facet counts), not relevance ordering. Same
    normalisation, prefix tsquery and blank/unsearchable semantics:
    blank -> unchanged, nothing searchable -> .none().
    """
    term = clean_search_term(raw_term)
    if not term:
        return queryset
    query = build_search_query(term)
    if query is None:
        return queryset.none()
    return queryset.filter(search_vector=query)
