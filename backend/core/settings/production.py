"""
core/settings/production.py
─────────────────────────────
Production overrides — HTTPS, SMTP email, strict security headers.

Usage:
    DJANGO_SETTINGS_MODULE=core.settings.production
"""

from decouple import config

from .base import *  # noqa: F401, F403

# ─── Core ─────────────────────────────────────────────────────────────────────
DEBUG = False

ALLOWED_HOSTS = config("ALLOWED_HOSTS").split(",")


# ─── CORS — production frontend origin only ───────────────────────────────────
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="https://yourdomain.com",
).split(",")


# ─── Email — SMTP via Gmail (or any provider) ─────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default=config("EMAIL_HOST_USER"))


# ─── Frontend URL ─────────────────────────────────────────────────────────────
FRONTEND_URL = config("FRONTEND_URL")


# ─── HTTP Security Headers ────────────────────────────────────────────────────
# These are safe to enable once your TLS cert is in place.
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# HSTS — tell browsers to always use HTTPS for this domain
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Misc headers
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

# Session & CSRF cookie hardening
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_HTTPONLY = False  # React needs to read the CSRF token
CSRF_COOKIE_SAMESITE = "Lax"
