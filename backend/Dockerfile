# ─── backend/Dockerfile ───────────────────────────────────────────────────────
# Multi-stage build: base → development | production
#
# Build args are used ONLY in the production stage to run collectstatic
# without a real database. They are not baked into the final image —
# runtime config still comes from the .env file / environment.

# ─── Stage 1: base — shared OS packages + Python deps ────────────────────────
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System libraries for WeasyPrint (PDF invoices, Task 8.1.2.1). A pip install
# alone is NOT enough: WeasyPrint loads Pango/HarfBuzz through the OS at
# runtime. Current WeasyPrint (>= 53) no longer needs cairo or gdk-pixbuf;
# only Pango, HarfBuzz-subset and a font are required.
#   fonts-dejavu-core: python:3.11-slim ships NO fonts, so without one the PDF
#   text would render blank. DejaVu Sans also covers Arabic-script glyphs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz-subset0 \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip config --user set global.index https://mirror-pypi.runflare.com/simple \
    && pip config --user set global.index-url https://mirror-pypi.runflare.com/simple \
    && pip config --user set global.trusted-host repo.hmirror.ir \
    && pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .

# ─── Stage 2: development — Django dev server (hot reload via volume mount) ───
FROM base AS development

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# ─── Stage 3: production — Daphne ASGI (HTTP + WebSocket) ────────────────────
FROM base AS production

# Build-time args so collectstatic can run without a live DB / env file.
# These are ONLY used during the Docker build — runtime values override them.
ARG DJANGO_SETTINGS_MODULE=core.settings.production
ARG SECRET_KEY=build-time-placeholder
ARG DATABASE_NAME=placeholder
ARG DATABASE_USER=placeholder
ARG DATABASE_PASSWORD=placeholder
ARG DATABASE_HOST=placeholder
ARG DATABASE_PORT=5432

ENV DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE} \
    SECRET_KEY=${SECRET_KEY} \
    DATABASE_NAME=${DATABASE_NAME} \
    DATABASE_USER=${DATABASE_USER} \
    DATABASE_PASSWORD=${DATABASE_PASSWORD} \
    DATABASE_HOST=${DATABASE_HOST} \
    DATABASE_PORT=${DATABASE_PORT}

EXPOSE 8000
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "core.asgi:application"]
