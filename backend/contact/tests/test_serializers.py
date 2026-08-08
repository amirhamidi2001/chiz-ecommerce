from contact.models import ContactMessage
from contact.serializers import ContactMessageSerializer
from django.test import TestCase

# ─── helpers ──────────────────────────────────────────────────────────────────

VALID_PAYLOAD = {
    "name": "Jane Doe",
    "email": "Jane@Example.COM",
    "subject": "Product question",
    "message": "I'd like to know more about your return policy.",
}


def make_serializer(data: dict) -> ContactMessageSerializer:
    return ContactMessageSerializer(data=data)


# ─── valid data ───────────────────────────────────────────────────────────────


class SerializerValidDataTests(TestCase):

    def test_valid_payload_is_valid(self):
        s = make_serializer(VALID_PAYLOAD)
        self.assertTrue(s.is_valid(), s.errors)

    def test_valid_payload_creates_db_record(self):
        s = make_serializer(VALID_PAYLOAD)
        s.is_valid(raise_exception=True)
        instance = s.save()

        self.assertIsInstance(instance, ContactMessage)
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_read_only_fields_not_writable(self):
        payload = {**VALID_PAYLOAD, "id": 999, "created_at": "2000-01-01T00:00:00Z"}
        s = make_serializer(payload)
        self.assertTrue(s.is_valid(), s.errors)
        instance = s.save()

        self.assertNotEqual(instance.pk, 999)

    def test_representation_includes_id_and_created_at(self):
        s = make_serializer(VALID_PAYLOAD)
        s.is_valid(raise_exception=True)
        instance = s.save()
        data = ContactMessageSerializer(instance).data

        self.assertIn("id", data)
        self.assertIn("created_at", data)


# ─── required fields ──────────────────────────────────────────────────────────


class SerializerRequiredFieldTests(TestCase):

    REQUIRED_FIELDS = ["name", "email", "subject", "message"]

    def _assert_field_required(self, field: str):
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != field}
        s = make_serializer(payload)
        self.assertFalse(s.is_valid())
        self.assertIn(field, s.errors)

    def test_name_required(self):
        self._assert_field_required("name")

    def test_email_required(self):
        self._assert_field_required("email")

    def test_subject_required(self):
        self._assert_field_required("subject")

    def test_message_required(self):
        self._assert_field_required("message")

    def test_all_fields_missing_returns_all_errors(self):
        s = make_serializer({})
        self.assertFalse(s.is_valid())
        for field in self.REQUIRED_FIELDS:
            self.assertIn(field, s.errors, f"Expected error for '{field}'")


# ─── whitespace trimming ──────────────────────────────────────────────────────


class SerializerWhitespaceTrimTests(TestCase):

    def test_name_is_trimmed(self):
        s = make_serializer({**VALID_PAYLOAD, "name": "  Jane Doe  "})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["name"], "Jane Doe")

    def test_subject_is_trimmed(self):
        s = make_serializer({**VALID_PAYLOAD, "subject": "\tProduct question\n"})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["subject"], "Product question")

    def test_message_is_trimmed(self):
        s = make_serializer({**VALID_PAYLOAD, "message": "  Hello world.  "})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["message"], "Hello world.")

    def test_whitespace_only_name_is_invalid(self):
        s = make_serializer({**VALID_PAYLOAD, "name": "   "})
        self.assertFalse(s.is_valid())
        self.assertIn("name", s.errors)

    def test_whitespace_only_subject_is_invalid(self):
        s = make_serializer({**VALID_PAYLOAD, "subject": "   "})
        self.assertFalse(s.is_valid())
        self.assertIn("subject", s.errors)

    def test_whitespace_only_message_is_invalid(self):
        s = make_serializer({**VALID_PAYLOAD, "message": "\n\t  "})
        self.assertFalse(s.is_valid())
        self.assertIn("message", s.errors)

    def test_empty_string_name_is_invalid(self):
        s = make_serializer({**VALID_PAYLOAD, "name": ""})
        self.assertFalse(s.is_valid())
        self.assertIn("name", s.errors)


# ─── email validation & normalisation ────────────────────────────────────────


class SerializerEmailTests(TestCase):

    def test_email_is_lowercased(self):
        s = make_serializer({**VALID_PAYLOAD, "email": "Jane@Example.COM"})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["email"], "jane@example.com")

    def test_email_is_stripped(self):
        s = make_serializer({**VALID_PAYLOAD, "email": "  jane@example.com  "})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["email"], "jane@example.com")

    def test_invalid_email_no_at_sign(self):
        s = make_serializer({**VALID_PAYLOAD, "email": "notanemail"})
        self.assertFalse(s.is_valid())
        self.assertIn("email", s.errors)

    def test_invalid_email_no_domain(self):
        s = make_serializer({**VALID_PAYLOAD, "email": "user@"})
        self.assertFalse(s.is_valid())
        self.assertIn("email", s.errors)

    def test_invalid_email_no_local_part(self):
        s = make_serializer({**VALID_PAYLOAD, "email": "@example.com"})
        self.assertFalse(s.is_valid())
        self.assertIn("email", s.errors)

    def test_invalid_email_spaces_inside(self):
        s = make_serializer({**VALID_PAYLOAD, "email": "user @example.com"})
        self.assertFalse(s.is_valid())
        self.assertIn("email", s.errors)


# ─── persisted values ─────────────────────────────────────────────────────────


class SerializerPersistenceTests(TestCase):

    def test_saved_instance_has_normalised_email(self):
        s = make_serializer({**VALID_PAYLOAD, "email": "UPPER@EXAMPLE.COM"})
        s.is_valid(raise_exception=True)
        instance = s.save()
        instance.refresh_from_db()

        self.assertEqual(instance.email, "upper@example.com")

    def test_saved_instance_has_trimmed_name(self):
        s = make_serializer({**VALID_PAYLOAD, "name": "  Jane  "})
        s.is_valid(raise_exception=True)
        instance = s.save()
        instance.refresh_from_db()

        self.assertEqual(instance.name, "Jane")
