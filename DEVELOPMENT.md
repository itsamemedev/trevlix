# Development Guide

Praktische Anleitung für lokale Entwicklung am TREVLIX-Projekt.
Für Architektur-Details siehe `docs/ARCHITECTURE.md` und `docs/MODULE_MAPPING.md`.
Für operative Spielregeln (Code-Style, Git-Workflow, Commit-Format) siehe `CLAUDE.md`.

---

## 1. Voraussetzungen

- Python **3.11+** (Minimum 3.9 funktioniert mit Einschränkungen bei Typ-Annotationen)
- MariaDB/MySQL 10.4+ (oder SQLite-Fallback für isolierte Tests)
- `git`, `make`, `curl`
- Optional: `ruff`, `pytest` (via `requirements-dev.txt` falls vorhanden, sonst direkt aus pip)
- Optional: lokales Ollama (`curl -fsSL https://ollama.com/install.sh | sh`) für KI-Tests

---

## 2. Erstes Setup

```bash
git clone https://github.com/itsamemedev/trevlix.git
cd trevlix

# Virtuelle Umgebung
python3 -m venv venv
source venv/bin/activate

# Abhängigkeiten
pip install --upgrade pip wheel setuptools
pip install -r requirements.txt

# Environment
cp .env.example .env
# → Pflichtwerte setzen: ADMIN_PASSWORD, JWT_SECRET, SECRET_KEY, ENCRYPTION_KEY,
#   MYSQL_*, EXCHANGE, API_KEY/SECRET (oder PAPER_TRADING=true)

# Secrets generieren (falls keine vorhanden):
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
python -c "import secrets; print('JWT_SECRET=' + secrets.token_hex(32))"
python -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"
```

Für lokales Testen ohne Exchange-Zugriff: `PAPER_TRADING=true` in `.env`.

---

## 3. Server starten

```bash
source venv/bin/activate
python server.py
```

Beim Start erscheint ein farbiges Banner mit System-, DB-, Security-,
Trading- und Integrations-Status, gefolgt von einer Ready-Summary
(Threads, DB-Ping, Ollama-Health, Bot-Loop-Status).

Dashboard: <http://localhost:5000> · REST-API: <http://localhost:5000/api/v1/>
· API-Docs (Swagger): <http://localhost:5000/api/v1/docs>

---

## 4. Tests & Linting

Das Projekt hat **500+ Tests**. Pflichtprogramm vor jedem Commit:

```bash
ruff check .               # Lint – muss grün sein
ruff format --check .      # Formatierung – muss grün sein
python3 -m pytest tests/ -q --tb=short   # Tests – alle grün
```

Einzelne Tests laufen lassen:
```bash
pytest tests/test_virginie.py -v
pytest tests/ -k "exchange" -v
```

Formatieren statt nur prüfen:
```bash
ruff format .
ruff check --fix .
```

---

## 5. Git-Workflow

- **Feature-Branch:** Name beginnt mit `claude/...` und spiegelt die Session-ID.
- **Commits:** Conventional-Commits-Stil – `feat(...)`, `fix(...)`, `refactor(...)`, `chore(...)`, `docs(...)`.
  Siehe `CLAUDE.md` für Session-Trailer.
- **Keine direkten Pushes auf `main`.** Immer über PR.
- **Push mit Tracking:** `git push -u origin <branch>`.
- **Niemals** `--no-verify` oder force-push auf `main`.

Beispiel-Commit:

```bash
git commit -m "$(cat <<'EOF'
feat(services): neues Grid-Trading-Modul

Kurzbeschreibung der Änderung und warum sie notwendig war.
EOF
)"
```

---

## 6. Pre-Commit-Checkliste

| ✓ | Check |
|---|-------|
| ☐ | `ruff check .` – 0 Fehler |
| ☐ | `ruff format --check .` – alle Dateien formatiert |
| ☐ | `pytest tests/ -q` – alle Tests grün |
| ☐ | Neue Features haben mindestens einen Test |
| ☐ | Neue DB-Tabellen in **beiden** Stellen: `server.py:_init_db_once()` und `docker/mysql-init.sql` |
| ☐ | Keine hardcoded Secrets, API-Keys oder Passwörter |
| ☐ | Keine Loop-Variable-Capture-Probleme (`lambda var=var: ...` statt `lambda: ...`) |
| ☐ | Keine bare `except:` – immer spezifisch |
| ☐ | Max. 100 Zeichen Zeilenbreite (wird von Ruff geprüft) |
| ☐ | Public Functions/Classes haben Docstrings + Type Hints |
| ☐ | Commit-Message erklärt das **Warum**, nicht nur das **Was** |

---

## 7. Typische Debug-Workflows

**Nur Backend lokal, kein MariaDB:**
- `MYSQL_HOST=localhost` und MariaDB via Docker (`docker run -d -p 3306:3306 -e MARIADB_ROOT_PASSWORD=... mariadb`).
- Alternativ: Tests nutzen SQLite-Fallback via `tests/conftest.py` – keine externe DB nötig.

**Live-Logs beobachten:**
```bash
tail -f logs/trevlix.log
# oder bei systemd-Install:
journalctl -u trevlix -f
```

**Bot stoppen (im dev ohne systemd):** `Ctrl+C` ist sauber – `lifecycle._graceful_shutdown`
beendet Healer, Cluster-Controller, DB-Pool und SocketIO-Loop.

**Failed Test isolieren:**
```bash
pytest tests/test_virginie.py::test_virginie_autonomy -v -s
```

**Neuen Endpunkt bauen:** Schema in `app/core/api_docs_schema.py` ergänzen,
Route (vorerst noch in `server.py`) registrieren, Test in `tests/` anlegen.
Für die geplante Blueprint-Migration siehe TODO.md.

**Ollama lokal anschließen:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:3b
# in .env:
LLM_ENDPOINT=http://127.0.0.1:11434/api/chat
LLM_MODEL=qwen2.5:3b
```

---

## 8. Struktur-Überblick

Eine Datei pro klar umrissene Aufgabe. Neue Logik gehört zuerst in
`services/` (stateless Kern), die Verdrahtung in `app/core/`. HTTP/SocketIO-
Handler bleiben in `server.py`, bis sie in Blueprints wandern. Siehe
`docs/MODULE_MAPPING.md` für die vollständige Modul-Liste.

**Wichtige Leitplanken (CLAUDE.md-Auszug):**
- Minimal Impact: Änderungen so klein wie möglich halten.
- Kein spekulatives Abstrahieren – Duplication > falsche Abstraktion.
- Änderungen, die Drittsysteme berühren (Push, PR, Externes API), nur mit explizitem User-OK.

---

## 9. Weitere Ressourcen

- `docs/ARCHITECTURE.md` – System-Schichten, Datenflüsse
- `docs/SERVICES.md` – Details zu einzelnen Services
- `docs/DATABASE.md` – Schema + Migrationen
- `docs/SECURITY.md` – Threat-Model und Härtung
- `docs/SETUP.md` – Produktive Installation
- `docs/TRADING.md` – Strategie- und Risk-Konzepte
- `docs/MODULE_MAPPING.md` – 1-Zeiler pro Python-Modul
- `tasks/lessons.md` – gelernte Lektionen aus vergangenen Sessions
