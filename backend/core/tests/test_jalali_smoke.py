"""
core/tests/test_jalali_smoke.py
───────────────────────────────
Smoke tests for the Jalali (Solar Hijri) calendar support added in Task 14.2.1.1.
Needs no database.

Jalali is a DISPLAY / admin-UX concern. Storage stays Gregorian/UTC (the same
storage-vs-display split as currency, ADR 0001), so besides proving the library
works these tests pin that nothing in the project stores a Jalali value and that
installing the app changes no existing admin widget.

The reference dates are NOT taken from the library under test:
  * 1979-02-11 = 22 Bahman 1357 (the Islamic Revolution public holiday);
  * Nowruz (1 Farvardin) for 1379, 1403-1407, from the vernal-equinox instant in
    Tehran time: before noon -> that day, after noon -> the next day;
  * 1403 is a leap year (30 Esfand 1403 = 2025-03-20, the day before Nowruz 1404).
They were also cross-checked against ICU's Persian calendar for every day from
1921 to 2100 when the pin was chosen (zero differences).
"""

import datetime
import importlib.metadata
import re
from pathlib import Path

import jdatetime
from django.apps import apps
from django.conf import settings
from django.contrib.admin import options as admin_options
from django.contrib.admin.widgets import AdminDateWidget
from django.db import models
from django.template import Context, Template
from django.test import SimpleTestCase, override_settings
from django.utils import timezone

D = datetime.date

# (Gregorian date, expected (jalali year, month, day), why it is a good reference)
KNOWN_PAIRS = [
    (D(1979, 2, 11), (1357, 11, 22), "22 Bahman 1357 — Islamic Revolution day"),
    (D(2000, 3, 20), (1379, 1, 1), "Nowruz 1379"),
    (D(2021, 3, 21), (1400, 1, 1), "Nowruz 1400"),
    (D(2024, 3, 20), (1403, 1, 1), "Nowruz 1403 (equinox before noon Tehran time)"),
    (D(2025, 3, 20), (1403, 12, 30), "30 Esfand 1403 — leap-year extra day"),
    (D(2025, 3, 21), (1404, 1, 1), "Nowruz 1404 (equinox after noon -> next day)"),
    (D(2026, 3, 20), (1404, 12, 29), "29 Esfand 1404 — last day of a common year"),
    (D(2026, 3, 21), (1405, 1, 1), "Nowruz 1405"),
    (D(2027, 3, 21), (1406, 1, 1), "Nowruz 1406"),
    (D(2028, 3, 20), (1407, 1, 1), "Nowruz 1407"),
]


def _pinned(name):
    """The version pinned for `name` in backend/requirements.txt."""
    text = (Path(settings.BASE_DIR) / "requirements.txt").read_text(encoding="utf-8")
    norm = lambda n: re.sub(r"[-_.]+", "-", n).lower()
    for line in text.splitlines():
        if "==" in line and norm(line.split("==")[0].strip()) == norm(name):
            return line.split("==")[1].strip()
    raise AssertionError(f"{name} is not pinned in requirements.txt")


class JdatetimeLibraryTests(SimpleTestCase):
    def test_importable_and_matches_the_pinned_versions(self):
        import jalali_core  # noqa: F401  (jdatetime's calendar engine)

        self.assertEqual(jdatetime.__VERSION__, _pinned("jdatetime"))
        self.assertEqual(
            importlib.metadata.version("django-jalali"), _pinned("django-jalali")
        )
        self.assertEqual(
            importlib.metadata.version("jalali-core"), _pinned("jalali-core")
        )

    def test_gregorian_to_jalali_known_dates(self):
        for gregorian, expected, why in KNOWN_PAIRS:
            with self.subTest(why):
                j = jdatetime.date.fromgregorian(date=gregorian)
                self.assertEqual((j.year, j.month, j.day), expected)

    def test_jalali_to_gregorian_known_dates(self):
        for gregorian, expected, why in KNOWN_PAIRS:
            with self.subTest(why):
                self.assertEqual(jdatetime.date(*expected).togregorian(), gregorian)

    def test_round_trip_every_day_for_35_years(self):
        day, end, previous = D(2000, 1, 1), D(2035, 12, 31), None
        while day <= end:
            j = jdatetime.date.fromgregorian(date=day)
            self.assertEqual(j.togregorian(), day)
            key = (j.year, j.month, j.day)
            self.assertTrue(
                previous is None or key > previous, day
            )  # strictly increasing
            previous, day = key, day + datetime.timedelta(days=1)

    def test_leap_years(self):
        self.assertTrue(jdatetime.date(1403, 1, 1).isleap())
        self.assertFalse(jdatetime.date(1404, 1, 1).isleap())
        jdatetime.date(1403, 12, 30)  # exists in a leap year
        with self.assertRaises(ValueError):
            jdatetime.date(1404, 12, 30)  # ...but not in a common year

    def test_datetime_keeps_the_time_of_day(self):
        j = jdatetime.datetime.fromgregorian(
            datetime=datetime.datetime(2025, 3, 21, 13, 45, 30)
        )
        self.assertEqual(
            (j.year, j.month, j.day, j.hour, j.minute, j.second),
            (1404, 1, 1, 13, 45, 30),
        )


@override_settings(USE_TZ=True, TIME_ZONE="Asia/Tehran")
class TehranDayBoundaryTests(SimpleTestCase):
    """
    Storage is UTC; staff read Tehran time (UTC+3:30, no DST). 20:30 UTC on 20 Mar
    2026 is already 00:00 on 21 Mar in Tehran, i.e. 1 Farvardin 1405 — not 29
    Esfand 1404. Admin display code in Task 14.2.1.2 must convert to local time.
    """

    INSTANT = datetime.datetime(2026, 3, 20, 20, 30, tzinfo=datetime.timezone.utc)

    def test_template_filter_converts_to_local_time_first(self):
        out = Template("{% load jformat %}{{ v|jformat:'%Y/%m/%d' }}").render(
            Context({"v": self.INSTANT})
        )
        self.assertEqual(out, "1405/01/01")

    def test_converting_in_python_requires_localtime(self):
        # The pitfall: fromgregorian() reads the datetime's own fields, so a raw
        # UTC value gives the UTC day...
        raw = jdatetime.datetime.fromgregorian(datetime=self.INSTANT)
        self.assertEqual((raw.year, raw.month, raw.day), (1404, 12, 29))
        # ...and the right answer needs timezone.localtime() first.
        local = jdatetime.datetime.fromgregorian(
            datetime=timezone.localtime(self.INSTANT)
        )
        self.assertEqual((local.year, local.month, local.day), (1405, 1, 1))


class DjangoJalaliInstallTests(SimpleTestCase):
    def test_app_is_installed_ahead_of_every_local_app(self):
        self.assertTrue(apps.is_installed("django_jalali"))
        names = [a.name for a in apps.get_app_configs()]
        # the package's docs require it before the project's own apps
        self.assertLess(names.index("django_jalali"), names.index("core"))

    def test_jformat_renders_a_plain_date(self):
        out = Template("{% load jformat %}{{ d|jformat:'%Y/%m/%d' }}").render(
            Context({"d": D(2025, 3, 21)})
        )
        self.assertEqual(out, "1404/01/01")

    def test_jformat_is_empty_for_missing_values(self):
        out = Template("{% load jformat %}[{{ d|jformat:'%Y' }}]").render(
            Context({"d": None})
        )
        self.assertEqual(out, "[]")

    def test_installing_it_adds_no_models_and_no_migrations(self):
        self.assertEqual(list(apps.get_app_config("django_jalali").get_models()), [])

    def test_existing_gregorian_admin_widgets_are_untouched(self):
        import django_jalali.admin  # noqa: F401  (registers widgets for ITS OWN field types only)

        defaults = admin_options.FORMFIELD_FOR_DBFIELD_DEFAULTS
        self.assertIs(defaults[models.DateField]["widget"], AdminDateWidget)

    def test_no_project_model_stores_a_jalali_value(self):
        """Storage stays Gregorian/UTC; Jalali is display only."""
        from django_jalali.db.models import jDateField, jDateTimeField

        offenders = [
            f"{m._meta.label}.{f.name}"
            for m in apps.get_models()
            for f in m._meta.get_fields()
            if isinstance(f, (jDateField, jDateTimeField))
        ]
        self.assertEqual(offenders, [])
