"""
core/settings/base.py
─────────────────────
Shared settings that apply to every environment.
Never import this file directly — use development.py or production.py.
"""

from datetime import timedelta
from pathlib import Path

from decouple import config

# ─── Paths ────────────────────────────────────────────────────────────────────
# base.py lives at  backend/core/settings/base.py
# BASE_DIR must still resolve to  backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent


# ─── Security ─────────────────────────────────────────────────────────────────
SECRET_KEY = config("SECRET_KEY")


# ─── Installed Applications ───────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    # Third-party
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "django_filters",
    "channels",
    "django_celery_beat",
    # Local
    "accounts.apps.AccountsConfig",
    "contact.apps.ContactConfig",
    "shop.apps.ShopConfig",
    "cart.apps.CartConfig",
    "order.apps.OrderConfig",
    "dashboard.apps.DashboardConfig",
    "chat.apps.ChatConfig",
    "blog.apps.BlogConfig",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"
ASGI_APPLICATION = "core.asgi.application"


# ─── Database ─────────────────────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DATABASE_NAME"),
        "USER": config("DATABASE_USER"),
        "PASSWORD": config("DATABASE_PASSWORD"),
        "HOST": config("DATABASE_HOST"),
        "PORT": config("DATABASE_PORT", default="5432"),
    }
}


# ─── Password Validation ──────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ─── Internationalisation ─────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# ─── Static & Media ───────────────────────────────────────────────────────────
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ─── Custom User Model ────────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"


# ─── Django REST Framework ────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "shop.pagination.StandardResultsPagination",
    "PAGE_SIZE": 12,
    # ── Rate limiting ────────────────────────────────────────────────────
    # General, project-wide throttling (Task 2.1.3.1). Before this, ONLY
    # the OTP-specific scope below existed (Task 2.1.2.4) — every other
    # endpoint (product listing, cart, checkout, login, everything) had
    # zero rate limiting at all.
    #
    # NOTE: setting `throttle_classes` explicitly on a view (as
    # OTPRequestView does, for PhoneOTPRequestThrottle) REPLACES these
    # global defaults for that view entirely — DRF does not merge
    # per-view throttle_classes with DEFAULT_THROTTLE_CLASSES, it's one
    # or the other. See accounts/views.py:OTPRequestView for the
    # deliberate decision on whether that view also gets general
    # anon-rate protection on top of its phone-based cooldown.
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        # Initial, reasonable-guess starting rates for an e-commerce
        # storefront — generous enough not to break normal
        # browsing/pagination/search-as-you-type, tight enough to blunt
        # basic scripted abuse. These are NOT permanently correct: tune
        # them once the site has real traffic data to look at.
        "anon": "100/min",
        "user": "300/min",
        # Tighter scope for sensitive, high-value-target auth endpoints
        # (login, register, password-reset-request/confirm) — 10/min per
        # anonymous client/IP, deliberately much stricter than the
        # general 100/min anon rate, since these are the endpoints a
        # credential-stuffing / mass-fake-account / email-enumeration
        # script would actually target, unlike ordinary browsing. See
        # accounts/throttles.py:AuthSensitiveRateThrottle and its
        # application on LoginView/RegisterView/PasswordResetRequestView/
        # PasswordResetConfirmView in accounts/views.py.
        "auth_sensitive": "10/min",
        # 3 OTP requests per phone number per 10 minutes — hard,
        # DRF-level cap independent of the OTP service's own ~60s
        # per-(phone, purpose) resend cooldown (Task 2.1.2.2), to stop
        # SMS-bombing abuse (many purposes, or simply waiting out the
        # service cooldown repeatedly). See accounts/throttles.py.
        "otp_request": "3/10min",
    },
}


# ─── SimpleJWT ────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}


# ─── Redis DB Allocation ───────────────────────────────────────────────────────
# This project uses a SINGLE Redis instance for multiple purposes.
# Each subsystem MUST use a distinct logical DB index to avoid key
# collisions between unrelated systems:
#   DB 0 — Django Channels (chat/notifications WebSocket layer)
#   DB 1 — Celery broker/result backend (this task — now landed)
#   DB 2 — Django cache framework (general-purpose, disposable entries —
#          category/product-list caching, Tasks 21.1.1.2/21.1.1.3)
#   DB 3 — Django sessions — deliberately SEPARATE from DB 2:
#          sessions need to persist reliably for their configured
#          lifetime, while the general cache's entries are disposable
#          by design. Mixing them in one DB risks eviction under memory
#          pressure hitting the wrong kind of data. A separate DB index
#          also gives clean operational visibility (redis-cli -n 3 KEYS
#          "*" shows ONLY session data).
REDIS_DB_CHANNELS = config("REDIS_DB_CHANNELS", default=0, cast=int)
REDIS_DB_CACHE = config("REDIS_DB_CACHE", default=2, cast=int)
REDIS_DB_SESSIONS = config("REDIS_DB_SESSIONS", default=3, cast=int)


# ─── Django Channels / Redis ──────────────────────────────────────────────────
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [
                {
                    # NOTE: channels_redis 4.3.0's decode_hosts() treats an
                    # "address" key as a connection URL string, not a
                    # (host, port) tuple. Passing host/port/db as separate
                    # dict keys (rather than an "address" tuple) is the
                    # verified-correct way to set an explicit db index on
                    # this installed version.
                    "host": config("REDIS_HOST", default="127.0.0.1"),
                    "port": int(config("REDIS_PORT", default=6379)),
                    "db": REDIS_DB_CHANNELS,  # explicit, matching the documented allocation scheme above
                }
            ],
            "capacity": 1500,
            "expiry": 10,
        },
    }
}


# ─── Cache (Redis) ──────────────────────────────────────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{config('REDIS_HOST', default='127.0.0.1')}:{config('REDIS_PORT', default=6379)}/{REDIS_DB_CACHE}",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "chiz",  # namespace cache keys, in case this Redis instance is ever shared with another project/environment
        "TIMEOUT": 300,  # sensible default TTL (5 min) for any cache.set() call that doesn't specify its own explicit timeout
    },
    "sessions": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{config('REDIS_HOST', default='127.0.0.1')}:{config('REDIS_PORT', default=6379)}/{REDIS_DB_SESSIONS}",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "chiz_session",
        # No blanket TIMEOUT override here — session expiry is governed
        # by SESSION_COOKIE_AGE below, not this cache backend's generic
        # default timeout.
    },
}


# ─── Sessions ───────────────────────────────────────────────────────────────────
# cached_db (not the pure "cache" backend) deliberately: sessions were
# ALREADY exclusively database-backed before this task (SESSION_ENGINE was
# unset everywhere, so Django used its db-backed default), so moving to
# cached_db is a pure improvement — Redis becomes a fast read-through
# layer in front of the existing sessions table, and a Redis restart or
# eviction can never silently log out an active session, since the DB
# row is still there as a fallback. The pure "cache" backend would have
# been faster but would regress reliability versus what this project had
# before. No new migration is needed either way — django.contrib.sessions
# and its table already exist and continue to be used as the fallback.
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_CACHE_ALIAS = "sessions"
# Confirmed no existing SESSION_COOKIE_AGE (or SESSION_ENGINE) anywhere in
# core/settings/*.py before adding this — production.py only sets
# SESSION_COOKIE_SECURE/HTTPONLY/SAMESITE, which don't conflict.
SESSION_COOKIE_AGE = config(
    "SESSION_COOKIE_AGE", default=1209600, cast=int
)  # 2 weeks (Django's own default)


# ─── Celery ─────────────────────────────────────────────────────────────────────
REDIS_DB_CELERY = config("REDIS_DB_CELERY", default=1, cast=int)
CELERY_BROKER_URL = f"redis://{config('REDIS_HOST', default='127.0.0.1')}:{config('REDIS_PORT', default=6379)}/{REDIS_DB_CELERY}"
CELERY_RESULT_BACKEND = CELERY_BROKER_URL  # same Redis instance/DB serves as both broker and result store — acceptable for this project's scale; revisit if result-storage volume ever becomes a real operational concern
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
# Reuses whatever TIME_ZONE is actually configured above (currently "UTC" —
# NOTE: no "Asia/Tehran" setting exists anywhere in this project despite the
# Iran-market regulatory-compliance settings further below; if that ever
# changes, CELERY_TIMEZONE tracks it automatically since it references the
# variable rather than a hardcoded string).
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers.DatabaseScheduler"


# ─── CORS ─────────────────────────────────────────────────────────────────────
# Override in environment-specific files as needed.
CORS_ALLOW_CREDENTIALS = True


# ─── OTP (phone-based login/registration) ──────────────────────────────────────
OTP_CODE_TTL_SECONDS = config("OTP_CODE_TTL_SECONDS", default=120, cast=int)
OTP_RESEND_COOLDOWN_SECONDS = config(
    "OTP_RESEND_COOLDOWN_SECONDS", default=60, cast=int
)
OTP_MAX_VERIFICATION_ATTEMPTS = config(
    "OTP_MAX_VERIFICATION_ATTEMPTS", default=5, cast=int
)


# ─── SMS provider (Feature 2.2.1) ───────────────────────────────────────────────
SMS_PROVIDER_CLASS = config(
    "SMS_PROVIDER_CLASS", default="accounts.sms.console.ConsoleSMSProvider"
)


# ─── Regulatory compliance (Iran cosmetics IRC registration) ───────────────────
# OFF by default: when True, a Product that HAS an irc_regulatory_code
# entered but hasn't been marked regulatory_verified fails full_clean().
# This deliberately does NOT make IRC codes mandatory for every
# product — see Product.clean() in shop/models.py for the exact scope.
REQUIRE_REGULATORY_VERIFICATION = config(
    "REQUIRE_REGULATORY_VERIFICATION", default=False, cast=bool
)
