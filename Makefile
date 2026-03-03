# ╔══════════════════════════════════════════════════════════════╗
# ║  TREVLIX – Makefile                                          ║
# ║  Verwendung: make <target>                                   ║
# ╚══════════════════════════════════════════════════════════════╝

.PHONY: help install dev docker-up docker-down docker-logs docker-build \
        test test-cov lint format clean backup keys

# Standardziel
.DEFAULT_GOAL := help

PYTHON  ?= python3
PIP     ?= pip3
VENV    ?= .venv
COMPOSE ?= docker compose

# ── Hilfe ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  TREVLIX – Verfügbare Targets"
	@echo "  ────────────────────────────────────────────────────────────"
	@echo "  make install      → Virtuelle Umgebung + Abhängigkeiten installieren"
	@echo "  make dev          → Bot direkt starten (ohne Docker)"
	@echo "  make docker-up    → Docker-Container starten"
	@echo "  make docker-down  → Docker-Container stoppen"
	@echo "  make docker-build → Docker-Image neu bauen"
	@echo "  make docker-logs  → Live-Logs der Container"
	@echo "  make test         → Tests ausführen"
	@echo "  make test-cov     → Tests mit Coverage-Report"
	@echo "  make lint         → Code-Qualität prüfen (ruff)"
	@echo "  make format       → Code formatieren (ruff format)"
	@echo "  make clean        → Temporäre Dateien löschen"
	@echo "  make keys         → Neue Sicherheitsschlüssel generieren"
	@echo "  make backup       → Datenbank-Backup erstellen"
	@echo ""

# ── Installation ───────────────────────────────────────────────────────────────
install:
	@echo "→ Erstelle virtuelle Umgebung..."
	$(PYTHON) -m venv $(VENV)
	@echo "→ Installiere Abhängigkeiten..."
	$(VENV)/bin/pip install --upgrade pip wheel
	$(VENV)/bin/pip install -r requirements.txt
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "⚠  .env aus .env.example erstellt – bitte Werte anpassen!"; \
	fi
	@echo "✓ Installation abgeschlossen"

# ── Entwicklung ────────────────────────────────────────────────────────────────
dev:
	@if [ ! -f .env ]; then echo "Fehler: .env fehlt! (cp .env.example .env)"; exit 1; fi
	$(VENV)/bin/python server.py

# ── Docker ─────────────────────────────────────────────────────────────────────
docker-up:
	@if [ ! -f .env ]; then echo "Fehler: .env fehlt! (cp .env.example .env)"; exit 1; fi
	$(COMPOSE) up -d
	@echo "✓ TREVLIX läuft auf http://localhost:$${PORT:-5000}"

docker-down:
	$(COMPOSE) down

docker-build:
	$(COMPOSE) build --no-cache

docker-logs:
	$(COMPOSE) logs -f trevlix

docker-prod:
	$(COMPOSE) --profile production up -d

docker-restart:
	$(COMPOSE) restart trevlix

# ── Tests ──────────────────────────────────────────────────────────────────────
test:
	$(VENV)/bin/pytest tests/ -v --tb=short

test-cov:
	$(VENV)/bin/pytest tests/ -v --cov=. --cov-report=term-missing --cov-report=html
	@echo "✓ Coverage-Report: htmlcov/index.html"

# ── Code-Qualität ──────────────────────────────────────────────────────────────
lint:
	@command -v ruff &>/dev/null || $(VENV)/bin/pip install --quiet ruff
	$(VENV)/bin/ruff check server.py ai_engine.py trevlix_i18n.py services/ tests/

format:
	@command -v ruff &>/dev/null || $(VENV)/bin/pip install --quiet ruff
	$(VENV)/bin/ruff format server.py ai_engine.py trevlix_i18n.py services/ tests/

# ── Sicherheit ─────────────────────────────────────────────────────────────────
keys:
	@echo ""
	@echo "  Neue Sicherheitsschlüssel für .env:"
	@echo "  ──────────────────────────────────────────────────────────"
	@echo -n "  DASHBOARD_SECRET = "; python3 -c "import secrets; print(secrets.token_hex(32))"
	@echo -n "  JWT_SECRET       = "; python3 -c "import secrets; print(secrets.token_hex(32))"
	@echo -n "  SECRET_KEY       = "; python3 -c "import secrets; print(secrets.token_hex(32))"
	@echo -n "  ENCRYPTION_KEY   = "; python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || python3 -c "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
	@echo ""

# ── Backup ─────────────────────────────────────────────────────────────────────
backup:
	@mkdir -p backups
	@TIMESTAMP=$$(date +%Y%m%d_%H%M%S); \
	docker exec trevlix_mysql mysqldump -u trevlix -p$${MYSQL_PASS} trevlix \
		> backups/trevlix_$${TIMESTAMP}.sql && \
	echo "✓ Backup: backups/trevlix_$${TIMESTAMP}.sql"

# ── Aufräumen ──────────────────────────────────────────────────────────────────
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name "*.pyo" -delete 2>/dev/null || true
	rm -rf .pytest_cache/ htmlcov/ .coverage coverage.xml 2>/dev/null || true
	@echo "✓ Bereinigt"
