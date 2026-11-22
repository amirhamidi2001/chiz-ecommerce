"""
Seed the email templates that notify()'s default channels require but 0002
didn't create.

notifications.services sends order-update events (confirmed / status change /
shipping) to SMS + email and back-in-stock / price-drop to email. 0002 seeded
email only for order_confirmed, welcome and password_reset, so the other four
pairs would always have been logged SKIPPED ("No active template").

Same conventions and placeholder contract as 0002 (see its docstring).
get_or_create: never overwrites staff edits; reverse is a no-op.
"""

from django.db import migrations

EMAIL = "email"

# (channel, event, subject, body)
SEED_TEMPLATES = [
    (
        EMAIL,
        "order_status_changed",
        "تغییر وضعیت سفارش {order_number}",
        "{customer_name} عزیز،\n\n"
        "وضعیت سفارش شما با شماره {order_number} به «{status}» تغییر کرد.\n\n"
        "از همراهی شما سپاسگزاریم.",
    ),
    (
        EMAIL,
        "shipping_update",
        "وضعیت ارسال سفارش {order_number}",
        "{customer_name} عزیز،\n\n"
        "وضعیت ارسال سفارش شما با شماره {order_number}: {shipping_status}\n"
        "کد رهگیری مرسوله: {tracking_number}\n\n"
        "از شکیبایی شما سپاسگزاریم.",
    ),
    (
        EMAIL,
        "back_in_stock",
        "«{product_name}» دوباره موجود شد",
        "{customer_name} عزیز،\n\n"
        "محصولی که منتظر آن بودید، «{product_name}»، دوباره موجود شد. "
        "برای خرید می‌توانید از لینک زیر استفاده کنید:\n{product_url}\n\n"
        "موجودی ممکن است محدود باشد؛ پیشنهاد می‌کنیم زودتر اقدام کنید.",
    ),
    (
        EMAIL,
        "price_drop",
        "کاهش قیمت «{product_name}»",
        "{customer_name} عزیز،\n\n"
        "قیمت «{product_name}» از {old_price} تومان به {new_price} تومان "
        "کاهش یافت.\n{product_url}\n\n"
        "این قیمت ممکن است برای مدت محدودی معتبر باشد.",
    ),
]


def seed_templates(apps, schema_editor):
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    for channel, event, subject, body in SEED_TEMPLATES:
        NotificationTemplate.objects.get_or_create(
            channel=channel,
            event=event,
            defaults={"subject": subject, "body": body, "is_active": True},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0003_notificationlog"),
    ]

    operations = [
        migrations.RunPython(seed_templates, migrations.RunPython.noop),
    ]
