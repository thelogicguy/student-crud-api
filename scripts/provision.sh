#!/usr/bin/env bash
# scripts/provision.sh — sets up the Vagrant VM as a production environment.
# Each concern is isolated into its own function: readable, testable, idempotent.

set -euo pipefail
IFS=$'\n\t'

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()     { echo -e "${GREEN}[provision] $*${NC}"; }
warn()    { echo -e "${YELLOW}[provision] WARNING: $*${NC}"; }
error()   { echo -e "${RED}[provision] ERROR: $*${NC}" >&2; exit 1; }
section() { echo -e "\n${GREEN}════════════════════════════════════════${NC}"; log "$*"; }

# ── Guard: only run on Ubuntu/Debian ─────────────────────────────────────────
check_os() {
  section "Checking OS"
  grep -qi "ubuntu\|debian" /etc/os-release 2>/dev/null \
    || error "This script requires Ubuntu or Debian."
  log "OS: $(grep PRETTY_NAME /etc/os-release | cut -d= -f2 | tr -d '"')"
}

# ── System update ─────────────────────────────────────────────────────────────
update_system() {
  section "Updating system packages"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get upgrade -y -qq
  log "System updated"
}

# ── Core utilities ────────────────────────────────────────────────────────────
install_utilities() {
  section "Installing core utilities"
  apt-get install -y -qq \
    curl wget git make ca-certificates gnupg \
    lsb-release apt-transport-https \
    software-properties-common unzip jq
  log "Utilities installed"
}

# ── Docker Engine (from Docker's official APT repo, not the distro snap) ──────
install_docker() {
  section "Installing Docker Engine"

  if command -v docker &>/dev/null; then
    log "Docker already installed: $(docker --version)"
    return 0
  fi

  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg

  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
    | tee /etc/apt/sources.list.d/docker.list > /dev/null

  apt-get update -qq
  apt-get install -y -qq \
    docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin

  systemctl enable docker
  systemctl start docker
  log "Docker installed: $(docker --version)"
}

# ── Docker Compose V2 + legacy shim ───────────────────────────────────────────
install_docker_compose() {
  section "Verifying Docker Compose"

  docker compose version &>/dev/null \
    || error "Docker Compose V2 plugin not found. Re-run install_docker."

  if ! command -v docker-compose &>/dev/null; then
    cat > /usr/local/bin/docker-compose << 'EOF'
#!/bin/sh
exec docker compose "$@"
EOF
    chmod +x /usr/local/bin/docker-compose
    log "docker-compose shim created"
  fi
  log "Docker Compose: $(docker compose version)"
}

# ── Add vagrant user to docker group ─────────────────────────────────────────
configure_docker_user() {
  section "Configuring docker group"
  if ! id -nG vagrant | grep -qw docker; then
    usermod -aG docker vagrant
    log "vagrant added to docker group"
  else
    log "vagrant already in docker group"
  fi
}

# ── Environment file ──────────────────────────────────────────────────────────
setup_env_file() {
  section "Setting up .env"
  local env_file="/vagrant/.env"

  if [[ -f "$env_file" ]]; then
    log ".env already exists — skipping"
    return 0
  fi

  [[ -f "/vagrant/.env.example" ]] || error ".env.example not found"

  cp /vagrant/.env.example "$env_file"
  sed -i "s|DATABASE_URL=.*|DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/student_db|g" "$env_file"
  sed -i "s|FLASK_ENV=.*|FLASK_ENV=production|g" "$env_file"
  sed -i "s|PORT=.*|PORT=8000|g" "$env_file"
  log ".env created"
}

# ── Deploy: build → start → migrate ──────────────────────────────────────────
deploy_application() {
  section "Deploying application"
  cd /vagrant

  log "Building Docker images..."
  make docker-build

  log "Starting services with 2 API replicas..."
  docker compose -f docker-compose.prod.yml up -d --scale api=2

  log "Waiting for PostgreSQL..."
  local retries=30
  until docker compose -f docker-compose.prod.yml exec -T db \
      pg_isready -U postgres -d student_db &>/dev/null; do
    retries=$((retries - 1))
    [[ $retries -le 0 ]] && error "Database did not become ready."
    log "  Waiting... ($retries left)"
    sleep 2
  done

  log "Running migrations..."
  docker compose -f docker-compose.prod.yml exec -T api flask db upgrade
  log "Application deployed"
}

# ── Smoke test ────────────────────────────────────────────────────────────────
smoke_test() {
  section "Smoke test"
  local retries=15

  until curl -sf http://localhost/healthcheck &>/dev/null; do
    retries=$((retries - 1))
    if [[ $retries -le 0 ]]; then
      warn "Healthcheck not yet responding — check logs with: make docker-logs"
      return 0
    fi
    log "Waiting for API... ($retries left)"; sleep 3
  done

  local status
  status=$(curl -s http://localhost/healthcheck | jq -r '.status' 2>/dev/null || echo "unknown")
  log "Healthcheck: status=$status — PASSED"
}

# ── Summary ───────────────────────────────────────────────────────────────────
print_summary() {
  section "Provisioning complete"
  docker compose -f /vagrant/docker-compose.prod.yml ps 2>/dev/null || true
  echo ""
  log "API  : http://localhost:8080/api/v1/students  (from your laptop)"
  log "Health: http://localhost:8080/healthcheck"
}

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
  check_os
  update_system
  install_utilities
  install_docker
  install_docker_compose
  configure_docker_user
  setup_env_file
  deploy_application
  smoke_test
  print_summary
}

main "$@"