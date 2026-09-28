from decimal import Decimal

import pytest
from shipping.providers.base import RateQuoteResult
from shipping.providers.post import PostCarrierProvider


class TestPostCarrierProviderGetRate:
    def test_get_rate_always_returns_unsuccessful_pointing_to_rate_table(self):
        # Iran Post has no confirmed public live-quoting API (see
        # post.py's module docstring for the documentation research) —
        # this must always come back success=False so callers fall back
        # to the Task 7.1.1.3 static rate table, per
        # CarrierProvider.get_rate()'s own documented contract for
        # rate-card-only carriers.
        provider = PostCarrierProvider()

        result = provider.get_rate(
            origin={"province": "tehran"},
            destination={"province": "fars"},
            weight_g=500,
        )

        assert isinstance(result, RateQuoteResult)
        assert result.success is False
        assert (
            result.error_message == "Iran Post rate quoting uses the static rate table."
        )
        # Confirms this never fabricates a price alongside success=False
        # — price stays at the dataclass default rather than some
        # invented number.
        assert result.price == Decimal("0")

    def test_get_rate_is_unsuccessful_regardless_of_inputs(self):
        # Not carrying inputs through to a (nonexistent) API call means
        # the result should be identical no matter what's passed in —
        # locking that in explicitly rather than just testing one input
        # combination.
        provider = PostCarrierProvider()

        result_a = provider.get_rate({}, {}, 0)
        result_b = provider.get_rate(
            {"province": "isfahan"}, {"province": "yazd", "city": "Yazd"}, 50_000
        )

        assert result_a.success is False
        assert result_b.success is False
        assert result_a.error_message == result_b.error_message


class TestPostCarrierProviderCreateShipment:
    def test_create_shipment_raises_not_implemented_error(self):
        # No confirmed public booking API exists for Iran Post —
        # fulfillment is manual (e-bazaar business panel or a post
        # office counter, with the tracking number entered by hand
        # afterward). This must raise clearly rather than silently doing
        # nothing or crashing unpredictably.
        provider = PostCarrierProvider()

        with pytest.raises(NotImplementedError):
            provider.create_shipment(order=None, destination={"province": "tehran"})

    def test_create_shipment_error_message_explains_manual_fulfillment(self):
        provider = PostCarrierProvider()

        with pytest.raises(NotImplementedError, match="manual"):
            provider.create_shipment(order=None, destination={})


class TestPostCarrierProviderTrack:
    def test_track_raises_not_implemented_error(self):
        # No confirmed public tracking API exists either — tracking is
        # checked manually against tracking.post.ir. Must raise clearly
        # rather than silently doing nothing or crashing unpredictably.
        provider = PostCarrierProvider()

        with pytest.raises(NotImplementedError):
            provider.track("123456789012345678901234")

    def test_track_error_message_explains_manual_tracking(self):
        provider = PostCarrierProvider()

        with pytest.raises(NotImplementedError, match="manual"):
            provider.track("some-tracking-number")


class TestPostCarrierProviderRegisteredInFactory:
    def test_get_carrier_provider_post_returns_post_carrier_provider(self):
        from shipping.providers import get_carrier_provider

        provider = get_carrier_provider("post")

        assert isinstance(provider, PostCarrierProvider)
