from decimal import Decimal

import pytest
from django.core.exceptions import ImproperlyConfigured
from shipping.providers import get_carrier_provider
from shipping.providers.base import (
    CarrierProvider,
    RateQuoteResult,
    ShipmentCreateResult,
    TrackingResult,
)


class TestCarrierProviderInterface:

    def test_carrierprovider_cannot_be_instantiated_directly(self):
        # It's an ABC with abstract methods — instantiating it directly
        # must fail, same as any other abstract base class.
        with pytest.raises(TypeError):
            CarrierProvider()

    def test_subclass_without_abstract_methods_cannot_be_instantiated(self):
        class Incomplete(CarrierProvider):
            pass

        with pytest.raises(TypeError):
            Incomplete()

    def test_subclass_implementing_contract_can_be_instantiated(self):
        class DummyProvider(CarrierProvider):
            def get_rate(self, origin, destination, weight_g):
                return RateQuoteResult(
                    success=True,
                    price=Decimal("45000.00"),
                    estimated_days_min=1,
                    estimated_days_max=3,
                )

            def create_shipment(self, order, destination):
                return ShipmentCreateResult(
                    success=True,
                    tracking_number="TRK123",
                    label_url="https://example.test/labels/TRK123",
                )

            def track(self, tracking_number):
                return TrackingResult(
                    success=True,
                    status="in_transit",
                    status_description="Package is on its way",
                )

        provider = DummyProvider()

        assert isinstance(provider, CarrierProvider)

        rate_result = provider.get_rate({}, {}, 500)
        assert rate_result.success is True
        assert rate_result.price == Decimal("45000.00")

        shipment_result = provider.create_shipment(order=None, destination={})
        assert shipment_result.success is True
        assert shipment_result.tracking_number == "TRK123"

        tracking_result = provider.track("TRK123")
        assert tracking_result.success is True
        assert tracking_result.status == "in_transit"

    def test_get_rate_returning_unsuccessful_is_a_valid_outcome(self):
        # Per the ABC's own docstring: a carrier with no live-quoting API
        # (priced via the Task 7.1.1.3 rate table instead) is expected to
        # return success=False here, not raise or fake a price.
        class RateTableOnlyProvider(CarrierProvider):
            def get_rate(self, origin, destination, weight_g):
                return RateQuoteResult(
                    success=False,
                    error_message="Live quoting not supported; use rate table.",
                )

            def create_shipment(self, order, destination):
                return ShipmentCreateResult(success=True, tracking_number="X")

            def track(self, tracking_number):
                return TrackingResult(success=True, status="unknown")

        provider = RateTableOnlyProvider()
        result = provider.get_rate({}, {}, 500)

        assert result.success is False
        assert "rate table" in result.error_message.lower()


class TestGetCarrierProvider:

    def test_unknown_provider_code_raises_improperly_configured(self):
        with pytest.raises(ImproperlyConfigured) as exc_info:
            get_carrier_provider("nonexistent")

        assert "nonexistent" in str(exc_info.value)

    def test_carrier_provider_classes_setting_has_post_registered(self, settings):
        # Task 7.2.1.2 registers the first concrete carrier (Iran Post);
        # tipax/snapbox/alopeyk are populated incrementally by Tasks
        # 7.2.1.3 through 7.2.1.5.
        assert settings.CARRIER_PROVIDER_CLASSES["post"] == (
            "shipping.providers.post.PostCarrierProvider"
        )

    def test_class_not_implementing_carrier_provider_raises_improperly_configured(
        self, settings
    ):
        settings.CARRIER_PROVIDER_CLASSES = {
            **settings.CARRIER_PROVIDER_CLASSES,
            "bogus": "shipping.tests.test_providers.NotACarrierProvider",
        }

        with pytest.raises(ImproperlyConfigured) as exc_info:
            get_carrier_provider("bogus")

        assert "does not implement" in str(exc_info.value)
        assert "CarrierProvider" in str(exc_info.value)

    def test_nonexistent_dotted_path_raises_improperly_configured(self, settings):
        settings.CARRIER_PROVIDER_CLASSES = {
            **settings.CARRIER_PROVIDER_CLASSES,
            "bogus": "totally.bogus.module.DoesNotExist",
        }

        with pytest.raises(ImproperlyConfigured):
            get_carrier_provider("bogus")


class NotACarrierProvider:
    """A class that doesn't subclass CarrierProvider at all — used to
    confirm get_carrier_provider() checks isinstance(), not just that
    the dotted path resolves to *something* importable."""

    def get_rate(self, *args, **kwargs):
        return None

    def create_shipment(self, *args, **kwargs):
        return None

    def track(self, *args, **kwargs):
        return None
