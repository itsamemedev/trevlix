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
# ║  Algorithmic Trading Intelligence  ·  Installer v1.0.4                      ║
# ║  Unterstützt: Ubuntu 16.04-24.04 · Debian 6-12                             ║
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
for arg in "$@"; do
    case "$arg" in
        --no-tf)   SKIP_TF=true ;;
        --no-shap) SKIP_SHAP=true ;;
        --yes|-y)  AUTO_NO=true ;;
        --dir)     shift; INSTALL_DIR="$1" ;;
    esac
done

# ── Farben ─────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; RESET='\033[0m'
JADE='\033[38;5;47m'

# ── Konfiguration ──────────────────────────────────────────────────────────────
INSTALL_DIR="/opt/trevlix"
SERVICE_USER="trevlix"
SERVICE_NAME="trevlix"
PYTHON_MIN="3.9"
LOG_FILE="/tmp/trevlix_install_$(date +%Y%m%d_%H%M%S).log"
REPO_URL="https://github.com/DEIN_USER/trevlix"  # ← beim Release ersetzen

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
echo -e "  ${DIM}Algorithmic Trading Intelligence · Installer v1.0.4${RESET}"
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
    OS_VER=$(cat /etc/debian_version | cut -d. -f1)
else
    err "Unbekanntes Betriebssystem. Nur Ubuntu/Debian wird unterstützt."
fi

log "Erkannt: ${OS_ID} ${OS_VER} (${OS_CODENAME:-})"

case "$OS_ID" in
    ubuntu)
        VER_MAJOR=$(echo "$OS_VER" | cut -d. -f1)
        if [[ $VER_MAJOR -lt 16 ]]; then
            err "Ubuntu ${OS_VER} wird nicht unterstützt. Minimum: Ubuntu 16.04"
        fi
        ok "Ubuntu ${OS_VER} wird unterstützt"
        PKG_MANAGER="apt-get"
        ;;
    debian)
        DEB_VER=$(echo "$OS_VER" | cut -d. -f1)
        if [[ $DEB_VER -lt 6 ]]; then
            err "Debian ${OS_VER} wird nicht unterstützt. Minimum: Debian 6"
        fi
        ok "Debian ${OS_VER} wird unterstützt"
        PKG_MANAGER="apt-get"
        ;;
    *)
        err "Nur Ubuntu und Debian werden unterstützt (erkannt: ${OS_ID})"
        ;;
esac

# ── System-Update ──────────────────────────────────────────────────────────────
step "System-Pakete aktualisieren"
export DEBIAN_FRONTEND=noninteractive
$PKG_MANAGER update -qq || warn "Update-Fehler (wird fortgesetzt)"
ok "Paketliste aktualisiert"

# ── Basis-Abhängigkeiten ───────────────────────────────────────────────────────
step "Basis-Abhängigkeiten installieren"
BASE_PKGS="curl wget git ca-certificates gnupg lsb-release software-properties-common \
           build-essential libssl-dev libffi-dev pkg-config \
           libmysqlclient-dev default-libmysqlclient-dev \
           libxml2-dev libxslt1-dev zlib1g-dev \
           systemd"

for pkg in $BASE_PKGS; do
    if ! dpkg -s "$pkg" &>/dev/null 2>&1; then
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
        $PKG_MANAGER install -y -qq python3-software-properties || true
        add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
        $PKG_MANAGER update -qq
        $PKG_MANAGER install -y -qq python3.11 python3.11-venv python3.11-dev python3.11-distutils || true
    fi
    # Fallback: pip für 3.11
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11 - 2>/dev/null || true
}

detect_python() {
    for py in python3.11 python3.10 python3.9 python3.8 python3; do
        if command -v "$py" &>/dev/null; then
            PY_VER=$($py -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
            PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
            PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
            if [[ $PY_MAJOR -ge 3 ]] && [[ $PY_MINOR -ge 9 ]]; then
                PYTHON_BIN="$py"
                ok "Python ${PY_VER} gefunden: $(command -v $py)"
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
    curl -sS https://bootstrap.pypa.io/get-pip.py | $PYTHON_BIN - --quiet
fi
ok "Python: $($PYTHON_BIN --version)"

# ── MySQL Installation ─────────────────────────────────────────────────────────
step "MySQL installieren & konfigurieren"

install_mysql() {
    if command -v mysql &>/dev/null; then
        ok "MySQL bereits installiert: $(mysql --version)"
        return
    fi

    log "Installiere MySQL Server..."
    # Versuche mysql-server; fallback auf mariadb
    if $PKG_MANAGER install -y -qq mysql-server 2>/dev/null; then
        ok "MySQL Server installiert"
    elif $PKG_MANAGER install -y -qq mariadb-server mariadb-client 2>/dev/null; then
        ok "MariaDB Server installiert (MySQL-kompatibel)"
    else
        # Für alte Distros: MySQL 5.7 via apt
        wget -qO /tmp/mysql-apt.deb https://dev.mysql.com/get/mysql-apt-config_0.8.29-1_all.deb 2>/dev/null || true
        if [[ -f /tmp/mysql-apt.deb ]]; then
            DEBIAN_FRONTEND=noninteractive dpkg -i /tmp/mysql-apt.deb || true
            $PKG_MANAGER update -qq
            $PKG_MANAGER install -y -qq mysql-server || err "MySQL konnte nicht installiert werden"
        else
            err "MySQL-Installation fehlgeschlagen. Bitte manuell installieren."
        fi
    fi
}

install_mysql

# MySQL starten
if command -v systemctl &>/dev/null && systemctl is-system-running &>/dev/null 2>&1; then
    systemctl enable mysql 2>/dev/null || systemctl enable mariadb 2>/dev/null || true
    systemctl start  mysql 2>/dev/null || systemctl start  mariadb 2>/dev/null || true
else
    service mysql start 2>/dev/null || service mariadb start 2>/dev/null || true
fi
ok "MySQL läuft"

# ── MySQL Passwort & Datenbank ─────────────────────────────────────────────────
step "MySQL Datenbank & Nutzer einrichten"

# Generiere sicheres Passwort
if command -v openssl &>/dev/null; then
    DB_PASS=$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)
    DB_ROOT_PASS=$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)
    ADMIN_PASS=$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)
    JWT_SECRET=$(openssl rand -hex 32)
    FLASK_SECRET=$(openssl rand -hex 32)
    DASH_SECRET=$(openssl rand -hex 32)
    # Fernet-Key für API-Key-Verschlüsselung
    if "$VENV_DIR/bin/python" -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" &>/dev/null 2>&1; then
        ENCRYPTION_KEY=$("$VENV_DIR/bin/python" -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    else
        ENCRYPTION_KEY=$(openssl rand -base64 32 | head -c 44)
    fi
else
    DB_PASS="trevlix_$(date +%s | sha256sum | head -c 12)"
    DB_ROOT_PASS="root_$(date +%s | sha256sum | head -c 14)"
    ADMIN_PASS="Admin_$(date +%s | sha256sum | head -c 10)"
    JWT_SECRET="$(head /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 64)"
    FLASK_SECRET="$(head /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 64)"
    DASH_SECRET="$(head /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 64)"
    ENCRYPTION_KEY="$(head /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 44)"
fi

# DB einrichten
SQL_CMD="CREATE DATABASE IF NOT EXISTS trevlix CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; CREATE USER IF NOT EXISTS 'trevlix'@'localhost' IDENTIFIED BY '${DB_PASS}'; GRANT ALL PRIVILEGES ON trevlix.* TO 'trevlix'@'localhost'; FLUSH PRIVILEGES;"
mysql -u root -e "$SQL_CMD" 2>/dev/null || mysql -u root --execute="$SQL_CMD" 2>/dev/null || \
    warn "DB-Einrichtung fehlgeschlagen – bitte manuell ausführen: mysql -u root"
ok "Datenbank 'trevlix' und Nutzer erstellt"

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
    for f in server.py dashboard.html index.html INSTALLATION.html \
              trevlix_translations.js trevlix_i18n.py requirements.txt; do
        [[ -f "./$f" ]] && cp "./$f" "$INSTALL_DIR/$f" && ok "Kopiert: $f"
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
    $PYTHON_BIN -m venv "$VENV_DIR" || err "venv-Erstellung fehlgeschlagen"
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

# ── .env erstellen ─────────────────────────────────────────────────────────────
step ".env Konfigurationsdatei erstellen"

if [[ ! -f "$INSTALL_DIR/.env" ]]; then
    cat > "$INSTALL_DIR/.env" << ENV_EOF
# TREVLIX v1.0.4 – Auto-generiert am $(date)
# ⚠️  Niemals in Git committen! (steht in .gitignore)

# ── Exchange (jetzt konfigurieren!) ──────────────────────────────
EXCHANGE=cryptocom
API_KEY=
API_SECRET=

# ── MySQL (auto-generiert) ────────────────────────────────────────
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=trevlix
MYSQL_PASS=${DB_PASS}
MYSQL_ROOT_PASS=${DB_ROOT_PASS}
MYSQL_DB=trevlix

# ── Sicherheit (auto-generiert) ───────────────────────────────────
ADMIN_PASSWORD=${ADMIN_PASS}
DASHBOARD_SECRET=${DASH_SECRET}
JWT_SECRET=${JWT_SECRET}
SECRET_KEY=${FLASK_SECRET}
# Fernet-Key für API-Key-Verschlüsselung (auto-generiert)
ENCRYPTION_KEY=${ENCRYPTION_KEY}
SESSION_TIMEOUT_MIN=30
ALLOWED_ORIGINS=http://localhost:5000

# ── Trading (Empfehlung: erst mit Paper-Trading starten!) ─────────
PAPER_TRADING=true

# ── Features (optional) ───────────────────────────────────────────
DISCORD_WEBHOOK=
TELEGRAM_TOKEN=
TELEGRAM_CHAT_ID=
CRYPTOPANIC_TOKEN=
BLOCKNATIVE_KEY=
GITHUB_REPO=
LANGUAGE=de
PORT=5000
ENV_EOF
    chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/.env"
    chmod 600 "$INSTALL_DIR/.env"
    ok ".env erstellt (Passwörter auto-generiert)"
else
    ok ".env existiert bereits — wird nicht überschrieben"
fi

# ── Systemd Service ────────────────────────────────────────────────────────────
step "Systemd Service einrichten"

if command -v systemctl &>/dev/null && systemctl is-system-running &>/dev/null 2>&1; then
    cat > "/etc/systemd/system/${SERVICE_NAME}.service" << SERVICE_EOF
[Unit]
Description=TREVLIX Algorithmic Trading Bot
After=network.target mysql.service mariadb.service
Wants=mysql.service mariadb.service

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

    # Autostart nach Reboot
    ok "Bot startet automatisch nach Neustart"
else
    # SysV init fallback (Debian 6/7, Ubuntu 16 ohne systemd)
    INIT_SCRIPT="/etc/init.d/${SERVICE_NAME}"
    cat > "$INIT_SCRIPT" << INIT_EOF
#!/bin/bash
### BEGIN INIT INFO
# Provides:          trevlix
# Required-Start:    \$network \$mysql
# Required-Stop:     \$network
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: TREVLIX Trading Bot
### END INIT INFO

DAEMON=${VENV_DIR}/bin/python
DAEMON_ARGS="${INSTALL_DIR}/server.py"
PIDFILE=/var/run/trevlix.pid
USER=${SERVICE_USER}

case "\$1" in
  start)
    cd ${INSTALL_DIR}
    set -a; . ${INSTALL_DIR}/.env; set +a
    start-stop-daemon --start --quiet --chuid \$USER --pidfile \$PIDFILE \
        --make-pidfile --background --exec \$DAEMON -- \$DAEMON_ARGS
    echo "TREVLIX gestartet"
    ;;
  stop)
    start-stop-daemon --stop --quiet --pidfile \$PIDFILE
    echo "TREVLIX gestoppt"
    ;;
  restart)
    \$0 stop; sleep 2; \$0 start
    ;;
  status)
    if start-stop-daemon --status --pidfile \$PIDFILE; then
        echo "TREVLIX läuft (PID: \$(cat \$PIDFILE))"
    else
        echo "TREVLIX nicht aktiv"
    fi
    ;;
  *)
    echo "Verwendung: \$0 {start|stop|restart|status}"
    exit 1
esac
INIT_EOF
    chmod +x "$INIT_SCRIPT"
    update-rc.d "$SERVICE_NAME" defaults 2>/dev/null || true
    ok "Init-Script erstellt: $INIT_SCRIPT"
fi

# ── Berechtigungen ─────────────────────────────────────────────────────────────
step "Berechtigungen setzen"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
chmod 750 "$INSTALL_DIR"
chmod 600 "$INSTALL_DIR/.env"
ok "Berechtigungen gesetzt"

# ── Firewall (UFW) ─────────────────────────────────────────────────────────────
step "Firewall konfigurieren"
if command -v ufw &>/dev/null; then
    ufw allow 5000/tcp comment "TREVLIX Dashboard" 2>/dev/null || true
    ok "UFW: Port 5000 freigegeben"
elif command -v iptables &>/dev/null; then
    iptables -I INPUT -p tcp --dport 5000 -j ACCEPT 2>/dev/null || true
    ok "iptables: Port 5000 freigegeben"
fi

# ── Bot starten ────────────────────────────────────────────────────────────────
step "TREVLIX starten"
if command -v systemctl &>/dev/null && systemctl is-system-running &>/dev/null 2>&1; then
    systemctl start "$SERVICE_NAME" && ok "Bot gestartet (systemctl)" || warn "Start fehlgeschlagen — manuell prüfen"
else
    service "$SERVICE_NAME" start 2>/dev/null && ok "Bot gestartet" || warn "Manuell starten: sudo service trevlix start"
fi

# Installation erfolgreich – Trap deaktivieren
_CLEANUP_DONE=true

# ── Zusammenfassung ────────────────────────────────────────────────────────────
IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

echo ""
echo -e "${JADE}╔══════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${JADE}║${RESET}  ${BOLD}${GREEN}✓ TREVLIX ERFOLGREICH INSTALLIERT!${RESET}                          ${JADE}║${RESET}"
echo -e "${JADE}╠══════════════════════════════════════════════════════════════╣${RESET}"
echo -e "${JADE}║${RESET}  ${BOLD}Dashboard:${RESET}    http://${IP}:5000                            ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}  ${BOLD}Admin-Login:${RESET}  Nutzer: admin                                 ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}  ${BOLD}Passwort:${RESET}     ${ADMIN_PASS}                ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}  ${BOLD}Install-Dir:${RESET}  ${INSTALL_DIR}                        ${JADE}║${RESET}"
echo -e "${JADE}╠══════════════════════════════════════════════════════════════╣${RESET}"
echo -e "${JADE}║${RESET}  ${YELLOW}⚠  API-Keys in .env eintragen:${RESET}                             ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}  nano ${INSTALL_DIR}/.env                                   ${JADE}║${RESET}"
echo -e "${JADE}╠══════════════════════════════════════════════════════════════╣${RESET}"
echo -e "${JADE}║${RESET}  ${DIM}Bot-Befehle:${RESET}                                               ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}  systemctl status trevlix    # Status                         ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}  systemctl restart trevlix   # Neustart                       ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}  journalctl -u trevlix -f    # Live-Logs                      ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}  ${DIM}Log dieser Installation: ${LOG_FILE}${RESET}   ${JADE}║${RESET}"
echo -e "${JADE}╚══════════════════════════════════════════════════════════════╝${RESET}"
echo ""
echo -e "  ${RED}WICHTIG: Starte zuerst im Paper-Trading Modus!${RESET}"
echo ""
echo -e "  ${DIM}Multi-Exchange: Crypto.com, Binance, Bybit, OKX, KuCoin${RESET}"
echo -e "  ${DIM}Aktivieren: nano ${INSTALL_DIR}/.env  -->  BINANCE_ENABLED=true${RESET}"
echo -e "  ${DIM}PAPER_TRADING=true ist bereits in der .env gesetzt.${RESET}"
echo ""
