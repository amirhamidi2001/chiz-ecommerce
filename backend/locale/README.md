# Translations (`backend/locale/`)

Persian (`fa`) is the site default; English (`en`) is the source language of every msgid.

## Workflow
```bash
cd backend
python manage.py makemessages -l fa --ignore=venv --ignore="*/tests/*"   # 1. extract new/changed strings
#   edit locale/fa/LC_MESSAGES/django.po                                  # 2. translate; clear any "#, fuzzy" flags
python manage.py compilemessages                                         # 3. build django.mo
```
- Needs the **GNU gettext** system package (`apt-get install gettext`); the backend Dockerfile installs it.
- `django.po` is committed. `django.mo` is **gitignored** and built at deploy time: the Dockerfile runs
  `django-admin compilemessages` at image build, and `docker-compose.dev.yml` runs it at container start
  (the dev bind mount hides anything built into the image).
- Validate before committing: `msgfmt -c --check-format --check-header -o /dev/null locale/fa/LC_MESSAGES/django.po`
- `core/tests/test_persian_catalog.py` fails if any entry loses Persian text or changes its `%(placeholders)s`.

## Language selection
`LocaleMiddleware` picks the language per request from `Accept-Language` (only `fa`/`en`), otherwise
`LANGUAGE_CODE = "fa"`. WebSocket (chat) traffic does not go through it and always uses the site default.
Tests are pinned to English by `backend/conftest.py`; translation tests opt in explicitly.

## Style conventions used in `fa`
- Digits: **Latin (0-9)** inside messages, so numbers match values interpolated from Python (`%(stock)s`).
  Convert digits at the frontend if Persian numerals are wanted.
- Terms: رمز عبور (password), کد تخفیف (coupon), سبد خرید (cart), تنوع محصول (product variant),
  تعرفه ارسال (shipping rate), درگاه (payment gateway), دیدگاه (review). Django's own admin chrome says «گذرواژه».
- Address the customer formally (شما). Use «» for quoted names. Use ZWNJ (نیم‌فاصله) in compounds (می‌شود, ‌ها).
- Never edit or translate `%(name)s` placeholders; they must appear exactly as in the msgid.
