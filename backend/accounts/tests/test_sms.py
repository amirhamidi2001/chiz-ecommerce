import pytest
from accounts.sms.base import SMSProvider, get_sms_provider
from django.core.exceptions import ImproperlyConfigured


class TestSMSProviderInterface:

    def test_smsprovider_cannot_be_instantiated_directly(self):
        # It's an ABC with an abstract method — instantiating it
        # directly must fail, same as any other abstract base class.
        with pytest.raises(TypeError):
            SMSProvider()

    def test_subclass_without_send_cannot_be_instantiated(self):
        class Incomplete(SMSProvider):
            pass

        with pytest.raises(TypeError):
            Incomplete()

    def test_subclass_implementing_send_can_be_instantiated(self):
        class Complete(SMSProvider):
            def send(self, phone_number: str, message: str) -> bool:
                return True

        provider = Complete()
        assert isinstance(provider, SMSProvider)
        assert provider.send("09123456789", "hello") is True


class TestGetSMSProvider:

    def test_returns_instance_of_configured_valid_provider(self, settings):
        settings.SMS_PROVIDER_CLASS = "accounts.tests.sms_doubles.ValidTestProvider"

        provider = get_sms_provider()

        assert isinstance(provider, SMSProvider)
        assert provider.send("09123456789", "your code is 123456") is True

    def test_default_setting_value_is_the_console_provider_path(self, settings):
        # Sanity check on the configured default itself (Task 2.2.1.2
        # implements this class — not yet present as of this task).
        assert settings.SMS_PROVIDER_CLASS == "accounts.sms.console.ConsoleSMSProvider"

    def test_nonexistent_dotted_path_raises_improperly_configured(self, settings):
        settings.SMS_PROVIDER_CLASS = "totally.bogus.module.DoesNotExist"

        with pytest.raises(ImproperlyConfigured) as exc_info:
            get_sms_provider()

        message = str(exc_info.value)
        assert "totally.bogus.module.DoesNotExist" in message
        # Must be a clear, actionable message — not a bare/cryptic
        # ImportError leaking through unhandled.
        assert "import" in message.lower()

    def test_malformed_dotted_path_raises_improperly_configured(self, settings):
        # No dots at all — import_string can't even split this into a
        # module path and attribute name.
        settings.SMS_PROVIDER_CLASS = "not_a_dotted_path"

        with pytest.raises(ImproperlyConfigured):
            get_sms_provider()

    def test_class_not_implementing_sms_provider_raises_improperly_configured(
        self, settings
    ):
        settings.SMS_PROVIDER_CLASS = "accounts.tests.sms_doubles.NotAnSMSProvider"

        with pytest.raises(ImproperlyConfigured) as exc_info:
            get_sms_provider()

        message = str(exc_info.value)
        assert "NotAnSMSProvider" in message or "does not implement" in message
        assert "SMSProvider" in message

    def test_class_requiring_constructor_args_raises_improperly_configured(
        self, settings
    ):
        settings.SMS_PROVIDER_CLASS = (
            "accounts.tests.sms_doubles.ProviderRequiringConstructorArgs"
        )

        with pytest.raises(ImproperlyConfigured) as exc_info:
            get_sms_provider()

        assert "could not be instantiated" in str(exc_info.value)

    def test_incomplete_provider_missing_send_raises_improperly_configured(
        self, settings
    ):
        settings.SMS_PROVIDER_CLASS = "accounts.tests.sms_doubles.IncompleteProvider"

        with pytest.raises(ImproperlyConfigured):
            get_sms_provider()

    def test_error_messages_never_leak_a_bare_import_error(self, settings):
        """
        The acceptance criteria specifically calls for a "clear,
        actionable error, not a cryptic ImportError" — confirm the
        exception type itself is ImproperlyConfigured, never a raw
        ImportError/ModuleNotFoundError/TypeError escaping unhandled.
        """
        for bad_path in [
            "totally.bogus.module.DoesNotExist",
            "accounts.tests.sms_doubles.NotAnSMSProvider",
            "accounts.tests.sms_doubles.ProviderRequiringConstructorArgs",
        ]:
            settings.SMS_PROVIDER_CLASS = bad_path
            with pytest.raises(ImproperlyConfigured):
                get_sms_provider()
