from decimal import Decimal

import pytest
from django.core.exceptions import ImproperlyConfigured
from payments.gateways import get_payment_gateway
from payments.gateways.base import (
    PaymentGateway,
    PaymentRequestResult,
    PaymentVerifyResult,
)


class TestPaymentGatewayInterface:

    def test_paymentgateway_cannot_be_instantiated_directly(self):
        # It's an ABC with abstract methods — instantiating it directly
        # must fail, same as any other abstract base class.
        with pytest.raises(TypeError):
            PaymentGateway()

    def test_subclass_without_abstract_methods_cannot_be_instantiated(self):
        class Incomplete(PaymentGateway):
            pass

        with pytest.raises(TypeError):
            Incomplete()

    def test_subclass_implementing_contract_can_be_instantiated(self):
        class DummyGateway(PaymentGateway):
            def request_payment(
                self, amount: Decimal, callback_url: str, description: str = ""
            ) -> PaymentRequestResult:
                return PaymentRequestResult(
                    success=True,
                    authority="A123",
                    redirect_url="https://example.test/pay/A123",
                )

            def verify_payment(
                self, authority: str, amount: Decimal
            ) -> PaymentVerifyResult:
                return PaymentVerifyResult(success=True, ref_id="R456")

            def extract_callback_params(self, request) -> dict:
                return {"authority": "A123", "is_customer_cancelled": False}

        gateway = DummyGateway()

        assert isinstance(gateway, PaymentGateway)

        request_result = gateway.request_payment(Decimal("10.00"), "https://x/cb")
        assert request_result.success is True
        assert request_result.authority == "A123"

        verify_result = gateway.verify_payment("A123", Decimal("10.00"))
        assert verify_result.success is True
        assert verify_result.ref_id == "R456"


class TestGetPaymentGateway:

    def test_unknown_gateway_name_raises_improperly_configured(self):
        with pytest.raises(ImproperlyConfigured) as exc_info:
            get_payment_gateway("nonexistent")

        assert "nonexistent" in str(exc_info.value)

    def test_default_gateway_setting_is_zarinpal(self, settings):
        # Sanity check on the configured default itself (Task 6.2.1.1
        # implements ZarinPalGateway — not yet present as of this task).
        assert settings.DEFAULT_PAYMENT_GATEWAY == "zarinpal"
        assert "zarinpal" in settings.PAYMENT_GATEWAY_CLASSES

    def test_class_not_implementing_payment_gateway_raises_improperly_configured(
        self, settings
    ):
        settings.PAYMENT_GATEWAY_CLASSES = {
            **settings.PAYMENT_GATEWAY_CLASSES,
            "bogus": "payments.tests.test_gateways.NotAPaymentGateway",
        }

        with pytest.raises(ImproperlyConfigured) as exc_info:
            get_payment_gateway("bogus")

        assert "does not implement" in str(exc_info.value)
        assert "PaymentGateway" in str(exc_info.value)

    def test_nonexistent_dotted_path_raises_improperly_configured(self, settings):
        settings.PAYMENT_GATEWAY_CLASSES = {
            **settings.PAYMENT_GATEWAY_CLASSES,
            "bogus": "totally.bogus.module.DoesNotExist",
        }

        with pytest.raises(ImproperlyConfigured):
            get_payment_gateway("bogus")


class NotAPaymentGateway:
    """A class that doesn't subclass PaymentGateway at all — used to
    confirm get_payment_gateway() checks isinstance(), not just that
    the dotted path resolves to *something* importable."""

    def request_payment(self, *args, **kwargs):
        return None

    def verify_payment(self, *args, **kwargs):
        return None
