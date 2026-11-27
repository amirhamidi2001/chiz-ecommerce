"""
End-to-end proof that the Settings page toggles control REAL notification dispatch.

The SPA's SettingsTab PATCHes /api/auth/profile/ with order_updates / promotions /
newsletter. A checkbox that only saves a DB value nobody reads would pass every
unit test, so these tests go the whole way, with no mock on notify() or on
_default_channels_for():

    PATCH /api/auth/profile/  (the exact call SettingsTab makes)
      -> real domain event (variant price drop, restock, order status change)
      -> real signal -> real Celery task body -> real notify()
      -> real email task -> Django's locmem outbox   /   mocked SMS gateway

Only the transports are faked: Celery's `.delay` runs the task body inline (the
project's convention for async side effects) and the SMS provider is a MagicMock.
"""

from unittest.mock import MagicMock, patch

import pytest
from dashboard.models import Wishlist
from django.core import mail
from notifications.models import NotificationLog, NotificationTemplate
from notifications.tasks import send_notification_email_task
from shop.models import StockAlertSubscription, StockMovement
from shop.tasks import notify_price_drop_subscribers, notify_stock_alert_subscribers
from shop.tests.factories import (
    ProductFactory,
    ProductVariantFactory,
    StockMovementFactory,
)

PROFILE_URL = "/api/auth/profile/"
Event = NotificationTemplate.Event


# ─── harness ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def inline_tasks():
    """Run the three Celery tasks in the chain synchronously instead of queueing."""
    with (
        patch(
            "shop.signals.notify_price_drop_subscribers.delay",
            side_effect=lambda *a, **k: notify_price_drop_subscribers(*a, **k),
        ),
        patch(
            "shop.signals.notify_stock_alert_subscribers.delay",
            side_effect=lambda *a, **k: notify_stock_alert_subscribers(*a, **k),
        ),
        patch(
            "notifications.email.send_notification_email_task.delay",
            side_effect=lambda *a, **k: send_notification_email_task(*a, **k),
        ),
    ):
        yield


@pytest.fixture
def sms():
    provider = MagicMock()
    provider.send.return_value = True
    with patch("notifications.sms.get_sms_provider", return_value=provider):
        yield provider


@pytest.fixture
def commit(django_capture_on_commit_callbacks):
    """Run a block, then fire its on_commit hooks like a real commit would."""
    return lambda: django_capture_on_commit_callbacks(execute=True)


def save_prefs(client, **prefs):
    """Exactly what SettingsTab.savePreferences() does, then check it persisted."""
    res = client.patch(PROFILE_URL, prefs, format="json")
    assert res.status_code == 200, res.data
    return res


def price_drops(user, commit):
    """Wishlist a product, then genuinely lower its lowest active price."""
    product = ProductFactory()
    variant = ProductVariantFactory(product=product, price=100_000, stock=5)
    Wishlist.objects.create(user=user, product=product)
    variant.price = 80_000
    with commit():
        variant.save()


def restock(user, commit):
    """Subscribe to a sold-out variant's alert, then restock it 0 -> 5."""
    variant = ProductVariantFactory(stock=0)
    StockAlertSubscription.objects.create(user=user, variant=variant)
    with commit():
        StockMovementFactory(
            variant=variant,
            reason=StockMovement.Reason.RESTOCK,
            quantity_delta=5,
            stock_after=5,
        )


def logs_for(user, event):
    return NotificationLog.objects.filter(user=user, event=event)


# ─── promotions toggle -> price-drop / back-in-stock ──────────────────────────

TRIGGERS = [
    pytest.param(price_drops, Event.PRICE_DROP, id="price_drop"),
    pytest.param(restock, Event.BACK_IN_STOCK, id="back_in_stock"),
]


@pytest.mark.django_db
@pytest.mark.parametrize("trigger, event", TRIGGERS)
class TestPromotionsToggleControlsDispatch:
    def test_off_by_default_so_nothing_is_sent(self, customer, commit, trigger, event):
        assert customer.profile.promotions is False  # the registration default
        trigger(customer, commit)
        assert mail.outbox == []
        assert not logs_for(customer, event).exists()

    def test_turning_it_on_in_settings_delivers_the_email(
        self, customer_client, customer, commit, trigger, event
    ):
        res = save_prefs(customer_client, promotions=True)
        assert res.data["promotions"] is True
        customer.profile.refresh_from_db()
        assert customer.profile.promotions is True  # persisted, not just echoed

        trigger(customer, commit)

        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [customer.email]
        sent = logs_for(customer, event).filter(
            channel="email", status=NotificationLog.Status.SENT
        )
        assert sent.count() == 1

    def test_turning_it_back_off_stops_it_again(
        self, customer_client, customer, commit, trigger, event
    ):
        save_prefs(customer_client, promotions=True)
        save_prefs(customer_client, promotions=False)

        trigger(customer, commit)

        assert mail.outbox == []
        assert not logs_for(customer, event).exists()

    def test_unrelated_toggles_do_not_enable_it(
        self, customer_client, customer, commit, trigger, event
    ):
        save_prefs(customer_client, order_updates=True, newsletter=True)
        trigger(customer, commit)
        assert mail.outbox == []


@pytest.mark.django_db
class TestOnlyTheOptedInUserIsNotified:
    def test_two_wishlisters_one_price_drop(self, customer, make_user, commit):
        other = make_user(email="other@example.com")
        customer.profile.promotions = True
        customer.profile.save()  # `other` keeps the default (off)

        product = ProductFactory()
        variant = ProductVariantFactory(product=product, price=100_000, stock=5)
        Wishlist.objects.create(user=customer, product=product)
        Wishlist.objects.create(user=other, product=product)
        variant.price = 80_000
        with commit():
            variant.save()

        assert [m.to for m in mail.outbox] == [[customer.email]]
        assert not NotificationLog.objects.filter(user=other).exists()


# ─── order_updates toggle -> order status change (Epic 8 signal) ──────────────


@pytest.mark.django_db
class TestOrderUpdatesToggleControlsDispatch:
    def ship(self, order, commit):
        # Load the order fresh, as the admin status-change request would. The
        # fixture's in-memory `order.user.profile` was cached BEFORE the PATCH and
        # would still hold the old preference, which no real request ever sees.
        from order.models import Order

        order = Order.objects.get(pk=order.pk)
        order.status = "shipped"
        with commit():
            order.save()

    def test_on_sends_sms_and_email(self, customer_client, make_order, sms, commit):
        save_prefs(customer_client, order_updates=True)
        order = make_order()

        self.ship(order, commit)

        sms.send.assert_called_once()
        assert order.order_number in sms.send.call_args.args[1]
        assert len(mail.outbox) == 1
        assert logs_for(order.user, Event.ORDER_STATUS_CHANGED).count() >= 2

    def test_off_in_settings_sends_nothing(
        self, customer_client, make_order, sms, commit
    ):
        save_prefs(customer_client, order_updates=False)
        order = make_order()

        self.ship(order, commit)

        sms.send.assert_not_called()
        assert mail.outbox == []
        assert not logs_for(order.user, Event.ORDER_STATUS_CHANGED).exists()

    def test_the_two_categories_are_independent(
        self, customer_client, customer, make_order, sms, commit
    ):
        """promotions on + order_updates off: promo mail yes, order texts no."""
        save_prefs(customer_client, promotions=True, order_updates=False)

        price_drops(customer, commit)
        assert len(mail.outbox) == 1  # the promo email

        self.ship(make_order(), commit)
        sms.send.assert_not_called()
        assert len(mail.outbox) == 1  # still just the promo email
