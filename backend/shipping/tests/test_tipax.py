from decimal import Decimal

import pytest
from shipping.providers.base import RateQuoteResult
from shipping.providers.tipax import TipaxCarrierProvider


class TestTipaxCarrierProviderGetRate:
    def test_get_rate_always_returns_unsuccessful_pointing_to_rate_table(self):
        # Tipax has no confirmed public live-quoting API (see tipax.py's
        # module docstring for the documentation research — including
        # why the task's initial "more modern API" assumption didn't
        # hold up) — this must always come back success=False so
        # callers fall back to the Task 7.1.1.3 static rate table, per
        # CarrierProvider.get_rate()'s own documented contract for
        # rate-card-only carriers.
        provider = TipaxCarrierProvider()

        result = provider.get_rate(
            origin={"province": "tehran"},
            destination={"province": "fars"},
            weight_g=500,
        )

        assert isinstance(result, RateQuoteResult)
        assert result.success is False
        assert result.error_message == "Tipax rate quoting uses the static rate table."
        # Confirms this never fabricates a price alongside success=False
        # — price stays at the dataclass default rather than some
        # invented number.
        assert result.price == Decimal("0")

    def test_get_rate_is_unsuccessful_regardless_of_inputs(self):
        # Not carrying inputs through to a (nonexistent) API call means
        # the result should be identical no matter what's passed in —
        # locking that in explicitly rather than just testing one input
        # combination.
        provider = TipaxCarrierProvider()

        result_a = provider.get_rate({}, {}, 0)
        result_b = provider.get_rate(
            {"province": "isfahan"}, {"province": "yazd", "city": "Yazd"}, 50_000
        )

        assert result_a.success is False
        assert result_b.success is False
        assert result_a.error_message == result_b.error_message


class TestTipaxCarrierProviderCreateShipment:
    def test_create_shipment_raises_not_implemented_error(self):
        # No confirmed public booking API exists for Tipax — fulfillment
        # is portal-based (eTipax business portal, with the tracking
        # code entered by hand afterward). This must raise clearly
        # rather than silently doing nothing or crashing unpredictably.
        provider = TipaxCarrierProvider()

        with pytest.raises(NotImplementedError):
            provider.create_shipment(order=None, destination={"province": "tehran"})

    def test_create_shipment_error_message_explains_portal_based_fulfillment(self):
        provider = TipaxCarrierProvider()

        with pytest.raises(NotImplementedError, match="portal"):
            provider.create_shipment(order=None, destination={})


class TestTipaxCarrierProviderTrack:
    def test_track_raises_not_implemented_error(self):
        # No confirmed public tracking API exists either — tracking is
        # checked manually against the eTipax portal or mt.tipax.ir.
        # Must raise clearly rather than silently doing nothing or
        # crashing unpredictably.
        provider = TipaxCarrierProvider()

        with pytest.raises(NotImplementedError):
            provider.track("TPX1234567890")

    def test_track_error_message_explains_manual_tracking(self):
        provider = TipaxCarrierProvider()

        with pytest.raises(NotImplementedError, match="manual"):
            provider.track("some-tracking-number")


class TestTipaxCarrierProviderRegisteredInFactory:
    def test_get_carrier_provider_tipax_returns_tipax_carrier_provider(self):
        from shipping.providers import get_carrier_provider

        provider = get_carrier_provider("tipax")

        assert isinstance(provider, TipaxCarrierProvider)
