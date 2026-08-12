import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
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

    # ── user FK (Task 1.3.1.2 — nullable, backward-compatible) ──────────────

    def test_review_can_be_created_with_user_none(self, db):
        """
        Backward compatibility: any existing code path that hasn't been
        updated yet (and all pre-migration historical rows) must still be
        able to create/hold a Review with no associated user.
        """
        review = ReviewFactory(user=None)
        assert review.user is None
        assert review.user_id is None
        # `name` (the denormalized display cache) is unaffected by user
        # being absent.
        assert review.name

    def test_review_can_be_created_with_a_real_user(self, db):
        User = get_user_model()
        user = User.objects.create_user(
            email="reviewer@example.com", password="TestPass123!"
        )
        review = ReviewFactory(user=user, name="Reviewer Name")

        assert review.user_id == user.id
        assert review.user == user
        # name is still stored independently of the linked user (kept as
        # a denormalized display cache per this task's requirements).
        assert review.name == "Reviewer Name"

    def test_deleting_user_sets_review_user_to_null_not_cascade(self, db):
        """
        on_delete=SET_NULL: deleting the linked User must not delete the
        Review itself (unlike `product`, which cascades) — the review
        (and its denormalized `name`) should survive with user=None.
        """
        User = get_user_model()
        user = User.objects.create_user(
            email="departing-user@example.com", password="TestPass123!"
        )
        review = ReviewFactory(user=user, name="Someone")
        review_id = review.id

        user.delete()

        review.refresh_from_db()
        assert Review.objects.filter(id=review_id).exists()
        assert review.user is None
        assert review.name == "Someone"  # unaffected — still denormalized

    # ── is_verified_purchase (Task 1.3.1.2 — field only, no logic yet) ──────

    def test_is_verified_purchase_defaults_to_false(self, db):
        review = ReviewFactory()
        assert review.is_verified_purchase is False

    def test_is_verified_purchase_can_be_set_true(self, db):
        # No computation logic exists yet (Task 1.3.1.5) — just confirming
        # the field itself is a normal, settable boolean.
        review = ReviewFactory(is_verified_purchase=True)
        assert review.is_verified_purchase is True

    # ── unique_together (product, user) — Task 1.3.1.4 ──────────────────────

    def test_duplicate_product_user_review_raises_integrity_error(self, db):
        """
        DB-level enforcement: the unique_together constraint itself,
        independent of the serializer-layer check (which is covered
        separately in shop/tests/test_views.py). This is the last line
        of defense against duplicate reviews if the application layer is
        ever bypassed (e.g. a management command, a future internal
        endpoint, a bug in the serializer check).
        """
        User = get_user_model()
        user = User.objects.create_user(
            email="dupe-checker@example.com", password="TestPass123!"
        )
        product = ProductFactory()
        ReviewFactory(product=product, user=user)

        # Wrapped in its own atomic() block: on Postgres, an IntegrityError
        # aborts the enclosing transaction until a ROLLBACK — nesting this
        # in its own savepoint keeps the rest of the test (and pytest-django's
        # transaction-per-test teardown) usable afterward.
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ReviewFactory(product=product, user=user)

    def test_multiple_null_user_reviews_on_same_product_do_not_conflict(self, db):
        """
        Confirms the documented NULL-handling caveat in Review.Meta: on
        this project's PostgreSQL backend, a UNIQUE constraint treats
        NULL as distinct from every other NULL, so multiple historical
        `user=None` reviews on the same product remain valid and do NOT
        trip the (product, user) uniqueness constraint.
        """
        product = ProductFactory()
        review_one = ReviewFactory(product=product, user=None, name="Anon One")
        review_two = ReviewFactory(product=product, user=None, name="Anon Two")

        assert review_one.pk is not None
        assert review_two.pk is not None
        assert (
            Review.objects.filter(product=product, user__isnull=True).count() == 2
        )

    def test_same_user_can_review_different_products(self, db):
        User = get_user_model()
        user = User.objects.create_user(
            email="multi-product-reviewer@example.com", password="TestPass123!"
        )
        product_a = ProductFactory()
        product_b = ProductFactory()

        ReviewFactory(product=product_a, user=user)
        ReviewFactory(product=product_b, user=user)

        assert Review.objects.filter(user=user).count() == 2
