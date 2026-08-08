import pytest
from django.utils.text import slugify
from shop.models import Brand, Category, Color, Product, ProductColor, Review
from shop.tests.factories import (
    BrandFactory,
    CategoryFactory,
    ColorFactory,
    ProductColorFactory,
    ProductFactory,
    ReviewFactory,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Category
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestCategoryModel:

    def test_str_returns_name(self):
        cat = CategoryFactory.build(name="Electronics")
        assert str(cat) == "Electronics"

    def test_slug_auto_generated_from_name(self, db):
        cat = CategoryFactory(name="Home & Kitchen")
        assert cat.slug == slugify("Home & Kitchen")

    def test_explicit_slug_is_respected(self, db):
        cat = CategoryFactory(name="Electronics", slug="my-custom-slug")
        assert cat.slug == "my-custom-slug"

    def test_parent_child_relationship(self, db):
        parent = CategoryFactory(name="Electronics")
        child = CategoryFactory(name="Smartphones", parent=parent)

        assert child.parent == parent
        assert child in parent.children.all()

    def test_parent_is_nullable(self, db):
        cat = CategoryFactory()
        assert cat.parent is None

    def test_ordering_is_alphabetical(self, db):
        CategoryFactory(name="Zebra")
        CategoryFactory(name="Apple")
        CategoryFactory(name="Mango")
        names = list(Category.objects.values_list("name", flat=True))
        assert names == sorted(names)

    def test_created_at_is_set(self, db):
        cat = CategoryFactory()
        assert cat.created_at is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Brand
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestBrandModel:

    def test_str_returns_name(self):
        brand = BrandFactory.build(name="Nike")
        assert str(brand) == "Nike"

    def test_slug_auto_generated(self, db):
        brand = BrandFactory(name="Under Armour")
        assert brand.slug == "under-armour"

    def test_slug_uniqueness_enforced_at_db(self, db):
        BrandFactory(name="Nike", slug="nike")
        with pytest.raises(Exception):
            BrandFactory(name="Nike2", slug="nike")  # duplicate slug → DB error


# ═══════════════════════════════════════════════════════════════════════════════
# Color
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestColorModel:

    def test_str_includes_name_and_hex(self, db):
        color = ColorFactory(name="Black", hex_code="#000000")
        assert str(color) == "Black (#000000)"

    def test_ordering_is_alphabetical(self, db):
        ColorFactory(name="Yellow")
        ColorFactory(name="Blue")
        names = list(Color.objects.values_list("name", flat=True))
        assert names == sorted(names)


# ═══════════════════════════════════════════════════════════════════════════════
# Product
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestProductModel:

    def test_str_returns_name(self):
        product = ProductFactory.build(name="Wireless Headphones")
        assert str(product) == "Wireless Headphones"

    def test_slug_auto_generated(self, db):
        product = ProductFactory(name="Smart Watch Pro")
        assert product.slug == "smart-watch-pro"

    def test_slug_collision_resolved_with_counter(self, db):
        p1 = ProductFactory(name="Cool Shoes")
        # Force a second product with the same base slug
        p2 = Product.objects.create(
            name="Cool Shoes",
            price=99,
            stock=10,
        )
        assert p2.slug == "cool-shoes-1"

        p3 = Product.objects.create(name="Cool Shoes", price=99, stock=5)
        assert p3.slug == "cool-shoes-2"

    def test_discount_percent_when_on_sale(self, db):
        product = ProductFactory(price=80, original_price=100)
        assert product.discount_percent == 20

    def test_discount_percent_zero_when_no_original_price(self, db):
        product = ProductFactory(price=80, original_price=None)
        assert product.discount_percent == 0

    def test_discount_percent_zero_when_price_equals_original(self, db):
        product = ProductFactory(price=100, original_price=100)
        assert product.discount_percent == 0

    def test_ordering_newest_first(self, db):
        p1 = ProductFactory(name="Old Product")
        p2 = ProductFactory(name="New Product")
        products = list(Product.objects.all())
        assert products[0] == p2  # newest first

    def test_is_new_default_false(self, db):
        product = ProductFactory()
        assert product.is_new is False

    def test_is_sale_default_false(self, db):
        product = ProductFactory()
        assert product.is_sale is False

    def test_stock_can_be_zero(self, db):
        product = ProductFactory(stock=0)
        assert product.stock == 0


# ═══════════════════════════════════════════════════════════════════════════════
# ProductColor
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestProductColorModel:

    def test_str_representation(self, db):
        pc = ProductColorFactory()
        assert pc.product.name in str(pc)
        assert pc.color.name in str(pc)

    def test_unique_together_enforced(self, db):
        pc = ProductColorFactory()
        with pytest.raises(Exception):
            ProductColorFactory(product=pc.product, color=pc.color)


# ═══════════════════════════════════════════════════════════════════════════════
# Review
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestReviewModel:

    def test_str_includes_reviewer_product_and_rating(self, db):
        review = ReviewFactory(name="Alice", rating=5)
        text = str(review)
        assert "Alice" in text
        assert review.product.name in text
        assert "5" in text

    def test_ordering_newest_first(self, db):
        product = ProductFactory()
        r1 = ReviewFactory(product=product)
        r2 = ReviewFactory(product=product)
        reviews = list(Review.objects.filter(product=product))
        assert reviews[0] == r2

    def test_rating_choices_1_to_5(self, db):
        for rating in range(1, 6):
            r = ReviewFactory(rating=rating)
            assert r.rating == rating

    def test_cascade_delete_with_product(self, db):
        review = ReviewFactory()
        product_id = review.product.id
        review.product.delete()
        assert Review.objects.filter(id=review.id).count() == 0
