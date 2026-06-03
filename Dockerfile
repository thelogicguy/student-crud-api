# ──────────────────────────────────────────────────────────────────────────────
# ARGs declared before any FROM so they are available to all stages
# ──────────────────────────────────────────────────────────────────────────────
ARG PYTHON_VERSION=3.12
ARG ENVIRONMENT=production

# ──────────────────────────────────────────────────────────────────────────────
# STAGE 1 — python-base
# Single alias for the base image so every stage uses the exact same version.
# Update PYTHON_VERSION in one place → all stages follow.
# ──────────────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS python-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ──────────────────────────────────────────────────────────────────────────────
# STAGE 2 — builder
# Inherits from python-base. Installs ALL dependencies (including dev) into
# an isolated virtual environment so nothing leaks into the final image.
# ──────────────────────────────────────────────────────────────────────────────
FROM python-base AS builder

WORKDIR /build

# Install system build dependencies
# DL3008: apt versions deliberately unpinned — they track the slim base image and
# pinning exact strings breaks on every upstream base-image refresh.
# DL3005: apt-get upgrade is intentional — it pulls Debian security patches into
# the slim base layer so the Trivy image gate doesn't fail on fixable OS CVEs.
# hadolint ignore=DL3008,DL3005
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install dependencies first (better layer caching —
# requirements.txt changes far less often than source code)
COPY requirements.txt .
# DL3013: application packages are fully pinned in requirements.txt; only pip
# itself is upgraded here, which we intentionally leave unpinned.
# hadolint ignore=DL3013
RUN pip install --upgrade pip && pip install -r requirements.txt

# ──────────────────────────────────────────────────────────────────────────────
# STAGE 3 — production
# Minimal image: inherits from python-base (NOT builder), copies only the
# pre-built venv and the application source. No build tools, no cache.
# ──────────────────────────────────────────────────────────────────────────────
FROM python-base AS production

WORKDIR /app

# Install only the runtime system library (not the dev headers)
# DL3005: apt-get upgrade applies Debian security patches to the runtime layer —
# this is the layer that actually ships, so it's where the OS CVE fixes must land.
# hadolint ignore=DL3008,DL3005
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy the fully-built venv from builder — avoids recompiling anything
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source
COPY . .

# Run as a non-root user for security
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser

EXPOSE 8000

# Liveness/readiness probe. The slim base has no curl, so use the stdlib —
# urlopen raises on any non-2xx (e.g. the /healthcheck 503 when the DB is down),
# which marks the container unhealthy. Satisfies Checkov CKV_DOCKER_2 / Trivy DS026.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthcheck', timeout=3)" || exit 1

CMD ["gunicorn", "run:app", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--log-level", "info", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]

# ──────────────────────────────────────────────────────────────────────────────
# STAGE 4 — test
# Inherits from builder (has all deps). Copies the production image contents
# so we test exactly what ships — then runs pytest.
# ──────────────────────────────────────────────────────────────────────────────
FROM builder AS test

WORKDIR /app

COPY --from=production /app .
ENV PATH="/opt/venv/bin:$PATH" \
    FLASK_ENV=testing \
    DATABASE_URL=sqlite:///:memory:

RUN pytest tests/ -v --tb=short

# ──────────────────────────────────────────────────────────────────────────────
# STAGE 5 — development
# Inherits from builder (full deps). Copies the production image contents so
# dev always runs the same code that will be released. Adds a shell + hot-reload.
# ──────────────────────────────────────────────────────────────────────────────
FROM builder AS development

WORKDIR /app

COPY --from=production /app .
ENV PATH="/opt/venv/bin:$PATH" \
    FLASK_ENV=development \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["flask", "run", "--host", "0.0.0.0", "--port", "8000", "--debug"]

# ──────────────────────────────────────────────────────────────────────────────
# Default target — production (must be last)
# Building without --target produces the minimal production image.
# ──────────────────────────────────────────────────────────────────────────────
FROM production