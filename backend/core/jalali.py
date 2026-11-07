"""
Jalali (Solar Hijri) DISPLAY helpers for the Django admin (Task 14.2.1.2).

Jalali is a display concern only: every model field stays a standard Gregorian
`DateTimeField` stored in UTC (the same storage-vs-display split as currency,
ADR 0001), and nothing here is a form widget — editing still happens in the
Gregorian inputs, so the old jQuery bundled with django-jalali's date-picker
is never loaded.

The one rule that makes the output correct: **convert to local time first.**
Stored values are UTC; staff read Tehran time (UTC+3:30). 20:30 UTC on 20 Mar
2026 is already 00:00 on 21 Mar in Tehran — 1 Farvardin 1405, not 29 Esfand
1404. `jdatetime.datetime.fromgregorian()` does not do that conversion itself
(it reads the datetime's own fields), so `to_jalali_string()` does.

Usage in a ModelAdmin:

    class CouponAdmin(JalaliAdminMixin, admin.ModelAdmin):
        valid_from_jalali = jalali_column("valid_from", _("Valid from (Jalali)"))
        list_display = (..., "valid_from", "valid_from_jalali")
        readonly_fields = ("valid_from_jalali",)
        jalali_companions = {"valid_from": "valid_from_jalali"}  # shown beside its source
"""

import datetime

import jdatetime
from django.contrib import admin
from django.utils import timezone

DATETIME_FORMAT = "%Y/%m/%d %H:%M"
DATE_FORMAT = "%Y/%m/%d"


def to_jalali_string(value, fmt=None):
    """
    Gregorian date/datetime -> Jalali string, e.g. "1405/01/01 00:00".

    * an aware datetime is converted to the current time zone first (Tehran);
    * a naive datetime is taken as already local;
    * a plain date has no time part and is converted as-is;
    * None -> None (the caller decides how to show "empty").
    Digits are Western — the admin keeps Western digits (constants/numerals.js).
    """
    if value is None:
        return None
    if isinstance(value, datetime.datetime):  # check first: datetime is a date subclass
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return jdatetime.datetime.fromgregorian(datetime=value).strftime(
            fmt or DATETIME_FORMAT
        )
    if isinstance(value, datetime.date):
        return jdatetime.date.fromgregorian(date=value).strftime(fmt or DATE_FORMAT)
    raise TypeError(f"Cannot show {type(value).__name__!s} as a Jalali date.")


def jalali_column(field_name, description, *, fmt=None):
    """
    Build a read-only admin column that shows `field_name` as a Jalali date.

    Assign it in the ModelAdmin class body; the attribute name is what you put in
    `list_display` / `readonly_fields`. The column sorts by the underlying
    Gregorian field and shows the admin's usual empty value for None.
    """

    @admin.display(description=description, ordering=field_name)
    def column(self, obj):
        text = to_jalali_string(getattr(obj, field_name), fmt)
        return self.get_empty_value_display() if text is None else text

    column.__name__ = f"{field_name}_jalali"
    return column


class JalaliAdminMixin:
    """
    Put each Jalali companion field immediately after the field it mirrors on the
    detail page, for admins that rely on Django's automatic field layout.

    `jalali_companions = {"valid_from": "valid_from_jalali"}`. Admins with explicit
    `fieldsets` (e.g. OrderAdmin) place the companion there by hand instead.
    The companion names must also be listed in `readonly_fields`.
    """

    jalali_companions: dict = {}

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        for source, companion in self.jalali_companions.items():
            if source not in fields:
                continue
            if companion in fields:  # Django appends read-only fields at the end
                fields.remove(companion)
            fields.insert(fields.index(source) + 1, companion)
        return fields
