import logging

from accounts.models import UserType
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.db import transaction
from django.template.response import TemplateResponse

from .gateways.base import PaymentVerifyResult
from .models import PaymentAdminOverride, PaymentGatewayConfig, PaymentTransaction
from .services import finalize_transaction_failure, finalize_transaction_success

logger = logging.getLogger(__name__)


def _user_may_force_override(request):
    """
    Same authorization semantic as dashboard.permissions.IsAdminOrSuperuser
    (ADMIN or SUPERUSER account type) — this is a financially sensitive
    override capability that a merely `is_staff` account with basic admin
    access shouldn't be able to reach, even though `is_staff` is already
    required just to log into /admin/ at all.
    """
    user = getattr(request, "user", None)
    return bool(
        user
        and user.is_authenticated
        and user.is_staff
        and user.type in (UserType.ADMIN, UserType.SUPERUSER)
    )


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "gateway",
        "status",
        "authority",
        "amount",
        "created_at",
    )
    list_filter = ("gateway", "status")
    search_fields = ("order__order_number", "authority", "ref_id")
    readonly_fields = [f.name for f in PaymentTransaction._meta.fields]
    ordering = ("-created_at",)
    actions = ["force_mark_success", "force_mark_failed"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    # ── Task 6.4.2.2: deliberate, audit-logged manual override ──────────────

    def has_force_override_permission(self, request):
        """
        Ties the `permissions=["force_override"]` actions below to this
        method, per Django's documented "custom action permission"
        pattern — Django calls has_<name>_permission(self, request) to
        decide both (a) whether the action appears in the dropdown at
        all for this user, and (b) whether a raw POST invoking it by
        name is honored — a non-privileged user forging the request
        directly is rejected by Django's own action-dispatch machinery
        (get_actions() filters the action out of the valid-choices list
        before the view function is ever reached), not just by hiding
        the UI element.
        """
        return _user_may_force_override(request)

    @admin.action(
        description="Manually mark selected as SUCCESS (requires confirmation + reason)",
        permissions=["force_override"],
    )
    def force_mark_success(self, request, queryset):
        return self._force_override(
            request, queryset, PaymentTransaction.Status.SUCCESS
        )

    @admin.action(
        description="Manually mark selected as FAILED (requires confirmation + reason)",
        permissions=["force_override"],
    )
    def force_mark_failed(self, request, queryset):
        return self._force_override(request, queryset, PaymentTransaction.Status.FAILED)

    def _force_override(self, request, queryset, target_status):
        """
        Django's documented "admin action with an intermediate
        confirmation page" pattern (the same shape as the built-in
        delete_selected action): the first POST (from the changelist's
        action dropdown) has no "apply" marker, so this renders a
        confirmation page asking for a free-text reason instead of
        applying anything; only a SECOND POST — from that confirmation
        page's own form, carrying apply=yes plus the reason — actually
        performs the override. A one-click bulk action with no
        justification captured was explicitly what this task avoids.

        NOTE on reusing finalize_transaction_success/failure as
        instructed, rather than a third independent copy: those
        functions were written for the PENDING-only, race-guarded
        callback/reconciliation paths (Task 6.4.2.1), where
        finalize_transaction_failure()'s stock release is conditional on
        `order.status == PENDING`. A manual override is explicitly meant
        to correct transactions in ANY current state — e.g. reversing an
        erroneously-recorded SUCCESS back to FAILED — and in that
        specific reversal, the order would already be PROCESSING (not
        PENDING), so this reused function will NOT retroactively release
        stock. That's a real, known limitation of reusing this function
        as-is rather than redesigning it; it's flagged here rather than
        silently working around it, since changing that function's
        behavior is out of this task's scope.
        """
        if "apply" in request.POST:
            reason = request.POST.get("reason", "").strip()
            if not reason:
                self.message_user(
                    request,
                    "A reason is required to apply a manual override.",
                    level=messages.ERROR,
                )
                return self._render_override_confirmation(
                    request, queryset, target_status, reason_error=True
                )

            updated = 0
            for txn_pk in queryset.values_list("pk", flat=True):
                with transaction.atomic():
                    txn = (
                        PaymentTransaction.objects.select_for_update()
                        .select_related("order")
                        .get(pk=txn_pk)
                    )
                    previous_status = txn.status

                    if target_status == PaymentTransaction.Status.SUCCESS:
                        # No real gateway verification happened here —
                        # this is an admin's own manual correction, not
                        # a confirmed gateway response. raw_callback_
                        # payload is set to say so explicitly, rather
                        # than fabricating something that looks like
                        # real gateway data in the audit trail.
                        synthetic_result = PaymentVerifyResult(
                            success=True,
                            ref_id=txn.ref_id,
                            raw_response={
                                "manual_admin_override": True,
                                "actor": request.user.email,
                                "reason": reason,
                            },
                        )
                        finalize_transaction_success(txn, synthetic_result)
                    else:
                        finalize_transaction_failure(txn)

                    PaymentAdminOverride.objects.create(
                        transaction=txn,
                        actor=request.user,
                        previous_status=previous_status,
                        new_status=target_status,
                        reason=reason,
                    )
                    logger.warning(
                        "Manual payment override: transaction %s (order %s) "
                        "forced %s -> %s by %s. Reason: %s",
                        txn.pk,
                        txn.order.order_number,
                        previous_status,
                        target_status,
                        request.user.email,
                        reason,
                    )
                updated += 1

            self.message_user(
                request,
                f"Manually marked {updated} transaction(s) as {target_status}.",
                level=messages.SUCCESS,
            )
            return None

        return self._render_override_confirmation(request, queryset, target_status)

    def _render_override_confirmation(
        self, request, queryset, target_status, reason_error=False
    ):
        action_name = (
            "force_mark_success"
            if target_status == PaymentTransaction.Status.SUCCESS
            else "force_mark_failed"
        )
        context = {
            **self.admin_site.each_context(request),
            "title": f"Confirm manual override to {target_status.upper()}",
            "queryset": queryset,
            "opts": self.model._meta,
            "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
            "action_name": action_name,
            "target_status": target_status,
            "reason_error": reason_error,
        }
        return TemplateResponse(
            request,
            "admin/payments/paymenttransaction/force_override_confirmation.html",
            context,
        )


@admin.register(PaymentGatewayConfig)
class PaymentGatewayConfigAdmin(admin.ModelAdmin):
    list_display = ("active_gateway", "fallback_order", "updated_at")

    def has_add_permission(self, request):
        return (
            not PaymentGatewayConfig.objects.exists()
        )  # enforce singleton in the UI too

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PaymentAdminOverride)
class PaymentAdminOverrideAdmin(admin.ModelAdmin):
    """
    Fully read-only audit log — same pattern as StockMovement/
    StockAlertSubscription (Epic 4): rows are created ONLY by
    PaymentTransactionAdmin's force_mark_success/force_mark_failed
    actions, never hand-edited or deleted through the admin.
    """

    list_display = (
        "id",
        "transaction",
        "actor",
        "previous_status",
        "new_status",
        "created_at",
    )
    list_filter = ("previous_status", "new_status", "created_at")
    search_fields = (
        "transaction__order__order_number",
        "transaction__authority",
        "actor__email",
        "reason",
    )
    readonly_fields = [f.name for f in PaymentAdminOverride._meta.fields]
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
