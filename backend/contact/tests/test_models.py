from contact.models import ContactMessage
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

# ─── helpers ──────────────────────────────────────────────────────────────────


def make_message(**kwargs) -> ContactMessage:
    defaults = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "subject": "Test Subject",
        "message": "Hello, this is a test message.",
    }
    defaults.update(kwargs)
    return ContactMessage.objects.create(**defaults)


# ─── field defaults & persistence ─────────────────────────────────────────────


class ContactMessageFieldTests(TestCase):

    def test_create_saves_all_fields(self):
        msg = make_message()
        msg.refresh_from_db()

        self.assertEqual(msg.name, "Jane Doe")
        self.assertEqual(msg.email, "jane@example.com")
        self.assertEqual(msg.subject, "Test Subject")
        self.assertEqual(msg.message, "Hello, this is a test message.")

    def test_created_at_is_set_automatically(self):
        before = timezone.now()
        msg = make_message()
        after = timezone.now()

        self.assertIsNotNone(msg.created_at)
        self.assertGreaterEqual(msg.created_at, before)
        self.assertLessEqual(msg.created_at, after)

    def test_created_at_is_immutable_on_save(self):
        msg = make_message()
        original_ts = msg.created_at

        msg.name = "Updated Name"
        msg.save()
        msg.refresh_from_db()

        self.assertEqual(msg.created_at, original_ts)

    def test_pk_is_auto_assigned(self):
        msg = make_message()
        self.assertIsNotNone(msg.pk)
        self.assertIsInstance(msg.pk, int)

    def test_multiple_messages_get_distinct_pks(self):
        m1 = make_message()
        m2 = make_message()
        self.assertNotEqual(m1.pk, m2.pk)


# ─── __str__ ──────────────────────────────────────────────────────────────────


class ContactMessageStrTests(TestCase):

    def test_str_contains_subject_and_email(self):
        msg = make_message(subject="Order inquiry", email="buyer@shop.com")
        result = str(msg)

        self.assertIn("Order inquiry", result)
        self.assertIn("buyer@shop.com", result)

    def test_str_contains_date(self):
        msg = make_message()
        # Date portion is formatted as YYYY-MM-DD
        expected_date = msg.created_at.strftime("%Y-%m-%d")
        self.assertIn(expected_date, str(msg))


# ─── ordering ─────────────────────────────────────────────────────────────────


class ContactMessageOrderingTests(TestCase):

    def test_default_ordering_is_newest_first(self):
        m1 = make_message(subject="First")
        m2 = make_message(subject="Second")
        m3 = make_message(subject="Third")

        messages = list(ContactMessage.objects.all())
        self.assertEqual(messages[0], m3)
        self.assertEqual(messages[1], m2)
        self.assertEqual(messages[2], m1)


# ─── field constraints ────────────────────────────────────────────────────────


class ContactMessageConstraintTests(TestCase):

    def test_name_max_length_150(self):
        msg = make_message(name="a" * 150)
        msg.full_clean()  # should not raise

    def test_name_exceeds_max_length_raises(self):
        obj = ContactMessage(
            name="a" * 151,
            email="x@x.com",
            subject="s",
            message="m",
        )
        with self.assertRaises(ValidationError):
            obj.full_clean()

    def test_subject_max_length_255(self):
        msg = ContactMessage(
            name="N",
            email="n@n.com",
            subject="s" * 255,
            message="m",
        )
        msg.full_clean()  # should not raise

    def test_subject_exceeds_max_length_raises(self):
        obj = ContactMessage(
            name="N",
            email="n@n.com",
            subject="s" * 256,
            message="m",
        )
        with self.assertRaises(ValidationError):
            obj.full_clean()

    def test_invalid_email_format_raises(self):
        obj = ContactMessage(
            name="N",
            email="not-an-email",
            subject="s",
            message="m",
        )
        with self.assertRaises(ValidationError):
            obj.full_clean()

    def test_message_field_accepts_long_text(self):
        long_text = "word " * 2000
        msg = make_message(message=long_text)
        msg.refresh_from_db()
        self.assertEqual(msg.message, long_text)

    def test_name_cannot_be_null(self):
        with self.assertRaises((IntegrityError, ValidationError)):
            ContactMessage.objects.create(
                name=None,
                email="x@x.com",
                subject="s",
                message="m",
            )

    def test_email_cannot_be_null(self):
        with self.assertRaises((IntegrityError, ValidationError)):
            ContactMessage.objects.create(
                name="N",
                email=None,
                subject="s",
                message="m",
            )


# ─── meta ─────────────────────────────────────────────────────────────────────


class ContactMessageMetaTests(TestCase):

    def test_verbose_name(self):
        self.assertEqual(ContactMessage._meta.verbose_name, "Contact Message")

    def test_verbose_name_plural(self):
        self.assertEqual(ContactMessage._meta.verbose_name_plural, "Contact Messages")

    def test_ordering_meta(self):
        self.assertEqual(ContactMessage._meta.ordering, ["-created_at"])
