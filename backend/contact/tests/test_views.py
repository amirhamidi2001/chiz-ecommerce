from unittest.mock import patch
from urllib.parse import urlencode

from contact.models import ContactMessage
from django.core import mail
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

ENDPOINT = "/api/contact/"

VALID_PAYLOAD = {
    "name": "Jane Doe",
    "email": "jane@example.com",
    "subject": "Return policy question",
    "message": "How do I return a product?",
}


# ─── helpers ──────────────────────────────────────────────────────────────────


def post(client: APIClient, payload: dict, **kwargs):
    return client.post(ENDPOINT, data=payload, format="json", **kwargs)


# ─── HTTP method routing ──────────────────────────────────────────────────────


class ContactEndpointMethodTests(TestCase):

    def setUp(self):
        self.client = APIClient()

    def test_post_is_allowed(self):
        response = post(self.client, VALID_PAYLOAD)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_get_is_not_allowed(self):
        response = self.client.get(ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_put_is_not_allowed(self):
        response = self.client.put(ENDPOINT, data=VALID_PAYLOAD, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_patch_is_not_allowed(self):
        response = self.client.patch(ENDPOINT, data=VALID_PAYLOAD, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_delete_is_not_allowed(self):
        response = self.client.delete(ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


# ─── authentication ───────────────────────────────────────────────────────────


class ContactEndpointAuthTests(TestCase):
    """Endpoint must be fully public — zero auth required."""

    def setUp(self):
        self.client = APIClient()

    def test_unauthenticated_request_succeeds(self):
        response = post(self.client, VALID_PAYLOAD)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_request_with_invalid_jwt_still_succeeds(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer totally.invalid.token")
        response = post(self.client, VALID_PAYLOAD)
        # authentication_classes=[] means token is never inspected
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


# ─── successful submission ────────────────────────────────────────────────────


class ContactEndpointSuccessTests(TestCase):

    def setUp(self):
        self.client = APIClient()

    def test_returns_201(self):
        response = post(self.client, VALID_PAYLOAD)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_response_body_contains_message_key(self):
        response = post(self.client, VALID_PAYLOAD)
        self.assertIn("message", response.data)

    def test_response_message_value(self):
        response = post(self.client, VALID_PAYLOAD)
        self.assertEqual(response.data["message"], "Message sent successfully")

    def test_record_is_persisted_in_db(self):
        post(self.client, VALID_PAYLOAD)
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_persisted_record_has_correct_name(self):
        post(self.client, VALID_PAYLOAD)
        msg = ContactMessage.objects.get()
        self.assertEqual(msg.name, VALID_PAYLOAD["name"])

    def test_persisted_record_has_normalised_email(self):
        post(self.client, {**VALID_PAYLOAD, "email": "Jane@Example.COM"})
        msg = ContactMessage.objects.get()
        self.assertEqual(msg.email, "jane@example.com")

    def test_persisted_record_has_correct_subject(self):
        post(self.client, VALID_PAYLOAD)
        msg = ContactMessage.objects.get()
        self.assertEqual(msg.subject, VALID_PAYLOAD["subject"])

    def test_persisted_record_has_correct_message_body(self):
        post(self.client, VALID_PAYLOAD)
        msg = ContactMessage.objects.get()
        self.assertEqual(msg.message, VALID_PAYLOAD["message"])

    def test_multiple_submissions_create_multiple_records(self):
        post(self.client, VALID_PAYLOAD)
        post(self.client, {**VALID_PAYLOAD, "email": "other@example.com"})
        self.assertEqual(ContactMessage.objects.count(), 2)


# ─── email dispatch ───────────────────────────────────────────────────────────


class ContactEndpointEmailTests(TestCase):
    """Uses Django's in-memory email backend (set in test settings automatically)."""

    def setUp(self):
        self.client = APIClient()
        mail.outbox = []

    def test_email_is_sent_on_success(self):
        post(self.client, VALID_PAYLOAD)
        self.assertEqual(len(mail.outbox), 1)

    def test_email_subject_contains_contact_subject(self):
        post(self.client, VALID_PAYLOAD)
        self.assertIn(VALID_PAYLOAD["subject"], mail.outbox[0].subject)

    def test_email_body_contains_sender_name(self):
        post(self.client, VALID_PAYLOAD)
        self.assertIn(VALID_PAYLOAD["name"], mail.outbox[0].body)

    def test_email_body_contains_sender_email(self):
        post(self.client, VALID_PAYLOAD)
        self.assertIn(VALID_PAYLOAD["email"], mail.outbox[0].body)

    def test_email_body_contains_message_text(self):
        post(self.client, VALID_PAYLOAD)
        self.assertIn(VALID_PAYLOAD["message"], mail.outbox[0].body)

    def test_reply_to_is_set_to_sender_email(self):
        post(self.client, VALID_PAYLOAD)
        self.assertIn(VALID_PAYLOAD["email"], mail.outbox[0].reply_to)

    def test_email_failure_does_not_prevent_201(self):
        """SMTP errors must never surface to the API caller."""
        with patch(
            "contact.views.EmailMessage.send",
            side_effect=Exception("SMTP connection refused"),
        ):
            response = post(self.client, VALID_PAYLOAD)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_email_failure_still_persists_db_record(self):
        with patch(
            "contact.views.EmailMessage.send",
            side_effect=Exception("SMTP connection refused"),
        ):
            post(self.client, VALID_PAYLOAD)

        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_no_email_sent_on_validation_failure(self):
        post(self.client, {**VALID_PAYLOAD, "email": "bad-email"})
        self.assertEqual(len(mail.outbox), 0)


# ─── validation failures → 400 ────────────────────────────────────────────────


class ContactEndpointValidationTests(TestCase):

    def setUp(self):
        self.client = APIClient()

    def _assert_field_error(self, payload: dict, field: str):
        response = post(self.client, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", response.data)
        self.assertIn(field, response.data["errors"])

    # missing fields
    def test_missing_name_returns_400(self):
        self._assert_field_error(
            {k: v for k, v in VALID_PAYLOAD.items() if k != "name"}, "name"
        )

    def test_missing_email_returns_400(self):
        self._assert_field_error(
            {k: v for k, v in VALID_PAYLOAD.items() if k != "email"}, "email"
        )

    def test_missing_subject_returns_400(self):
        self._assert_field_error(
            {k: v for k, v in VALID_PAYLOAD.items() if k != "subject"}, "subject"
        )

    def test_missing_message_returns_400(self):
        self._assert_field_error(
            {k: v for k, v in VALID_PAYLOAD.items() if k != "message"}, "message"
        )

    # blank / whitespace-only
    def test_blank_name_returns_400(self):
        self._assert_field_error({**VALID_PAYLOAD, "name": ""}, "name")

    def test_whitespace_only_name_returns_400(self):
        self._assert_field_error({**VALID_PAYLOAD, "name": "   "}, "name")

    def test_blank_subject_returns_400(self):
        self._assert_field_error({**VALID_PAYLOAD, "subject": ""}, "subject")

    def test_whitespace_only_message_returns_400(self):
        self._assert_field_error({**VALID_PAYLOAD, "message": "\n\t"}, "message")

    # email format
    def test_invalid_email_returns_400(self):
        self._assert_field_error({**VALID_PAYLOAD, "email": "notanemail"}, "email")

    def test_empty_body_returns_400_with_all_field_errors(self):
        response = post(self.client, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        errors = response.data.get("errors", {})
        for field in ("name", "email", "subject", "message"):
            self.assertIn(field, errors, f"Expected error key '{field}'")

    def test_no_db_record_created_on_validation_failure(self):
        post(self.client, {**VALID_PAYLOAD, "email": "bad"})
        self.assertEqual(ContactMessage.objects.count(), 0)

    # response shape
    def test_400_response_has_errors_key_not_message_key(self):
        response = post(self.client, {})
        self.assertIn("errors", response.data)
        self.assertNotIn("message", response.data)

    def test_201_response_has_message_key_not_errors_key(self):
        response = post(self.client, VALID_PAYLOAD)
        self.assertIn("message", response.data)
        self.assertNotIn("errors", response.data)


# ─── content-type handling ────────────────────────────────────────────────────


class ContactEndpointContentTypeTests(TestCase):

    def setUp(self):
        self.client = APIClient()

    def test_json_content_type_accepted(self):
        response = self.client.post(
            ENDPOINT, data=VALID_PAYLOAD, content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_form_encoded_content_type_accepted(self):
        encoded_data = urlencode(VALID_PAYLOAD)
        response = self.client.post(
            ENDPOINT,
            data=encoded_data,
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
