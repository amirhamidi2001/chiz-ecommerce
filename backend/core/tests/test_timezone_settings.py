"""
core/tests/test_timezone_settings.py
────────────────────────────────────
Guards the Iran display-timezone setting (Task 14.1.1.2). Settings-only;
needs no database.
"""

from datetime import datetime
from datetime import timezone as dt_timezone

from django.conf import settings
from django.test import SimpleTestCase
from django.utils import timezone


class TimezoneSettingsTests(SimpleTestCase):
    def test_time_zone_is_tehran(self):
        self.assertEqual(settings.TIME_ZONE, "Asia/Tehran")

    def test_use_tz_remains_enabled(self):
        # Storage stays UTC-aware; TIME_ZONE is display/interpretation only.
        self.assertTrue(settings.USE_TZ)

    def test_utc_instant_localizes_to_iran_standard_time(self):
        utc_dt = datetime(2026, 1, 1, 0, 0, tzinfo=dt_timezone.utc)
        local = timezone.localtime(utc_dt)
        self.assertEqual((local.hour, local.minute), (3, 30))

    def test_no_dst_offset_is_constant_year_round(self):
        # Iran abolished DST in 2022; requires an up-to-date tzdata.
        winter = timezone.localtime(datetime(2026, 1, 1, tzinfo=dt_timezone.utc))
        summer = timezone.localtime(datetime(2026, 7, 1, tzinfo=dt_timezone.utc))
        self.assertEqual(winter.utcoffset(), summer.utcoffset())
