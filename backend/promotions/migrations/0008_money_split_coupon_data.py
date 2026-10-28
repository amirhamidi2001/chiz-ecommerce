# Step 4/5 of the Task 14.1.2.2 money migration for `promotions` (ADR 0001 §7.3).
#
# DATA ONLY: copy the legacy dual-purpose Coupon.value into the two new columns
# by discount_type. FIXED values were already re-baselined to whole-Toman Rial
# in 0006 (x10,000); PERCENT values were deliberately left untouched.
# Reversible: copies back into `value`.

from django.db import migrations
from django.db.models import BigIntegerField, F
from django.db.models.functions import Cast


def forwards(apps, schema_editor):
    Coupon = apps.get_model("promotions", "Coupon")
    Coupon.objects.filter(discount_type="percent").update(percent_off=F("value"))
    Coupon.objects.filter(discount_type="fixed").update(
        fixed_amount=Cast(F("value"), BigIntegerField())
    )


def backwards(apps, schema_editor):
    Coupon = apps.get_model("promotions", "Coupon")
    Coupon.objects.filter(discount_type="percent").update(value=F("percent_off"))
    Coupon.objects.filter(discount_type="fixed").update(value=F("fixed_amount"))


class Migration(migrations.Migration):

    dependencies = [
        ("promotions", "0007_money_split_coupon_columns"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
