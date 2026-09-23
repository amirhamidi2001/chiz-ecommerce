from django.db import migrations


def seed_periodic_task(apps, schema_editor):
    IntervalSchedule = apps.get_model("django_celery_beat", "IntervalSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    # IntervalSchedule (not CrontabSchedule, unlike shop's nightly
    # deactivate_expired_variants task) is the right tool here: this task
    # needs to run on a fixed, repeating cadence ("every 15 minutes"),
    # not at a specific time of day. Data migrations use apps.get_model(),
    # which returns the historical migration-state model — that model
    # doesn't carry the real class's IntervalSchedule.MINUTES constant,
    # so the literal string "minutes" (IntervalSchedule.PERIOD_CHOICES'
    # actual stored value) is used directly instead.
    every_15_minutes, _ = IntervalSchedule.objects.get_or_create(
        every=15,
        period="minutes",
    )
    PeriodicTask.objects.get_or_create(
        name="Reconcile stuck payment transactions",
        task="payments.tasks.reconcile_stuck_payment_transactions",
        defaults={"interval": every_15_minutes},
    )


def unseed_periodic_task(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(
        task="payments.tasks.reconcile_stuck_payment_transactions"
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("django_celery_beat", "0019_alter_periodictasks_options"),
        ("payments", "0002_paymentgatewayconfig"),
    ]

    operations = [
        migrations.RunPython(seed_periodic_task, unseed_periodic_task),
    ]
