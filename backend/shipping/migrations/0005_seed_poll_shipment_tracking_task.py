from django.db import migrations


def seed_periodic_task(apps, schema_editor):
    IntervalSchedule = apps.get_model("django_celery_beat", "IntervalSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    # Same IntervalSchedule mechanism as payments'
    # 0003_seed_reconcile_stuck_payment_transactions_task migration: a
    # fixed, repeating cadence, not a specific time of day, so
    # IntervalSchedule (not CrontabSchedule) is the right tool. 45 minutes
    # sits in the middle of the 30-60 minute range this task calls
    # "reasonable" for shipment tracking — unlike payment reconciliation
    # (Task 6.5.1.1, every 15 minutes), a shipment's status being a little
    # stale is a non-event, not a stuck-money problem.
    every_45_minutes, _ = IntervalSchedule.objects.get_or_create(
        every=45,
        period="minutes",
    )
    PeriodicTask.objects.get_or_create(
        name="Poll shipment tracking",
        task="shipping.tasks.poll_shipment_tracking",
        defaults={"interval": every_45_minutes},
    )


def unseed_periodic_task(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(task="shipping.tasks.poll_shipment_tracking").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("django_celery_beat", "0019_alter_periodictasks_options"),
        ("shipping", "0004_shipment"),
    ]

    operations = [
        migrations.RunPython(seed_periodic_task, unseed_periodic_task),
    ]
