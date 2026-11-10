# Task 14.4.1.2 / ADR 0002 - same bug and same fix as shop 0038, for the blog's
# Category and Post slugs (the blog models used the same plain slugify()).
# The blog never normalised names before slugging, hence normalize=False.
# Not reversible: the old slugs were empty or meaningless, so reverse is a no-op.
import logging

from django.db import migrations
from shop.text_utils import regenerate_legacy_slugs

logger = logging.getLogger(__name__)


def regenerate_slugs(apps, schema_editor):
    for model_name, name_field, fallback in (
        ("Category", "name", "category"),
        ("Post", "title", "post"),
    ):
        changed = regenerate_legacy_slugs(
            apps.get_model("blog", model_name),
            name_field,
            fallback=fallback,
            normalize=False,
        )
        logger.info("blog.%s: regenerated %d slug(s)", model_name, len(changed))


class Migration(migrations.Migration):

    dependencies = [
        ("blog", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(regenerate_slugs, migrations.RunPython.noop),
    ]
