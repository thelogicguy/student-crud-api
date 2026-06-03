.PHONY: help install run dev test test-cov \
        db-init db-migrate db-upgrade db-downgrade db-reset \
        lint clean \
        docker-build docker-build-dev docker-test docker-up docker-dev docker-down docker-logs docker-migrate \
        vagrant-up vagrant-provision vagrant-ssh vagrant-halt vagrant-destroy vagrant-status \
        prod-up prod-down prod-logs prod-status prod-migrate prod-restart prod-rebuild

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
	FLASK_ENV=development $(FLASK) run --host 0.0.0.0 --port $${PORT:-5000} --debug

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


# ─── Clean ────────────────────────────────────────────────────────────────────
clean:         ## Remove Python cache files and htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -type f -name "*.pyc" -delete
	rm -rf htmlcov .coverage .pytest_cache

# ─── Docker ───────────────────────────────────────────────────────────────────
docker-build:      ## Build the production Docker image
	docker build --target production -t student-api:latest .

docker-build-dev:  ## Build the development Docker image
	docker build --target development -t student-api:dev .

docker-test:       ## Run tests inside Docker (uses test stage)
	docker build --target test -t student-api:test .

docker-up:         ## Start Postgres + API (production) via Docker Compose
	docker compose up -d --build

docker-dev:        ## Start Postgres + API (development, hot-reload)
	docker compose --profile dev up -d --build api-dev db

docker-down:       ## Stop all Docker Compose services
	docker compose down

docker-logs:       ## Tail API logs
	docker compose logs -f api

docker-migrate:    ## Run DB migrations inside the running API container
	docker compose exec api flask db upgrade

# ─── Vagrant ──────────────────────────────────────────────────────────────────
vagrant-up:       ## Start the Vagrant VM and provision it (first run)
	vagrant up

vagrant-provision: ## Re-run the provisioning script on the VM
	vagrant provision

vagrant-ssh:      ## SSH into the Vagrant VM
	vagrant ssh

vagrant-halt:     ## Gracefully shut down the Vagrant VM
	vagrant halt

vagrant-destroy:  ## Destroy the Vagrant VM (removes everything)
	vagrant destroy -f

vagrant-status:   ## Show the current status of the Vagrant VM
	vagrant status

# ─── Production deployment (run inside the Vagrant VM) ───────────────────────
prod-up:          ## Start all production services (2 API + DB + Nginx)
	docker compose -f docker-compose.prod.yml up -d --scale api=2

prod-down:        ## Stop all production services
	docker compose -f docker-compose.prod.yml down

prod-logs:        ## Tail logs from all production services
	docker compose -f docker-compose.prod.yml logs -f

prod-status:      ## Show running production containers
	docker compose -f docker-compose.prod.yml ps

prod-migrate:     ## Run DB migrations in the production API container
	docker compose -f docker-compose.prod.yml exec api flask db upgrade

prod-restart:     ## Restart only the API containers (zero-downtime rolling)
	docker compose -f docker-compose.prod.yml up -d --scale api=2 --no-deps api

prod-rebuild:     ## Rebuild images and restart (e.g. after code change)
	docker compose -f docker-compose.prod.yml build api
	docker compose -f docker-compose.prod.yml up -d --scale api=2 --no-deps api