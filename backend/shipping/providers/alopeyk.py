"""
AloPeyk (الوپیک, alopeyk.com) carrier provider.

DOCUMENTATION RESEARCH (Task 7.2.1.5) — read before touching this file
========================================================================
Per this epic's standing "verify current API docs before hardcoding" rule.
AloPeyk's live documentation (docs.alopeyk.com) disallows automated fetching,
but AloPeyk itself publishes and maintains official open-source SDKs whose
actual SOURCE CODE (not just READMEs) was read directly:
AloPeyk/AloPeyk-Api-PHP and AloPeyk/AloPeyk-Api-Laravel on GitHub. Findings:

1. AloPeyk HAS A REAL, DOCUMENTED MERCHANT API — same conclusion as SnapBox
   (7.2.1.4), unlike Iran Post/Tipax (7.2.1.2/.3). Auth is a static,
   long-lived "ACCESS-TOKEN" (JWT) issued by AloPeyk's sales team
   (alopeyk.com/contact?unit=sales — a business relationship is still
   required to obtain the token, but once issued it is used directly, no
   separate login/exchange call), sent as `Authorization: Bearer <token>` —
   confirmed literally from the SDK's HTTP layer (getCurlOptions() in
   AloPeykApiHandler.php), along with `Content-Type: application/json;
   charset=utf-8` and `X-Requested-With: XMLHttpRequest`.

2. THE INITIAL "TEHRAN, MASHHAD, ISFAHAN, ETC." ASSUMPTION IN THIS TASK'S
   OWN CONTEXT DOES NOT MATCH REALITY. Per AloPeyk's own company-news page
   (digiato.com, an established Iranian tech-news outlet, article checked
   as of this task): "در حال حاضر ناوگان الوپیک در شهرهای تهران، کرج، مشهد و
   شیراز فعال است" — AloPeyk's fleet is currently active in exactly TEHRAN,
   KARAJ, MASHHAD, and SHIRAZ. Isfahan is notably NOT currently served,
   contrary to the common assumption. The same article states AloPeyk is
   gradually expanding to more cities, so — per this task's own guidance —
   this hardcoded list should be re-verified periodically rather than
   trusted indefinitely; there is no documented serviceability-check API
   endpoint to query this dynamically instead (see point 5 below).

3. Confirmed REST endpoints and payload/response shapes (from
   AloPeykApiHandler.php's actual request-building code and the PHP
   package's own documented sample responses — not guessed):
     - POST `orders/price/calc`  — price a quote (Order::getPrice())
     - POST `orders/batch-price` — price up to 15 quotes in one call
       (not used here; out of scope, like SnapBox's cancel/webhooks)
     - POST `orders`             — create a shipment (Order::create())
     - GET  `orders/{id}?columns=*,addresses,screenshot,progress,
       courier_info,next_address_any,customer,last_position_minimal,
       eta_minimal` — order detail / tracking (Order::getDetails());
       {id} is validated as an integer by the SDK itself.
     - GET  `orders/{id}/cancel` / `orders/{id}/finish` — out of scope,
       like SnapBox's cancel/webhook endpoints (no CarrierProvider method
       needs them).
   Response envelope: {"status": "success"|"fail", "message": ..., "object":
   ...}. On failure, the SDK reads the error text from, in order:
   response.message, then response.object.error_msg, then
   response.object.message (itself sometimes a JSON-encoded list of
   per-field validation errors, in which case the first entry is used) —
   replicated exactly in _error_message() below, since this is copied from
   real SDK behavior rather than guessed.
   Price quote response (object): "price" (total, in Toman, per the SDK's
   own inline comment), "distance" (meters), "duration" (seconds), "city",
   "status" ("OK" for a valid quote — a distinct field from the order's own
   lifecycle status), "addresses" (per-leg price/distance/duration).
   Create-order response adds "id" (numeric — used as tracking_number),
   "invoice_number", "order_token", "status" ("new" immediately after
   creation, confirmed in the SDK's own sample response).

4. Address payload shape: {"type": "origin"|"destination", "lat", "lng"},
   plus optional "description", "unit", "number", "person_fullname",
   "person_phone" for create_shipment (the pricing call needs only
   type/lat/lng). AloPeyk resolves the city itself server-side from
   coordinates — it is not sent as an input field, only returned. So, as
   with SnapBox, `origin`/`destination` here must carry latitude/longitude
   (nothing in the wider system stores these yet — see SnapBox's module
   docstring for that same, still-open gap); `city`/`province` are used
   ONLY for this provider's own is_available_for_city() pre-check, not sent
   to AloPeyk at all.

5. is_available_for_city() is a HARDCODED LIST (task-approved option), not
   a live API call: no serviceability-check endpoint exists in the
   confirmed method list above (authenticate, getAddress,
   getLocationSuggestion, getPrice, getBatchPrice, createOrder,
   getOrderDetail, cancelOrder, finishOrder, getUserProfile,
   validateCoupon, getPaymentGateways, getTransportTypes, getPaymentRoute,
   getTrackingUrl, getPrintInvoice, getAppConfig, getSignaturePath,
   CustomerLoyaltyProducts — nothing resembling "is this city served").
   A live quote call WOULD presumably fail for an out-of-area coordinate,
   but that is a paid/rate-limited API call — checking a small hardcoded
   list first, per this task's explicit instruction, avoids that call
   entirely for a city we already know isn't served.

6. FOLLOW-THROUGH DECISION (this task's "your call" on 7.1.1.4 /
   7.2.1.6): the ShippingRate-table-only safeguard (no admin ever adding an
   AloPeyk rate for an unserved city) is judged INSUFFICIENT on its own —
   an admin could add such a row by mistake (typo, copy-paste from another
   city, or AloPeyk's service area itself later CONTRACTING in some city
   without anyone updating the rate table). Since this provider now offers
   a free, local, no-API-call is_available_for_city() check, Task 7.2.1.6's
   quote endpoint SHOULD call get_carrier_provider("alopeyk")
   .is_available_for_city(city, province) as an explicit second layer, in
   addition to (not instead of) curating ShippingRate rows correctly — this
   is a recommendation for that task to act on, since this file cannot
   modify shipping's checkout/quote endpoint itself.

UNVERIFIED POINTS — smoke-test against a real token before activating
========================================================================
The carrier is seeded is_active=False, so nothing here goes live until an
admin deliberately enables it. Before doing so, confirm:
  a. ALOPEYK_API_BASE_URL: only the production host (api.alopeyk.com) could
     be independently confirmed, from a screenshot URL embedded in one of
     AloPeyk's own documented sample API responses. The SDK supports a
     separate 'sandbox' endpoint, but its literal URL lives in a package
     config file this research could not access — get the real value (and
     any sandbox URL) from AloPeyk's sales contact before going live, and
     set ALOPEYK_API_BASE_URL accordingly per environment.
  b. Order status values: "new", "delivered", and "cancelled" are confirmed
     directly from the SDK's own sample responses. The others in
     _STATUS_DESCRIPTIONS ("accepted", "picking", "delivering", "finished",
     "stopped", "removed") are INFERRED from timestamp field names visible
     in the same sample response (accepted_at, picking_at, delivering_at,
     finished_at, stopped_at, removed_at) — plausible, but not literally
     confirmed as the exact status string AloPeyk sends.
  c. Currency: the SDK's own inline comment states price is in Toman
     (unlike SnapBox, where this was unstated) — still, reconcile against
     this project's Rial-denominated payment gateways before charging a
     live quote for real.
  d. hasReturn/has_return semantics ($order->setHasReturn(true) in the
     SDK's own examples) are always sent as False here (no round-trip
     courier legs), since nothing in this project's checkout needs one.

Out of scope (not part of the CarrierProvider interface): cancelOrder,
finishOrder (rating/comment on completion), batch pricing, coupon
validation, and AloPeyk's own tracking-URL helper (a customer-facing page,
not the CarrierProvider.track() contract, which needs a status, not a URL).
"""

import math
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings

# Safe top-level import — same reasoning as shipping/providers/snapbox.py's
# identical import (shipping/models.py imports nothing from this package,
# and concrete providers are only ever resolved lazily by dotted path).
from ..models import Shipment
from .base import CarrierProvider, RateQuoteResult, ShipmentCreateResult, TrackingResult

# Source: digiato.com company-news article (see module docstring, point 2).
# city -> expected IranProvince slug (Task 7.1.1.3's ShippingRate.province
# choices), used as a defensive cross-check in is_available_for_city().
_SERVED_CITIES = {
    "tehran": "tehran",
    "karaj": "alborz",
    "mashhad": "khorasan_razavi",
    "shiraz": "fars",
}
_CITY_ALIASES = {
    "تهران": "tehran",
    "کرج": "karaj",
    "مشهد": "mashhad",
    "شیراز": "shiraz",
}

_STATUS_DESCRIPTIONS = {
    # Confirmed directly from the SDK's own documented sample responses.
    "NEW": "Order placed; waiting for a courier to accept it",
    "DELIVERED": "The package has been delivered",
    "CANCELLED": "The order was cancelled",
    # Inferred from timestamp field names on the order-detail response
    # (accepted_at, picking_at, delivering_at, finished_at, stopped_at,
    # removed_at) — not literally confirmed; see module docstring point b.
    "ACCEPTED": "A courier has accepted the order",
    "PICKING": "The courier is picking up the package",
    "DELIVERING": "The courier is en route to the destination",
    "FINISHED": "The order was completed and rated",
    "STOPPED": "The order was stopped",
    "REMOVED": "The order was removed",
}

# Task 7.2.2.1 (poll_shipment_tracking): maps AloPeyk's own status
# vocabulary onto THIS platform's Shipment.Status values — an interpretive
# approximation (like SnapBox's equivalent _STATUS_MAP), not something
# AloPeyk documents as a formal mapping, since several of these raw
# statuses are themselves inferred rather than confirmed (see
# _STATUS_DESCRIPTIONS above and module docstring point b).
#   - NEW/ACCEPTED/PICKING all map to PENDING: the package hasn't left
#     the pickup point yet in any of these.
#   - DELIVERING maps to OUT_FOR_DELIVERY: a direct semantic match for an
#     on-demand courier actively en route to the destination.
#   - DELIVERED and FINISHED (completed + rated, a terminal state that
#     follows DELIVERED) both map to DELIVERED.
#   - STOPPED/REMOVED/CANCELLED all map to FAILED.
#   - Anything unrecognized maps to IN_TRANSIT rather than treated as a
#     failure, same reasoning as SnapBox's default: the order genuinely
#     exists and has *some* non-terminal status.
_STATUS_MAP = {
    "NEW": Shipment.Status.PENDING,
    "ACCEPTED": Shipment.Status.PENDING,
    "PICKING": Shipment.Status.PENDING,
    "DELIVERING": Shipment.Status.OUT_FOR_DELIVERY,
    "DELIVERED": Shipment.Status.DELIVERED,
    "FINISHED": Shipment.Status.DELIVERED,
    "STOPPED": Shipment.Status.FAILED,
    "REMOVED": Shipment.Status.FAILED,
    "CANCELLED": Shipment.Status.FAILED,
}


def _normalize_status(raw_status):
    """Maps a raw AloPeyk status string to a Shipment.Status value."""
    return _STATUS_MAP.get(raw_status.upper(), Shipment.Status.IN_TRANSIT)


def _to_float(value):
    """Parse a coordinate; None for missing, non-numeric, NaN or infinite."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


class AloPeykCarrierProvider(CarrierProvider):
    """
    AloPeyk carrier provider. See this module's docstring for the research
    behind every choice, and the points to confirm before activating.
    """

    PRICE_PATH = "orders/price/calc"
    CREATE_ORDER_PATH = "orders"
    ORDER_DETAIL_PATH = (
        "orders/{order_id}"
        "?columns=*,addresses,screenshot,progress,courier_info,"
        "next_address_any,customer,last_position_minimal,eta_minimal"
    )

    REQUEST_TIMEOUT_SECONDS = 15

    # ── City availability (this task's headline feature) ────────────────

    @staticmethod
    def _normalize_city(raw_city):
        city = str(raw_city or "").strip()
        if city in _CITY_ALIASES:
            return _CITY_ALIASES[city]
        return city.lower()

    def is_available_for_city(self, city: str, province: str) -> bool:
        """
        Whether AloPeyk currently serves the given city. AloPeyk-specific
        capability beyond the shared CarrierProvider interface (no other
        carrier in this epic needs a service-area check), so it lives here
        on the concrete class rather than on the ABC.

        Checked against a hardcoded list of AloPeyk's currently-served
        cities (see module docstring, points 2 and 5, for why this is a
        list rather than a live API call, and its source/staleness
        caveat). `province` is a defensive cross-check: if it's supplied
        and doesn't match the city's expected province, this returns
        False rather than trusting a possibly-inconsistent combination —
        pass an empty province to skip that cross-check.
        """
        code = self._normalize_city(city)
        expected_province = _SERVED_CITIES.get(code)
        if expected_province is None:
            return False
        if province and str(province).strip().lower() != expected_province:
            return False
        return True

    # ── HTTP plumbing ────────────────────────────────────────────────────

    def _headers(self):
        return {
            "Content-Type": "application/json; charset=utf-8",
            "X-Requested-With": "XMLHttpRequest",
            "Authorization": f"Bearer {settings.ALOPEYK_API_KEY}",
        }

    def _call(self, method, path, payload=None):
        """
        Returns (data, error). `error` is non-empty for transport-level/
        JSON-decoding failures AND for AloPeyk's own {"status": "fail"}
        envelope (its error text extracted the same way the official SDK
        does — see module docstring, point 3).
        """
        try:
            response = requests.request(
                method,
                f"{settings.ALOPEYK_API_BASE_URL.rstrip('/')}/{path}",
                json=payload,
                headers=self._headers(),
                timeout=self.REQUEST_TIMEOUT_SECONDS,
            )
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            return None, str(exc)

        if not isinstance(data, dict) or data.get("status") != "success":
            return None, self._extract_error(data)
        return data.get("object"), ""

    @staticmethod
    def _extract_error(data):
        """Mirrors AloPeykApiHandler::getApiResponse()'s own error-text logic."""
        if not isinstance(data, dict):
            return "AloPeyk returned an unrecognized response."
        message = data.get("message")
        obj = data.get("object")
        if not message and isinstance(obj, dict):
            message = obj.get("error_msg") or obj.get("message")
        return str(message).strip() if message else "AloPeyk request failed."

    # ── Location handling ────────────────────────────────────────────────

    @staticmethod
    def _configured_pickup():
        return {
            "city": settings.ALOPEYK_PICKUP_CITY,
            "latitude": settings.ALOPEYK_PICKUP_LATITUDE,
            "longitude": settings.ALOPEYK_PICKUP_LONGITUDE,
            "contact_name": settings.ALOPEYK_PICKUP_CONTACT_NAME,
            "contact_phone": settings.ALOPEYK_PICKUP_CONTACT_PHONE,
        }

    def _normalize_location(self, raw, label, require_contact=False):
        """Validate a location dict. Returns (location, error)."""
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
                f"AloPeyk requires valid latitude/longitude for the {label}; "
                "none were supplied (addresses are not geocoded)."
            )

        location = {
            "latitude": latitude,
            "longitude": longitude,
            "city": str(raw.get("city") or "").strip(),
            "province": str(raw.get("province") or "").strip(),
            "address": str(raw.get("address") or "").strip(),
            "contact_name": str(raw.get("contact_name") or "").strip(),
            "contact_phone": str(raw.get("contact_phone") or "").strip(),
        }
        if require_contact:
            missing = [
                name for name in ("contact_name", "contact_phone") if not location[name]
            ]
            if missing:
                return None, f"AloPeyk requires {', '.join(missing)} for the {label}."
        return location, ""

    @staticmethod
    def _address_payload(location_type, location, include_contact=False):
        payload = {
            "type": location_type,
            "lat": location["latitude"],
            "lng": location["longitude"],
        }
        if include_contact:
            payload["description"] = location["address"]
            payload["person_fullname"] = location["contact_name"]
            payload["person_phone"] = location["contact_phone"]
        return payload

    # ── CarrierProvider interface ────────────────────────────────────────

    def get_rate(
        self, origin: dict, destination: dict, weight_g: int
    ) -> RateQuoteResult:
        """
        Live quote from AloPeyk's `orders/price/calc` endpoint. Checks
        is_available_for_city() against the destination FIRST — an
        unserved city fails immediately with no network call, per this
        task's explicit requirement, rather than attempting a quote that
        would fail anyway. `weight_g` is accepted (interface contract) but
        AloPeyk's pricing has no weight field — it prices by distance and
        transport type — so it is ignored, same as SnapBox.
        """
        destination = destination or {}
        if not self.is_available_for_city(
            destination.get("city", ""), destination.get("province", "")
        ):
            return RateQuoteResult(
                success=False,
                error_message="AloPeyk is not available in this city.",
            )

        if not settings.ALOPEYK_API_KEY:
            return RateQuoteResult(
                success=False, error_message="ALOPEYK_API_KEY is not configured."
            )

        origin_loc, error = self._normalize_location(
            origin or self._configured_pickup(), "pickup location"
        )
        if error:
            return RateQuoteResult(success=False, error_message=error)
        destination_loc, error = self._normalize_location(destination, "destination")
        if error:
            return RateQuoteResult(success=False, error_message=error)

        payload = {
            "transport_type": settings.ALOPEYK_DEFAULT_TRANSPORT_TYPE,
            "has_return": False,
            "addresses": [
                self._address_payload("origin", origin_loc),
                self._address_payload("destination", destination_loc),
            ],
        }
        data, error = self._call("POST", self.PRICE_PATH, payload)
        if error:
            return RateQuoteResult(success=False, error_message=error)

        try:
            price = Decimal(str(data.get("price")))
        except (InvalidOperation, TypeError):
            return RateQuoteResult(
                success=False, error_message="AloPeyk returned an unparseable price."
            )
        if price < 0:
            return RateQuoteResult(
                success=False, error_message="AloPeyk returned a negative price."
            )

        # On-demand courier with no documented ETA field — same-day.
        return RateQuoteResult(success=True, price=price)

    def create_shipment(self, order, destination: dict) -> ShipmentCreateResult:
        """
        Book a courier via AloPeyk's `orders` endpoint. `destination` must
        carry latitude/longitude, city and province (city/province are
        used only for the is_available_for_city() pre-check below — they
        are never sent to AloPeyk, which derives city server-side from
        coordinates). Falls back to the Order's shipping fields for
        contact name/phone/address; the pickup terminal comes from
        ALOPEYK_PICKUP_*. tracking_number is AloPeyk's numeric order id
        (there is no label, so label_url stays empty).
        """
        destination = dict(destination or {})
        if not self.is_available_for_city(
            destination.get("city", ""), destination.get("province", "")
        ):
            return ShipmentCreateResult(
                success=False,
                error_message="AloPeyk is not available in this city.",
            )

        if not settings.ALOPEYK_API_KEY:
            return ShipmentCreateResult(
                success=False, error_message="ALOPEYK_API_KEY is not configured."
            )

        pickup, error = self._normalize_location(
            self._configured_pickup(), "pickup location", require_contact=True
        )
        if error:
            return ShipmentCreateResult(
                success=False,
                error_message=f"{error} Check the ALOPEYK_PICKUP_* settings.",
            )

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

        payload = {
            "transport_type": settings.ALOPEYK_DEFAULT_TRANSPORT_TYPE,
            "has_return": False,
            "addresses": [
                self._address_payload("origin", pickup, include_contact=True),
                self._address_payload("destination", drop, include_contact=True),
            ],
        }
        data, error = self._call("POST", self.CREATE_ORDER_PATH, payload)
        if error:
            return ShipmentCreateResult(success=False, error_message=error)

        order_id = data.get("id") if isinstance(data, dict) else None
        if order_id in (None, ""):
            return ShipmentCreateResult(
                success=False,
                error_message="AloPeyk order creation response had no order id.",
            )
        return ShipmentCreateResult(success=True, tracking_number=str(order_id))

    def track(self, tracking_number: str) -> TrackingResult:
        """
        Current status of an AloPeyk order, by its numeric order id (the
        tracking_number returned from create_shipment). Statuses "new",
        "delivered" and "cancelled" are confirmed from AloPeyk's own
        sample responses; others are inferred (see module docstring,
        point b) — an unrecognized status is still passed through with an
        empty description rather than treated as a failure, since the
        order genuinely exists and has *some* status.
        """
        if not settings.ALOPEYK_API_KEY:
            return TrackingResult(
                success=False, error_message="ALOPEYK_API_KEY is not configured."
            )

        order_id = str(tracking_number or "").strip()
        if not (order_id.isascii() and order_id.isdigit()):
            return TrackingResult(
                success=False,
                error_message=(
                    "AloPeyk tracking numbers are numeric order IDs; got "
                    f"{tracking_number!r}."
                ),
            )

        data, error = self._call(
            "GET", self.ORDER_DETAIL_PATH.format(order_id=order_id)
        )
        if error:
            return TrackingResult(success=False, error_message=error)

        raw_status = data.get("status") if isinstance(data, dict) else None
        if not raw_status:
            return TrackingResult(
                success=False,
                error_message="AloPeyk order lookup returned no status.",
            )

        raw_status = str(raw_status)
        return TrackingResult(
            success=True,
            status=_normalize_status(raw_status),
            status_description=_STATUS_DESCRIPTIONS.get(raw_status.upper(), ""),
        )
