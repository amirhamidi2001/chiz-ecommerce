"""
SnapBox (Snapp! Box, snapp-box.com) carrier provider.

DOCUMENTATION RESEARCH (Task 7.2.1.4) — read before touching this file
========================================================================
Per this epic's standing "verify current API docs before hardcoding" rule.
Findings, several of which contradict this task's own framing:

1. SnapBox HAS A REAL, DOCUMENTED MERCHANT API — unlike Iran Post (7.2.1.2)
   and Tipax (7.2.1.3), whose research ended in "portal only, no API". So
   this provider makes real HTTP calls, with the same discipline as Epic 6's
   gateways (timeout=15, `except (requests.RequestException, ValueError)`,
   never raises, always returns the dataclass result with a populated
   error_message on failure). Source: the OpenAPI 3.0 spec ("Snapp! Box —
   API Documentation", v0.1.5) bundled in SnapBox's official npm SDK
   (@snapp-store/snapp-box-sdk). Hosts: production
   https://customer.snapp-box.com, staging https://customer-stg.snapp-box.com.
   Auth: customer token in the `Authorization` header.

2. SNAPBOX IS NOT LOCKER/PICKUP-POINT BASED. The task context suspected
   destinations might be locker IDs. The spec contains no locker or pickup-
   point concept at all: SnapBox is an ON-DEMAND BIKE/VAN COURIER (delivery
   categories "bike", "bike-without-box", "van", "van-heavy"), and every stop
   ("terminal") is addressed by LATITUDE/LONGITUDE plus contact name/phone.
   So the speculative `pickup_point_id` extension was NOT built — there is
   nothing for it to carry. The shared CarrierProvider ABC is unchanged.

3. THE REAL INTERFACE-FIT PROBLEM IS COORDINATES, and it is a genuine gap
   in the wider system, surfaced here rather than papered over:
     - `destination` (and `origin` for get_rate) must include `latitude` and
       `longitude`. This is a SnapBox-specific requirement of the existing
       dict parameter shape; other carriers ignore extra keys. Accepted keys:
         destination: latitude*, longitude*, address, city, contact_name,
                      contact_phone   (* required)
         origin:      same keys; if empty, falls back to SNAPBOX_PICKUP_*.
       For create_shipment, address/city/contact_* fall back to the Order's
       shipping_address/shipping_city/first_name+last_name/phone; latitude and
       longitude have NO fallback.
     - NOTHING IN THE CURRENT SYSTEM STORES COORDINATES: dashboard.Address
       and order.Order have no latitude/longitude fields, and checkout does
       not collect them. Until the checkout flow captures a map pin or a
       geocoding step exists (a follow-up for the Phase 7.2 checkout UI work),
       this provider will return success=False with an explicit "coordinates
       required" message. That is deliberate fail-safe behaviour, not a bug.
     - create_shipment(order, destination) has no origin parameter, so the
       pickup terminal (the store) comes from the SNAPBOX_PICKUP_* settings.

4. SnapBox is CITY-RESTRICTED: the spec names only tehran, mashhad and
   isfahan, and the API takes a single `city` per request, so origin and
   destination must be in the same supported city. It is also same-day by
   nature (ShippingCarrier.supports_same_day). Note the Task 7.1.1.2 seed row
   has supports_same_day=False; an admin should flip it for SnapBox.

5. Pricing is by delivery category and route, NOT package weight: the pricing
   endpoint has no weight field. `weight_g` is accepted (interface contract)
   and deliberately ignored.

UNVERIFIED POINTS — smoke-test against a STAGING token before activating
========================================================================
The carrier is seeded is_active=False, so nothing here goes live until an
admin deliberately enables it. Before doing so, confirm:
  a. The spec comes from the SDK package, published roughly a year ago; the
     live docs (api-docs.snapp-box.com) disallow automated fetching, so this
     could not be cross-checked against the current version.
  b. Auth header format: sent as the raw token (as in the spec's example),
     without a "Bearer " prefix.
  c. Currency unit of `totalFare` is not stated in the spec. It is returned
     unconverted; reconcile with the site's currency (the payment gateways
     here use Rials) before using a live quote for real charging.
  d. GET /v2/orders/{id} has NO documented response body. track() reads a
     top-level `status` (or `data.status`) and returns success=False with an
     explicit message if neither is present, rather than guessing further.
     The raw value is then mapped to a Shipment.Status via _STATUS_MAP below
     (Task 7.2.2.1's poll_shipment_tracking() relies on every provider
     normalizing to this platform's own status vocabulary, not SnapBox's
     raw strings) — that mapping is this file's own interpretation, not
     something SnapBox documents, so revisit it if their status vocabulary
     changes.
  e. The spec contradicts itself in places. Followed the prose parameter
     table for required fields and the schema/example for object shapes:
     `timeSlotDTO` and `pricingId` are optional in the table but required in
     the schema; `packageSize` is in the schema/example but not the table;
     `orderDetails` is typed Array in the table but is an object in the
     schema/example; `vehicleCategory` is required in the table but absent
     from the example. This provider omits timeSlotDTO (also because the
     project runs TIME_ZONE="UTC" and the spec's timestamp timezone is
     unstated) and packageSize, sends vehicleCategory (= deliveryCategory)
     and a pricingId obtained from a preceding pricing call. If staging
     rejects the payload, those are the fields to revisit.
  f. `customerName`/`customerPhonenumber` refer to the merchant account
     ("customer" in SnapBox's terminology), so the pickup contact is used.

Out of scope (not part of the CarrierProvider interface): the cancel_order,
update-order and Verification endpoints, and SnapBox's push webhooks
(ORDER_ACCEPTED, PICKED_UP, DELIVERED, CANCELLED) which would need a
callback view. Only prepaid fares and prepaid terminals are supported — no
cash-on-delivery.
"""

import math
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings

# Shipment lives in shipping/models.py, which imports nothing from
# shipping/providers (and nothing in this package is imported eagerly by
# shipping/__init__.py or models.py — concrete providers are only ever
# resolved lazily, by dotted path, via get_carrier_provider()) — so this
# top-level import is safe, same reasoning already documented for the
# dashboard.models/cart.views imports in shipping/serializers.py and
# shipping/views.py.
from ..models import Shipment
from .base import CarrierProvider, RateQuoteResult, ShipmentCreateResult, TrackingResult

_SUPPORTED_CITIES = ("tehran", "mashhad", "isfahan")
_CITY_ALIASES = {"تهران": "tehran", "مشهد": "mashhad", "اصفهان": "isfahan"}
_DELIVERY_CATEGORIES = ("bike", "bike-without-box", "van", "van-heavy")

_STATUS_DESCRIPTIONS = {
    "PREPENDING": "Scheduled; not yet released to couriers",
    "PENDING": "Waiting for a courier to accept the order",
    "ACCEPTED": "A courier has accepted the order",
    "ARRIVED": "The courier has arrived at the pickup point",
    "ARRIVIED": "The courier has arrived at the pickup point",
    "PICKED_UP": "The package has been picked up",
    "DELIVERED": "The package has been delivered",
    "CANCELLED": "The order was cancelled",
}

# Task 7.2.2.1 (poll_shipment_tracking): maps SnapBox's own status
# vocabulary onto THIS platform's Shipment.Status values. This is an
# interpretive approximation, not a literal 1:1 correspondence — SnapBox
# has no "in transit vs. out for delivery" distinction for a single-leg
# same-day courier the way a multi-hub carrier might. The polling task
# itself stays carrier-agnostic by relying on every concrete provider
# doing this mapping here, rather than normalizing raw carrier strings
# generically.
#   - Every pre-pickup stage (scheduled, waiting for/assigned to a
#     courier, courier en route to or arrived at pickup) maps to PENDING:
#     the package hasn't moved yet from this platform's point of view.
#   - PICKED_UP maps to IN_TRANSIT: the package is now in the courier's
#     possession and moving toward the destination. There's no separate
#     "out for delivery" leg to distinguish for a single-courier,
#     point-to-point same-day delivery.
#   - CANCELLED maps to FAILED.
#   - Anything unrecognized maps to IN_TRANSIT rather than treated as a
#     failure: the order genuinely exists and has *some* non-terminal
#     status, so IN_TRANSIT is the safer default than silently treating
#     an unmapped (but real) status as delivered or failed.
_STATUS_MAP = {
    "PREPENDING": Shipment.Status.PENDING,
    "PENDING": Shipment.Status.PENDING,
    "ACCEPTED": Shipment.Status.PENDING,
    "ARRIVED": Shipment.Status.PENDING,
    "ARRIVIED": Shipment.Status.PENDING,
    "PICKED_UP": Shipment.Status.IN_TRANSIT,
    "DELIVERED": Shipment.Status.DELIVERED,
    "CANCELLED": Shipment.Status.FAILED,
}


def _normalize_status(raw_status):
    """Maps a raw SnapBox status string to a Shipment.Status value."""
    return _STATUS_MAP.get(raw_status.upper(), Shipment.Status.IN_TRANSIT)


def _to_float(value):
    """Parse a coordinate; None for missing, non-numeric, NaN or infinite."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


class SnapBoxCarrierProvider(CarrierProvider):
    """
    SnapBox carrier provider. See this module's docstring for the research
    behind every choice, and the list of points to smoke-test on staging.
    """

    PRODUCTION_BASE_URL = "https://customer.snapp-box.com"
    STAGING_BASE_URL = "https://customer-stg.snapp-box.com"
    PRICING_PATH = "/v1/customer/order/pricing"
    CREATE_ORDER_PATH = "/v1/customer/create_order"
    ORDER_DETAILS_PATH = "/v2/orders/{order_id}"

    REQUEST_TIMEOUT_SECONDS = 15

    # ── HTTP plumbing ────────────────────────────────────────────────────

    def _base_url(self):
        if settings.SNAPBOX_SANDBOX:
            return self.STAGING_BASE_URL
        return self.PRODUCTION_BASE_URL

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Raw token, no "Bearer " prefix — matches the spec's example.
            "Authorization": settings.SNAPBOX_API_KEY,
        }

    def _call(self, method, path, payload=None):
        """
        Returns (http_status, parsed_json, error). `error` is non-empty only
        for transport-level/JSON-decoding failures. Like IDPayGateway, this
        deliberately does not call raise_for_status(): SnapBox's error
        envelope ({"message", "key", ...}) is informative, and discarding it
        in favor of a generic "400 Client Error" would be strictly worse.
        """
        try:
            response = requests.request(
                method,
                f"{self._base_url()}{path}",
                json=payload,
                headers=self._headers(),
                timeout=self.REQUEST_TIMEOUT_SECONDS,
            )
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            return None, None, str(exc)
        return response.status_code, data, ""

    @staticmethod
    def _is_success_status(status):
        return status is not None and 200 <= status < 300

    @staticmethod
    def _error_message(status, data, default):
        detail = ""
        if isinstance(data, dict):
            detail = str(data.get("message") or data.get("error") or "").strip()
        if detail:
            return f"{default} ({detail})"
        if status is not None:
            return f"{default} (HTTP {status})"
        return default

    # ── Location handling ────────────────────────────────────────────────

    @staticmethod
    def _configured_pickup():
        return {
            "city": settings.SNAPBOX_PICKUP_CITY,
            "address": settings.SNAPBOX_PICKUP_ADDRESS,
            "latitude": settings.SNAPBOX_PICKUP_LATITUDE,
            "longitude": settings.SNAPBOX_PICKUP_LONGITUDE,
            "contact_name": settings.SNAPBOX_PICKUP_CONTACT_NAME,
            "contact_phone": settings.SNAPBOX_PICKUP_CONTACT_PHONE,
        }

    @staticmethod
    def _normalize_city(raw_city):
        """Returns a SnapBox city code, or None if unsupported/unrecognised."""
        city = str(raw_city or "").strip()
        if city in _CITY_ALIASES:
            return _CITY_ALIASES[city]
        city = city.lower()
        return city if city in _SUPPORTED_CITIES else None

    def _normalize_location(self, raw, label, require_contact=False):
        """
        Validate a location dict. Returns (location, error); exactly one of
        the two is meaningful. Coordinates are always required — SnapBox
        addresses every stop by latitude/longitude.
        """
        raw = raw or {}
        latitude = _to_float(raw.get("latitude"))
        longitude = _to_float(raw.get("longitude"))
        if (
            latitude is None
            or longitude is None
            or not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
        ):
            return None, (
                f"SnapBox requires valid latitude/longitude for the {label}; "
                "none were supplied (addresses are not geocoded)."
            )

        location = {
            "latitude": latitude,
            "longitude": longitude,
            "address": str(raw.get("address") or "").strip(),
            "contact_name": str(raw.get("contact_name") or "").strip(),
            "contact_phone": str(raw.get("contact_phone") or "").strip(),
            "raw_city": str(raw.get("city") or "").strip(),
        }
        if require_contact:
            missing = [
                name
                for name in ("address", "contact_name", "contact_phone")
                if not location[name]
            ]
            if missing:
                return None, (f"SnapBox requires {', '.join(missing)} for the {label}.")
        return location, ""

    def _resolve_city(self, origin, destination):
        """Returns (city_code, error). Both stops must share one supported city."""
        codes = []
        for loc in (origin, destination):
            if not loc["raw_city"]:
                continue
            code = self._normalize_city(loc["raw_city"])
            if code is None:
                return None, (
                    f"SnapBox does not serve {loc['raw_city']!r}; supported "
                    f"cities: {', '.join(c.title() for c in _SUPPORTED_CITIES)}."
                )
            codes.append(code)
        if not codes:
            return None, "SnapBox requires a city for the pickup or destination."
        if len(set(codes)) > 1:
            return None, (
                "SnapBox delivers within a single city; the pickup and "
                "destination cities differ."
            )
        return codes[0], ""

    @staticmethod
    def _terminal(terminal_type, sequence, location):
        return {
            "type": terminal_type,
            "sequenceNumber": sequence,
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "address": location["address"],
            "contactName": location["contact_name"],
            "contactPhoneNumber": location["contact_phone"],
            # Prepaid only; no cash collected at either stop.
            "paymentType": "prepaid",
            "cashOnPickup": 0,
            "cashOnDelivery": 0,
        }

    def _delivery_category(self):
        category = settings.SNAPBOX_DEFAULT_DELIVERY_CATEGORY
        if category not in _DELIVERY_CATEGORIES:
            return None, (
                f"SNAPBOX_DEFAULT_DELIVERY_CATEGORY={category!r} is not one of "
                f"{', '.join(_DELIVERY_CATEGORIES)}."
            )
        return category, ""

    # ── Pricing (shared by get_rate and create_shipment) ─────────────────

    def _quote(self, origin, destination, city, category):
        """Returns ({"price": Decimal, "pricing_id": str}, error)."""
        payload = {
            "city": city,
            "deliveryCategory": category,
            "deliveryFarePaymentType": "prepaid",
            "isReturn": False,
            "pricingId": None,
            "sequenceNumberDeliveryCollection": 1,
            "totalFare": None,
            "voucherCode": None,
            "waitingTime": 0,
            "customerWalletType": settings.SNAPBOX_CUSTOMER_WALLET_TYPE,
            # The pricing endpoint requires `items` but has no weight field;
            # a single nominal unit stands in (see module docstring).
            "items": [{"quantity": 1, "quantityMeasuringUnit": "unit"}],
            "terminals": [
                self._terminal("pickup", 1, origin),
                self._terminal("drop", 2, destination),
            ],
        }
        status, data, error = self._call("POST", self.PRICING_PATH, payload)
        if error:
            return None, error
        if (
            not self._is_success_status(status)
            or not isinstance(data, dict)
            or data.get("totalFare") is None
        ):
            return None, self._error_message(
                status, data, "SnapBox pricing request failed."
            )
        try:
            price = Decimal(str(data["totalFare"]))
        except InvalidOperation:
            return None, "SnapBox returned an unparseable totalFare."
        if price < 0:
            return None, "SnapBox returned a negative totalFare."
        return {"price": price, "pricing_id": data.get("pricingId") or ""}, ""

    # ── CarrierProvider interface ────────────────────────────────────────

    def get_rate(
        self, origin: dict, destination: dict, weight_g: int
    ) -> RateQuoteResult:
        """
        Live quote from SnapBox's pricing endpoint. `origin` and
        `destination` must carry latitude/longitude (see module docstring);
        an empty `origin` falls back to the SNAPBOX_PICKUP_* settings.
        `weight_g` is ignored — SnapBox prices by category and route, not
        weight. Returns success=False (never raises) if credentials or
        coordinates are missing, the city is unsupported, or the API call
        fails. The price is returned in SnapBox's own currency unit,
        unconverted (see module docstring, point c).
        """
        if not settings.SNAPBOX_API_KEY:
            return RateQuoteResult(
                success=False, error_message="SNAPBOX_API_KEY is not configured."
            )

        origin_loc, error = self._normalize_location(
            origin or self._configured_pickup(), "pickup location"
        )
        if error:
            return RateQuoteResult(success=False, error_message=error)
        destination_loc, error = self._normalize_location(destination, "destination")
        if error:
            return RateQuoteResult(success=False, error_message=error)

        city, error = self._resolve_city(origin_loc, destination_loc)
        if error:
            return RateQuoteResult(success=False, error_message=error)
        category, error = self._delivery_category()
        if error:
            return RateQuoteResult(success=False, error_message=error)

        quote, error = self._quote(origin_loc, destination_loc, city, category)
        if error:
            return RateQuoteResult(success=False, error_message=error)

        # SnapBox is an on-demand courier and the pricing response carries no
        # ETA, so the day estimates stay at 0 (same-day).
        return RateQuoteResult(success=True, price=quote["price"])

    def create_shipment(self, order, destination: dict) -> ShipmentCreateResult:
        """
        Book a courier: one pricing call (to obtain a pricingId, as the spec
        recommends) followed by create_order. `destination` must carry
        latitude/longitude; address/city/contact fall back to the Order's
        shipping fields. The pickup terminal comes from SNAPBOX_PICKUP_*.

        tracking_number is SnapBox's numeric orderId (there is no label, so
        label_url stays empty). The Order's order_number is sent as
        customerRefId, which SnapBox requires to be unique — so an
        accidental second call for the same order is rejected server-side
        rather than double-booking a courier.
        """
        if not settings.SNAPBOX_API_KEY:
            return ShipmentCreateResult(
                success=False, error_message="SNAPBOX_API_KEY is not configured."
            )

        order_number = str(getattr(order, "order_number", "") or "").strip()
        if not order_number:
            return ShipmentCreateResult(
                success=False,
                error_message="SnapBox requires the order's order_number.",
            )

        pickup, error = self._normalize_location(
            self._configured_pickup(), "pickup location", require_contact=True
        )
        if error:
            return ShipmentCreateResult(
                success=False,
                error_message=f"{error} Check the SNAPBOX_PICKUP_* settings.",
            )

        # Fall back to the Order's shipping fields for anything absent OR
        # blank in the caller's dict. Coordinates deliberately have no
        # fallback — nothing in the system stores them.
        destination = dict(destination or {})
        full_name = " ".join(
            part
            for part in (
                getattr(order, "first_name", ""),
                getattr(order, "last_name", ""),
            )
            if part
        )
        for key, fallback in (
            ("address", getattr(order, "shipping_address", "")),
            ("city", getattr(order, "shipping_city", "")),
            ("contact_name", full_name),
            ("contact_phone", getattr(order, "phone", "")),
        ):
            if not destination.get(key):
                destination[key] = fallback

        drop, error = self._normalize_location(
            destination, "destination", require_contact=True
        )
        if error:
            return ShipmentCreateResult(success=False, error_message=error)

        city, error = self._resolve_city(pickup, drop)
        if error:
            return ShipmentCreateResult(success=False, error_message=error)
        category, error = self._delivery_category()
        if error:
            return ShipmentCreateResult(success=False, error_message=error)

        quote, error = self._quote(pickup, drop, city, category)
        if error:
            return ShipmentCreateResult(success=False, error_message=error)

        order_details = {
            "city": city,
            "customerRefId": order_number,
            # SnapBox's "customer" is the merchant account, not the buyer.
            "customerName": pickup["contact_name"],
            "customerPhonenumber": pickup["contact_phone"],
            "deliveryCategory": category,
            "vehicleCategory": category,
            "deliveryFarePaymentType": "prepaid",
            "isReturn": False,
        }
        if quote["pricing_id"]:
            order_details["pricingId"] = quote["pricing_id"]

        payload = {
            "data": {
                "itemDetails": self._item_details(order, order_number),
                "orderDetails": order_details,
                "pickUpDetails": [self._terminal("pickup", 1, pickup)],
                "dropOffDetails": [self._terminal("drop", 2, drop)],
            }
        }

        status, data, error = self._call("POST", self.CREATE_ORDER_PATH, payload)
        if error:
            return ShipmentCreateResult(success=False, error_message=error)

        order_id = None
        if isinstance(data, dict) and isinstance(data.get("data"), dict):
            order_id = data["data"].get("orderId")
        if not self._is_success_status(status) or order_id in (None, ""):
            return ShipmentCreateResult(
                success=False,
                error_message=self._error_message(
                    status, data, "SnapBox order creation failed."
                ),
            )
        return ShipmentCreateResult(success=True, tracking_number=str(order_id))

    def track(self, tracking_number: str) -> TrackingResult:
        """
        Current status of a SnapBox order, by its numeric orderId (the
        tracking_number returned from create_shipment). The endpoint's
        response body is undocumented in the spec — see module docstring,
        point d: a top-level `status` (or `data.status`) is read, and
        success=False with an explicit message is returned if absent.
        """
        if not settings.SNAPBOX_API_KEY:
            return TrackingResult(
                success=False, error_message="SNAPBOX_API_KEY is not configured."
            )

        order_id = str(tracking_number or "").strip()
        # The value is interpolated into a URL path: accept only plain ASCII
        # digits, which also matches SnapBox's numeric orderId.
        if not (order_id.isascii() and order_id.isdigit()):
            return TrackingResult(
                success=False,
                error_message=(
                    "SnapBox tracking numbers are numeric order IDs; got "
                    f"{tracking_number!r}."
                ),
            )

        status, data, error = self._call(
            "GET", self.ORDER_DETAILS_PATH.format(order_id=order_id)
        )
        if error:
            return TrackingResult(success=False, error_message=error)
        if not self._is_success_status(status) or not isinstance(data, dict):
            return TrackingResult(
                success=False,
                error_message=self._error_message(
                    status, data, "SnapBox order lookup failed."
                ),
            )

        raw_status = data.get("status")
        if not raw_status and isinstance(data.get("data"), dict):
            raw_status = data["data"].get("status")
        if not raw_status:
            return TrackingResult(
                success=False,
                error_message=(
                    "SnapBox order lookup returned no recognizable status "
                    "(response shape is undocumented)."
                ),
            )

        raw_status = str(raw_status)
        return TrackingResult(
            success=True,
            status=_normalize_status(raw_status),
            status_description=_STATUS_DESCRIPTIONS.get(raw_status.upper(), ""),
        )

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _item_details(order, order_number):
        items = []
        order_items = getattr(order, "items", None)
        if order_items is not None:
            for item in order_items.all():
                items.append(
                    {
                        "pickedUpSequenceNumber": 1,
                        "dropOffSequenceNumber": 2,
                        "name": item.product_name,
                        "quantity": item.quantity,
                        "quantityMeasuringUnit": "unit",
                    }
                )
        if not items:
            items.append(
                {
                    "pickedUpSequenceNumber": 1,
                    "dropOffSequenceNumber": 2,
                    "name": f"Order {order_number}",
                    "quantity": 1,
                    "quantityMeasuringUnit": "unit",
                }
            )
        return items
