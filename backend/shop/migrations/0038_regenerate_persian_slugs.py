# Task 14.4.1.2 / ADR 0002 - FIXES A LIVE BUG: Persian-named Products, Categories
# and Brands got slugs from Django's slugify() without allow_unicode, which deletes
# every non-ASCII character ("" for most names; "", "-1", "-2" for products).
#
# Rewrites ONLY slugs the old generator produced (see
# shop.text_utils.regenerate_legacy_slugs for the exact rule and its caveats:
# no redirects; ZWNJ word boundaries are unrecoverable for existing rows).
# Uses queryset.update(): historical models have no custom save(), and the
# search_vector does not depend on the slug, so it needs no refresh.
# Not reversible: the old slugs were empty or meaningless, so reverse is a no-op.
import logging

from django.db import migrations
from shop.text_utils import regenerate_legacy_slugs

logger = logging.getLogger(__name__)


def regenerate_slugs(apps, schema_editor):
    for model_name, fallback in (
        ("Category", "category"),
        ("Brand", "brand"),
        ("Product", "product"),
    ):
        changed = regenerate_legacy_slugs(
            apps.get_model("shop", model_name), "name", fallback=fallback
        )
        logger.info("shop.%s: regenerated %d slug(s)", model_name, len(changed))


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0037_money_to_integer_rial"),
    ]

    operations = [
        migrations.RunPython(regenerate_slugs, migrations.RunPython.noop),
    ]
