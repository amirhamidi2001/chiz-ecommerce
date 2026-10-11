from django.db import migrations, models


def approve_existing_reviews(apps, schema_editor):
    """
    Every review that exists before moderation was introduced was already
    publicly visible and counted in Product.rating. Grandfather them in as
    approved so deploying this migration doesn't make them vanish (and doesn't
    reset ratings to 0 on the next stats refresh).
    """
    Review = apps.get_model("shop", "Review")
    Review.objects.update(is_approved=True)


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0024_seed_deactivate_expired_variants_task"),
    ]

    operations = [
        migrations.AddField(
            model_name="review",
            name="is_approved",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(approve_existing_reviews, migrations.RunPython.noop),
    ]
