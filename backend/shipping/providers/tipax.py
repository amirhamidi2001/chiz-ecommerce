"""
Tipax (تیپاکس, tipaxco.com) carrier provider.

DOCUMENTATION RESEARCH (Task 7.2.1.3) — read before touching this file
========================================================================
Per this epic's standing "verify current API docs before hardcoding"
rule, and this task's own explicit prompt to verify rather than assume
Tipax has "a more modern, developer-facing API than some alternatives",
Tipax's actual API surface was checked against current, public sources
before writing anything below.

Finding: THE INITIAL ASSUMPTION DOES NOT HOLD UP. Tipax has NO publicly
documented, self-service REST/SOAP developer API for rate quoting,
shipment creation, or tracking — the same conclusion as Iran Post (Task
7.2.1.2), not the more-modern-API exception the task context speculated
might apply here:

  - Tipax's business-facing product is "eTipax" (etipaxco.com), described
    on tipaxco.com as a web-based e-commerce logistics platform covering
    order registration, door-to-door pickup, shipping, tracking, and
    reporting. Every description of it is in terms of a WEB PORTAL
    businesses log into (registration + login), not a documented REST/
    SOAP API with API keys, request/response schemas, or a developer
    portal.
  - No official Tipax developer documentation, API reference, or SDK
    could be found. (An unrelated, unofficial, unaffiliated GitHub demo
    project happens to share the name "Tipax" — a static
    HTML/CSS/JS admin-panel mockup with a placeholder "API settings"
    page and hardcoded sample JSON data — but its own README describes
    "connecting a real API" as a FUTURE roadmap item it hasn't built,
    and it isn't affiliated with the actual Tipax company in any way.
    It is not evidence of a real Tipax API and was disregarded.)
  - Consumer-facing tracking is via Tipax's own tracking site
    (mt.tipax.ir, referenced by third-party tracking aggregators) and
    the "My TIPAX" mobile app — both consumer surfaces, not a documented
    public API.

Given this, the implementation below follows the exact same honesty
principle as PostCarrierProvider (Task 7.2.1.2), because the facts turn
out to be the same shape, not because the code was copy-pasted without
re-checking:

  - get_rate(): always returns success=False. Like Iran Post, Tipax
    pricing for this integration comes entirely from the static rate
    table (Task 7.1.1.3's ShippingRate.find_rate()), never a live quote.
  - create_shipment() / track(): both raise NotImplementedError. Tipax
    fulfillment here is PORTAL-BASED: an admin registers the shipment
    through the eTipax web portal (login required) and records the
    resulting tracking code against the order by hand; tracking status
    is checked by hand against the eTipax portal or mt.tipax.ir rather
    than pulled programmatically.

If Tipax ever publishes a documented developer API under an eTipax
business account, settings.TIPAX_ACCOUNT_USERNAME/TIPAX_ACCOUNT_PASSWORD
(see core/settings/base.py) are where those portal credentials would go,
and create_shipment()/track() would need to be rewritten against
whatever that API surface actually turns out to provide — nothing about
that hypothetical future API's shape is guessed at here.
"""

from .base import CarrierProvider, RateQuoteResult, ShipmentCreateResult, TrackingResult


class TipaxCarrierProvider(CarrierProvider):
    """
    Tipax carrier provider. See this module's docstring for the
    documentation research behind every choice below — in particular,
    why this ends up structurally identical to PostCarrierProvider
    despite this task's initial "more modern API" assumption.
    """

    def get_rate(
        self, origin: dict, destination: dict, weight_g: int
    ) -> RateQuoteResult:
        """
        Tipax has no confirmed public live-quoting API — pricing for
        this carrier comes entirely from the static Task 7.1.1.3 rate
        table (see shipping.models.ShippingRate.find_rate()). Always
        returns success=False so callers fall back to that table, per
        CarrierProvider.get_rate()'s own documented contract for
        rate-card-only carriers — this is the expected outcome, not an
        error condition.
        """
        return RateQuoteResult(
            success=False,
            error_message="Tipax rate quoting uses the static rate table.",
        )

    def create_shipment(self, order, destination: dict) -> ShipmentCreateResult:
        """
        Tipax has no confirmed public API for booking a shipment
        programmatically. Fulfillment here is portal-based: an admin
        registers the shipment through Tipax's eTipax business web
        portal (etipaxco.com, login required), then manually records the
        resulting tracking code against the order via the
        admin/fulfillment UI.

        There is nothing for this method to actually call, so it raises
        NotImplementedError rather than pretending to support
        programmatic booking with a nonfunctional stub.
        """
        raise NotImplementedError(
            "Tipax shipment creation is portal-based: register the "
            "shipment via the eTipax business portal (etipaxco.com), then "
            "enter the resulting tracking code by hand. No public API "
            "exists for this as of this integration — see this module's "
            "docstring."
        )

    def track(self, tracking_number: str) -> TrackingResult:
        """
        Tipax's tracking surfaces (the eTipax portal, mt.tipax.ir, the
        "My TIPAX" app) are consumer/business-portal-facing, not a
        documented public API with a stable contract. Tracking here is
        manual: an admin or customer checks the tracking code against
        one of those surfaces directly.

        Raises NotImplementedError rather than pretending to support
        programmatic tracking with a nonfunctional stub.
        """
        raise NotImplementedError(
            "Tipax tracking is manual: check the tracking code via the "
            "eTipax portal or mt.tipax.ir directly. No confirmed public "
            "tracking API exists for this integration — see this module's "
            "docstring."
        )
