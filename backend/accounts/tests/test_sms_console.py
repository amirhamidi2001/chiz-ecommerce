import logging

from accounts.sms.base import SMSProvider
from accounts.sms.console import ConsoleSMSProvider


class TestConsoleSMSProvider:

    def test_is_a_real_smsprovider_subclass(self):
        assert issubclass(ConsoleSMSProvider, SMSProvider)
        assert isinstance(ConsoleSMSProvider(), SMSProvider)

    def test_send_returns_true_and_does_not_raise(self):
        provider = ConsoleSMSProvider()
        result = provider.send("09123456789", "Your code is 654321")
        assert result is True

    def test_send_logs_phone_number_and_message(self, caplog):
        provider = ConsoleSMSProvider()

        with caplog.at_level(logging.INFO, logger="accounts.sms"):
            provider.send("09123456789", "Your code is 654321")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.name == "accounts.sms"
        assert record.levelno == logging.INFO
        # The logger uses %-style lazy formatting (logger.info("...%s...", a, b))
        # — check the fully rendered message, not the raw format string.
        assert "09123456789" in record.getMessage()
        assert "Your code is 654321" in record.getMessage()

    def test_send_prints_to_stdout_for_local_dev_visibility(self, capsys):
        provider = ConsoleSMSProvider()
        provider.send("09129998888", "Your code is 111222")

        captured = capsys.readouterr()
        assert "[DEV SMS]" in captured.out
        assert "09129998888" in captured.out
        assert "111222" in captured.out

    def test_send_works_for_multiple_distinct_calls(self, caplog):
        """Not stateful/singleton in any way that would break repeated use."""
        provider = ConsoleSMSProvider()

        with caplog.at_level(logging.INFO, logger="accounts.sms"):
            assert provider.send("09121111111", "code A") is True
            assert provider.send("09122222222", "code B") is True

        assert len(caplog.records) == 2
        messages = [r.getMessage() for r in caplog.records]
        assert any("09121111111" in m and "code A" in m for m in messages)
        assert any("09122222222" in m and "code B" in m for m in messages)


class TestConsoleSMSProviderSettingsWiring:

    def test_development_settings_point_at_console_provider(self, settings):
        # pytest.ini configures DJANGO_SETTINGS_MODULE = core.settings.development
        assert settings.SMS_PROVIDER_CLASS == "accounts.sms.console.ConsoleSMSProvider"

    def test_get_sms_provider_resolves_to_console_provider_under_dev_settings(self):
        from accounts.sms.base import get_sms_provider

        provider = get_sms_provider()
        assert isinstance(provider, ConsoleSMSProvider)
