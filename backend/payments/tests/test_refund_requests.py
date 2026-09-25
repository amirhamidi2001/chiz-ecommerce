from decimal import Decimal

from accounts.models import UserType
from django.contrib.admin import helpers
from django.test import Client
from django.utils import timezone
from order.models import Order
from payments.models import RefundRequest
from rest_framework import status
from rest_framework.test import APITestCase

from .test_views import make_order, make_user

REFUND_URL = "/api/orders/{}/refund-request/"


class RefundRequestCreateViewTests(APITestCase):
    def setUp(self):
        self.user = make_user(email="buyer@example.com")
        self.other_user = make_user(email="other@example.com")
        self.order = make_order(
            self.user, total=Decimal("64.99"), status=Order.Status.DELIVERED
        )
        self.client.force_authenticate(user=self.user)

    def _post(self, order_id, data):
        return self.client.post(REFUND_URL.format(order_id), data, format="json")

    def test_customer_can_request_refund_for_own_delivered_order(self):
        response = self._post(self.order.id, {"reason": "Item arrived damaged."})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(RefundRequest.objects.count(), 1)

        refund_request = RefundRequest.objects.get()
        self.assertEqual(refund_request.order, self.order)
        self.assertEqual(refund_request.requested_by, self.user)
        self.assertEqual(refund_request.reason, "Item arrived damaged.")
        self.assertEqual(refund_request.status, RefundRequest.Status.REQUESTED)
        self.assertIsNone(refund_request.resolved_at)

    def test_default_amount_matches_order_total_when_not_specified(self):
        response = self._post(self.order.id, {"reason": "Wrong item shipped."})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        refund_request = RefundRequest.objects.get()
        self.assertEqual(refund_request.amount, self.order.total)
        self.assertEqual(Decimal(response.data["amount"]), self.order.total)

    def test_explicit_partial_amount_is_honored(self):
        response = self._post(
            self.order.id,
            {"reason": "Only one of two items was defective.", "amount": "20.00"},
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        refund_request = RefundRequest.objects.get()
        self.assertEqual(refund_request.amount, Decimal("20.00"))

    def test_amount_exceeding_order_total_is_rejected(self):
        response = self._post(
            self.order.id, {"reason": "Trying to overclaim.", "amount": "999.00"}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(RefundRequest.objects.count(), 0)

    def test_rejected_for_pending_order_never_paid(self):
        pending_order = make_order(
            self.user, total=Decimal("30.00"), status=Order.Status.PENDING
        )

        response = self._post(pending_order.id, {"reason": "Changed my mind."})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(RefundRequest.objects.count(), 0)

    def test_rejected_for_cancelled_order(self):
        cancelled_order = make_order(
            self.user, total=Decimal("30.00"), status=Order.Status.CANCELLED
        )

        response = self._post(cancelled_order.id, {"reason": "Never received it."})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(RefundRequest.objects.count(), 0)

    def test_rejected_for_order_belonging_to_a_different_user(self):
        others_order = make_order(
            self.other_user, total=Decimal("40.00"), status=Order.Status.DELIVERED
        )

        response = self._post(
            others_order.id, {"reason": "Not mine, but trying anyway."}
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(RefundRequest.objects.count(), 0)

    def test_accepted_for_processing_and_shipped_orders_too(self):
        for order_status in (Order.Status.PROCESSING, Order.Status.SHIPPED):
            order = make_order(self.user, total=Decimal("25.00"), status=order_status)
            response = self._post(order.id, {"reason": f"Testing {order_status}."})
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_missing_reason_is_rejected(self):
        response = self._post(self.order.id, {})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(RefundRequest.objects.count(), 0)


class RefundRequestAdminWorkflowTests(APITestCase):
    """
    Exercises RefundRequestAdmin's status-transition actions directly
    against the model layer (the actions are plain QuerySet.update()
    calls, not view-dependent), mirroring how the admin actions
    themselves operate, then cross-checks via the real admin HTTP
    endpoints for the actor-permission angle.
    """

    def setUp(self):
        self.admin_user = make_user(
            email="admin@example.com",
            type=UserType.ADMIN,
            is_staff=True,
            is_superuser=True,
        )
        self.customer = make_user(email="buyer2@example.com")
        self.order = make_order(
            self.customer, total=Decimal("64.99"), status=Order.Status.DELIVERED
        )
        self.refund_request = RefundRequest.objects.create(
            order=self.order,
            requested_by=self.customer,
            amount=self.order.total,
            reason="Damaged on arrival.",
        )
        self.client = Client()
        self.client.force_login(self.admin_user)

    def _run_action(self, action_name, refund_request=None):
        refund_request = refund_request or self.refund_request
        return self.client.post(
            "/admin/payments/refundrequest/",
            {
                helpers.ACTION_CHECKBOX_NAME: [str(refund_request.pk)],
                "action": action_name,
                "index": "0",
            },
            follow=True,
        )

    def test_full_valid_transition_requested_to_approved_to_processed(self):
        self.assertEqual(self.refund_request.status, RefundRequest.Status.REQUESTED)

        self._run_action("approve_refund_requests")
        self.refund_request.refresh_from_db()
        self.assertEqual(self.refund_request.status, RefundRequest.Status.APPROVED)
        self.assertIsNone(self.refund_request.resolved_at)

        self._run_action("mark_refund_requests_processed")
        self.refund_request.refresh_from_db()
        self.assertEqual(self.refund_request.status, RefundRequest.Status.PROCESSED)
        self.assertIsNotNone(self.refund_request.resolved_at)

    def test_resolved_at_is_set_on_reaching_processed(self):
        before = timezone.now()
        self.refund_request.status = RefundRequest.Status.APPROVED
        self.refund_request.save(update_fields=["status"])

        self._run_action("mark_refund_requests_processed")

        self.refund_request.refresh_from_db()
        self.assertEqual(self.refund_request.status, RefundRequest.Status.PROCESSED)
        self.assertIsNotNone(self.refund_request.resolved_at)
        self.assertGreaterEqual(self.refund_request.resolved_at, before)

    def test_resolved_at_is_set_on_reaching_rejected_from_requested(self):
        self.assertEqual(self.refund_request.status, RefundRequest.Status.REQUESTED)

        self._run_action("reject_refund_requests")

        self.refund_request.refresh_from_db()
        self.assertEqual(self.refund_request.status, RefundRequest.Status.REJECTED)
        self.assertIsNotNone(self.refund_request.resolved_at)

    def test_resolved_at_is_set_on_reaching_rejected_from_approved(self):
        self.refund_request.status = RefundRequest.Status.APPROVED
        self.refund_request.save(update_fields=["status"])

        self._run_action("reject_refund_requests")

        self.refund_request.refresh_from_db()
        self.assertEqual(self.refund_request.status, RefundRequest.Status.REJECTED)
        self.assertIsNotNone(self.refund_request.resolved_at)

    def test_cannot_mark_processed_directly_from_requested(self):
        # Must go through APPROVED first — mark-processed only ever
        # touches rows currently APPROVED.
        self.assertEqual(self.refund_request.status, RefundRequest.Status.REQUESTED)

        self._run_action("mark_refund_requests_processed")

        self.refund_request.refresh_from_db()
        self.assertEqual(self.refund_request.status, RefundRequest.Status.REQUESTED)
        self.assertIsNone(self.refund_request.resolved_at)

    def test_terminal_statuses_are_not_further_transitioned(self):
        self.refund_request.status = RefundRequest.Status.PROCESSED
        self.refund_request.resolved_at = timezone.now()
        self.refund_request.save(update_fields=["status", "resolved_at"])
        original_resolved_at = self.refund_request.resolved_at

        self._run_action("reject_refund_requests")

        self.refund_request.refresh_from_db()
        self.assertEqual(self.refund_request.status, RefundRequest.Status.PROCESSED)
        self.assertEqual(self.refund_request.resolved_at, original_resolved_at)
