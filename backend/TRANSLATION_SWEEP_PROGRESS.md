# Translation sweep progress (Task 14.1.1.3)

Re-run after each session: `python manage.py makemessages -l fa --ignore=venv --ignore="*/tests/*"`
Regression guard: `core/tests/test_translation_sweep.py` (fails on `_(f"...")`, `_("..." % x)`, `_("...".format())`).

Conventions
- Per-request strings (serializers/views/services): `from django.utils.translation import gettext as _`
- Definition-time strings (models, module-level validators): `gettext_lazy as _` (model `clean()` messages too)
- Interpolate AFTER translating: `_("Only %(stock)s left.") % {"stock": n}`; never split one sentence into translated fragments.
- Never wrap choice KEYS, logging calls, or developer-only invariants.

## Done
| App | Tier 1 (errors/messages) | Tier 2 (verbose_name/help_text) | Tier 3 (choice labels) |
|---|---|---|---|
| accounts | done (incl. emails subject/body, OTP SMS, phone validator) | done | done |
| order | done | done | done |
| cart | done | done | done |
| shop | done (incl. validators) | done | done |
| promotions | done (coupon validation messages) | done | done |
| payments | done | done | done |
| shipping | n/a (no customer-facing view strings) | done | done |
| contact | done | done | n/a |
| blog | done | done | n/a |
| chat | done (views + consumer) | done | n/a |
| dashboard | done for customer-facing (profile, password, wishlist) | done | done (IranProvince etc.) |

## Pending
- Admin tier: admin-only f-strings in dashboard/serializers.py (order status transition) and dashboard/views.py;
  stock-adjustment / duplicate-coupon / coupon-delete messages; dashboard/permissions.py message (needs gettext_lazy);
  all admin.py (list_display, actions); accounts/throttles.py messages.
- HTML email templates (accounts/emails/*.html): need `{% trans %}`, not Python wrapping.
- Contact notification email body (staff-facing) — optional.
- Deliberately left: PricingError messages, payment-gateway passthrough messages, logging, Celery task return strings,
  internal stock-movement notes, seed commands.
- (Task 14.1.1.4 — DONE: LOCALE_PATHS, LocaleMiddleware, full fa translation, compilemessages in Dockerfile + dev compose. See locale/README.md.)
- Re-run makemessages + translate any new msgids whenever the pending items above get wrapped.

## Related findings (belong to Task 14.1.1.2, not this sweep)
- `timezone.now().date()` returns the UTC date: cart/serializers.py, order/serializers.py, shop/admin.py, shop/tasks.py,
  dashboard/services.py -> use `timezone.localdate()`.
- Admin date filters (`__date__gte/lte`) now use Tehran calendar days; fixtures in dashboard/tests/test_filters.py were
  updated to be timezone-aware.
