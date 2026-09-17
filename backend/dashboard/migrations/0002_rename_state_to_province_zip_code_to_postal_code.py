from django.db import migrations


class Migration(migrations.Migration):
    """
    Task 5.2.1.4, part 1 of 2: pure RenameField operations only.

    Deliberately split from the follow-up migration (which adds the
    IranProvince choices constraint, the postal code regex validator,
    and cleans up legacy data that doesn't match either) — attempting
    to do a RunPython data cleanup and an AlterField on the SAME
    just-renamed column within a single migration's transaction fails
    against Postgres with "cannot ALTER TABLE ... because it has
    pending trigger events" (confirmed by actually running it). Two
    separate migrations means two separate transactions, which avoids
    that entirely.
    """

    dependencies = [
        ("dashboard", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="address",
            old_name="state",
            new_name="province",
        ),
        migrations.RenameField(
            model_name="address",
            old_name="zip_code",
            new_name="postal_code",
        ),
    ]
