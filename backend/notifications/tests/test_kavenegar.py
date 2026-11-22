"""
Tests for notifications.sms.kavenegar.KavenegarSMSProvider.

`requests.post` is always patched — no test touches the network. Responses are
real `requests.Response` objects (not bare mocks) so `.ok` and the
non-JSON failure of `.json()` behave exactly as they do in production.
"""

import json
import logging
import os
import subprocess
import sys
from unittest.mock import patch

import pytest
import requests
from django.conf import settings as django_settings
from notifications.sms import SMSProvider, get_sms_provider
from notifications.sms.kavenegar import KavenegarSMSProvider

KEY = "6D4a72476C4b5A31"
SENDER = "10004346"
PHONE = "09123456789"
OTP_CODE = "482913"  # distinct from any substring of PHONE
MESSAGE = f"کد تأیید شما: {OTP_CODE}"
URL = f"https://api.kavenegar.com/v1/{KEY}/sms/send.json"

SUCCESS_BODY = {
    "return": {"status": 200, "message": "تایید شد"},
    "entries": [
        {
            "messageid": 8792343,
            "message": MESSAGE,
            "status": 1,
            "statustext": "در صف ارسال",
            "sender": SENDER,
            "receptor": PHONE,
            "date": 1356619709,
            "cost": 120,
        }
    ],
}


def make_response(body, status_code=200):
    """A real requests.Response with `body` (dict/list/str/bytes) as content."""
    response = requests.Response()
    response.status_code = status_code
    if isinstance(body, bytes):
        response._content = body
    elif isinstance(body, str):
        response._content = body.encode("utf-8")
    else:
        response._content = json.dumps(body, ensure_ascii=False).encode("utf-8")
    response.encoding = "utf-8"
    return response


@pytest.fixture(autouse=True)
def kavenegar_settings(settings):
    settings.KAVENEGAR_API_KEY = KEY
    settings.KAVENEGAR_SENDER_LINE = SENDER


@pytest.fixture
def mock_post():
    with patch("notifications.sms.kavenegar.requests.post") as mock:
        mock.return_value = make_response(SUCCESS_BODY)
        yield mock


@pytest.fixture
def provider():
    return KavenegarSMSProvider()


@pytest.fixture
def errors(caplog):
    with caplog.at_level(logging.ERROR, logger="notifications.sms"):
        yield caplog


def error_records(caplog):
    return [r for r in caplog.records if r.levelno >= logging.ERROR]


# ─── success ───────────────────────────────────────────────────────────────


class TestSuccess:
    def test_successful_response_returns_true(self, provider, mock_post, errors):
        assert provider.send(PHONE, MESSAGE) is True
        assert error_records(errors) == []

    def test_posts_to_the_documented_endpoint_with_the_documented_fields(
        self, provider, mock_post
    ):
        provider.send(PHONE, MESSAGE)

        mock_post.assert_called_once()
        assert mock_post.call_args.args == (URL,)
        assert mock_post.call_args.kwargs["data"] == {
            "receptor": PHONE,
            "message": MESSAGE,  # Persian text passed through untouched
            "sender": SENDER,
        }

    def test_sender_is_omitted_when_not_configured(self, provider, mock_post, settings):
        settings.KAVENEGAR_SENDER_LINE = ""

        assert provider.send(PHONE, MESSAGE) is True

        assert "sender" not in mock_post.call_args.kwargs["data"]

    def test_is_a_real_sms_provider_resolvable_through_the_factory(self, settings):
        settings.SMS_PROVIDER_CLASS = "notifications.sms.kavenegar.KavenegarSMSProvider"

        resolved = get_sms_provider()

        assert isinstance(resolved, KavenegarSMSProvider)
        assert isinstance(resolved, SMSProvider)


# ─── timeout ───────────────────────────────────────────────────────────────


class TestTimeout:
    def test_request_includes_a_positive_timeout(self, provider, mock_post):
        provider.send(PHONE, MESSAGE)

        timeout = mock_post.call_args.kwargs["timeout"]
        assert timeout == KavenegarSMSProvider.REQUEST_TIMEOUT_SECONDS
        assert isinstance(timeout, (int, float)) and timeout > 0

    def test_timeout_is_set_on_failure_paths_too(self, provider, mock_post):
        mock_post.return_value = make_response({"return": {"status": 401}}, 401)

        provider.send(PHONE, MESSAGE)

        assert mock_post.call_args.kwargs["timeout"] > 0


# ─── rejected responses ────────────────────────────────────────────────────


class TestRejected:
    def test_rejection_in_a_200_response_returns_false_and_logs_reason(
        self, provider, mock_post, errors
    ):
        mock_post.return_value = make_response(
            {"return": {"status": 412, "message": "ارسال کننده نامعتبر است"}}
        )

        assert provider.send(PHONE, MESSAGE) is False

        records = error_records(errors)
        assert len(records) == 1
        text = records[0].getMessage()
        assert PHONE in text
        assert "412" in text
        assert "ارسال کننده نامعتبر است" in text

    def test_http_error_still_surfaces_the_reason_from_the_body(
        self, provider, mock_post, errors
    ):
        """raise_for_status() would have discarded return.status/message."""
        mock_post.return_value = make_response(
            {"return": {"status": 401, "message": "reason from body"}},
            status_code=401,
        )

        assert provider.send(PHONE, MESSAGE) is False

        text = error_records(errors)[0].getMessage()
        assert "HTTP 401" in text
        assert "reason from body" in text

    def test_success_body_with_an_http_error_status_is_not_success(
        self, provider, mock_post, errors
    ):
        mock_post.return_value = make_response(SUCCESS_BODY, status_code=500)

        assert provider.send(PHONE, MESSAGE) is False
        assert len(error_records(errors)) == 1

    @pytest.mark.parametrize(
        "body",
        [
            {},
            [],
            "ok",
            "null",
            {"return": None},
            {"return": "ok"},
            {"return": {}},
            {"return": {"status": "200"}},  # string, not the integer 200
            {"return": {"status": None}},
            {"entries": []},
        ],
    )
    def test_unexpected_but_valid_json_shapes_return_false(
        self, provider, mock_post, errors, body
    ):
        mock_post.return_value = make_response(
            body if not isinstance(body, str) or body == "null" else json.dumps(body)
        )

        assert provider.send(PHONE, MESSAGE) is False
        assert len(error_records(errors)) == 1

    def test_rejection_log_does_not_echo_the_sms_text(
        self, provider, mock_post, errors
    ):
        """A rejection body can echo `entries[].message` — the OTP code."""
        mock_post.return_value = make_response(
            {
                "return": {"status": 411, "message": "bad receptor"},
                "entries": [{"message": MESSAGE}],
            }
        )

        provider.send(PHONE, MESSAGE)

        assert OTP_CODE not in errors.text
        assert MESSAGE not in errors.text


# ─── network failures ──────────────────────────────────────────────────────


class TestNetworkFailures:
    @pytest.mark.parametrize(
        "exc",
        [
            requests.Timeout("timed out"),
            requests.ConnectTimeout("connect timed out"),
            requests.ReadTimeout("read timed out"),
            requests.ConnectionError("connection refused"),
            requests.exceptions.SSLError("bad cert"),
            requests.RequestException("anything else"),
        ],
        ids=lambda e: type(e).__name__,
    )
    def test_network_errors_return_false_and_never_raise(
        self, provider, mock_post, errors, exc
    ):
        mock_post.side_effect = exc

        assert provider.send(PHONE, MESSAGE) is False

        records = error_records(errors)
        assert len(records) == 1
        assert PHONE in records[0].getMessage()
        assert type(exc).__name__ in records[0].getMessage()


# ─── malformed responses ───────────────────────────────────────────────────


class TestMalformedResponse:
    @pytest.mark.parametrize(
        "body",
        [
            b"<html><body>502 Bad Gateway</body></html>",
            b"",
            b"not json at all",
            b'{"return": {"status": 200',  # truncated JSON
        ],
    )
    def test_non_json_response_returns_false_and_logs(
        self, provider, mock_post, errors, body
    ):
        mock_post.return_value = make_response(body)

        assert provider.send(PHONE, MESSAGE) is False

        assert "non-JSON" in error_records(errors)[0].getMessage()

    def test_non_json_http_error_page_returns_false(self, provider, mock_post, errors):
        mock_post.return_value = make_response(b"<html>Bad Gateway</html>", 502)

        assert provider.send(PHONE, MESSAGE) is False
        assert "HTTP 502" in error_records(errors)[0].getMessage()


# ─── never raises / never leaks ────────────────────────────────────────────


class TestSafety:
    def test_unexpected_exception_is_contained(self, provider, mock_post, errors):
        mock_post.side_effect = RuntimeError("bug in a library")

        assert provider.send(PHONE, MESSAGE) is False

        assert "RuntimeError" in error_records(errors)[0].getMessage()

    def test_api_key_never_appears_in_logs_for_request_errors(
        self, provider, mock_post, errors
    ):
        # requests puts the full URL — i.e. the key — in exception messages.
        mock_post.side_effect = requests.ConnectionError(
            "HTTPSConnectionPool(host='api.kavenegar.com', port=443): Max "
            f"retries exceeded with url: /v1/{KEY}/sms/send.json"
        )

        provider.send(PHONE, MESSAGE)

        assert KEY not in errors.text
        assert "api.kavenegar.com" in errors.text  # the rest is still useful

    def test_api_key_never_appears_in_logs_for_unexpected_errors(
        self, provider, mock_post, errors
    ):
        mock_post.side_effect = RuntimeError(f"failure calling {URL}")

        provider.send(PHONE, MESSAGE)

        assert KEY not in errors.text

    def test_url_quoted_form_of_the_key_is_masked_too(
        self, provider, mock_post, errors, settings
    ):
        settings.KAVENEGAR_API_KEY = "Ab12+/xyz=Qq99"
        mock_post.side_effect = requests.ConnectionError(
            "url: /v1/Ab12%2B%2Fxyz%3DQq99/sms/send.json and raw Ab12+/xyz=Qq99"
        )

        provider.send(PHONE, MESSAGE)

        assert "Ab12+/xyz=Qq99" not in errors.text
        assert "Ab12%2B%2Fxyz%3DQq99" not in errors.text

    def test_sms_text_is_never_logged_on_failures(self, provider, mock_post, errors):
        mock_post.side_effect = requests.ConnectionError("down")

        provider.send(PHONE, MESSAGE)

        assert OTP_CODE not in errors.text

    def test_missing_credentials_fail_cleanly_without_a_request(
        self, provider, mock_post, errors, settings
    ):
        settings.KAVENEGAR_API_KEY = ""

        assert provider.send(PHONE, MESSAGE) is False

        mock_post.assert_not_called()
        assert "KAVENEGAR_API_KEY" in error_records(errors)[0].getMessage()

    def test_missing_setting_attribute_fails_cleanly(
        self, provider, mock_post, errors, settings
    ):
        del settings.KAVENEGAR_API_KEY

        assert provider.send(PHONE, MESSAGE) is False
        mock_post.assert_not_called()


# ─── settings wiring (real settings modules, in a subprocess) ──────────────

_BASE_ENV = {
    "SECRET_KEY": "x",
    "DATABASE_NAME": "n",
    "DATABASE_USER": "u",
    "DATABASE_PASSWORD": "p",
    "DATABASE_HOST": "localhost",
    "ALLOWED_HOSTS": "example.com",
    "EMAIL_HOST_USER": "u",
    "EMAIL_HOST_PASSWORD": "p",
    "FRONTEND_URL": "https://example.com",
}


def import_settings(module, **extra_env):
    """Import a real settings module in a clean process; return
    (SMS_PROVIDER_CLASS, KAVENEGAR_API_KEY, stderr)."""
    code = (
        "import logging; logging.basicConfig(level=logging.WARNING)\n"
        "import importlib, json, sys\n"
        f"s = importlib.import_module({module!r})\n"
        "print(json.dumps([s.SMS_PROVIDER_CLASS, s.KAVENEGAR_API_KEY]))\n"
    )
    env = {"PATH": os.environ.get("PATH", ""), **_BASE_ENV, **extra_env}
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=django_settings.BASE_DIR,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    provider_class, api_key = json.loads(result.stdout.strip().splitlines()[-1])
    return provider_class, api_key, result.stderr


KAVENEGAR_PATH = "notifications.sms.kavenegar.KavenegarSMSProvider"
CONSOLE_PATH = "notifications.sms.console.ConsoleSMSProvider"


class TestSettingsWiring:
    def test_production_defaults_to_kavenegar(self):
        provider_class, _key, _err = import_settings(
            "core.settings.production", KAVENEGAR_API_KEY="k"
        )

        assert provider_class == KAVENEGAR_PATH

    def test_development_still_defaults_to_the_console_provider(self):
        provider_class, _key, _err = import_settings("core.settings.development")

        assert provider_class == CONSOLE_PATH

    def test_production_provider_can_still_be_overridden_by_env(self):
        provider_class, _key, _err = import_settings(
            "core.settings.production",
            SMS_PROVIDER_CLASS="some.other.Provider",
            KAVENEGAR_API_KEY="k",
        )

        assert provider_class == "some.other.Provider"

    def test_kavenegar_credentials_default_to_empty_and_read_from_env(self):
        _cls, empty_key, _err = import_settings("core.settings.production")
        _cls, set_key, _err = import_settings(
            "core.settings.production", KAVENEGAR_API_KEY="secret-key"
        )

        assert empty_key == ""
        assert set_key == "secret-key"

    def test_production_warns_when_kavenegar_has_no_api_key(self):
        _cls, _key, stderr = import_settings("core.settings.production")

        assert "KAVENEGAR_API_KEY is empty" in stderr

    def test_production_does_not_warn_when_the_api_key_is_set(self):
        _cls, _key, stderr = import_settings(
            "core.settings.production", KAVENEGAR_API_KEY="k"
        )

        assert "KAVENEGAR_API_KEY" not in stderr

    def test_production_warns_loudly_if_forced_back_to_the_console_provider(self):
        _cls, _key, stderr = import_settings(
            "core.settings.production", SMS_PROVIDER_CLASS=CONSOLE_PATH
        )

        assert "console provider" in stderr
