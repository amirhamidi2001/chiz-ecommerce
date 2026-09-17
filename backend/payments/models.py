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
