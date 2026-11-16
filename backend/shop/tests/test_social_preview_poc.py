"""
EXPLORATORY PoC tests (Task 15.1.2.3 spike) for shop/social_preview.py.

These pin what the PoC claims: a crawler that does not run JavaScript gets the same facts
(title, description, absolute image, canonical URL, raw-Rial price) the SPA would render, as
safe, script-free HTML. A production implementation needs a fuller suite (see the evaluation).
"""

from html.parser import HTMLParser

import pytest
from shop.models import Product
from shop.social_preview import truncate_at_word
from shop.tests.factories import (
    BrandFactory,
    CategoryFactory,
    ProductFactory,
    ProductImageFactory,
    ProductVariantFactory,
)

FRONTEND_URL = "https://chiz.example"


class Page(HTMLParser):
    """Collects what a link-preview crawler reads: <title>, <meta>, <link>, any <script>."""

    def __init__(self, html):
        super().__init__()
        self.title = ""
        self.og = {}
        self.names = {}
        self.links = {}
        self.scripts = 0
        self._in_title = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "meta" and "property" in a:
            self.og[a["property"]] = a.get("content")
        elif tag == "meta" and "name" in a:
            self.names[a["name"]] = a.get("content")
        elif tag == "link":
            self.links[a.get("rel")] = a.get("href")
        elif tag == "script":
            self.scripts += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


@pytest.fixture(autouse=True)
def frontend(settings):
    settings.FRONTEND_URL = FRONTEND_URL


@pytest.fixture
def product(db):
    return ProductFactory(
        name="سرم ویتامین سی",
        slug="serum-vitamin-c",
        brand=BrandFactory(name="کلینیک"),
        category=CategoryFactory(name="مراقبت پوست"),
        short_description=(
            "سرم سبک و بدون چربی با ویتامین سی برای روشن کردن و شادابی پوست در استفاده روزانه"
        ),
        price=4_990_000,
    )


def fetch(client, slug="serum-vitamin-c"):
    response = client.get(f"/share/product/{slug}")
    return response, Page(response.content.decode("utf-8"))


def test_serves_the_open_graph_facts_as_script_free_html(client, product):
    ProductVariantFactory(product=product, price=4_990_000, is_active=True)

    response, page = fetch(client)

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/html")
    assert page.scripts == 0  # nothing here needs (or runs) JavaScript
    assert page.og["og:type"] == "product"
    assert page.og["og:title"] == "سرم ویتامین سی"
    assert page.og["og:site_name"] == "Chiz"
    assert page.og["og:locale"] == "fa_IR"
    assert page.og["og:description"] == page.names["description"]
    assert page.title == "سرم ویتامین سی | کلینیک | Chiz"


def test_urls_name_the_frontend_not_the_host_the_request_arrived_on(client, product):
    _, page = fetch(client)

    expected = f"{FRONTEND_URL}/product/serum-vitamin-c"
    assert page.og["og:url"] == expected
    assert page.links["canonical"] == expected
    assert "testserver" not in page.og["og:url"]


def test_image_is_the_products_own_absolute_url(client, product):
    Product.objects.filter(pk=product.pk).update(
        thumbnail="products/thumbnails/serum.jpg"
    )

    _, page = fetch(client)

    assert (
        page.og["og:image"] == "http://testserver/media/products/thumbnails/serum.jpg"
    )
    assert page.og["og:image"].startswith(
        ("http://", "https://")
    )  # absolute, as crawlers need


def test_falls_back_to_the_gallery_and_then_to_the_branded_default(client, product):
    _, page = fetch(client)
    assert page.og["og:image"] == f"{FRONTEND_URL}/og-default.jpg"  # no images at all

    ProductImageFactory(product=product)
    _, page = fetch(client)
    assert page.og["og:image"].startswith("http://testserver/media/products/images/")


def test_price_is_the_lowest_active_variant_in_raw_rial(client, product):
    ProductVariantFactory(product=product, price=7_500_000, is_active=True)
    ProductVariantFactory(product=product, price=4_990_000, is_active=True)
    ProductVariantFactory(product=product, price=100_000, is_active=False)  # ignored

    _, page = fetch(client)

    assert page.og["product:price:amount"] == "4990000"  # Rial, not Toman (499000)
    assert page.og["product:price:currency"] == "IRR"


def test_uses_the_legacy_price_when_there_are_no_variants(client, product):
    _, page = fetch(client)
    assert page.og["product:price:amount"] == "4990000"


def test_description_is_cut_at_a_word_boundary(client, product):
    long_text = ("این سرم با فرمولی سبک پوست را روشن می\u200cکند " * 6).strip()
    Product.objects.filter(pk=product.pk).update(short_description=long_text)

    _, page = fetch(client)

    description = page.names["description"]
    assert len(description) <= 155 and description.endswith("…")
    assert description[:-1].split(" ")[-1] in set(
        long_text.split(" ")
    )  # never mid-word


def test_short_description_falls_back_to_a_template_with_brand_and_category(
    client, product
):
    Product.objects.filter(pk=product.pk).update(short_description="جدید")

    _, page = fetch(client)

    for word in ("سرم ویتامین سی", "کلینیک", "مراقبت پوست", "Chiz"):
        assert word in page.names["description"]


def test_hostile_product_text_cannot_break_out_of_the_markup(client, product):
    Product.objects.filter(pk=product.pk).update(name='"><script>alert(1)</script>x')

    response, page = fetch(client)
    body = response.content.decode("utf-8")

    assert "<script" not in body
    assert page.scripts == 0
    assert 'content=""><' not in body  # the quote did not close the attribute
    assert page.og["og:title"].startswith('">')  # kept as inert, escaped text


def test_unknown_product_is_a_404_so_nginx_can_fall_back_to_the_spa(client, db):
    response, _ = fetch(client, slug="does-not-exist")
    assert response.status_code == 404


def test_is_cacheable_for_a_few_minutes(client, product):
    response, _ = fetch(client)
    assert response["Cache-Control"] == "public, max-age=300"


def test_frontend_url_trailing_slash_does_not_double_up(client, product, settings):
    settings.FRONTEND_URL = "https://chiz.example/"
    _, page = fetch(client)
    assert page.og["og:url"] == "https://chiz.example/product/serum-vitamin-c"


def test_a_persian_named_product_links_to_its_ascii_slug(client, db):
    persian = ProductFactory(name="کرم مرطوب کننده", slug="")
    persian.refresh_from_db()
    assert persian.slug.isascii() and persian.slug

    _, page = fetch(client, slug=persian.slug)

    assert page.og["og:url"] == f"{FRONTEND_URL}/product/{persian.slug}"


class TestTruncate:
    def test_short_text_is_unchanged(self):
        assert truncate_at_word("سرم ویتامین سی") == "سرم ویتامین سی"

    def test_never_exceeds_the_limit(self):
        assert len(truncate_at_word("کلمه " * 80)) <= 155
