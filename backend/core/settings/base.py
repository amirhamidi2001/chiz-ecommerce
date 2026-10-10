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
    "payments.apps.PaymentsConfig",
    "shipping.apps.ShippingConfig",
    "promotions.apps.PromotionsConfig",
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


# ─── Payment gateways (Feature 6.1.1) ───────────────────────────────────────────
# Unlike SMS_PROVIDER_CLASS above (a single active provider), gateways are
# looked up by name since Phase 6.3 supports multiple simultaneously-available
# gateways with admin-configurable selection/fallback.
DEFAULT_PAYMENT_GATEWAY = config("DEFAULT_PAYMENT_GATEWAY", default="zarinpal")
PAYMENT_GATEWAY_CLASSES = {
    "zarinpal": "payments.gateways.zarinpal.ZarinPalGateway",
    "zibal": "payments.gateways.zibal.ZibalGateway",
    "idpay": "payments.gateways.idpay.IDPayGateway",
}

# ZarinPal credentials/mode (Task 6.2.1.1). ZARINPAL_SANDBOX defaults to True so
# a fresh checkout (dev/CI, no .env override) never accidentally talks to the
# live gateway with real money before a merchant ID has been configured.
ZARINPAL_MERCHANT_ID = config("ZARINPAL_MERCHANT_ID", default="")
ZARINPAL_SANDBOX = config("ZARINPAL_SANDBOX", default=True, cast=bool)

# Zibal credentials (Task 6.3.1.1). Unlike ZarinPal, Zibal has no separate
# sandbox subdomain/URL set — request/verify/start all use the same production
# host (gateway.zibal.ir) regardless of mode. Zibal's own documented sandbox
# mechanism is a special, literal merchant value: setting
# ZIBAL_MERCHANT_ID=zibal (the literal string "zibal", not a real merchant ID)
# makes the gateway itself operate in test mode against those same URLs —
# confirmed against Zibal's official Node.js SDK
# (https://github.com/zibalco/gateway-nodejs) and cross-checked against
# several independent third-party client libraries. So there's deliberately
# no ZIBAL_SANDBOX boolean here to mirror ZARINPAL_SANDBOX — that would imply
# a URL-switching mechanism Zibal doesn't have. The safe default is still the
# empty string: an unconfigured merchant ID fails at actual payment-attempt
# time via ZibalGateway.request_payment()'s existing error handling, not at
# import/startup time, and never accidentally reaches a real Zibal merchant
# account.
ZIBAL_MERCHANT_ID = config("ZIBAL_MERCHANT_ID", default="")

# IDPay credentials/mode (Task 6.3.1.2). Unlike ZarinPal (separate sandbox
# subdomain) and Zibal (special literal merchant value), IDPay's sandbox
# mechanism is a genuine settings toggle — it's just sent as an HTTP header
# (X-SANDBOX) on every request rather than encoded in the URL or merchant
# field. Confirmed against IDPay's own official documentation
# (https://idpay.ir/web-service/v1.1/). Safe default is True (sandbox mode)
# for the same reason as ZARINPAL_SANDBOX: a fresh checkout/CI environment
# with no .env override should never accidentally reach IDPay's production
# API before an API key has been configured.
IDPAY_API_KEY = config("IDPAY_API_KEY", default="")
IDPAY_SANDBOX = config("IDPAY_SANDBOX", default=True, cast=bool)

# Payment reconciliation (Task 6.5.1.1). How long a PaymentTransaction can
# sit PENDING before the periodic reconcile_stuck_payment_transactions
# Celery task actively re-verifies it against its gateway — covers the
# customer-abandoned-the-gateway-page case that PaymentCallbackView alone
# can never catch (nothing ever calls that view if the gateway never
# redirects back).
PAYMENT_RECONCILIATION_THRESHOLD_MINUTES = config(
    "PAYMENT_RECONCILIATION_THRESHOLD_MINUTES", default=30, cast=int
)


# ─── Carrier providers (Feature 7.1.1) ──────────────────────────────────────────
# Mirrors PAYMENT_GATEWAY_CLASSES exactly, one layer over in the shipping
# domain: carriers are looked up by code (matching ShippingCarrier.Code —
# "post", "tipax", "snapbox", "alopeyk") rather than a single active
# provider, since multiple carriers are simultaneously available and the
# one to use is resolved per-order from the customer's selection.
CARRIER_PROVIDER_CLASSES = {
    "post": "shipping.providers.post.PostCarrierProvider",
    "tipax": "shipping.providers.tipax.TipaxCarrierProvider",
    "snapbox": "shipping.providers.snapbox.SnapBoxCarrierProvider",
    "alopeyk": "shipping.providers.alopeyk.AloPeykCarrierProvider",
}

# Iran Post credentials (Task 7.2.1.2). Confirmed against post.ir's own
# "e-bazaar" (ای‌بازار) business/organizational panel documentation and
# independent tracking-aggregator sources (e.g. 17TRACK, which explicitly
# notes Iran Post's official public tracking API is unconfirmed): Iran Post
# has NO publicly documented, self-service REST/SOAP API for rate quoting,
# shipment creation, or tracking. Structured business access (bulk pickup,
# booking) instead requires signing a direct contract ("عقد قرارداد
# مستقیم") through their e-bazaar panel — an account relationship, not a
# self-service API-key signup. There is deliberately no "sandbox" toggle
# here (unlike ZARINPAL_SANDBOX/IDPAY_SANDBOX above) because no live API
# call is made anywhere in this integration — see
# shipping/providers/post.py's module docstring for the full research
# behind that. IRAN_POST_ACCOUNT_NUMBER is a forward-looking placeholder
# for the account/contract identifier Iran Post would issue if/when such a
# business contract is signed and grants real API access; it is currently
# unused by any code path.
IRAN_POST_ACCOUNT_NUMBER = config("IRAN_POST_ACCOUNT_NUMBER", default="")

# Tipax credentials (Task 7.2.1.3). Verified against Tipax's own public
# presence (tipaxco.com) and its "eTipax" business platform
# (etipaxco.com): despite this integration's initial assumption that
# Tipax — being a more modern private courier — might expose a
# documented, self-service developer API, no such API was found. eTipax
# is a login-based WEB PORTAL for businesses (order registration,
# door-to-door pickup, tracking, reporting), not a documented REST/SOAP
# API with API keys — structurally the same shape as Iran Post's
# e-bazaar panel (see IRAN_POST_ACCOUNT_NUMBER above), not the
# ZarinPal/Zibal/IDPay-style merchant API this task's context suggested
# might exist here. See shipping/providers/tipax.py's module docstring
# for the full research behind this. As with Iran Post, there is
# deliberately no "sandbox" toggle here because no live API call is made
# anywhere in this integration. TIPAX_ACCOUNT_USERNAME/
# TIPAX_ACCOUNT_PASSWORD are forward-looking placeholders for eTipax
# business-portal login credentials, should a documented API ever become
# available under that account; both are currently unused by any code
# path.
TIPAX_ACCOUNT_USERNAME = config("TIPAX_ACCOUNT_USERNAME", default="")
TIPAX_ACCOUNT_PASSWORD = config("TIPAX_ACCOUNT_PASSWORD", default="")

# SnapBox credentials/config (Task 7.2.1.4). Unlike Iran Post/Tipax above,
# SnapBox DOES publish a real, documented merchant API (OpenAPI spec bundled
# with its official SDK; production https://customer.snapp-box.com, staging
# https://customer-stg.snapp-box.com). It is an on-demand bike/van courier
# (not a locker/pickup-point service, contrary to this task's initial
# assumption) that addresses every stop by latitude/longitude — see
# shipping/providers/snapbox.py's module docstring for the full findings and
# the unverified points to smoke-test against a staging token before
# activating this carrier.
#
# SNAPBOX_API_KEY is the customer token sent in the `Authorization` header.
# SNAPBOX_SANDBOX selects the staging host and defaults to True, for the same
# reason as ZARINPAL_SANDBOX/IDPAY_SANDBOX: a fresh checkout/CI environment
# must never hit production by accident.
SNAPBOX_API_KEY = config("SNAPBOX_API_KEY", default="")
SNAPBOX_SANDBOX = config("SNAPBOX_SANDBOX", default=True, cast=bool)
# One of SnapBox's documented delivery categories: "bike", "bike-without-box",
# "van", "van-heavy". Pricing depends on this, NOT on package weight.
SNAPBOX_DEFAULT_DELIVERY_CATEGORY = config(
    "SNAPBOX_DEFAULT_DELIVERY_CATEGORY", default="bike"
)
# Sent as `customerWalletType` on pricing requests; "SNAPP_BOX" is the value
# used in SnapBox's own documented example.
SNAPBOX_CUSTOMER_WALLET_TYPE = config(
    "SNAPBOX_CUSTOMER_WALLET_TYPE", default="SNAPP_BOX"
)
# The store's own pickup location. create_shipment(order, destination) has no
# origin parameter, so the pickup terminal must come from configuration.
# Latitude/longitude are kept as strings (python-decouple can't cast a None
# default to float) and parsed/validated by the provider; all default to
# empty, in which case SnapBox shipment creation fails with a clear message
# rather than sending a bogus pickup.
SNAPBOX_PICKUP_CITY = config("SNAPBOX_PICKUP_CITY", default="")
SNAPBOX_PICKUP_ADDRESS = config("SNAPBOX_PICKUP_ADDRESS", default="")
SNAPBOX_PICKUP_LATITUDE = config("SNAPBOX_PICKUP_LATITUDE", default="")
SNAPBOX_PICKUP_LONGITUDE = config("SNAPBOX_PICKUP_LONGITUDE", default="")
SNAPBOX_PICKUP_CONTACT_NAME = config("SNAPBOX_PICKUP_CONTACT_NAME", default="")
SNAPBOX_PICKUP_CONTACT_PHONE = config("SNAPBOX_PICKUP_CONTACT_PHONE", default="")

# AloPeyk credentials/config (Task 7.2.1.5). AloPeyk DOES publish a real
# RESTful merchant API (confirmed from AloPeyk's own official open-source
# SDKs — AloPeyk/AloPeyk-Api-PHP and AloPeyk/AloPeyk-Api-Laravel on GitHub,
# whose source was read directly, not just their README examples) — a
# static, long-lived JWT "ACCESS-TOKEN" issued by AloPeyk's sales team
# (alopeyk.com/contact?unit=sales), sent as `Authorization: Bearer <token>`
# on every request, no separate login/exchange step. See
# shipping/providers/alopeyk.py's module docstring for the full findings,
# including the confirmed served-city list (Tehran, Karaj, Mashhad, Shiraz —
# NOT the "Tehran, Mashhad, Isfahan" this task's own context speculated).
#
# ALOPEYK_API_BASE_URL exists (rather than a hardcoded host) because the
# SDK source shows the base URL is an explicitly configurable endpoint
# (Configs::ENDPOINTS, with 'production'/'sandbox'/'custom' entries) whose
# literal values live in a config file this research could not access —
# only the production API host could be independently confirmed (from a
# screenshot URL embedded in AloPeyk's own documented API response, see
# module docstring point 2). No sandbox host could be confirmed, so no
# ALOPEYK_SANDBOX toggle is offered here (unlike SNAPBOX_SANDBOX above) —
# get whichever URL(s) AloPeyk's sales contact actually provides and set
# this per-environment instead of assuming a guessed staging subdomain.
ALOPEYK_API_KEY = config("ALOPEYK_API_KEY", default="")
ALOPEYK_API_BASE_URL = config("ALOPEYK_API_BASE_URL", default="https://api.alopeyk.com")
# One of Configs::TRANSPORT_TYPES confirmed in the SDK's own examples:
# "motor_taxi", "car", "cargo_s", "cargo".
ALOPEYK_DEFAULT_TRANSPORT_TYPE = config(
    "ALOPEYK_DEFAULT_TRANSPORT_TYPE", default="motor_taxi"
)
# The store's own pickup location — create_shipment(order, destination) has
# no origin parameter, so it comes from configuration, mirroring
# SNAPBOX_PICKUP_* above. Latitude/longitude are kept as strings (decouple
# can't cast a None default to float) and parsed/validated by the provider.
ALOPEYK_PICKUP_LATITUDE = config("ALOPEYK_PICKUP_LATITUDE", default="")
ALOPEYK_PICKUP_LONGITUDE = config("ALOPEYK_PICKUP_LONGITUDE", default="")
ALOPEYK_PICKUP_CITY = config("ALOPEYK_PICKUP_CITY", default="")
ALOPEYK_PICKUP_CONTACT_NAME = config("ALOPEYK_PICKUP_CONTACT_NAME", default="")
ALOPEYK_PICKUP_CONTACT_PHONE = config("ALOPEYK_PICKUP_CONTACT_PHONE", default="")


# ─── Regulatory compliance (Iran cosmetics IRC registration) ───────────────────
# OFF by default: when True, a Product that HAS an irc_regulatory_code
# entered but hasn't been marked regulatory_verified fails full_clean().
# This deliberately does NOT make IRC codes mandatory for every
# product — see Product.clean() in shop/models.py for the exact scope.
REQUIRE_REGULATORY_VERIFICATION = config(
    "REQUIRE_REGULATORY_VERIFICATION", default=False, cast=bool
)
