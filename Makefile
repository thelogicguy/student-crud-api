.PHONY: help install run dev test test-cov \
        db-init db-migrate db-upgrade db-downgrade db-reset \
        lint clean docker-up docker-down

PYTHON     := python3
PIP        := $(PYTHON) -m pip
FLASK      := flask
PYTEST     := pytest
APP_MODULE := run:app

# ─── Help ─────────────────────────────────────────────────────────────────────
help:          ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Setup ────────────────────────────────────────────────────────────────────
install:       ## Install Python dependencies
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

env:           ## Copy .env.example to .env (skips if .env exists)
	@test -f .env || (cp .env.example .env && echo ".env created from .env.example")

# ─── Run ──────────────────────────────────────────────────────────────────────
run:           ## Start the API server with Gunicorn (production-like)
	gunicorn $(APP_MODULE) \
	  --bind 0.0.0.0:$$PORT \
	  --workers 2 \
	  --log-level info \
	  --access-logfile -

dev:           ## Start the API server in Flask dev mode (hot-reload)
	FLASK_ENV=development $(FLASK) run --host 0.0.0.0 --port $${PORT:-8000} --debug

# ─── Database Migrations ──────────────────────────────────────────────────────
db-init:       ## Initialise Flask-Migrate (first time only)
	$(FLASK) db init

db-migrate:    ## Auto-generate a new migration script
	$(FLASK) db migrate -m "$(msg)"

db-upgrade:    ## Apply all pending migrations
	$(FLASK) db upgrade

db-downgrade:  ## Revert the last migration
	$(FLASK) db downgrade

db-reset:      ## ⚠ Drop all tables and re-apply migrations (destructive!)
	$(FLASK) db downgrade base
	$(FLASK) db upgrade

# ─── Testing ──────────────────────────────────────────────────────────────────
test:          ## Run all unit tests
	$(PYTEST) tests/ -v

test-cov:      ## Run tests with coverage report
	$(PYTEST) tests/ -v \
	  --cov=app \
	  --cov-report=term-missing \
	  --cov-report=html:htmlcov

# ─── Lint ─────────────────────────────────────────────────────────────────────
lint:          ## Run flake8 linter
	$(PYTHON) -m flake8 app/ tests/ --max-line-length=100

# ─── Docker ───────────────────────────────────────────────────────────────────
docker-up:     ## Start Postgres via Docker Compose
	docker compose up -d

docker-down:   ## Stop Docker Compose services
	docker compose down

# ─── Clean ────────────────────────────────────────────────────────────────────
clean:         ## Remove Python cache files and htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -type f -name "*.pyc" -delete
	rm -rf htmlcov .coverage .pytest_cache
