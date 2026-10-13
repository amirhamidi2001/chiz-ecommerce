"""
shop/tests/test_price_drop.py
─────────────────────────────
Price-drop notifications for wishlisted products:

  * Product.lowest_active_price  — the "starting at" comparison basis
  * handle_variant_price_change  — shop/signals.py post_save hook on ProductVariant
  * notify_price_drop_subscribers — shop/tasks.py (Epic 16 placeholder dispatch)
  * 0030 backfill migration       — baseline snapshot for pre-existing products

Signal tests mock `notify_price_drop_subscribers.delay` (as the stock-alert
signal tests do) and assert on the args. The task is queued through
transaction.on_commit, and pytest-django wraps tests in a transaction, so the
signal-triggering saves run inside `django_capture_on_commit_callbacks(execute=True)`
to fire the commit hooks the way a real commit would.
"""

import importlib
from decimal import Decimal
from unittest.mock import patch

import pytest
from dashboard.models import Wishlist
from django.apps import apps
from django.db import transaction
from shop.models import ProductPriceSnapshot
from shop.tasks import notify_price_drop_subscribers
from shop.tests.factories import ProductFactory, ProductVariantFactory, UserFactory

backfill_module = importlib.import_module(
    "shop.migrations.0030_backfill_product_price_snapshots"
)


def D(value):
    return Decimal(value)


def snapshot_prices(product):
    """Newest first (the model's default ordering)."""
    return [s.price for s in product.price_snapshots.all()]


@pytest.fixture
def delay():
    with patch("shop.signals.notify_price_drop_subscribers.delay") as mock_delay:
        yield mock_delay


@pytest.fixture
def commit(django_capture_on_commit_callbacks):
    """Context manager: run the block, then fire on_commit hooks as a real commit would."""
    return lambda: django_capture_on_commit_callbacks(execute=True)


@pytest.fixture
def product(db):
    return ProductFactory()


@pytest.fixture
def cheap(product):
    return ProductVariantFactory(product=product, price=D("10.00"), stock=5)


@pytest.fixture
def dear(product, cheap):  # depends on `cheap` so creation order is deterministic
    return ProductVariantFactory(product=product, price=D("15.00"), stock=5)


def change(variant, commit, **fields):
    """Update fields on an EXISTING variant and save it, committing hooks."""
    for name, value in fields.items():
        setattr(variant, name, value)
    with commit():
        variant.save()


# ══════════════════════════════════════════════════════════════════════════════
# Product.lowest_active_price
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestLowestActivePrice:

    def test_is_the_cheapest_variant_price(self, product, cheap, dear):
        assert product.lowest_active_price == D("10.00")

    def test_inactive_variants_are_ignored(self, product, cheap, dear):
        cheap.is_active = False
        cheap.save()
        assert product.lowest_active_price == D("15.00")

    def test_none_when_there_are_no_active_variants(self, product, cheap):
        cheap.is_active = False
        cheap.save()
        assert product.lowest_active_price is None

    def test_none_when_there_are_no_variants(self, product):
        assert product.lowest_active_price is None

    def test_out_of_stock_variants_still_count(self, product, cheap, dear):
        """Same basis as the storefront card's "starting at": stock is not
        part of it, so selling out / restocking never moves the price."""
        cheap.stock = 0
        cheap.save()
        assert product.lowest_active_price == D("10.00")

    def test_uses_prefetched_variants_without_extra_queries(
        self, product, cheap, dear, django_assert_num_queries
    ):
        from shop.models import Product

        fetched = Product.objects.prefetch_related("variants").get(pk=product.pk)
        with django_assert_num_queries(0):
            assert fetched.lowest_active_price == D("10.00")


# ══════════════════════════════════════════════════════════════════════════════
# Signal — acceptance criteria
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPriceDropSignal:

    # ── 1. decrease that lowers the product's lowest price ──────────────────

    def test_decrease_of_lowest_variant_records_snapshot_and_notifies(
        self, product, cheap, dear, delay, commit
    ):
        assert snapshot_prices(product) == [D("10.00")]  # baseline from creation

        change(cheap, commit, price=D("8.00"))

        assert snapshot_prices(product) == [D("8.00"), D("10.00")]
        delay.assert_called_once_with(product.id, "10.00", "8.00")

    def test_a_dearer_variant_undercutting_the_cheapest_is_a_drop(
        self, product, cheap, dear, delay, commit
    ):
        change(dear, commit, price=D("7.00"))  # now the cheapest of all

        assert snapshot_prices(product)[0] == D("7.00")
        delay.assert_called_once_with(product.id, "10.00", "7.00")

    # ── 2. increase updates baseline, no notification ───────────────────────

    def test_increase_records_new_baseline_without_notifying(
        self, product, cheap, dear, delay, commit
    ):
        change(cheap, commit, price=D("12.00"))

        assert snapshot_prices(product) == [D("12.00"), D("10.00")]
        delay.assert_not_called()

    def test_drop_is_measured_from_the_raised_baseline(
        self, product, cheap, dear, delay, commit
    ):
        """After 10 -> 12 (silent), 12 -> 11 is a drop from 12."""
        change(cheap, commit, price=D("12.00"))
        change(cheap, commit, price=D("11.00"))

        delay.assert_called_once_with(product.id, "12.00", "11.00")

    # ── 3. change that doesn't affect the product's lowest price ────────────

    def test_non_lowest_variant_getting_cheaper_but_staying_above_lowest(
        self, product, cheap, dear, delay, commit
    ):
        """The trickiest case: `dear` drops 15 -> 12 but `cheap` (10) is
        unchanged and still the cheapest — "starting at" didn't move."""
        change(dear, commit, price=D("12.00"))

        assert snapshot_prices(product) == [D("10.00")]  # nothing new recorded
        delay.assert_not_called()

    def test_non_lowest_variant_getting_dearer(
        self, product, cheap, dear, delay, commit
    ):
        change(dear, commit, price=D("20.00"))

        assert snapshot_prices(product) == [D("10.00")]
        delay.assert_not_called()

    def test_non_lowest_variant_matching_the_lowest_is_not_a_drop(
        self, product, cheap, dear, delay, commit
    ):
        change(dear, commit, price=D("10.00"))

        assert snapshot_prices(product) == [D("10.00")]
        delay.assert_not_called()

    def test_resaving_with_an_unchanged_price_does_nothing(
        self, product, cheap, dear, delay, commit
    ):
        change(cheap, commit, price=D("10.00"))

        assert snapshot_prices(product) == [D("10.00")]
        delay.assert_not_called()

    # ── 5. newly created variants never notify ──────────────────────────────

    def test_creating_a_variant_never_notifies(self, product, delay, commit):
        with commit():
            ProductVariantFactory(product=product, price=D("20.00"))
        delay.assert_not_called()

    def test_creating_a_cheaper_variant_lowers_baseline_silently(
        self, product, cheap, delay, commit
    ):
        with commit():
            ProductVariantFactory(product=product, price=D("6.00"))

        assert snapshot_prices(product) == [D("6.00"), D("10.00")]
        delay.assert_not_called()

    def test_creating_the_first_variant_records_a_baseline(
        self, product, delay, commit
    ):
        assert snapshot_prices(product) == []
        with commit():
            ProductVariantFactory(product=product, price=D("10.00"))
        assert snapshot_prices(product) == [D("10.00")]
        delay.assert_not_called()

    # ── The first real change after creation is a detectable drop ───────────

    def test_first_price_cut_on_a_brand_new_product_notifies(
        self, product, delay, commit
    ):
        variant = ProductVariantFactory(product=product, price=D("10.00"))
        change(variant, commit, price=D("9.00"))
        delay.assert_called_once_with(product.id, "10.00", "9.00")


# ══════════════════════════════════════════════════════════════════════════════
# Signal — guards and edge cases
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPriceDropSignalEdgeCases:

    def test_stock_only_saves_are_ignored(self, product, cheap, dear, delay, commit):
        """What every order line / admin adjustment does."""
        before = snapshot_prices(product)
        cheap.stock -= 1
        with commit():
            cheap.save(update_fields=["stock"])

        assert snapshot_prices(product) == before
        delay.assert_not_called()

    def test_stock_only_saves_never_touch_the_snapshot_table(
        self, product, cheap, dear, django_capture_on_commit_callbacks
    ):
        """Every order line saves its variant, so the price-drop hook must be
        free on that path: no snapshot reads or writes at all."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        cheap.stock -= 1
        with CaptureQueriesContext(connection) as ctx:
            with django_capture_on_commit_callbacks(execute=True):
                cheap.save(update_fields=["stock"])

        assert not [
            q["sql"] for q in ctx.captured_queries if "productpricesnapshot" in q["sql"]
        ]

    def test_selling_out_then_restocking_the_cheapest_is_not_a_price_drop(
        self, product, cheap, dear, delay, commit
    ):
        """Regression guard: with a stock-filtered 'lowest price', the
        cheapest selling out would raise the baseline and its restock
        would then look like a price drop."""
        before = snapshot_prices(product)

        cheap.stock = 0
        with commit():
            cheap.save(update_fields=["stock"])
        cheap.stock = 5
        with commit():
            cheap.save(update_fields=["stock"])

        assert snapshot_prices(product) == before
        delay.assert_not_called()

    def test_deactivating_the_cheapest_raises_baseline_without_notifying(
        self, product, cheap, dear, delay, commit
    ):
        change(cheap, commit, is_active=False)  # starting-at: 10 -> 15

        assert snapshot_prices(product) == [D("15.00"), D("10.00")]
        delay.assert_not_called()

    def test_inactive_variant_price_cut_does_not_notify(
        self, product, cheap, dear, delay, commit
    ):
        dear.is_active = False
        dear.save()
        change(dear, commit, price=D("1.00"))  # inactive: not on sale to anyone

        assert snapshot_prices(product) == [D("10.00")]
        delay.assert_not_called()

    def test_product_with_no_prior_snapshot_only_records_a_baseline(
        self, product, cheap, dear, delay, commit
    ):
        product.price_snapshots.all().delete()

        change(cheap, commit, price=D("8.00"))

        assert snapshot_prices(product) == [D("8.00")]
        delay.assert_not_called()

    def test_rolled_back_save_notifies_nobody(
        self, product, cheap, dear, delay, commit
    ):
        before = snapshot_prices(product)

        with commit():
            with pytest.raises(RuntimeError), transaction.atomic():
                cheap.price = D("5.00")
                cheap.save()
                raise RuntimeError("later failure, e.g. an admin inline error")

        delay.assert_not_called()
        assert snapshot_prices(product) == before

    def test_task_args_are_json_safe_strings(self, product, cheap, dear, delay, commit):
        change(cheap, commit, price=D("8.50"))
        _, old_price, new_price = delay.call_args.args
        assert (old_price, new_price) == ("10.00", "8.50")
        assert isinstance(old_price, str) and isinstance(new_price, str)

    def test_snapshots_are_ordered_newest_first(self, product, cheap, dear, commit):
        change(cheap, commit, price=D("9.00"))
        change(cheap, commit, price=D("8.00"))
        assert product.price_snapshots.first().price == D("8.00")


# ══════════════════════════════════════════════════════════════════════════════
# Task — notify_price_drop_subscribers
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestNotifyPriceDropSubscribers:

    def test_counts_only_authenticated_wishlist_subscribers(self, product):
        for _ in range(2):
            Wishlist.objects.create(user=UserFactory(), product=product)
        Wishlist.objects.create(session_key="guest-1", product=product)
        Wishlist.objects.create(session_key="guest-2", product=product)

        result = notify_price_drop_subscribers(product.id, "10.00", "8.00")

        assert result == (
            f"Would notify 2 wishlist subscriber(s) for product {product.id} "
            "price drop 10.00 -> 8.00."
        )

    def test_guest_only_wishlist_notifies_nobody(self, product):
        Wishlist.objects.create(session_key="guest-1", product=product)
        result = notify_price_drop_subscribers(product.id, "10.00", "8.00")
        assert result.startswith("Would notify 0 wishlist subscriber(s)")

    def test_other_products_subscribers_are_not_counted(self, product):
        other = ProductFactory()
        Wishlist.objects.create(user=UserFactory(), product=product)
        Wishlist.objects.create(user=UserFactory(), product=other)
        Wishlist.objects.create(user=UserFactory(), product=other)

        result = notify_price_drop_subscribers(product.id, "10.00", "8.00")

        assert result.startswith("Would notify 1 wishlist subscriber(s)")

    def test_no_subscribers_is_fine(self, product):
        result = notify_price_drop_subscribers(product.id, "10.00", "8.00")
        assert result.startswith("Would notify 0 wishlist subscriber(s)")

    def test_missing_product_returns_message_instead_of_raising(self):
        assert (
            notify_price_drop_subscribers(999999, "10.00", "8.00")
            == "Product no longer exists."
        )

    def test_end_to_end_signal_to_task(self, product, cheap, dear, commit):
        """Real signal -> task (no mocks): .delay is executed eagerly."""
        Wishlist.objects.create(user=UserFactory(), product=product)
        with patch(
            "shop.signals.notify_price_drop_subscribers.delay",
            side_effect=notify_price_drop_subscribers,
        ) as spy:
            change(cheap, commit, price=D("8.00"))
        spy.assert_called_once_with(product.id, "10.00", "8.00")


# ══════════════════════════════════════════════════════════════════════════════
# 0030 backfill migration
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestBackfillPriceSnapshots:

    def test_every_product_with_active_variants_gets_its_lowest_price(
        self, product, cheap, dear
    ):
        other = ProductFactory()
        ProductVariantFactory(product=other, price=D("30.00"))
        ProductPriceSnapshot.objects.all().delete()  # simulate pre-feature data

        backfill_module.backfill_price_snapshots(apps, None)

        assert snapshot_prices(product) == [D("10.00")]
        assert snapshot_prices(other) == [D("30.00")]

    def test_inactive_variants_do_not_set_the_baseline(self, product, cheap, dear):
        cheap.is_active = False
        cheap.save()
        ProductPriceSnapshot.objects.all().delete()

        backfill_module.backfill_price_snapshots(apps, None)

        assert snapshot_prices(product) == [D("15.00")]

    def test_products_without_active_variants_get_no_snapshot(self, product, cheap):
        cheap.is_active = False
        cheap.save()
        bare = ProductFactory()  # no variants at all
        ProductPriceSnapshot.objects.all().delete()

        backfill_module.backfill_price_snapshots(apps, None)

        assert snapshot_prices(product) == []
        assert snapshot_prices(bare) == []
