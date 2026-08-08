"""
core/settings/development.py
─────────────────────────────
Development overrides — hot reload, verbose errors, console email.

Usage:
    DJANGO_SETTINGS_MODULE=core.settings.development
"""

from decouple import config

from .base import *  # noqa: F401, F403

# ─── Core ─────────────────────────────────────────────────────────────────────
DEBUG = True

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="localhost,127.0.0.1,0.0.0.0",
).split(",")


# ─── CORS — allow Vite dev server ─────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]


# ─── Email — print to console instead of sending ──────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


# ─── Frontend URL (used in email templates etc.) ──────────────────────────────
FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:3000")


# ─── Django Extensions (optional — install only if present) ───────────────────
# Uncomment if you add django-extensions to requirements.txt
# INSTALLED_APPS += ["django_extensions"]
