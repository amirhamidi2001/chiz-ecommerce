"""
Task 14.4.1.3 - the REAL seed command, end to end (ADR 0002).

These run ``manage.py seed_shop`` against a fresh (empty) test database and
assert on what actually lands in it, so a regression anywhere on the real path
(command -> Model.save() -> persian_slugify -> collision loop) is caught, not
only a regression inside persian_slugify() itself.
"""

import re
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from shop.management.commands import seed_shop
from shop.models import Brand, Category, Product, ProductVariant
from shop.text_utils import normalize_persian_text

VALID = re.compile(r"^[a-z0-9_]+(-[a-z0-9_]+)*$")
ZWNJ = "\u200c"


def seed(*args):
    out = StringIO()
    call_command("seed_shop", *args, stdout=out)
    return out.getvalue()


def slugs(model):
    return sorted(model.objects.values_list("slug", flat=True))


@pytest.fixture
def seeded(db):
    seed()


class TestSeededSlugsAreCorrect:
    def test_nothing_is_empty_or_malformed(self, seeded):
        assert not Product.objects.filter(slug="").exists()
        assert not Category.objects.filter(slug="").exists()
        assert not Brand.objects.filter(slug="").exists()
        for model in (Category, Brand, Product):
            bad = [s for s in slugs(model) if not VALID.match(s)]
            assert bad == [], (model.__name__, bad)

    def test_every_seed_row_was_created(self, seeded):
        n_categories = len(seed_shop.CATEGORIES) + sum(
            len(subs) for _, subs in seed_shop.CATEGORIES
        )
        assert Category.objects.count() == n_categories
        assert Brand.objects.count() == len(seed_shop.BRANDS)
        assert Product.objects.count() == len(seed_shop.PRODUCTS)

    def test_slugs_are_unique(self, seeded):
        for model in (Category, Brand, Product):
            assert len(set(slugs(model))) == model.objects.count()

    @pytest.mark.parametrize(
        "raw_name, expected",
        [
            ("آرایش", "araysh"),
            ("مرطوب~کننده", "mrtub-knnde"),
            ("پاک~کننده و شوینده صورت", "pak-knnde-va-shuinde-surt"),
            ("عطر و ادکلن", "atr-va-cologne"),
        ],
    )
    def test_category_slugs(self, seeded, raw_name, expected):
        name = normalize_persian_text(seed_shop.z(raw_name))
        assert Category.objects.get(name=name).slug == expected

    @pytest.mark.parametrize(
        "name, expected",
        [
            ("لورآل پاریس", "loreal-paris"),  # glossary + letter table
            ("گلدن رز", "golden-rose"),  # glossary phrase
            ("The Ordinary", "the-ordinary"),  # Latin passes through
            ("Dr. Jart+", "dr-jart"),  # Latin with '.' and '+'
        ],
    )
    def test_brand_slugs(self, seeded, name, expected):
        assert Brand.objects.get(name=name).slug == expected

    @pytest.mark.parametrize(
        "raw_name, expected",
        [
            # Persian + glossary + Persian numerals -> Western digits + ZWNJ boundary
            (
                "سرم ویتامین سی ۱۵ درصد روشن~کننده",
                "serum-vitamin-c-15-drsd-rushn-knnde",
            ),
            # THE mixed-script case: the Latin "C" survives, "٪" is a separator
            ("سرم ویتامین C ۱۰٪ ضد لک", "serum-vitamin-c-10-zd-lk"),
            # Latin-only product name
            (
                "The Ordinary Niacinamide 10% + Zinc 1%",
                "the-ordinary-niacinamide-10-zinc-1",
            ),
            # Latin token glued to digits
            ("کرم پودر مات 24H", "cream-powder-mat-24h"),
            ("ماسک مو کراتین ۲۵۰ میلی~لیتر", "mask-mu-keratin-250-mili-litr"),
        ],
    )
    def test_product_slugs(self, seeded, raw_name, expected):
        name = normalize_persian_text(seed_shop.z(raw_name))
        assert Product.objects.get(name=name).slug == expected

    def test_zwnj_word_boundaries_survive_the_real_save_path(self, seeded):
        # Stored names have ZWNJ stripped, yet the slug (built from the RAW name
        # inside save()) still has the boundary: "mrtub-knnde", not "mrtubknnde".
        p = Product.objects.get(slug="cream-mrtub-knnde-ruzane-mnasb-pust-khshk")
        assert ZWNJ not in p.name
        assert "mrtub-knnde" in p.slug

    def test_identical_names_get_distinct_slugs_through_the_collision_loop(
        self, seeded
    ):
        for raw in (
            "کرم مرطوب~کننده روزانه مناسب پوست خشک",
            "ضدآفتاب بی~رنگ SPF50+ مناسب پوست چرب",
        ):
            rows = Product.objects.filter(name=normalize_persian_text(seed_shop.z(raw)))
            assert sorted(rows.values_list("slug", flat=True)) == sorted(
                [
                    rows[0].slug.removesuffix("-1"),
                    rows[0].slug.removesuffix("-1") + "-1",
                ]
            )
            assert rows.count() == 2


class TestSeededCatalogIsUsable:
    def test_catalog_is_persian(self, seeded):
        persian = re.compile("[\u0600-\u06ff]")
        persian_products = [p for p in Product.objects.all() if persian.search(p.name)]
        assert (
            len(persian_products) >= len(seed_shop.PRODUCTS) - 3
        )  # a few Latin names on purpose
        assert all(persian.search(c.name) for c in Category.objects.all())

    def test_every_product_has_a_purchasable_variant_and_consistent_price(self, seeded):
        for product in Product.objects.all():
            variants = list(product.variants.all())
            assert variants, product
            assert any(v.stock > 0 for v in variants), product
            assert product.price == min(v.price for v in variants)
            assert product.stock == sum(v.stock for v in variants)

    def test_prices_are_whole_toman(self, seeded):
        assert not ProductVariant.objects.exclude(price__gt=0).exists()
        assert all(v.price % 10 == 0 for v in ProductVariant.objects.all())


class TestSeedCommandBehaviour:
    def test_rerun_is_idempotent(self, seeded):
        before = (
            slugs(Category),
            slugs(Brand),
            slugs(Product),
            ProductVariant.objects.count(),
        )
        out = seed()
        assert "0 new products" in out
        assert (
            slugs(Category),
            slugs(Brand),
            slugs(Product),
            ProductVariant.objects.count(),
        ) == before

    def test_clear_then_reseed_reproduces_the_same_slugs(self, seeded):
        before = (slugs(Category), slugs(Brand), slugs(Product))
        seed("--clear")
        assert (slugs(Category), slugs(Brand), slugs(Product)) == before

    def test_command_fails_loudly_on_an_invalid_slug(self, seeded):
        Product.objects.filter(pk=Product.objects.first().pk).update(slug="")
        with pytest.raises(CommandError, match="invalid slugs"):
            seed()

    def test_seed_really_goes_through_the_models_slug_generation(self, db, monkeypatch):
        """If the models stopped using persian_slugify correctly, seeding must notice.

        Patch the function the MODEL calls (shop.models.persian_slugify) to emit a
        malformed slug; the seed's own verification must then fail. This proves the
        command exercises Model.save(), rather than computing slugs itself.
        """
        monkeypatch.setattr("shop.models.persian_slugify", lambda *a, **k: "Bad Slug!")
        with pytest.raises(CommandError, match="invalid slugs"):
            seed()
