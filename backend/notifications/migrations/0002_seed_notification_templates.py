"""
Seed starting Persian copy for every (channel, event) pair this epic uses.

Style follows backend/locale/README.md: formal «شما», Latin digits, ZWNJ in
compounds, «» around quoted names.

Placeholder contract for the callers added by later tasks (all values are
plain strings, already formatted by the caller):

    {code}             OTP code
    {customer_name}    first name (or full name) of the recipient
    {order_number}     e.g. ORD-3A7F2B
    {order_total}      order total in Toman, digits only (the template adds «تومان»)
    {status}           localized order status label (e.g. «ارسال شد»)
    {shipping_status}  localized shipping status label
    {tracking_number}  carrier tracking code
    {product_name}     product (variant) display name
    {product_url}      absolute storefront URL of the product
    {old_price}        previous price in Toman, digits only
    {new_price}        new price in Toman, digits only
    {reset_url}        absolute password-reset link

Rows are created with get_or_create, so re-running never overwrites copy that
staff have since edited. The reverse is a no-op for the same reason.
"""

from django.db import migrations

SMS, EMAIL, IN_APP = "sms", "email", "in_app"

# (channel, event, subject, body)
SEED_TEMPLATES = [
    # ── OTP ── same wording as the existing localized string in
    # accounts/services/otp.py ("کد تأیید شما: %(code)s"), plus a safety line.
    (
        SMS,
        "otp_code",
        "",
        "کد تأیید شما: {code}\nاین کد را در اختیار هیچ‌کس قرار ندهید.",
    ),
    # ── Order confirmed ──
    (
        SMS,
        "order_confirmed",
        "",
        "{customer_name} عزیز، سفارش شما با شماره {order_number} با موفقیت ثبت شد. "
        "از خرید شما سپاسگزاریم.",
    ),
    (
        EMAIL,
        "order_confirmed",
        "تأیید سفارش {order_number}",
        "{customer_name} عزیز،\n\n"
        "سفارش شما با شماره {order_number} با موفقیت ثبت شد و در حال آماده‌سازی است.\n"
        "مبلغ کل سفارش: {order_total} تومان\n\n"
        "از اینکه ما را برای خرید انتخاب کردید سپاسگزاریم.",
    ),
    (
        IN_APP,
        "order_confirmed",
        "",
        "سفارش شما با شماره {order_number} با موفقیت ثبت شد.",
    ),
    # ── Order status changed ──
    (
        SMS,
        "order_status_changed",
        "",
        "{customer_name} عزیز، وضعیت سفارش {order_number} به «{status}» تغییر کرد.",
    ),
    (
        IN_APP,
        "order_status_changed",
        "",
        "وضعیت سفارش {order_number} به «{status}» تغییر کرد.",
    ),
    # ── Shipping update ──
    (
        SMS,
        "shipping_update",
        "",
        "{customer_name} عزیز، وضعیت ارسال سفارش {order_number}: {shipping_status}.\n"
        "کد رهگیری مرسوله: {tracking_number}",
    ),
    (
        IN_APP,
        "shipping_update",
        "",
        "وضعیت ارسال سفارش {order_number}: {shipping_status} "
        "(کد رهگیری: {tracking_number})",
    ),
    # ── Back in stock ──
    (
        SMS,
        "back_in_stock",
        "",
        "{customer_name} عزیز، «{product_name}» دوباره موجود شد. "
        "برای خرید از لینک زیر استفاده کنید:\n{product_url}",
    ),
    (
        IN_APP,
        "back_in_stock",
        "",
        "«{product_name}» دوباره موجود شد.",
    ),
    # ── Price drop ──
    (
        SMS,
        "price_drop",
        "",
        "{customer_name} عزیز، قیمت «{product_name}» از {old_price} به "
        "{new_price} تومان کاهش یافت.\n{product_url}",
    ),
    (
        IN_APP,
        "price_drop",
        "",
        "قیمت «{product_name}» به {new_price} تومان کاهش یافت.",
    ),
    # ── Welcome ── subject matches the existing localized email subject.
    (
        EMAIL,
        "welcome",
        "خوش آمدید! حساب کاربری شما آماده است.",
        "{customer_name} عزیز، خوش آمدید! حساب کاربری شما آماده است.\n\n"
        "اکنون می‌توانید محصولات را مشاهده کنید و خرید خود را ثبت نمایید.",
    ),
    # ── Password reset ── subject matches the existing localized email subject.
    (
        EMAIL,
        "password_reset",
        "بازیابی رمز عبور",
        "{customer_name} عزیز،\n\n"
        "برای تعیین رمز عبور جدید، از لینک زیر استفاده کنید:\n{reset_url}\n\n"
        "اگر این درخواست از طرف شما نبوده است، این پیام را نادیده بگیرید.",
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
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_templates, migrations.RunPython.noop),
    ]
