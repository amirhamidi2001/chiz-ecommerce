import pytest
from shop.filters import ProductFilter
from shop.models import Product
from shop.tests.factories import (
    BrandFactory,
    CategoryFactory,
    ColorFactory,
    ProductColorFactory,
    ProductFactory,
)


def apply_filter(data):
    """Helper: run ProductFilter over all Products and return the QS."""
    qs = Product.objects.select_related("category", "brand").prefetch_related(
        "colors__color"
    )
    f = ProductFilter(data=data, queryset=qs)
    return f.qs


@pytest.mark.django_db
class TestProductFilterCategory:

    def test_filter_by_category_slug(self):
        cat_a = CategoryFactory(name="Electronics", slug="electronics")
        cat_b = CategoryFactory(name="Clothing", slug="clothing")
        ProductFactory.create_batch(3, category=cat_a)
        ProductFactory.create_batch(2, category=cat_b)

        qs = apply_filter({"category": "electronics"})
        assert qs.count() == 3
        assert all(p.category.slug == "electronics" for p in qs)

    def test_filter_by_category_id(self):
        cat = CategoryFactory()
        ProductFactory.create_batch(2, category=cat)
        ProductFactory()  # different category

        qs = apply_filter({"category": str(cat.id)})
        assert qs.count() == 2

    def test_unknown_category_returns_empty(self):
        ProductFactory.create_batch(3)
        qs = apply_filter({"category": "nonexistent-slug"})
        assert qs.count() == 0


@pytest.mark.django_db
class TestProductFilterBrand:

    def test_filter_by_single_brand_slug(self):
        brand_a = BrandFactory(slug="nike")
        brand_b = BrandFactory(slug="adidas")
        ProductFactory.create_batch(3, brand=brand_a)
        ProductFactory.create_batch(2, brand=brand_b)

        qs = apply_filter({"brand": "nike"})
        assert qs.count() == 3

    def test_filter_by_multiple_brand_slugs(self):
        brand_a = BrandFactory(slug="nike")
        brand_b = BrandFactory(slug="adidas")
        brand_c = BrandFactory(slug="puma")
        ProductFactory.create_batch(2, brand=brand_a)
        ProductFactory.create_batch(2, brand=brand_b)
        ProductFactory.create_batch(2, brand=brand_c)

        qs = apply_filter({"brand": "nike,adidas"})
        assert qs.count() == 4

    def test_filter_by_brand_id(self):
        brand = BrandFactory()
        ProductFactory.create_batch(2, brand=brand)
        ProductFactory()

        qs = apply_filter({"brand": str(brand.id)})
        assert qs.count() == 2

    def test_empty_brand_returns_all(self):
        ProductFactory.create_batch(4)
        qs = apply_filter({"brand": ""})
        assert qs.count() == 4


@pytest.mark.django_db
class TestProductFilterColor:

    def test_filter_by_color_name(self):
        red = ColorFactory(name="Red", hex_code="#ff0000")
        blue = ColorFactory(name="Blue", hex_code="#0000ff")
        p_red = ProductFactory()
        p_blue = ProductFactory()
        ProductColorFactory(product=p_red, color=red)
        ProductColorFactory(product=p_blue, color=blue)

        qs = apply_filter({"color": "Red"})
        assert p_red in qs
        assert p_blue not in qs

    def test_filter_by_multiple_color_ids(self):
        red = ColorFactory(name="Red", hex_code="#ff0000")
        blue = ColorFactory(name="Blue", hex_code="#0000ff")
        p1 = ProductFactory()
        p2 = ProductFactory()
        p3 = ProductFactory()  # no color
        ProductColorFactory(product=p1, color=red)
        ProductColorFactory(product=p2, color=blue)

        qs = apply_filter({"color": f"{red.id},{blue.id}"})
        assert p1 in qs
        assert p2 in qs
        assert p3 not in qs


@pytest.mark.django_db
class TestProductFilterPrice:

    def test_min_price(self):
        ProductFactory(name="Cheap", price=10)
        ProductFactory(name="Mid", price=50)
        ProductFactory(name="Expensive", price=200)

        qs = apply_filter({"min_price": 49})
        names = list(qs.values_list("name", flat=True))
        assert "Cheap" not in names
        assert "Mid" in names
        assert "Expensive" in names

    def test_max_price(self):
        ProductFactory(name="Cheap", price=10)
        ProductFactory(name="Mid", price=50)
        ProductFactory(name="Expensive", price=200)

        qs = apply_filter({"max_price": 51})
        names = list(qs.values_list("name", flat=True))
        assert "Cheap" in names
        assert "Mid" in names
        assert "Expensive" not in names

    def test_price_range(self):
        ProductFactory(name="Low", price=5)
        ProductFactory(name="Mid", price=50)
        ProductFactory(name="High", price=500)

        qs = apply_filter({"min_price": 10, "max_price": 100})
        names = list(qs.values_list("name", flat=True))
        assert names == ["Mid"]


@pytest.mark.django_db
class TestProductFilterFlags:

    def test_is_new_filter(self):
        ProductFactory.create_batch(3, is_new=True)
        ProductFactory.create_batch(2, is_new=False)

        qs = apply_filter({"is_new": True})
        assert qs.count() == 3
        assert all(p.is_new for p in qs)

    def test_is_sale_filter(self):
        ProductFactory.create_batch(4, is_sale=True)
        ProductFactory.create_batch(3, is_sale=False)

        qs = apply_filter({"is_sale": True})
        assert qs.count() == 4

    def test_combined_flags_filter(self):
        ProductFactory.create_batch(2, is_new=True, is_sale=True)
        ProductFactory.create_batch(2, is_new=True, is_sale=False)
        ProductFactory.create_batch(2, is_new=False, is_sale=True)

        qs = apply_filter({"is_new": True, "is_sale": True})
        assert qs.count() == 2
