"""
Iran Post (شرکت ملی پست ایران / Post-e Iran, post.ir) carrier provider.

DOCUMENTATION RESEARCH (Task 7.2.1.2) — read before touching this file
========================================================================
Per this epic's standing "verify current API docs before hardcoding"
rule, Iran Post's actual API surface was checked against current,
public sources before writing anything below. Findings:

  - Iran Post has NO publicly documented, self-service REST/SOAP API for
    rate quoting, shipment creation, or tracking that a business could
    integrate against with a simple API key — unlike Epic 6's payment
    gateways (ZarinPal/Zibal/IDPay), which all publish a documented
    merchant API.
  - Structured business access instead goes through post.ir's own
    "e-bazaar" (ای‌بازار) organizational/business panel, which requires
    signing a DIRECT CONTRACT ("عقد قرارداد مستقیم") before a business
    gets bulk pickup/booking service — an account relationship gated by
    a signed contract, not a self-service developer signup with an API
    key.
  - The public tracking surface (tracking.post.ir / newtracking.post.ir,
    and the "Post Plus" mobile app) is a CONSUMER-FACING WEBSITE/APP, not
    a documented public API with a stable request/response contract.
    Independent tracking aggregators (e.g. 17TRACK) explicitly note that
    Iran Post's official public tracking API is unconfirmed, and route
    Iran Post tracking numbers through their own aggregator
    infrastructure rather than a documented Iran Post API.

Given this, the implementation below is deliberately honest about what's
actually possible today, per this task's explicit instructions for
exactly this situation:

  - get_rate(): always returns success=False. Iran Post pricing for this
    integration comes entirely from the static rate table (Task
    7.1.1.3's ShippingRate.find_rate()), never a live quote — this is
    the expected, documented outcome for a rate-card-only carrier per
    CarrierProvider.get_rate()'s own contract, not a bug or a stub
    standing in for something that should eventually make a network
    call.
  - create_shipment() / track(): both raise NotImplementedError. Iran
    Post fulfillment for this integration is MANUAL — an admin books the
    shipment through Iran Post's e-bazaar business panel or a post
    office counter, then manually records the resulting tracking number
    against the order; tracking status is likewise checked by hand
    against tracking.post.ir rather than pulled programmatically. This
    is a legitimate, expected outcome for this specific carrier (some
    carriers are portal/counter-based rather than API-driven), not a
    failure to complete this task.

If Iran Post ever grants real programmatic API access under a signed
e-bazaar business contract, settings.IRAN_POST_ACCOUNT_NUMBER (see
core/settings/base.py) is where that contract's account identifier would
go, and create_shipment()/track() would need to be rewritten against
whatever contract-specific API surface that access actually turns out to
provide — nothing about that hypothetical future API's shape is guessed
at here, since it can't be verified today.
"""

from .base import CarrierProvider, RateQuoteResult, ShipmentCreateResult, TrackingResult


class PostCarrierProvider(CarrierProvider):
    """
    Iran Post carrier provider. See this module's docstring for the
    documentation research behind every choice below.
    """

    def get_rate(
        self, origin: dict, destination: dict, weight_g: int
    ) -> RateQuoteResult:
        """
        Iran Post has no confirmed public live-quoting API — pricing for
        this carrier comes entirely from the static Task 7.1.1.3 rate
        table (see shipping.models.ShippingRate.find_rate()). Always
        returns success=False so callers fall back to that table, per
        CarrierProvider.get_rate()'s own documented contract for
        rate-card-only carriers — this is the expected outcome, not an
        error condition.
        """
        return RateQuoteResult(
            success=False,
            error_message="Iran Post rate quoting uses the static rate table.",
        )

    def create_shipment(self, order, destination: dict) -> ShipmentCreateResult:
        """
        Iran Post has no confirmed public API for booking a shipment
        programmatically. Fulfillment here is manual: an admin books the
        shipment through Iran Post's own e-bazaar business panel (which
        itself requires a signed business contract, per post.ir) or a
        post office counter, then manually records the resulting
        tracking number against the order via the admin/fulfillment UI.

        There is nothing for this method to actually call, so it raises
        NotImplementedError rather than pretending to support
        programmatic booking with a nonfunctional stub.
        """
        raise NotImplementedError(
            "Iran Post shipment creation is manual: book via Iran Post's "
            "e-bazaar business panel or a post office counter, then enter "
            "the resulting tracking number by hand. No public API exists "
            "for this as of this integration — see this module's docstring."
        )

    def track(self, tracking_number: str) -> TrackingResult:
        """
        Iran Post's tracking surface (tracking.post.ir) is a
        consumer-facing website/app, not a documented public API with a
        stable contract — third-party tracking aggregators note Iran
        Post's official tracking API is unconfirmed. Tracking here is
        manual: an admin or customer checks tracking.post.ir directly
        with the tracking barcode.

        Raises NotImplementedError rather than pretending to support
        programmatic tracking with a nonfunctional stub.
        """
        raise NotImplementedError(
            "Iran Post tracking is manual: check tracking.post.ir directly "
            "with the tracking barcode. No confirmed public tracking API "
            "exists for this integration — see this module's docstring."
        )
