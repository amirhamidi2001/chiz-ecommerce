from django.conf import settings
from django.db import models


class PaymentTransaction(models.Model):
    class Gateway(models.TextChoices):
        ZARINPAL = "zarinpal", "ZarinPal"
        ZIBAL = "zibal", "Zibal"
        IDPAY = "idpay", "IDPay"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    order = models.ForeignKey(
        "order.Order", on_delete=models.CASCADE, related_name="payment_transactions"
    )
    gateway = models.CharField(max_length=20, choices=Gateway.choices)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    authority = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Gateway-issued reference code for this transaction (ZarinPal calls this 'Authority').",
    )
    ref_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Gateway-issued final transaction reference, populated on success.",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    raw_callback_payload = models.JSONField(
        null=True,
        blank=True,
        help_text="Full raw payload received from the gateway's callback, stored for audit/debugging.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["gateway", "authority"])]

    def __str__(self):
        return f"{self.gateway} — {self.order.order_number} — {self.status}"


class PaymentGatewayConfig(models.Model):
    """
    Singleton config row (Task 6.3.1.3) letting an admin change which
    gateway checkout uses, and its fallback chain, at runtime — without
    an env var change + redeploy. No existing singleton-config pattern
    was found elsewhere in this codebase (checked first), so this uses
    the straightforward pk=1-enforced approach: save() always writes to
    pk=1, and get_solo() get-or-creates that one row, using this model's
    own field default (Gateway.ZARINPAL) the first time it's ever
    accessed — e.g. immediately after a fresh deploy, before an admin
    has configured anything through the admin site.
    """

    active_gateway = models.CharField(
        max_length=20,
        choices=PaymentTransaction.Gateway.choices,
        default=PaymentTransaction.Gateway.ZARINPAL,
    )
    fallback_order = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Ordered list of gateway names to try if the active gateway's "
            "request fails, e.g. ['zibal', 'idpay']."
        ),
    )
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.pk = 1  # enforce singleton
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Payment gateway config (active: {self.active_gateway})"


class PaymentAdminOverride(models.Model):
    """
    Audit log for a support/admin agent manually forcing a
    PaymentTransaction to SUCCESS or FAILED through the admin action
    (Task 6.4.2.2) — e.g. a support agent confirms via the gateway's own
    merchant dashboard that a payment actually succeeded despite this
    platform's records showing it failed, and needs to correct it
    without opening a full unrestricted edit form. Distinct from
    StockMovement (Epic 4's audit-logging convention) since this isn't
    specifically a stock event — it's about WHO overrode WHICH
    transaction, WHY, and what the status was before/after.

    Deliberately has no admin add/change/delete permission of its own
    (see PaymentAdminOverrideAdmin) — rows are only ever created by the
    force_mark_success/force_mark_failed admin actions on
    PaymentTransactionAdmin, never edited or deleted afterward.
    """

    transaction = models.ForeignKey(
        PaymentTransaction, on_delete=models.CASCADE, related_name="admin_overrides"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    previous_status = models.CharField(max_length=20)
    new_status = models.CharField(max_length=20)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"Override of transaction #{self.transaction_id}: "
            f"{self.previous_status} → {self.new_status}"
        )
