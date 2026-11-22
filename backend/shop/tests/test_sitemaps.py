"""
Sitemaps (Task 15.2): every <loc> must name the FRONTEND (settings.FRONTEND_URL), use the
SPA's real routes, and carry the current (Epic 14, Persian-transliterated) slugs.

The view is called directly, with the request arriving on a backend host that differs from
the frontend, so a URL built from the request host (the bug being fixed) cannot pass.
"""

import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree as ET

import pytest
from blog.tests.conftest import DraftPostFactory, PostFactory
from core.tests.sitemap_helpers import BACKEND_HOST, parse_locs, render_sitemaps
from shop.models import Brand, Category, Product
from shop.sitemaps import BrandSitemap, CategorySitemap, ProductSitemap
from shop.tests.factories import (
    BrandFactory,
    CategoryFactory,
    ProductFactory,
    ProductVariantFactory,
)

FRONTEND_URL = "https://chiz.example"
FRONTEND = urlparse(FRONTEND_URL)


@pytest.fixture(autouse=True)
def frontend_settings(settings):
    """A frontend origin that differs from the backend host the request arrives on."""
    settings.FRONTEND_URL = FRONTEND_URL
    settings.ALLOWED_HOSTS = [BACKEND_HOST, "testserver"]


# Persian names, slug="" so the models' own persian_slugify runs (the factories would
# otherwise pre-fill the slug with Django's ASCII slugify, which erases Persian text).
@pytest.fixture
def catalog(db):
    parent = CategoryFactory(name="مراقبت پوست", slug="")
    child = CategoryFactory(name="سرم", slug="", parent=parent)
    brand_fa = BrandFactory(name="لاروش پوزای", slug="")
    brand_en = BrandFactory(name="Cerave", slug="")
    product = ProductFactory(
        name="سرم ویتامین سی", slug="", category=child, brand=brand_fa
    )
    return {
        "parent": parent,
        "child": child,
        "brand_fa": brand_fa,
        "brand_en": brand_en,
        "product": product,
    }


SHOP_SITEMAPS = {
    "products": ProductSitemap,
    "categories": CategorySitemap,
    "brands": BrandSitemap,
}


# ─── 1. every <loc> uses the FRONTEND domain ────────────────────────────────────────
@pytest.mark.parametrize("name", list(SHOP_SITEMAPS))
def test_every_loc_uses_the_frontend_domain_not_the_request_host(catalog, name):
    locs = parse_locs(render_sitemaps({name: SHOP_SITEMAPS[name]}).content)

    assert locs, f"{name} sitemap produced no URLs"
    for loc in locs:
        parsed = urlparse(loc)
        assert parsed.netloc == FRONTEND.netloc, loc
        assert parsed.scheme == FRONTEND.scheme, loc
        assert BACKEND_HOST not in loc and "testserver" not in loc, loc


# ─── 2. a Persian-named product gets its transliterated slug in <loc> ───────────────
def test_persian_named_product_has_its_transliterated_slug_in_the_sitemap(catalog):
    product = catalog["product"]
    product.refresh_from_db()
    assert product.slug == "serum-vitamin-c"  # Epic 14's persian_slugify, not ''

    locs = parse_locs(render_sitemaps({"products": ProductSitemap}).content)

    assert locs == [f"{FRONTEND_URL}/product/serum-vitamin-c"]
    assert not any(
        loc.rstrip("/").endswith("/product") for loc in locs
    )  # no empty slug


def test_every_entry_uses_the_current_slug_of_its_row(catalog):
    """The sitemap reads obj.slug directly, so a slug that changes is reflected at once."""
    Product.objects.filter(pk=catalog["product"].pk).update(slug="changed-slug")

    locs = parse_locs(render_sitemaps({"products": ProductSitemap}).content)

    assert locs == [f"{FRONTEND_URL}/product/changed-slug"]


# ─── 3. BrandSitemap includes every brand, with the right URL ───────────────────────
def test_brand_sitemap_includes_all_brands_with_correct_urls(catalog):
    BrandFactory.create_batch(3)  # more brands, factory-style slugs
    locs = parse_locs(render_sitemaps({"brands": BrandSitemap}).content)

    expected = {f"{FRONTEND_URL}/category?brand={b.slug}" for b in Brand.objects.all()}
    assert Brand.objects.count() == 5
    assert set(locs) == expected
    assert len(locs) == len(set(locs)) == Brand.objects.count()
    # The Persian-named brand has a real transliterated slug, not an empty one.
    catalog["brand_fa"].refresh_from_db()
    assert catalog["brand_fa"].slug
    assert f"{FRONTEND_URL}/category?brand={catalog['brand_fa'].slug}" in locs


def test_brand_urls_are_a_filter_on_the_listing_that_the_api_understands(catalog):
    """The SPA has no brand page: a brand is ?brand=<slug> on /category (comma-separated
    slugs, see shop/filters.py filter_brand)."""
    for loc in parse_locs(render_sitemaps({"brands": BrandSitemap}).content):
        parsed = urlparse(loc)
        assert parsed.path == "/category"
        assert list(parse_qs(parsed.query)) == ["brand"]


# ─── routes: the paths the SPA really serves ────────────────────────────────────────
def test_urls_use_the_spas_real_routes_without_trailing_slashes(catalog):
    sitemaps = {
        "products": ProductSitemap,
        "categories": CategorySitemap,
        "blog": __import__("blog.sitemaps", fromlist=["BlogSitemap"]).BlogSitemap,
    }
    PostFactory(title="راهنمای خرید ضدآفتاب", slug="")
    locs = parse_locs(render_sitemaps(sitemaps).content)

    paths = [urlparse(loc).path for loc in locs]
    assert any(p.startswith("/product/") for p in paths)
    assert any(p.startswith("/blog/") for p in paths)
    assert not any(
        p.startswith(("/products/", "/category/")) for p in paths
    )  # old, wrong
    assert not any(loc.split("?")[0].endswith("/") for loc in locs), locs


def test_category_urls_carry_the_slug_as_the_category_query_param(catalog):
    locs = parse_locs(render_sitemaps({"categories": CategorySitemap}).content)

    assert set(locs) == {
        f"{FRONTEND_URL}/category?category={catalog['parent'].slug}",
        f"{FRONTEND_URL}/category?category={catalog['child'].slug}",  # sub-categories too
    }


def test_sitemap_paths_match_the_frontends_route_table():
    """Drift guard: the exact bug class here was backend paths disagreeing with App.jsx."""
    app = Path(__file__).resolve().parents[3] / "frontend" / "src" / "App.jsx"
    if not app.exists():
        pytest.skip("frontend sources are not present in this checkout/image")
    routes = set(
        re.findall(r'<Route\s+path="([^"]+)"', app.read_text(encoding="utf-8"))
    )

    # Routes the sitemaps point at must exist...
    assert {"/product/:slug", "/blog/:slug", "/category"} <= routes
    # ...and the ones they used to (wrongly) point at must not.
    assert "/products/:slug" not in routes and "/category/:slug" not in routes
    # BrandSitemap targets the listing filter because there is no brand page. If one is
    # ever added, point BrandSitemap at it (and give it its own canonical) instead.
    assert not any(
        r.startswith("/brand") for r in routes
    ), "A brand page route now exists: update BrandSitemap.location() to use it."


# ─── what is (not) in the sitemap ───────────────────────────────────────────────────
def test_out_of_stock_products_stay_in_the_sitemap(catalog):
    """A temporarily unavailable product page is still valid, indexable content."""
    Product.objects.filter(pk=catalog["product"].pk).update(stock=0)
    ProductVariantFactory(product=catalog["product"], is_active=False, stock=0)

    locs = parse_locs(render_sitemaps({"products": ProductSitemap}).content)

    assert locs == [f"{FRONTEND_URL}/product/serum-vitamin-c"]


def test_a_row_with_a_blank_slug_is_skipped_not_emitted_as_the_bare_section_url(
    catalog,
):
    """slug is unique, so at most one row per model can be blank; it must not become
    "/product" (or "/category?category=") while the other rows are unaffected."""
    Product.objects.filter(pk=catalog["product"].pk).update(slug="")
    Category.objects.filter(pk=catalog["parent"].pk).update(slug="")
    Brand.objects.filter(pk=catalog["brand_fa"].pk).update(slug="")

    products = parse_locs(render_sitemaps({"products": ProductSitemap}).content)
    categories = parse_locs(render_sitemaps({"categories": CategorySitemap}).content)
    brands = parse_locs(render_sitemaps({"brands": BrandSitemap}).content)

    assert products == []
    assert categories == [f"{FRONTEND_URL}/category?category={catalog['child'].slug}"]
    assert brands == [f"{FRONTEND_URL}/category?brand={catalog['brand_en'].slug}"]


def test_non_ascii_slugs_are_percent_encoded(catalog):
    """Slugs are ASCII since Epic 14, but a legacy/hand-edited row must still yield a valid
    URL (the sitemap protocol wants escaped URLs), not raw Unicode or a broken query."""
    Product.objects.filter(pk=catalog["product"].pk).update(slug="سرم")
    Brand.objects.filter(pk=catalog["brand_en"].pk).update(slug="a&b=c")

    products = parse_locs(render_sitemaps({"products": ProductSitemap}).content)
    brands = parse_locs(render_sitemaps({"brands": BrandSitemap}).content)

    assert products == [f"{FRONTEND_URL}/product/%D8%B3%D8%B1%D9%85"]
    assert f"{FRONTEND_URL}/category?brand=a%26b%3Dc" in brands


def test_tripwire_catalog_models_have_no_published_or_deleted_concept():
    """Product/Category/Brand have no visibility flag, so every row is a live page and the
    sitemaps filter nothing. If one is ever added, this fails: filter it out of
    shop/sitemaps.py (an unpublished product must not be submitted for indexing)."""
    visibility = {
        "is_active", "is_published", "published", "is_visible", "is_deleted",
        "deleted_at", "archived", "is_archived", "status", "published_at",
    }  # fmt: skip
    for model in (Product, Category, Brand):
        fields = {f.name for f in model._meta.get_fields()}
        assert not (fields & visibility), (
            f"{model.__name__} now has {sorted(fields & visibility)}: "
            "update the sitemap items() to exclude non-public rows."
        )


# ─── 4. the whole /sitemap.xml: all four sitemaps, well-formed ───────────────────────
def test_full_sitemap_xml_is_well_formed_and_covers_all_four_sitemaps(catalog, client):
    PostFactory(title="راهنمای خرید ضدآفتاب", slug="")
    DraftPostFactory(title="پیش نویس", slug="")

    response = client.get("/sitemap.xml", HTTP_HOST=BACKEND_HOST)

    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/xml")
    body = response.content.decode("utf-8")
    assert body.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    ET.fromstring(response.content)  # raises ParseError if malformed
    locs = parse_locs(response.content)

    by_kind = {
        "product": [loc for loc in locs if "/product/" in loc],
        "blog": [loc for loc in locs if "/blog/" in loc],
        "category": [loc for loc in locs if "/category?category=" in loc],
        "brand": [loc for loc in locs if "/category?brand=" in loc],
    }
    assert {k: len(v) for k, v in by_kind.items()} == {
        "product": 1,
        "blog": 1,  # the published post only; the draft is excluded
        "category": 2,
        "brand": 2,
    }
    assert len(locs) == len(set(locs)) == 6  # no duplicates, nothing else
    for loc in locs:
        assert urlparse(loc).netloc == FRONTEND.netloc, loc
    assert BACKEND_HOST not in body and "testserver" not in body
    assert "draft" not in body.lower()


def test_full_sitemap_xml_is_valid_when_there_is_no_content(db, client):
    response = client.get("/sitemap.xml", HTTP_HOST=BACKEND_HOST)

    assert response.status_code == 200
    assert parse_locs(response.content) == []
