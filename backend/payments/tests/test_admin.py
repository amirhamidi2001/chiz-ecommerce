from decimal import Decimal

from accounts.models import UserType
from django.contrib.admin import helpers
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase
from order.models import Order
from order.tests.factories import make_variant
from payments.models import PaymentAdminOverride, PaymentTransaction
from shop.models import StockMovement

from .test_views import make_order, make_order_item, make_user

FORCE_SUCCESS_URL = "/admin/payments/paymenttransaction/"


class PaymentAdminForceOverrideTests(TestCase):
    def setUp(self):
        self.customer = make_user(email="buyer@example.com")
        self.order = make_order(self.customer, total=Decimal("100.00"))
        self.variant = make_variant(stock=5)
        self.order_item = make_order_item(self.order, self.variant, quantity=2)
        self.stock_after_order_creation = self.variant.stock

        self.txn = PaymentTransaction.objects.create(
            order=self.order,
            gateway="zarinpal",
            authority="A00000000000000000000000000000000wOGYpd",
            amount=self.order.total,
            status=PaymentTransaction.Status.PENDING,
        )

        self.admin_user = make_user(
            email="admin@example.com",
            type=UserType.ADMIN,
            is_staff=True,
        )
        self.plain_staff_user = make_user(
            email="staff@example.com",
            type=UserType.CUSTOMER,
            is_staff=True,
        )
        # Both get ordinary Django admin view/change permission on
        # PaymentTransaction — this is baseline "has basic admin access"
        # (they can see the changelist at all, matching the acceptance
        # criteria's framing of the non-privileged user as a STAFF user,
        # not a logged-out stranger). The force_override action's OWN
        # gate (has_force_override_permission, checked separately below)
        # is what's actually under test — not basic changelist access.
        for user in (self.admin_user, self.plain_staff_user):
            content_type = ContentType.objects.get_for_model(PaymentTransaction)
            perms = Permission.objects.filter(
                content_type=content_type, codename__in=["view_paymenttransaction"]
            )
            user.user_permissions.add(*perms)

        self.client = Client()

    def _post_action(self, client, action, apply=False, reason=None, txn=None):
        txn = txn or self.txn
        data = {
            helpers.ACTION_CHECKBOX_NAME: [str(txn.pk)],
            "action": action,
            "index": "0",
        }
        if apply:
            data["apply"] = "yes"
        if reason is not None:
            data["reason"] = reason
        return client.post(FORCE_SUCCESS_URL, data, follow=True)

    # ── Privileged admin: force-success ─────────────────────────────────────

    def test_privileged_admin_force_success_with_reason_marks_success_and_creates_audit_row(
        self,
    ):
        self.client.force_login(self.admin_user)

        # Step 1: dropdown POST with no "apply" yet — shows the
        # confirmation page, applies nothing.
        confirm_response = self._post_action(self.client, "force_mark_success")
        self.assertEqual(confirm_response.status_code, 200)
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.status, PaymentTransaction.Status.PENDING)
        self.assertEqual(PaymentAdminOverride.objects.count(), 0)

        # Step 2: confirmation form's own POST, with apply=yes + a reason.
        apply_response = self._post_action(
            self.client,
            "force_mark_success",
            apply=True,
            reason="Confirmed paid via ZarinPal merchant dashboard directly.",
        )
        self.assertEqual(apply_response.status_code, 200)

        self.txn.refresh_from_db()
        self.order.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(self.txn.status, PaymentTransaction.Status.SUCCESS)
        self.assertEqual(self.order.status, Order.Status.PROCESSING)
        # Stock was already decremented at order-creation time — the
        # override must not touch it.
        self.assertEqual(self.variant.stock, self.stock_after_order_creation)

        override = PaymentAdminOverride.objects.get()
        self.assertEqual(override.transaction, self.txn)
        self.assertEqual(override.actor, self.admin_user)
        self.assertEqual(override.previous_status, PaymentTransaction.Status.PENDING)
        self.assertEqual(override.new_status, PaymentTransaction.Status.SUCCESS)
        self.assertEqual(
            override.reason, "Confirmed paid via ZarinPal merchant dashboard directly."
        )

    def test_privileged_admin_force_failed_marks_failed_cancels_order_and_restores_stock(
        self,
    ):
        self.client.force_login(self.admin_user)

        self._post_action(
            self.client,
            "force_mark_failed",
            apply=True,
            reason="Confirmed via merchant dashboard: payment never actually settled.",
        )

        self.txn.refresh_from_db()
        self.order.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(self.txn.status, PaymentTransaction.Status.FAILED)
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        self.assertEqual(
            self.variant.stock,
            self.stock_after_order_creation + self.order_item.quantity,
        )

        movement = StockMovement.objects.get(
            related_order=self.order, reason=StockMovement.Reason.CANCELLATION
        )
        self.assertEqual(movement.quantity_delta, self.order_item.quantity)

        override = PaymentAdminOverride.objects.get()
        self.assertEqual(override.new_status, PaymentTransaction.Status.FAILED)

    # ── Missing reason ───────────────────────────────────────────────────────

    def test_apply_without_reason_is_rejected_and_makes_no_state_changes(self):
        self.client.force_login(self.admin_user)

        response = self._post_action(
            self.client, "force_mark_success", apply=True, reason=""
        )

        self.assertEqual(response.status_code, 200)

        self.txn.refresh_from_db()
        self.order.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(self.txn.status, PaymentTransaction.Status.PENDING)
        self.assertEqual(self.order.status, Order.Status.PENDING)
        self.assertEqual(self.variant.stock, self.stock_after_order_creation)
        self.assertEqual(PaymentAdminOverride.objects.count(), 0)

    def test_apply_with_only_whitespace_reason_is_also_rejected(self):
        self.client.force_login(self.admin_user)

        self._post_action(self.client, "force_mark_success", apply=True, reason="   ")

        self.txn.refresh_from_db()
        self.assertEqual(self.txn.status, PaymentTransaction.Status.PENDING)
        self.assertEqual(PaymentAdminOverride.objects.count(), 0)

    # ── Non-privileged staff user ────────────────────────────────────────────

    def test_non_privileged_staff_user_cannot_execute_the_action(self):
        self.client.force_login(self.plain_staff_user)

        self._post_action(
            self.client,
            "force_mark_success",
            apply=True,
            reason="Trying to force it anyway.",
        )

        # Django's own action-dispatch machinery rejects an action name
        # that isn't in this user's permitted action list — the action
        # never runs at all, regardless of the apply/reason payload.
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.status, PaymentTransaction.Status.PENDING)
        self.assertEqual(PaymentAdminOverride.objects.count(), 0)

    def test_non_privileged_staff_user_does_not_see_the_action_in_the_dropdown(self):
        self.client.force_login(self.plain_staff_user)

        response = self.client.get(FORCE_SUCCESS_URL)

        self.assertNotContains(response, "force_mark_success")
        self.assertNotContains(response, "force_mark_failed")

    def test_privileged_admin_does_see_the_action_in_the_dropdown(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(FORCE_SUCCESS_URL)

        self.assertContains(response, "force_mark_success")
        self.assertContains(response, "force_mark_failed")


class PaymentAdminOverrideAdminTests(TestCase):
    """PaymentAdminOverride itself must be a fully read-only audit log."""

    def setUp(self):
        self.admin_user = make_user(
            email="admin2@example.com",
            type=UserType.ADMIN,
            is_staff=True,
            is_superuser=True,
        )
        self.customer = make_user(email="buyer2@example.com")
        self.order = make_order(self.customer, total=Decimal("50.00"))
        self.txn = PaymentTransaction.objects.create(
            order=self.order,
            gateway="zarinpal",
            authority="AUTH-1",
            amount=self.order.total,
            status=PaymentTransaction.Status.SUCCESS,
        )
        self.override = PaymentAdminOverride.objects.create(
            transaction=self.txn,
            actor=self.admin_user,
            previous_status=PaymentTransaction.Status.PENDING,
            new_status=PaymentTransaction.Status.SUCCESS,
            reason="test",
        )
        self.client = Client()
        self.client.force_login(self.admin_user)

    def test_cannot_add(self):
        response = self.client.get("/admin/payments/paymentadminoverride/add/")
        self.assertEqual(response.status_code, 403)

    def test_cannot_delete(self):
        self.client.post(
            "/admin/payments/paymentadminoverride/",
            {
                helpers.ACTION_CHECKBOX_NAME: [str(self.override.pk)],
                "action": "delete_selected",
                "index": "0",
            },
        )
        # delete_selected isn't even offered without delete permission,
        # so this POST is rejected before anything is deleted.
        self.assertEqual(PaymentAdminOverride.objects.count(), 1)

    def test_change_view_is_viewable_but_read_only(self):
        # Django's documented behavior for has_view_permission=True (the
        # default; unaffected by this override) combined with
        # has_change_permission=False: the detail page renders (200) in
        # read-only mode — it does NOT 403 on GET. Only an actual write
        # attempt is blocked (see test_post_to_change_view_is_forbidden
        # below) — that's the real immutability guarantee under test.
        response = self.client.get(
            f"/admin/payments/paymentadminoverride/{self.override.pk}/change/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="_save"')

    def test_post_to_change_view_is_forbidden_and_makes_no_change(self):
        response = self.client.post(
            f"/admin/payments/paymentadminoverride/{self.override.pk}/change/",
            {"reason": "trying to hand-edit the audit log"},
        )
        self.assertEqual(response.status_code, 403)

        self.override.refresh_from_db()
        self.assertEqual(self.override.reason, "test")
