# IranProvince is fundamentally a general-purpose "Iran's provinces"
# concept, not something that's actually dashboard-specific — it just
# happened to be introduced there first (Epic 5 Task 5.2.1.4) because
# Address.province was the first field that needed it. Checked for
# circularity before importing directly: dashboard doesn't import
# anything from shipping (dashboard/models.py, admin.py, views.py,
# serializers.py, services.py, filters.py all only import from
# accounts/blog/contact/order/shop, never shipping), so this top-level
# import is safe today. If a future app-loading-order or circular-
# import problem ever does bite, the right fix is moving IranProvince
# to a shared lower-level location (e.g. a small core app or
# common/choices.py) that both dashboard and shipping import from —
# not a local import hidden inside a function body.
from dashboard.models import IranProvince
from django.core.exceptions import ValidationError
from django.db import models


class ShippingCarrier(models.Model):
    class Code(models.TextChoices):
        POST = "post", "Iran Post"
        TIPAX = "tipax", "Tipax"
        SNAPBOX = "snapbox", "SnapBox"
        ALOPEYK = "alopeyk", "AloPeyk"

    code = models.CharField(max_length=20, choices=Code.choices, unique=True)
    display_name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Carrier-specific settings (API base URL overrides, account IDs, "
            "etc.) NOT including secret API keys — those belong in "
            "environment variables, never in this DB-stored JSON field."
        ),
    )
    supports_same_day = models.BooleanField(
        default=False,
        help_text=(
            "Whether this carrier can offer same-day/local delivery "
            "(relevant for AloPeyk-style city-restricted couriers)."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_name"]

    def __str__(self):
        return self.display_name


class ShippingRate(models.Model):
    carrier = models.ForeignKey(
        ShippingCarrier, on_delete=models.CASCADE, related_name="rates"
    )
    province = models.CharField(
        max_length=30,
        choices=IranProvince.choices,
        help_text="Destination province this rate applies to.",
    )
    city = models.CharField(
        max_length=100,
        blank=True,
        help_text=(
            "Optional: leave blank to apply to the whole province; set "
            "to override for a specific city (e.g. same-city rates for "
            "AloPeyk)."
        ),
    )
    min_weight_g = models.PositiveIntegerField(default=0)
    max_weight_g = models.PositiveIntegerField(
        help_text="Upper bound of this weight bracket, in grams."
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    estimated_days_min = models.PositiveSmallIntegerField(default=1)
    estimated_days_max = models.PositiveSmallIntegerField(default=3)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["carrier", "province", "min_weight_g"]
        indexes = [models.Index(fields=["carrier", "province", "city"])]

    def __str__(self):
        return (
            f"{self.carrier.display_name} — {self.get_province_display()} "
            f"({self.min_weight_g}-{self.max_weight_g}g): {self.price}"
        )

    def clean(self):
        super().clean()
        # Mirrors the expiration_date/manufacture_date ordering check
        # (Epic 3 Task 3.2.1.7): only meaningful once both bounds are
        # set, which they always are here (max_weight_g has no
        # default), but the explicit None-guard keeps this consistent
        # with that established pattern and safe against a form that
        # leaves the field unbound pre-validation.
        if (
            self.max_weight_g is not None
            and self.min_weight_g is not None
            and self.max_weight_g <= self.min_weight_g
        ):
            raise ValidationError(
                {"max_weight_g": "Max weight must be greater than min weight."}
            )

    @classmethod
    def find_rate(cls, carrier, province, city, weight_g):
        """
        Find the most specific matching active rate: prefer an exact
        city match over a province-wide (blank city) rate. Returns
        None when nothing matches (weight outside every defined
        bracket, or no rate configured at all for that
        carrier/province) — callers (Task 7.1.1.4) must handle a None
        result rather than assume a rate always exists.
        """
        qs = cls.objects.filter(
            carrier=carrier,
            province=province,
            is_active=True,
            min_weight_g__lte=weight_g,
            max_weight_g__gte=weight_g,
        )
        city_specific = qs.filter(city=city).first()
        if city_specific:
            return city_specific
        return qs.filter(city="").first()


class Shipment(models.Model):
    """
    The actual booked shipment for a paid order — created when a
    warehouse/admin physically packs and dispatches the order (Phase 7.2's
    admin fulfillment workflow), NOT at checkout/payment time.

    This is distinct from Order.shipping_carrier (Task 7.1.1.4), which
    only records which carrier the CUSTOMER selected/quoted at checkout —
    that field can exist with no Shipment yet (order is paid but not yet
    packed), and once dispatched this row is what actually carries the
    tracking number, label, and live delivery status.

    KNOWN SIMPLIFICATION: `order` is a OneToOneField because exactly one
    shipment exists per order in this initial implementation — there is
    no support for split/multi-package shipments per order yet. A future
    "split shipment" feature would need to change this to a ForeignKey
    (with related_name="shipments" instead of "shipment") and update
    every place that currently assumes order.shipment is a single object.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Pickup"
        IN_TRANSIT = "in_transit", "In Transit"
        OUT_FOR_DELIVERY = "out_for_delivery", "Out for Delivery"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"

    order = models.OneToOneField(
        "order.Order", on_delete=models.CASCADE, related_name="shipment"
    )
    # PROTECT, deliberately unlike most other FKs in this codebase (e.g.
    # ShippingRate.carrier above uses CASCADE): a ShippingCarrier must
    # never be DELETABLE while any Shipment still references it — deleting
    # the carrier would corrupt historical shipment records (losing the
    # ability to know who actually shipped a past order) in a way that's
    # worse than just blocking the deletion outright. If an admin genuinely
    # needs to retire a carrier, ShippingCarrier.is_active=False is the
    # correct mechanism, not deletion.
    carrier = models.ForeignKey(ShippingCarrier, on_delete=models.PROTECT)
    tracking_number = models.CharField(max_length=100, blank=True, db_index=True)
    label_url = models.URLField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    last_tracked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Shipment for {self.order.order_number} — {self.status}"
