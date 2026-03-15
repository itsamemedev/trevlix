#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                                                                              ║
# ║  ████████╗██████╗ ███████╗██╗   ██╗██╗     ██╗██╗  ██╗                    ║
# ║     ██╔══╝██╔══██╗██╔════╝██║   ██║██║     ██║╚██╗██╔╝                    ║
# ║     ██║   ██████╔╝█████╗  ██║   ██║██║     ██║ ╚███╔╝                     ║
# ║     ██║   ██╔══██╗██╔══╝  ╚██╗ ██╔╝██║     ██║ ██╔██╗                     ║
# ║     ██║   ██║  ██║███████╗ ╚████╔╝ ███████╗██║██╔╝ ██╗                    ║
# ║     ╚═╝   ╚═╝  ╚═╝╚══════╝  ╚═══╝  ╚══════╝╚═╝╚═╝  ╚═╝                   ║
# ║                                                                              ║
# ║  Algorithmic Trading Intelligence  ·  Installer v2.0.0                      ║
# ║  Unterstützt: Ubuntu 18.04-24.04 · Debian 10-12                            ║
# ║  Start: sudo bash install.sh                                                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

set -euo pipefail

# ── Hilfe ──────────────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Verwendung: sudo bash install.sh [OPTIONEN]"
    echo ""
    echo "Optionen:"
    echo "  --help, -h       Diese Hilfe anzeigen"
    echo "  --no-tf          TensorFlow überspringen (kein LSTM)"
    echo "  --no-shap        SHAP überspringen"
    echo "  --yes, -y        Alle optionalen Pakete automatisch ablehnen"
    echo "  --dir DIR        Installationsverzeichnis (Standard: /opt/trevlix)"
    echo ""
    echo "Beispiel: sudo bash install.sh --no-tf --no-shap"
    exit 0
fi

# ── Flags ──────────────────────────────────────────────────────────────────────
SKIP_TF=false
SKIP_SHAP=false
AUTO_NO=false
CUSTOM_INSTALL_DIR=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-tf)   SKIP_TF=true; shift ;;
        --no-shap) SKIP_SHAP=true; shift ;;
        --yes|-y)  AUTO_NO=true; shift ;;
        --dir)
            if [[ -n "${2:-}" ]]; then
                CUSTOM_INSTALL_DIR="$2"
                shift 2
            else
                echo "FEHLER: --dir benötigt ein Argument" >&2
                exit 1
            fi
            ;;
        *) shift ;;
    esac
done

# ── Farben ─────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; RESET='\033[0m'
JADE='\033[38;5;47m'

# ── Konfiguration ──────────────────────────────────────────────────────────────
INSTALL_DIR="${CUSTOM_INSTALL_DIR:-/opt/trevlix}"
SERVICE_USER="trevlix"
SERVICE_NAME="trevlix"
PYTHON_MIN="3.9"
LOG_FILE="/tmp/trevlix_install_$(date +%Y%m%d_%H%M%S).log"
REPO_URL="https://github.com/DEIN_USER/trevlix"  # ← beim Release ersetzen

# Domain-Variablen (werden später gesetzt)
USE_DOMAIN=false
DOMAIN=""

# ── Logging ────────────────────────────────────────────────────────────────────
exec > >(tee -a "$LOG_FILE") 2>&1

log()  { echo -e "${JADE}[TREVLIX]${RESET} $*"; }
ok()   { echo -e "${GREEN}  ✓${RESET} $*"; }
warn() { echo -e "${YELLOW}  ⚠${RESET} $*"; }
err()  { echo -e "${RED}  ✗ FEHLER:${RESET} $*"; exit 1; }
step() { echo -e "\n${BOLD}${CYAN}━━ $* ━━${RESET}"; }

# ── Banner ─────────────────────────────────────────────────────────────────────
clear
echo -e "${JADE}"
cat << 'EOF'
  ████████╗██████╗ ███████╗██╗   ██╗██╗     ██╗██╗  ██╗
     ██╔══╝██╔══██╗██╔════╝██║   ██║██║     ██║╚██╗██╔╝
     ██║   ██████╔╝█████╗  ██║   ██║██║     ██║ ╚███╔╝
     ██║   ██╔══██╗██╔══╝  ╚██╗ ██╔╝██║     ██║ ██╔██╗
     ██║   ██║  ██║███████╗ ╚████╔╝ ███████╗██║██╔╝ ██╗
     ╚═╝   ╚═╝  ╚═╝╚══════╝  ╚═══╝  ╚══════╝╚═╝╚═╝  ╚═╝
EOF
echo -e "${RESET}"
echo -e "  ${DIM}Algorithmic Trading Intelligence · Installer v2.0.0${RESET}"
echo -e "  ${DIM}Log: ${LOG_FILE}${RESET}"
echo ""

# ── Cleanup-Trap bei Fehler ────────────────────────────────────────────────────
_CLEANUP_DONE=false
cleanup_on_error() {
    if [[ "$_CLEANUP_DONE" == "false" ]]; then
        echo -e "\n${RED}  ✗ Installation abgebrochen! Bereinige...${RESET}"
        systemctl stop "$SERVICE_NAME" 2>/dev/null || true
        systemctl disable "$SERVICE_NAME" 2>/dev/null || true
        rm -f "/etc/systemd/system/${SERVICE_NAME}.service" 2>/dev/null || true
        systemctl daemon-reload 2>/dev/null || true
        echo -e "${YELLOW}  ⚠ Installationslog: ${LOG_FILE}${RESET}"
        _CLEANUP_DONE=true
    fi
}
trap cleanup_on_error ERR

# ── Root check ─────────────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    err "Bitte als root ausführen: sudo bash install.sh"
fi

# ── Pre-flight checks ──────────────────────────────────────────────────────────
step "Systemanforderungen prüfen"

# Freier Speicher (min. 2 GB)
FREE_MB=$(df / | awk 'NR==2 {print int($4/1024)}')
if [[ $FREE_MB -lt 2048 ]]; then
    warn "Weniger als 2 GB freier Speicher (${FREE_MB} MB). Installation könnte fehlschlagen."
else
    ok "Freier Speicher: ${FREE_MB} MB"
fi

# RAM (min. 512 MB)
if [[ -f /proc/meminfo ]]; then
    TOTAL_RAM_MB=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
    if [[ $TOTAL_RAM_MB -lt 512 ]]; then
        warn "Weniger als 512 MB RAM (${TOTAL_RAM_MB} MB). KI-Training könnte langsam sein."
    else
        ok "RAM: ${TOTAL_RAM_MB} MB"
    fi
fi

# ── OS Detection ───────────────────────────────────────────────────────────────
step "Betriebssystem erkennen"

if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    OS_ID="${ID:-unknown}"
    OS_VER="${VERSION_ID:-0}"
    OS_CODENAME="${VERSION_CODENAME:-${UBUNTU_CODENAME:-}}"
elif [[ -f /etc/debian_version ]]; then
    OS_ID="debian"
    OS_VER=$(cut -d. -f1 < /etc/debian_version)
else
    err "Unbekanntes Betriebssystem. Nur Ubuntu/Debian wird unterstützt."
fi

log "Erkannt: ${OS_ID} ${OS_VER} (${OS_CODENAME:-})"

case "$OS_ID" in
    ubuntu)
        VER_MAJOR=$(echo "$OS_VER" | cut -d. -f1)
        if [[ $VER_MAJOR -lt 18 ]]; then
            err "Ubuntu ${OS_VER} wird nicht unterstützt. Minimum: Ubuntu 18.04"
        fi
        ok "Ubuntu ${OS_VER} wird unterstützt"
        PKG_MANAGER="apt-get"
        ;;
    debian)
        DEB_VER=$(echo "$OS_VER" | cut -d. -f1)
        if [[ $DEB_VER -lt 10 ]]; then
            err "Debian ${OS_VER} wird nicht unterstützt. Minimum: Debian 10"
        fi
        ok "Debian ${OS_VER} wird unterstützt"
        PKG_MANAGER="apt-get"
        ;;
    *)
        err "Nur Ubuntu und Debian werden unterstützt (erkannt: ${OS_ID})"
        ;;
esac

# ── Domain-Abfrage ────────────────────────────────────────────────────────────
step "Domain-Konfiguration"
echo ""
echo -e "${YELLOW}Soll Trevlix mit einer Domain verknüpft werden?${RESET}"
echo -e "${DIM}  Beispiele: example.com, app.example.com, trading.meinedomain.de${RESET}"
echo -e "${DIM}  Leer lassen = nur über IP:5000 erreichbar${RESET}"
echo ""
read -rp "$(echo -e "${CYAN}Domain (leer = keine): ${RESET}")" DOMAIN

if [[ -n "$DOMAIN" ]]; then
    # Domain-Format validieren
    if [[ "$DOMAIN" =~ ^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?\.[a-zA-Z]{2,}$ ]]; then
        USE_DOMAIN=true
        ok "Domain: ${DOMAIN}"
    else
        warn "Ungültiges Domain-Format: '${DOMAIN}' — fahre ohne Domain fort"
        DOMAIN=""
    fi
else
    ok "Keine Domain — Dashboard erreichbar über http://IP:5000"
fi

# ── System-Update ──────────────────────────────────────────────────────────────
step "System-Pakete aktualisieren"
export DEBIAN_FRONTEND=noninteractive
$PKG_MANAGER update -qq || warn "Update-Fehler (wird fortgesetzt)"
ok "Paketliste aktualisiert"

# ── Basis-Abhängigkeiten ───────────────────────────────────────────────────────
step "Basis-Abhängigkeiten installieren"
BASE_PKGS="curl wget git ca-certificates gnupg lsb-release software-properties-common \
           build-essential libssl-dev libffi-dev pkg-config \
           libmariadb-dev default-libmysqlclient-dev \
           libxml2-dev libxslt1-dev zlib1g-dev"

for pkg in $BASE_PKGS; do
    if ! dpkg -s "$pkg" &>/dev/null; then
        $PKG_MANAGER install -y -qq "$pkg" || warn "Konnte $pkg nicht installieren"
    fi
done
ok "Basis-Pakete installiert"

# ── Python Installation (OS-abhängig) ─────────────────────────────────────────
step "Python 3.11+ installieren"

install_python_modern() {
    # deadsnakes PPA für Ubuntu < 22
    if ! python3.11 --version &>/dev/null 2>&1; then
        log "Füge deadsnakes PPA hinzu..."
        $PKG_MANAGER install -y -qq python3-software-properties 2>/dev/null || true
        add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
        $PKG_MANAGER update -qq
        $PKG_MANAGER install -y -qq python3.11 python3.11-venv python3.11-dev python3.11-distutils 2>/dev/null || true
    fi
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11 - 2>/dev/null || true
}

detect_python() {
    for py in python3.11 python3.10 python3.9 python3; do
        if command -v "$py" &>/dev/null; then
            PY_VER=$($py -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
            PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
            PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
            if [[ $PY_MAJOR -ge 3 ]] && [[ $PY_MINOR -ge 9 ]]; then
                PYTHON_BIN="$py"
                ok "Python ${PY_VER} gefunden: $(command -v "$py")"
                return 0
            fi
        fi
    done
    return 1
}

if ! detect_python; then
    log "Python 3.9+ nicht gefunden — installiere Python 3.11..."
    $PKG_MANAGER install -y -qq python3.11 python3.11-venv python3.11-dev 2>/dev/null || \
    install_python_modern
    detect_python || err "Python 3.9+ konnte nicht installiert werden"
fi

# pip
if ! command -v pip3 &>/dev/null; then
    curl -sS https://bootstrap.pypa.io/get-pip.py | "$PYTHON_BIN" - --quiet
fi
ok "Python: $("$PYTHON_BIN" --version)"

# ── MariaDB Installation ─────────────────────────────────────────────────────
step "MariaDB installieren & konfigurieren"

install_mariadb() {
    if command -v mariadb &>/dev/null || command -v mysql &>/dev/null; then
        local db_version
        db_version=$(mariadb --version 2>/dev/null || mysql --version 2>/dev/null)
        ok "Datenbank bereits installiert: ${db_version}"
        return
    fi

    log "Installiere MariaDB Server..."
    if $PKG_MANAGER install -y -qq mariadb-server mariadb-client 2>/dev/null; then
        ok "MariaDB Server installiert"
    else
        err "MariaDB konnte nicht installiert werden. Bitte manuell installieren."
    fi
}

install_mariadb

# MariaDB starten & aktivieren
if command -v systemctl &>/dev/null; then
    systemctl enable mariadb 2>/dev/null || systemctl enable mysql 2>/dev/null || true
    systemctl start  mariadb 2>/dev/null || systemctl start  mysql 2>/dev/null || true
else
    service mariadb start 2>/dev/null || service mysql start 2>/dev/null || true
fi
ok "MariaDB läuft"

# ── System-Nutzer ──────────────────────────────────────────────────────────────
step "System-Nutzer einrichten"
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd --system --shell /bin/bash --home "$INSTALL_DIR" --create-home "$SERVICE_USER"
    ok "Nutzer '${SERVICE_USER}' erstellt"
else
    ok "Nutzer '${SERVICE_USER}' existiert bereits"
fi

# ── Installations-Verzeichnis ──────────────────────────────────────────────────
step "Bot-Dateien installieren"
mkdir -p "$INSTALL_DIR"/{backups,logs,static}
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

# Herunterladen oder kopieren
if [[ -f "./server.py" ]]; then
    log "Lokale Dateien erkannt — kopiere..."
    # Kopiere alle relevanten Dateien und Verzeichnisse
    for f in server.py ai_engine.py trevlix_i18n.py validate_env.py requirements.txt \
              trevlix_translations.js; do
        [[ -f "./$f" ]] && cp "./$f" "$INSTALL_DIR/$f" && ok "Kopiert: $f"
    done
    for d in routes services templates static docker tests; do
        if [[ -d "./$d" ]]; then
            cp -r "./$d" "$INSTALL_DIR/$d" && ok "Kopiert: $d/"
        fi
    done
elif command -v git &>/dev/null && [[ "$REPO_URL" != *"DEIN_USER"* ]]; then
    log "Klone Repository: $REPO_URL"
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR/src" 2>/dev/null || \
        warn "Git-Clone fehlgeschlagen — bitte Dateien manuell in $INSTALL_DIR ablegen"
else
    warn "Keine Quelldateien gefunden. Bitte server.py & Co. nach $INSTALL_DIR kopieren."
fi

# ── Python Virtual Environment ─────────────────────────────────────────────────
step "Python Virtual Environment erstellen"
VENV_DIR="$INSTALL_DIR/venv"

if [[ ! -d "$VENV_DIR" ]]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR" || err "venv-Erstellung fehlgeschlagen"
fi
ok "venv: $VENV_DIR"

VENV_PY="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

# pip upgrade
"$VENV_PIP" install --quiet --upgrade pip wheel setuptools

# ── Python-Pakete installieren ─────────────────────────────────────────────────
step "Python-Abhängigkeiten installieren"

CORE_PKGS=(
    "flask>=3.0.0"
    "flask-socketio>=5.3.6"
    "flask-cors>=4.0.0"
    "eventlet>=0.35.0"
    "ccxt>=4.2.0"
    "PyMySQL>=1.1.0"
    "cryptography>=41.0.0"
    "pandas>=2.1.0"
    "numpy>=1.26.0"
    "requests>=2.31.0"
    "scikit-learn>=1.3.0"
    "xgboost>=2.0.0"
    "ta>=0.11.0"
    "PyJWT>=2.8.0"
    "bcrypt>=4.1.0"
    "python-dotenv>=1.0.0"
)

if [[ -f "$INSTALL_DIR/requirements.txt" ]]; then
    "$VENV_PIP" install --quiet -r "$INSTALL_DIR/requirements.txt" && ok "requirements.txt installiert"
else
    for pkg in "${CORE_PKGS[@]}"; do
        "$VENV_PIP" install --quiet "$pkg" && ok "$pkg"
    done
fi

# TensorFlow optional
if [[ "$SKIP_TF" == "false" && "$AUTO_NO" == "false" ]]; then
    echo ""
    read -rp "$(echo -e "${YELLOW}TensorFlow installieren? (LSTM + Transformer-KI, ~1.5GB) [j/N]:${RESET} ")" TF_CHOICE
    [[ "${TF_CHOICE,,}" == "j" ]] && SKIP_TF=false || SKIP_TF=true
fi
if [[ "$SKIP_TF" == "false" ]]; then
    log "Installiere TensorFlow (dauert einige Minuten)..."
    "$VENV_PIP" install --quiet tensorflow && ok "TensorFlow installiert" || warn "TensorFlow fehlgeschlagen — KI läuft ohne LSTM"
else
    ok "TensorFlow übersprungen (--no-tf)"
fi

# SHAP optional
if [[ "$SKIP_SHAP" == "false" && "$AUTO_NO" == "false" ]]; then
    echo ""
    read -rp "$(echo -e "${YELLOW}SHAP installieren? (KI-Erklärungen, ~200MB) [j/N]:${RESET} ")" SHAP_CHOICE
    [[ "${SHAP_CHOICE,,}" == "j" ]] && SKIP_SHAP=false || SKIP_SHAP=true
fi
if [[ "$SKIP_SHAP" == "false" ]]; then
    "$VENV_PIP" install --quiet shap && ok "SHAP installiert" || warn "SHAP fehlgeschlagen"
else
    ok "SHAP übersprungen (--no-shap)"
fi

# ── Passwörter & Secrets generieren ────────────────────────────────────────────
step "Sichere Passwörter & Secrets generieren"

if command -v openssl &>/dev/null; then
    DB_PASS=$(openssl rand -base64 18 | tr -d '/+=' | head -c 24)
    DB_ROOT_PASS=$(openssl rand -base64 18 | tr -d '/+=' | head -c 24)
    ADMIN_PASS=$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)
    JWT_SECRET=$(openssl rand -hex 32)
    FLASK_SECRET=$(openssl rand -hex 32)
    DASH_SECRET=$(openssl rand -hex 32)
else
    DB_PASS="$(head -c 64 /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 24)"
    DB_ROOT_PASS="$(head -c 64 /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 24)"
    ADMIN_PASS="$(head -c 64 /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 20)"
    JWT_SECRET="$(head -c 128 /dev/urandom | tr -dc 'a-f0-9' | head -c 64)"
    FLASK_SECRET="$(head -c 128 /dev/urandom | tr -dc 'a-f0-9' | head -c 64)"
    DASH_SECRET="$(head -c 128 /dev/urandom | tr -dc 'a-f0-9' | head -c 64)"
fi

# Fernet-Key generieren (nach venv-Erstellung, cryptography ist jetzt verfügbar)
if "$VENV_PY" -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" &>/dev/null 2>&1; then
    ENCRYPTION_KEY=$("$VENV_PY" -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
elif command -v openssl &>/dev/null; then
    ENCRYPTION_KEY=$(openssl rand -base64 32)
else
    ENCRYPTION_KEY="$(head -c 64 /dev/urandom | base64 | head -c 44)"
fi
ok "Alle Secrets generiert"

# ── MariaDB Datenbank & Nutzer einrichten ──────────────────────────────────────
step "MariaDB Datenbank & Nutzer einrichten"

# Bestimme den MariaDB/MySQL Client-Befehl
DB_CLIENT="mariadb"
if ! command -v mariadb &>/dev/null; then
    DB_CLIENT="mysql"
fi

SQL_SETUP=$(cat <<SQLEOF
CREATE DATABASE IF NOT EXISTS trevlix
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'trevlix'@'localhost' IDENTIFIED BY '${DB_PASS}';
GRANT ALL PRIVILEGES ON trevlix.* TO 'trevlix'@'localhost';
FLUSH PRIVILEGES;
SQLEOF
)

if $DB_CLIENT -u root -e "$SQL_SETUP" 2>/dev/null; then
    ok "Datenbank 'trevlix' und Nutzer erstellt"
else
    warn "DB-Einrichtung fehlgeschlagen — bitte manuell ausführen: sudo $DB_CLIENT -u root"
fi

# Schema importieren, falls mysql-init.sql vorhanden
INIT_SQL=""
if [[ -f "$INSTALL_DIR/docker/mysql-init.sql" ]]; then
    INIT_SQL="$INSTALL_DIR/docker/mysql-init.sql"
elif [[ -f "./docker/mysql-init.sql" ]]; then
    INIT_SQL="./docker/mysql-init.sql"
fi

if [[ -n "$INIT_SQL" ]]; then
    if $DB_CLIENT -u trevlix -p"${DB_PASS}" trevlix < "$INIT_SQL" 2>/dev/null; then
        ok "Datenbank-Schema importiert"
    else
        warn "Schema-Import fehlgeschlagen — Tabellen werden beim ersten Start automatisch erstellt"
    fi
fi

# ── .env erstellen ─────────────────────────────────────────────────────────────
step ".env Konfigurationsdatei erstellen"

# ALLOWED_ORIGINS bestimmen
if [[ "$USE_DOMAIN" == "true" ]]; then
    ALLOWED_ORIGINS="https://${DOMAIN}"
else
    ALLOWED_ORIGINS="http://localhost:5000"
fi

if [[ ! -f "$INSTALL_DIR/.env" ]]; then
    cat > "$INSTALL_DIR/.env" << ENV_EOF
# TREVLIX v2.0.0 – Auto-generiert am $(date)
# Niemals in Git committen! (steht in .gitignore)

# ── Exchange (jetzt konfigurieren!) ──────────────────────────────
EXCHANGE=cryptocom
API_KEY=
API_SECRET=

# ── MariaDB (auto-generiert) ────────────────────────────────────
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=trevlix
MYSQL_PASS=${DB_PASS}
MYSQL_ROOT_PASS=${DB_ROOT_PASS}
MYSQL_DB=trevlix

# ── Sicherheit (auto-generiert) ─────────────────────────────────
ADMIN_PASSWORD=${ADMIN_PASS}
DASHBOARD_SECRET=${DASH_SECRET}
JWT_SECRET=${JWT_SECRET}
SECRET_KEY=${FLASK_SECRET}
ENCRYPTION_KEY=${ENCRYPTION_KEY}
SESSION_TIMEOUT_MIN=30
ALLOWED_ORIGINS=${ALLOWED_ORIGINS}

# ── Trading (Empfehlung: erst mit Paper-Trading starten!) ───────
PAPER_TRADING=true

# ── Registrierung ───────────────────────────────────────────────
ALLOW_REGISTRATION=false

# ── Features (optional) ─────────────────────────────────────────
DISCORD_WEBHOOK=
TELEGRAM_TOKEN=
TELEGRAM_CHAT_ID=
CRYPTOPANIC_TOKEN=
CRYPTOPANIC_API_PLAN=free
BLOCKNATIVE_KEY=
LLM_ENDPOINT=
LLM_API_KEY=

# ── Server ──────────────────────────────────────────────────────
PORT=5000
LANGUAGE=de
AUTO_START=true
LOG_LEVEL=INFO
JSON_LOGS=false
COLOR_LOGS=true
ENV_EOF
    chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/.env"
    chmod 600 "$INSTALL_DIR/.env"
    ok ".env erstellt (Passwörter auto-generiert)"
else
    ok ".env existiert bereits — wird nicht überschrieben"
fi

# ── .env.example aktualisieren ─────────────────────────────────────────────────
# Aktualisiere die .env.example mit den generierten DB-Credentials als Referenz
if [[ -f "$INSTALL_DIR/.env.example" ]]; then
    ok ".env.example vorhanden"
fi

# ── Systemd Service ────────────────────────────────────────────────────────────
step "Systemd Service einrichten"

cat > "/etc/systemd/system/${SERVICE_NAME}.service" << SERVICE_EOF
[Unit]
Description=TREVLIX Algorithmic Trading Bot
After=network.target mariadb.service
Wants=mariadb.service

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=${VENV_DIR}/bin/python server.py
Restart=always
RestartSec=10
StandardOutput=append:${INSTALL_DIR}/logs/trevlix.log
StandardError=append:${INSTALL_DIR}/logs/trevlix_error.log

# Sicherheit
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=${INSTALL_DIR}

[Install]
WantedBy=multi-user.target
SERVICE_EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
ok "Systemd Service eingerichtet"
ok "Bot startet automatisch nach Neustart"

# ── Berechtigungen ─────────────────────────────────────────────────────────────
step "Berechtigungen setzen"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
chmod 750 "$INSTALL_DIR"
chmod 600 "$INSTALL_DIR/.env"
ok "Berechtigungen gesetzt"

# ── Nginx + SSL (Domain-Setup) ─────────────────────────────────────────────────
if [[ "$USE_DOMAIN" == "true" ]]; then
    step "Nginx Reverse Proxy einrichten"

    # Nginx installieren
    if ! command -v nginx &>/dev/null; then
        $PKG_MANAGER install -y -qq nginx || err "Nginx konnte nicht installiert werden"
    fi
    ok "Nginx installiert"

    # Nginx-Konfiguration erstellen
    cat > "/etc/nginx/sites-available/trevlix" << NGINX_EOF
# TREVLIX – Nginx Reverse Proxy (auto-generiert)
# Domain: ${DOMAIN}

# Rate-Limiting
limit_req_zone \$binary_remote_addr zone=trevlix_login:10m rate=5r/m;
limit_req_zone \$binary_remote_addr zone=trevlix_api:10m rate=30r/s;

# Upstream
upstream trevlix_backend {
    server 127.0.0.1:5000;
    keepalive 32;
}

# HTTP → HTTPS Redirect (wird von Certbot angepasst)
server {
    listen 80;
    server_name ${DOMAIN};

    # Certbot ACME-Challenge
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

# HTTPS + WebSocket Proxy
server {
    listen 443 ssl http2;
    server_name ${DOMAIN};

    # SSL-Zertifikate (werden von Certbot eingefügt)
    ssl_certificate     /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers on;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;

    # Security Headers
    add_header X-Frame-Options       SAMEORIGIN always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection      "1; mode=block" always;
    add_header Referrer-Policy        "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy     "camera=(), microphone=(), geolocation=()" always;
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;

    # Allgemeine Proxy-Einstellungen
    proxy_set_header Host              \$host;
    proxy_set_header X-Real-IP         \$remote_addr;
    proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;

    proxy_buffer_size          128k;
    proxy_buffers              4 256k;
    proxy_busy_buffers_size    256k;

    # Login & Registrierung (Rate-Limited)
    location /login {
        limit_req zone=trevlix_login burst=3 nodelay;
        limit_req_status 429;
        proxy_pass         http://trevlix_backend;
        proxy_read_timeout 30s;
    }

    location /register {
        limit_req zone=trevlix_login burst=3 nodelay;
        limit_req_status 429;
        proxy_pass         http://trevlix_backend;
        proxy_read_timeout 30s;
    }

    # REST API
    location /api/ {
        limit_req zone=trevlix_api burst=50 nodelay;
        limit_req_status 429;
        proxy_pass         http://trevlix_backend;
        proxy_read_timeout 60s;
    }

    # WebSocket (Socket.IO)
    location /socket.io/ {
        proxy_pass         http://trevlix_backend;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade    \$http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    # Statische Assets (Cache)
    location /static/ {
        proxy_pass http://trevlix_backend;
        proxy_cache_valid 200 1h;
        add_header Cache-Control "public, max-age=3600";
    }

    # Alle anderen Routen
    location / {
        proxy_pass         http://trevlix_backend;
        proxy_read_timeout 120s;
    }

    # Fehler-Seiten
    error_page 502 503 504 /50x.html;
    location = /50x.html {
        root /usr/share/nginx/html;
        internal;
    }

    # Versteckte Dateien blockieren
    location ~ /\. {
        deny all;
        return 404;
    }
}
NGINX_EOF

    # Aktivieren & Default entfernen
    ln -sf /etc/nginx/sites-available/trevlix /etc/nginx/sites-enabled/trevlix
    rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
    ok "Nginx-Konfiguration erstellt für ${DOMAIN}"

    # ── Certbot SSL-Zertifikat ─────────────────────────────────────────────
    step "SSL-Zertifikat mit Let's Encrypt (Certbot)"

    # Certbot installieren
    if ! command -v certbot &>/dev/null; then
        $PKG_MANAGER install -y -qq certbot python3-certbot-nginx || \
            warn "Certbot konnte nicht installiert werden"
    fi

    if command -v certbot &>/dev/null; then
        log "Erstelle SSL-Zertifikat für ${DOMAIN}..."
        echo ""
        read -rp "$(echo -e "${CYAN}E-Mail für Let's Encrypt (für Erneuerungshinweise): ${RESET}")" LE_EMAIL

        if [[ -n "$LE_EMAIL" ]]; then
            # Temporäre Nginx-Config ohne SSL für Certbot
            cat > "/etc/nginx/sites-available/trevlix-temp" << TEMP_EOF
server {
    listen 80;
    server_name ${DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}
TEMP_EOF
            ln -sf /etc/nginx/sites-available/trevlix-temp /etc/nginx/sites-enabled/trevlix
            nginx -t 2>/dev/null && systemctl restart nginx 2>/dev/null || true

            if certbot certonly --nginx -d "$DOMAIN" --non-interactive \
                --agree-tos --email "$LE_EMAIL" --redirect 2>/dev/null; then
                ok "SSL-Zertifikat erstellt für ${DOMAIN}"

                # Jetzt die vollständige Nginx-Config aktivieren
                ln -sf /etc/nginx/sites-available/trevlix /etc/nginx/sites-enabled/trevlix
                rm -f /etc/nginx/sites-available/trevlix-temp

                # Certbot Auto-Renewal Timer prüfen
                if systemctl is-active --quiet certbot.timer 2>/dev/null; then
                    ok "Certbot Auto-Renewal aktiv"
                else
                    systemctl enable --now certbot.timer 2>/dev/null || true
                    ok "Certbot Auto-Renewal aktiviert"
                fi
            else
                warn "SSL-Zertifikat konnte nicht erstellt werden"
                warn "Stelle sicher, dass die Domain ${DOMAIN} auf diesen Server zeigt (DNS A-Record)"
                warn "Versuche es später manuell: sudo certbot --nginx -d ${DOMAIN}"
                # Temporäre Config behalten (funktioniert ohne SSL)
                ln -sf /etc/nginx/sites-available/trevlix-temp /etc/nginx/sites-enabled/trevlix
            fi
        else
            warn "Keine E-Mail angegeben — SSL-Zertifikat wird nicht erstellt"
            warn "Manuell nachholen: sudo certbot --nginx -d ${DOMAIN}"
        fi
    else
        warn "Certbot nicht verfügbar — SSL muss manuell eingerichtet werden"
    fi

    # Nginx starten/neustarten
    nginx -t 2>/dev/null && systemctl enable nginx && systemctl restart nginx && \
        ok "Nginx gestartet" || warn "Nginx-Start fehlgeschlagen — Config prüfen: sudo nginx -t"
fi

# ── UFW Firewall ──────────────────────────────────────────────────────────────
step "UFW Firewall konfigurieren"

if ! command -v ufw &>/dev/null; then
    $PKG_MANAGER install -y -qq ufw || warn "UFW konnte nicht installiert werden"
fi

if command -v ufw &>/dev/null; then
    # Bestehende Regeln nicht löschen, nur hinzufügen
    ufw default deny incoming 2>/dev/null || true
    ufw default allow outgoing 2>/dev/null || true

    # SSH immer erlauben (Lockout verhindern!)
    ufw allow ssh comment "SSH" 2>/dev/null || true
    ok "UFW: SSH erlaubt"

    if [[ "$USE_DOMAIN" == "true" ]]; then
        # Mit Domain: HTTP/HTTPS für Nginx, kein direkter Port 5000
        ufw allow 80/tcp comment "HTTP (Nginx)" 2>/dev/null || true
        ufw allow 443/tcp comment "HTTPS (Nginx)" 2>/dev/null || true
        ok "UFW: HTTP (80) und HTTPS (443) freigegeben"

        # Port 5000 nur lokal (Nginx Proxy) — keine externe Freigabe nötig
        ufw deny 5000/tcp comment "TREVLIX intern (nur via Nginx)" 2>/dev/null || true
        ok "UFW: Port 5000 nur intern via Nginx erreichbar"
    else
        # Ohne Domain: Port 5000 direkt freigeben
        ufw allow 5000/tcp comment "TREVLIX Dashboard" 2>/dev/null || true
        ok "UFW: Port 5000 freigegeben"
    fi

    # UFW aktivieren (non-interactive)
    echo "y" | ufw enable 2>/dev/null || true
    ok "UFW Firewall aktiviert"
else
    warn "UFW nicht verfügbar — Firewall manuell konfigurieren"
fi

# ── Fail2ban ──────────────────────────────────────────────────────────────────
step "Fail2ban installieren & konfigurieren"

if ! command -v fail2ban-client &>/dev/null; then
    $PKG_MANAGER install -y -qq fail2ban || warn "Fail2ban konnte nicht installiert werden"
fi

if command -v fail2ban-client &>/dev/null; then
    # Jail-Konfiguration für Trevlix + SSH
    cat > /etc/fail2ban/jail.local << F2B_EOF
# TREVLIX Fail2ban Konfiguration (auto-generiert)
[DEFAULT]
bantime  = 3600
findtime = 600
maxretry = 5
banaction = ufw

# ── SSH Schutz ──────────────────────────────────────────────────
[sshd]
enabled  = true
port     = ssh
filter   = sshd
logpath  = /var/log/auth.log
maxretry = 3
bantime  = 7200
F2B_EOF

    # Nginx-Filter nur bei Domain-Setup
    if [[ "$USE_DOMAIN" == "true" ]]; then
        cat >> /etc/fail2ban/jail.local << F2B_NGINX_EOF

# ── Nginx Schutz ────────────────────────────────────────────────
[nginx-http-auth]
enabled  = true
port     = http,https
filter   = nginx-http-auth
logpath  = /var/log/nginx/error.log
maxretry = 3
bantime  = 3600

[nginx-botsearch]
enabled  = true
port     = http,https
filter   = nginx-botsearch
logpath  = /var/log/nginx/access.log
maxretry = 5
bantime  = 7200

[nginx-limit-req]
enabled  = true
port     = http,https
filter   = nginx-limit-req
logpath  = /var/log/nginx/error.log
maxretry = 10
bantime  = 3600
F2B_NGINX_EOF
    fi

    # Trevlix Login-Schutz Filter erstellen
    cat > /etc/fail2ban/filter.d/trevlix-login.conf << F2B_FILTER_EOF
# Fail2ban filter for TREVLIX failed login attempts
[Definition]
failregex = ^.*Login fehlgeschlagen.*IP=<HOST>.*$
            ^.*Failed login.*IP=<HOST>.*$
            ^.*401.*<HOST>.*login.*$
ignoreregex =
F2B_FILTER_EOF

    cat >> /etc/fail2ban/jail.local << F2B_TREVLIX_EOF

# ── TREVLIX Login-Schutz ────────────────────────────────────────
[trevlix-login]
enabled  = true
port     = 5000
filter   = trevlix-login
logpath  = ${INSTALL_DIR}/logs/trevlix.log
maxretry = 5
bantime  = 3600
findtime = 300
F2B_TREVLIX_EOF

    # Fail2ban starten
    systemctl enable fail2ban 2>/dev/null || true
    systemctl restart fail2ban 2>/dev/null || true
    ok "Fail2ban installiert und konfiguriert"
    ok "SSH: max 3 Versuche (2h Ban)"
    if [[ "$USE_DOMAIN" == "true" ]]; then
        ok "Nginx: HTTP-Auth, Bot-Schutz, Rate-Limit"
    fi
    ok "Trevlix: max 5 Login-Versuche (1h Ban)"
else
    warn "Fail2ban nicht verfügbar"
fi

# ── Bot starten ────────────────────────────────────────────────────────────────
step "TREVLIX starten"
systemctl start "$SERVICE_NAME" && ok "Bot gestartet (systemctl)" || \
    warn "Start fehlgeschlagen — manuell prüfen: sudo systemctl status trevlix"

# Installation erfolgreich – Trap deaktivieren
_CLEANUP_DONE=true

# ── Zusammenfassung ────────────────────────────────────────────────────────────
IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

echo ""
echo -e "${JADE}╔══════════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${JADE}║${RESET}  ${BOLD}${GREEN}TREVLIX ERFOLGREICH INSTALLIERT!${RESET}                                ${JADE}║${RESET}"
echo -e "${JADE}╠══════════════════════════════════════════════════════════════════╣${RESET}"

if [[ "$USE_DOMAIN" == "true" ]]; then
    echo -e "${JADE}║${RESET}  ${BOLD}Dashboard:${RESET}    https://${DOMAIN}                                   ${JADE}║${RESET}"
else
    echo -e "${JADE}║${RESET}  ${BOLD}Dashboard:${RESET}    http://${IP}:5000                                   ${JADE}║${RESET}"
fi

echo -e "${JADE}║${RESET}  ${BOLD}Install-Dir:${RESET}  ${INSTALL_DIR}                                         ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}                                                                  ${JADE}║${RESET}"
echo -e "${JADE}╠══════════════════════════════════════════════════════════════════╣${RESET}"
echo -e "${JADE}║${RESET}  ${BOLD}${CYAN}ZUGANGSDATEN (BITTE SICHERN!)${RESET}                                  ${JADE}║${RESET}"
echo -e "${JADE}╠══════════════════════════════════════════════════════════════════╣${RESET}"
echo -e "${JADE}║${RESET}  ${BOLD}Admin-Login:${RESET}                                                   ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}    Nutzer:    ${BOLD}admin${RESET}                                                ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}    Passwort:  ${BOLD}${ADMIN_PASS}${RESET}                                        ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}                                                                  ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}  ${BOLD}MariaDB:${RESET}                                                       ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}    Datenbank: ${BOLD}trevlix${RESET}                                              ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}    Nutzer:    ${BOLD}trevlix${RESET}                                              ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}    Passwort:  ${BOLD}${DB_PASS}${RESET}                                          ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}    Root-PW:   ${BOLD}${DB_ROOT_PASS}${RESET}                                     ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}                                                                  ${JADE}║${RESET}"
echo -e "${JADE}╠══════════════════════════════════════════════════════════════════╣${RESET}"
echo -e "${JADE}║${RESET}  ${YELLOW}Naechste Schritte:${RESET}                                             ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}  1. API-Keys eintragen:  nano ${INSTALL_DIR}/.env                 ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}  2. Bot neustarten:       systemctl restart trevlix               ${JADE}║${RESET}"

if [[ "$USE_DOMAIN" == "true" ]]; then
    echo -e "${JADE}║${RESET}  3. DNS pruefen:          ${DOMAIN} -> ${IP}                   ${JADE}║${RESET}"
fi

echo -e "${JADE}╠══════════════════════════════════════════════════════════════════╣${RESET}"
echo -e "${JADE}║${RESET}  ${DIM}Bot-Befehle:${RESET}                                                   ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}    systemctl status trevlix    ${DIM}# Status${RESET}                           ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}    systemctl restart trevlix   ${DIM}# Neustart${RESET}                         ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}    journalctl -u trevlix -f    ${DIM}# Live-Logs${RESET}                        ${JADE}║${RESET}"

if [[ "$USE_DOMAIN" == "true" ]]; then
    echo -e "${JADE}║${RESET}    certbot renew --dry-run    ${DIM}# SSL testen${RESET}                     ${JADE}║${RESET}"
fi

echo -e "${JADE}║${RESET}    fail2ban-client status      ${DIM}# Firewall-Status${RESET}                  ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}    ufw status                  ${DIM}# UFW-Regeln${RESET}                       ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}                                                                  ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}  ${DIM}Log: ${LOG_FILE}${RESET}                                  ${JADE}║${RESET}"
echo -e "${JADE}╚══════════════════════════════════════════════════════════════════╝${RESET}"
echo ""
echo -e "  ${RED}WICHTIG: Starte zuerst im Paper-Trading Modus!${RESET}"
echo -e "  ${DIM}PAPER_TRADING=true ist bereits in der .env gesetzt.${RESET}"
echo ""
echo -e "  ${DIM}Multi-Exchange: Crypto.com, Binance, Bybit, OKX, KuCoin${RESET}"
echo -e "  ${DIM}Aktivieren: nano ${INSTALL_DIR}/.env${RESET}"
echo ""
