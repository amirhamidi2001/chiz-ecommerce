import re

from django.db import migrations

IRAN_PROVINCE_VALUES = {
    "alborz",
    "ardabil",
    "bushehr",
    "chaharmahal_and_bakhtiari",
    "east_azerbaijan",
    "fars",
    "gilan",
    "golestan",
    "hamadan",
    "hormozgan",
    "ilam",
    "isfahan",
    "kerman",
    "kermanshah",
    "khuzestan",
    "kohgiluyeh_and_boyer_ahmad",
    "kurdistan",
    "lorestan",
    "markazi",
    "mazandaran",
    "north_khorasan",
    "qazvin",
    "qom",
    "khorasan_razavi",
    "semnan",
    "sistan_and_baluchestan",
    "south_khorasan",
    "tehran",
    "west_azerbaijan",
    "yazd",
    "zanjan",
}

_POSTAL_CODE_RE = re.compile(r"^\d{10}$")


def clear_invalid_provinces(apps, schema_editor):
    """
    Existing rows may contain arbitrary free text in the just-renamed
    province column (e.g. "CA", "NY", test data) left over from the old
    free-text state field — this doesn't match any IranProvince choice.
    Deliberately CLEARING those to blank rather than leaving them,
    since showing a garbage value against a choices-only field (e.g. a
    dropdown that only offers the 31 valid options) is worse than an
    empty field the customer is prompted to fill in correctly. This
    assumes no real, order-critical production address data is being
    lost silently — a blanked province is visibly incomplete (province
    is blank=True specifically to allow this) and directly prompts a
    fix, rather than silently misrepresenting an address as being in a
    province it was never actually in.
    """
    Address = apps.get_model("dashboard", "Address")
    for address in Address.objects.exclude(province__in=IRAN_PROVINCE_VALUES):
        address.province = ""
        address.save(update_fields=["province"])


def clear_invalid_postal_codes(apps, schema_editor):
    """
    Same reasoning as clear_invalid_provinces, PLUS a hard practical
    requirement: the AlterField below shrinks postal_code's max_length
    from 20 (the old zip_code's) to 10 — any existing value longer than
    10 characters would make that ALTER COLUMN fail outright at the
    database level. Clearing anything that isn't exactly 10 digits
    (too long, too short, or non-numeric — e.g. an old 5-digit US ZIP)
    to blank must run BEFORE that AlterField, not after.
    """
    Address = apps.get_model("dashboard", "Address")
    for address in Address.objects.all():
        if not _POSTAL_CODE_RE.match(address.postal_code or ""):
            address.postal_code = ""
            address.save(update_fields=["postal_code"])


def noop_reverse(apps, schema_editor):
    """
    Data loss from the clear_invalid_* functions above is NOT
    reversible (the original invalid free-text values are gone) — a
    deliberate, documented one-way data decision, not an oversight.
    """
    pass


class Migration(migrations.Migration):
    """
    Task 5.2.1.4, part 2 of 3: data cleanup only (RunPython), in its
    own migration/transaction — separate from the AlterField
    constraint changes in the next migration. Confirmed by actually
    running it: a RunPython UPDATE followed by an AlterField DDL
    statement on the SAME table within one transaction fails against
    Postgres with "cannot ALTER TABLE ... because it has pending
    trigger events" (Address has a FK to the user table, and Postgres
    won't let you run further DDL on a table with unfired FK-related
    trigger events from earlier DML in the same transaction).
    """

    dependencies = [
        ("dashboard", "0002_rename_state_to_province_zip_code_to_postal_code"),
    ]

    operations = [
        migrations.RunPython(clear_invalid_provinces, noop_reverse),
        migrations.RunPython(clear_invalid_postal_codes, noop_reverse),
    ]
