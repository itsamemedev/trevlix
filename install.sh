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
# ║  Algorithmic Trading Intelligence  ·  Installer v3.0.0                      ║
# ║                                                                              ║
# ║  Supported:                                                                  ║
# ║    Debian 10-12 · Ubuntu 18.04-24.04 · Raspberry Pi OS · Linux Mint         ║
# ║    CentOS Stream 8-9 · Rocky Linux 8-9 · AlmaLinux 8-9 · RHEL 8-9          ║
# ║    Fedora 37+ · openSUSE Leap 15.x / Tumbleweed · Arch Linux               ║
# ║                                                                              ║
# ║  Start: sudo bash install.sh                                                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

set -euo pipefail

# ── Help ─────────────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: sudo bash install.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --help, -h         Show this help"
    echo "  --no-tf            Skip TensorFlow (no LSTM)"
    echo "  --no-shap          Skip SHAP"
    echo "  --yes, -y          Auto-decline all optional packages"
    echo "  --dir DIR          Installation directory (default: /opt/trevlix)"
    echo "  --admin-user NAME  Set admin username (default: admin, min 3 chars)"
    echo "  --admin-pass PASS  Set admin password (min 12 chars, mixed case + special)"
    echo ""
    echo "Example: sudo bash install.sh --no-tf --no-shap --admin-user myadmin"
    exit 0
fi

# ── Flags ────────────────────────────────────────────────────────────────────
SKIP_TF=false
SKIP_SHAP=false
AUTO_NO=false
CUSTOM_INSTALL_DIR=""
CLI_ADMIN_USER=""
CLI_ADMIN_PASS=""
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
                echo "ERROR: --dir requires an argument" >&2
                exit 1
            fi
            ;;
        --admin-user)
            if [[ -n "${2:-}" ]]; then
                CLI_ADMIN_USER="$2"
                shift 2
            else
                echo "ERROR: --admin-user requires an argument" >&2
                exit 1
            fi
            ;;
        --admin-pass)
            if [[ -n "${2:-}" ]]; then
                CLI_ADMIN_PASS="$2"
                shift 2
            else
                echo "ERROR: --admin-pass requires an argument" >&2
                exit 1
            fi
            ;;
        *) shift ;;
    esac
done

# ── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; RESET='\033[0m'
JADE='\033[38;5;47m'

# ── Configuration ────────────────────────────────────────────────────────────
INSTALL_DIR="${CUSTOM_INSTALL_DIR:-/opt/trevlix}"
SERVICE_USER="trevlix"
SERVICE_NAME="trevlix"
PYTHON_MIN="3.9"
LOG_FILE="/tmp/trevlix_install_$(date +%Y%m%d_%H%M%S).log"
REPO_URL="https://github.com/itsamemedev/Trevlix"

# Domain variables (set later)
USE_DOMAIN=false
DOMAIN=""

# OS family variables (set during detection)
OS_FAMILY=""          # debian, rhel, fedora, suse, arch
PKG_MANAGER=""        # apt-get, dnf, yum, zypper, pacman
PKG_INSTALL=""        # full install command with quiet/yes flags
PKG_UPDATE=""         # update command

# ── Logging ──────────────────────────────────────────────────────────────────
exec > >(tee -a "$LOG_FILE") 2>&1

log()  { echo -e "${JADE}[TREVLIX]${RESET} $*"; }
ok()   { echo -e "${GREEN}  ✓${RESET} $*"; }
warn() { echo -e "${YELLOW}  ⚠${RESET} $*"; }
err()  { echo -e "${RED}  ✗ ERROR:${RESET} $*"; exit 1; }
step() { echo -e "\n${BOLD}${CYAN}━━ $* ━━${RESET}"; }

# ── Interaktive Prompts ─────────────────────────────────────────────────────
# ask_yn FRAGE DEFAULT  →  echo "yes" oder "no"
#   DEFAULT: "y" (Standard ja) oder "n" (Standard nein).
#   Bei --yes / -y oder nicht-interaktivem TTY wird DEFAULT ohne Frage genutzt.
ask_yn() {
    local question="$1" default="${2:-n}" reply
    if [[ "$AUTO_NO" == "true" || ! -t 0 ]]; then
        [[ "$default" == "y" ]] && echo "yes" || echo "no"
        return
    fi
    local hint="[y/N]"
    [[ "$default" == "y" ]] && hint="[Y/n]"
    read -rp "$(echo -e "${CYAN}${question} ${hint}: ${RESET}")" reply
    reply="${reply,,}"
    if [[ -z "$reply" ]]; then
        [[ "$default" == "y" ]] && echo "yes" || echo "no"
    elif [[ "$reply" =~ ^(y|yes|ja|j)$ ]]; then
        echo "yes"
    else
        echo "no"
    fi
}

# ask_value FRAGE DEFAULT  →  echo Antwort (DEFAULT bei leerer Eingabe)
ask_value() {
    local question="$1" default="${2:-}" reply hint=""
    if [[ "$AUTO_NO" == "true" || ! -t 0 ]]; then
        echo "$default"
        return
    fi
    [[ -n "$default" ]] && hint=" ${DIM}(leer = ${default})${RESET}"
    read -rp "$(echo -e "${CYAN}${question}${hint}: ${RESET}")" reply
    echo "${reply:-$default}"
}

# ask_secret FRAGE  →  echo Antwort (Eingabe ohne Echo, optional leer)
ask_secret() {
    local question="$1" reply
    if [[ "$AUTO_NO" == "true" || ! -t 0 ]]; then
        echo ""
        return
    fi
    read -rsp "$(echo -e "${CYAN}${question} ${DIM}(leer = überspringen)${RESET}: ")" reply
    echo "" >&2
    echo "$reply"
}

# ── Banner ───────────────────────────────────────────────────────────────────
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
echo -e "  ${DIM}Algorithmic Trading Intelligence · Installer v3.0.0${RESET}"
echo -e "  ${DIM}Log: ${LOG_FILE}${RESET}"
echo ""

# ── Cleanup trap on error ────────────────────────────────────────────────────
_CLEANUP_DONE=false
cleanup_on_error() {
    if [[ "$_CLEANUP_DONE" == "false" ]]; then
        echo -e "\n${RED}  ✗ Installation aborted! Cleaning up...${RESET}"
        systemctl stop "$SERVICE_NAME" 2>/dev/null || true
        systemctl disable "$SERVICE_NAME" 2>/dev/null || true
        rm -f "/etc/systemd/system/${SERVICE_NAME}.service" 2>/dev/null || true
        systemctl daemon-reload 2>/dev/null || true
        echo -e "${YELLOW}  ⚠ Installation log: ${LOG_FILE}${RESET}"
        _CLEANUP_DONE=true
    fi
}
trap cleanup_on_error ERR

# ── Root check ───────────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    err "Please run as root: sudo bash install.sh"
fi

# ── Pre-flight checks ───────────────────────────────────────────────────────
step "Checking system requirements"

# Free disk space (min. 2 GB)
FREE_MB=$(df / | awk 'NR==2 {print int($4/1024)}')
if [[ $FREE_MB -lt 2048 ]]; then
    warn "Less than 2 GB free disk space (${FREE_MB} MB). Installation may fail."
else
    ok "Free disk space: ${FREE_MB} MB"
fi

# RAM (min. 512 MB)
if [[ -f /proc/meminfo ]]; then
    TOTAL_RAM_MB=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
    if [[ $TOTAL_RAM_MB -lt 512 ]]; then
        warn "Less than 512 MB RAM (${TOTAL_RAM_MB} MB). AI training may be slow."
    else
        ok "RAM: ${TOTAL_RAM_MB} MB"
    fi
fi

# ══════════════════════════════════════════════════════════════════════════════
# ── OS Detection (broad Linux support) ───────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
step "Detecting operating system"

# Detect Raspberry Pi
IS_RASPBERRY_PI=false
if [[ -f /sys/firmware/devicetree/base/model ]]; then
    PI_MODEL=$(tr -d '\0' < /sys/firmware/devicetree/base/model 2>/dev/null || true)
    if [[ "$PI_MODEL" == *"Raspberry Pi"* ]]; then
        IS_RASPBERRY_PI=true
        log "Raspberry Pi detected: ${PI_MODEL}"
    fi
fi

if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    OS_ID="${ID:-unknown}"
    OS_VER="${VERSION_ID:-0}"
    OS_CODENAME="${VERSION_CODENAME:-${UBUNTU_CODENAME:-}}"
    OS_ID_LIKE="${ID_LIKE:-}"
elif [[ -f /etc/debian_version ]]; then
    OS_ID="debian"
    OS_VER=$(cut -d. -f1 < /etc/debian_version)
    OS_CODENAME=""
    OS_ID_LIKE=""
else
    err "Unknown operating system. Cannot continue."
fi

log "Detected: ${OS_ID} ${OS_VER} (${OS_CODENAME:-none})"

# Classify OS into families and set package manager commands
case "$OS_ID" in
    # ── Debian family ────────────────────────────────────────────────────────
    debian)
        DEB_VER=$(echo "$OS_VER" | cut -d. -f1)
        if [[ $DEB_VER -lt 10 ]]; then
            err "Debian ${OS_VER} is not supported. Minimum: Debian 10"
        fi
        ok "Debian ${OS_VER} supported"
        OS_FAMILY="debian"
        ;;
    ubuntu)
        VER_MAJOR=$(echo "$OS_VER" | cut -d. -f1)
        if [[ $VER_MAJOR -lt 18 ]]; then
            err "Ubuntu ${OS_VER} is not supported. Minimum: Ubuntu 18.04"
        fi
        ok "Ubuntu ${OS_VER} supported"
        OS_FAMILY="debian"
        ;;
    raspbian)
        ok "Raspbian (legacy Pi OS) detected"
        OS_FAMILY="debian"
        ;;
    linuxmint)
        ok "Linux Mint ${OS_VER} detected (Ubuntu-based)"
        OS_FAMILY="debian"
        ;;

    # ── RHEL family ──────────────────────────────────────────────────────────
    centos)
        RHEL_VER=$(echo "$OS_VER" | cut -d. -f1)
        if [[ $RHEL_VER -lt 8 ]]; then
            err "CentOS ${OS_VER} is not supported. Minimum: CentOS 8"
        fi
        ok "CentOS Stream ${OS_VER} supported"
        OS_FAMILY="rhel"
        ;;
    rocky)
        RHEL_VER=$(echo "$OS_VER" | cut -d. -f1)
        if [[ $RHEL_VER -lt 8 ]]; then
            err "Rocky Linux ${OS_VER} is not supported. Minimum: Rocky 8"
        fi
        ok "Rocky Linux ${OS_VER} supported"
        OS_FAMILY="rhel"
        ;;
    almalinux)
        RHEL_VER=$(echo "$OS_VER" | cut -d. -f1)
        if [[ $RHEL_VER -lt 8 ]]; then
            err "AlmaLinux ${OS_VER} is not supported. Minimum: AlmaLinux 8"
        fi
        ok "AlmaLinux ${OS_VER} supported"
        OS_FAMILY="rhel"
        ;;
    rhel)
        RHEL_VER=$(echo "$OS_VER" | cut -d. -f1)
        if [[ $RHEL_VER -lt 8 ]]; then
            err "RHEL ${OS_VER} is not supported. Minimum: RHEL 8"
        fi
        ok "RHEL ${OS_VER} supported"
        OS_FAMILY="rhel"
        ;;

    # ── Fedora ───────────────────────────────────────────────────────────────
    fedora)
        FED_VER=$(echo "$OS_VER" | cut -d. -f1)
        if [[ $FED_VER -lt 37 ]]; then
            err "Fedora ${OS_VER} is not supported. Minimum: Fedora 37"
        fi
        ok "Fedora ${OS_VER} supported"
        OS_FAMILY="fedora"
        ;;

    # ── openSUSE ─────────────────────────────────────────────────────────────
    opensuse-leap)
        ok "openSUSE Leap ${OS_VER} supported"
        OS_FAMILY="suse"
        ;;
    opensuse-tumbleweed)
        ok "openSUSE Tumbleweed supported"
        OS_FAMILY="suse"
        ;;

    # ── Arch Linux ───────────────────────────────────────────────────────────
    arch|manjaro|endeavouros)
        ok "Arch-based (${OS_ID}) supported"
        OS_FAMILY="arch"
        ;;

    # ── Fallback: try to detect by ID_LIKE ───────────────────────────────────
    *)
        if [[ "$OS_ID_LIKE" == *"debian"* || "$OS_ID_LIKE" == *"ubuntu"* ]]; then
            warn "Unknown Debian-derivative '${OS_ID}' — treating as Debian family"
            OS_FAMILY="debian"
        elif [[ "$OS_ID_LIKE" == *"rhel"* || "$OS_ID_LIKE" == *"centos"* || "$OS_ID_LIKE" == *"fedora"* ]]; then
            warn "Unknown RHEL-derivative '${OS_ID}' — treating as RHEL family"
            OS_FAMILY="rhel"
        elif [[ "$OS_ID_LIKE" == *"suse"* ]]; then
            warn "Unknown SUSE-derivative '${OS_ID}' — treating as openSUSE family"
            OS_FAMILY="suse"
        elif [[ "$OS_ID_LIKE" == *"arch"* ]]; then
            warn "Unknown Arch-derivative '${OS_ID}' — treating as Arch family"
            OS_FAMILY="arch"
        else
            err "Unsupported OS: ${OS_ID} (ID_LIKE=${OS_ID_LIKE}). Supported: Debian, Ubuntu, CentOS, Rocky, Alma, RHEL, Fedora, openSUSE, Arch"
        fi
        ;;
esac

if [[ "$IS_RASPBERRY_PI" == "true" ]]; then
    ok "Raspberry Pi optimizations will be applied"
fi

# ── Set package manager commands per OS family ───────────────────────────────
case "$OS_FAMILY" in
    debian)
        PKG_MANAGER="apt-get"
        PKG_INSTALL="apt-get install -y -qq"
        PKG_UPDATE="apt-get update -qq"
        ;;
    rhel)
        if command -v dnf &>/dev/null; then
            PKG_MANAGER="dnf"
            PKG_INSTALL="dnf install -y -q"
            PKG_UPDATE="dnf makecache -q"
        else
            PKG_MANAGER="yum"
            PKG_INSTALL="yum install -y -q"
            PKG_UPDATE="yum makecache -q"
        fi
        ;;
    fedora)
        PKG_MANAGER="dnf"
        PKG_INSTALL="dnf install -y -q"
        PKG_UPDATE="dnf makecache -q"
        ;;
    suse)
        PKG_MANAGER="zypper"
        PKG_INSTALL="zypper install -y --no-confirm"
        PKG_UPDATE="zypper refresh -q"
        ;;
    arch)
        PKG_MANAGER="pacman"
        PKG_INSTALL="pacman -S --noconfirm --needed"
        PKG_UPDATE="pacman -Sy --noconfirm"
        ;;
esac

ok "Package manager: ${PKG_MANAGER}"

# ── Domain prompt ────────────────────────────────────────────────────────────
step "Domain configuration"
echo ""
echo -e "${YELLOW}Should Trevlix be linked to a domain?${RESET}"
echo -e "${DIM}  Examples: example.com, app.example.com, trading.mydomain.de${RESET}"
echo -e "${DIM}  Leave empty = accessible only via IP:5000${RESET}"
echo ""
read -rp "$(echo -e "${CYAN}Domain (empty = none): ${RESET}")" DOMAIN

if [[ -n "$DOMAIN" ]]; then
    # Validate domain format
    if [[ "$DOMAIN" =~ ^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?\.[a-zA-Z]{2,}$ ]]; then
        USE_DOMAIN=true
        ok "Domain: ${DOMAIN}"
    else
        warn "Invalid domain format: '${DOMAIN}' — continuing without domain"
        DOMAIN=""
    fi
else
    ok "No domain — dashboard accessible at http://IP:5000"
fi

# ══════════════════════════════════════════════════════════════════════════════
# ── Admin Username + Password Prompt ─────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
step "Admin account configuration"

# ── Helper: validate password complexity ─────────────────────────────────────
validate_password() {
    local pass="$1"
    if [[ ${#pass} -lt 12 ]]; then
        echo "Password must be at least 12 characters long."
        return 1
    fi
    if ! [[ "$pass" =~ [a-z] ]]; then
        echo "Password must contain at least one lowercase letter."
        return 1
    fi
    if ! [[ "$pass" =~ [A-Z] ]]; then
        echo "Password must contain at least one uppercase letter."
        return 1
    fi
    if ! [[ "$pass" =~ [0-9] ]]; then
        echo "Password must contain at least one digit."
        return 1
    fi
    if ! [[ "$pass" =~ [^a-zA-Z0-9] ]]; then
        echo "Password must contain at least one special character."
        return 1
    fi
    return 0
}

# ── Helper: generate a secure random password ────────────────────────────────
generate_secure_password() {
    # Generate a password that satisfies complexity requirements
    local pass=""
    while true; do
        if command -v openssl &>/dev/null; then
            pass=$(openssl rand -base64 24 | tr -d '/\n' | head -c 20)
        else
            pass=$(head -c 64 /dev/urandom | tr -dc 'a-zA-Z0-9!@#$%^&*' | head -c 20)
        fi
        # Ensure complexity: append guaranteed chars if needed
        pass="${pass}Aa1!"
        pass=$(echo "$pass" | head -c 20)
        if validate_password "$pass" &>/dev/null; then
            echo "$pass"
            return 0
        fi
    done
}

# ── Admin username ───────────────────────────────────────────────────────────
ADMIN_USER=""
if [[ -n "$CLI_ADMIN_USER" ]]; then
    # From CLI flag
    if [[ ${#CLI_ADMIN_USER} -lt 3 ]]; then
        err "--admin-user must be at least 3 characters"
    fi
    ADMIN_USER="$CLI_ADMIN_USER"
    ok "Admin username (from flag): ${ADMIN_USER}"
else
    echo ""
    echo -e "${YELLOW}Choose an admin username for the dashboard.${RESET}"
    echo -e "${DIM}  Minimum 3 characters. Press Enter for default: admin${RESET}"
    echo ""
    read -rp "$(echo -e "${CYAN}Admin username [admin]: ${RESET}")" ADMIN_USER_INPUT
    ADMIN_USER="${ADMIN_USER_INPUT:-admin}"
    if [[ ${#ADMIN_USER} -lt 3 ]]; then
        warn "Username too short (min 3 chars) — using default: admin"
        ADMIN_USER="admin"
    fi
    ok "Admin username: ${ADMIN_USER}"
fi

# ── Admin password ───────────────────────────────────────────────────────────
ADMIN_PASS=""
ADMIN_PASS_GENERATED=false
if [[ -n "$CLI_ADMIN_PASS" ]]; then
    # From CLI flag
    validation_msg=$(validate_password "$CLI_ADMIN_PASS" 2>&1) || true
    if ! validate_password "$CLI_ADMIN_PASS" &>/dev/null; then
        err "--admin-pass does not meet requirements: ${validation_msg}"
    fi
    ADMIN_PASS="$CLI_ADMIN_PASS"
    ok "Admin password set (from flag)"
else
    echo ""
    echo -e "${YELLOW}Set an admin password for the dashboard.${RESET}"
    echo -e "${DIM}  Requirements: min 12 chars, uppercase + lowercase + digit + special char${RESET}"
    echo -e "${DIM}  Press Enter to auto-generate a secure random password.${RESET}"
    echo ""

    MAX_ATTEMPTS=3
    ATTEMPT=0
    while [[ $ATTEMPT -lt $MAX_ATTEMPTS ]]; do
        read -rsp "$(echo -e "${CYAN}Admin password (Enter = auto-generate): ${RESET}")" PASS_INPUT
        echo ""

        if [[ -z "$PASS_INPUT" ]]; then
            # Auto-generate
            ADMIN_PASS=$(generate_secure_password)
            ADMIN_PASS_GENERATED=true
            ok "Secure admin password auto-generated"
            break
        fi

        # Validate complexity
        validation_msg=$(validate_password "$PASS_INPUT" 2>&1) || true
        if ! validate_password "$PASS_INPUT" &>/dev/null; then
            warn "$validation_msg"
            ATTEMPT=$((ATTEMPT + 1))
            if [[ $ATTEMPT -lt $MAX_ATTEMPTS ]]; then
                echo -e "${DIM}  Try again (${ATTEMPT}/${MAX_ATTEMPTS})...${RESET}"
            fi
            continue
        fi

        # Confirm password
        read -rsp "$(echo -e "${CYAN}Confirm password: ${RESET}")" PASS_CONFIRM
        echo ""

        if [[ "$PASS_INPUT" != "$PASS_CONFIRM" ]]; then
            warn "Passwords do not match."
            ATTEMPT=$((ATTEMPT + 1))
            if [[ $ATTEMPT -lt $MAX_ATTEMPTS ]]; then
                echo -e "${DIM}  Try again (${ATTEMPT}/${MAX_ATTEMPTS})...${RESET}"
            fi
            continue
        fi

        ADMIN_PASS="$PASS_INPUT"
        ok "Admin password set"
        break
    done

    if [[ -z "$ADMIN_PASS" ]]; then
        ADMIN_PASS=$(generate_secure_password)
        ADMIN_PASS_GENERATED=true
        warn "Max attempts reached — auto-generating secure password"
    fi
fi

# ══════════════════════════════════════════════════════════════════════════════
# ── Optional Features Prompt ─────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
step "Optional features"
echo ""
echo -e "${DIM}Du kannst folgende Zusatzfunktionen jetzt konfigurieren oder später manuell"
echo -e "in ${INSTALL_DIR}/.env nachtragen. Leere Eingaben überspringen den jeweiligen Block.${RESET}"
echo ""

# Trading-Modus
PAPER_TRADING_CHOICE="true"
if [[ "$(ask_yn 'Paper-Trading-Modus aktivieren? (dringend empfohlen für den Erststart)' 'y')" == "no" ]]; then
    PAPER_TRADING_CHOICE="false"
    warn "LIVE-Trading aktiviert – echtes Geld wird eingesetzt!"
fi

# Auto-Start
AUTO_START_CHOICE="true"
if [[ "$(ask_yn 'Bot automatisch starten, sobald ein Exchange konfiguriert ist?' 'y')" == "no" ]]; then
    AUTO_START_CHOICE="false"
fi

# Exchange
EXCHANGE_CHOICE="$(ask_value 'Primärer Exchange (cryptocom/binance/bybit/okx/kucoin)' 'cryptocom')"
EXCHANGE_API_KEY=""
EXCHANGE_API_SECRET=""
if [[ "$(ask_yn 'Exchange API-Keys jetzt eintragen?' 'n')" == "yes" ]]; then
    EXCHANGE_API_KEY="$(ask_value "  API_KEY für ${EXCHANGE_CHOICE}" '')"
    EXCHANGE_API_SECRET="$(ask_secret "  API_SECRET für ${EXCHANGE_CHOICE}")"
fi

# CryptoPanic
CRYPTOPANIC_TOKEN_CHOICE=""
if [[ "$(ask_yn 'CryptoPanic News-Integration konfigurieren?' 'n')" == "yes" ]]; then
    CRYPTOPANIC_TOKEN_CHOICE="$(ask_value '  CryptoPanic Auth-Token' '')"
fi

# Discord
DISCORD_WEBHOOK_CHOICE=""
if [[ "$(ask_yn 'Discord-Benachrichtigungen aktivieren?' 'n')" == "yes" ]]; then
    DISCORD_WEBHOOK_CHOICE="$(ask_value '  Discord Webhook-URL' '')"
fi

# Telegram
TELEGRAM_TOKEN_CHOICE=""
TELEGRAM_CHAT_ID_CHOICE=""
if [[ "$(ask_yn 'Telegram-Benachrichtigungen aktivieren?' 'n')" == "yes" ]]; then
    TELEGRAM_TOKEN_CHOICE="$(ask_value '  Telegram Bot-Token' '')"
    TELEGRAM_CHAT_ID_CHOICE="$(ask_value '  Telegram Chat-ID' '')"
fi

# Ollama (lokales LLM)
INSTALL_OLLAMA_CHOICE="no"
OLLAMA_MODEL_CHOICE="qwen2.5:3b"
if [[ "$(ask_yn 'Lokales Ollama-LLM installieren? (für VIRGINIE-KI / News-Analyse, benötigt ~3-4 GB)' 'n')" == "yes" ]]; then
    INSTALL_OLLAMA_CHOICE="yes"
    OLLAMA_MODEL_CHOICE="$(ask_value '  Startmodell (leer = qwen2.5:3b)' 'qwen2.5:3b')"
fi

ok "Optionen erfasst"

# ══════════════════════════════════════════════════════════════════════════════
# ── System Update ────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
step "Updating system packages"

case "$OS_FAMILY" in
    debian)
        export DEBIAN_FRONTEND=noninteractive
        $PKG_UPDATE || warn "Update failed (continuing)"
        ;;
    rhel|fedora)
        $PKG_UPDATE || warn "Cache refresh failed (continuing)"
        ;;
    suse)
        $PKG_UPDATE || warn "Refresh failed (continuing)"
        ;;
    arch)
        $PKG_UPDATE || warn "Sync failed (continuing)"
        ;;
esac
ok "Package list updated"

# ══════════════════════════════════════════════════════════════════════════════
# ── Base Dependencies (per OS family) ────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
step "Installing base dependencies"

case "$OS_FAMILY" in
    debian)
        BASE_PKGS="build-essential libssl-dev libffi-dev pkg-config \
                   libmariadb-dev libxml2-dev libxslt1-dev zlib1g-dev \
                   curl wget git ca-certificates gnupg lsb-release software-properties-common \
                   cron"
        ;;
    rhel)
        BASE_PKGS="gcc gcc-c++ make openssl-devel libffi-devel pkgconfig \
                   mariadb-devel libxml2-devel libxslt-devel zlib-devel \
                   curl wget git ca-certificates gnupg2 cronie"
        # Enable EPEL for additional packages
        $PKG_INSTALL epel-release 2>/dev/null || true
        ;;
    fedora)
        BASE_PKGS="gcc gcc-c++ make openssl-devel libffi-devel pkgconfig \
                   mariadb-connector-c-devel libxml2-devel libxslt-devel zlib-devel \
                   curl wget git ca-certificates gnupg2 cronie"
        ;;
    suse)
        BASE_PKGS="gcc gcc-c++ make libopenssl-devel libffi-devel pkg-config \
                   libmariadb-devel libxml2-devel libxslt-devel zlib-devel \
                   curl wget git ca-certificates gpg2 cron"
        ;;
    arch)
        BASE_PKGS="base-devel openssl libffi pkg-config mariadb-libs \
                   libxml2 libxslt zlib curl wget git ca-certificates gnupg cronie"
        ;;
esac

# Install packages using the appropriate method per OS family
case "$OS_FAMILY" in
    debian)
        for pkg in $BASE_PKGS; do
            if ! dpkg -s "$pkg" &>/dev/null; then
                $PKG_INSTALL "$pkg" || warn "Could not install $pkg"
            fi
        done
        ;;
    rhel|fedora)
        # dnf/yum can handle multiple packages at once efficiently
        $PKG_INSTALL $BASE_PKGS || warn "Some base packages could not be installed"
        ;;
    suse)
        $PKG_INSTALL $BASE_PKGS || warn "Some base packages could not be installed"
        ;;
    arch)
        $PKG_INSTALL $BASE_PKGS || warn "Some base packages could not be installed"
        ;;
esac
ok "Base packages installed"

# ══════════════════════════════════════════════════════════════════════════════
# ── Python Installation (OS-dependent) ───────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
step "Installing Python 3.11+"

install_python_debian() {
    # deadsnakes PPA for Ubuntu < 22 / older Debian
    if ! python3.11 --version &>/dev/null 2>&1; then
        log "Adding deadsnakes PPA..."
        $PKG_INSTALL python3-software-properties 2>/dev/null || true
        add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
        $PKG_UPDATE
        $PKG_INSTALL python3.11 python3.11-venv python3.11-dev python3.11-distutils 2>/dev/null || true
    fi
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11 - 2>/dev/null || true
}

install_python_rhel() {
    local rhel_ver
    rhel_ver=$(echo "$OS_VER" | cut -d. -f1)
    if [[ $rhel_ver -eq 8 ]]; then
        # CentOS/RHEL/Rocky/Alma 8: use AppStream module or python39
        $PKG_INSTALL python39 python39-devel python39-pip 2>/dev/null || \
        $PKG_INSTALL python3 python3-devel python3-pip 2>/dev/null || true
    else
        # RHEL 9+
        $PKG_INSTALL python3 python3-devel python3-pip 2>/dev/null || true
    fi
}

install_python_fedora() {
    $PKG_INSTALL python3 python3-devel python3-pip 2>/dev/null || true
}

install_python_suse() {
    $PKG_INSTALL python311 python311-devel python311-pip 2>/dev/null || \
    $PKG_INSTALL python3 python3-devel python3-pip 2>/dev/null || true
}

install_python_arch() {
    $PKG_INSTALL python python-pip 2>/dev/null || true
}

detect_python() {
    for py in python3.11 python3.10 python3.9 python3; do
        if command -v "$py" &>/dev/null; then
            PY_VER=$($py -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
            PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
            PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
            if [[ $PY_MAJOR -ge 3 ]] && [[ $PY_MINOR -ge 9 ]]; then
                PYTHON_BIN="$py"
                ok "Python ${PY_VER} found: $(command -v "$py")"
                return 0
            fi
        fi
    done
    return 1
}

if ! detect_python; then
    log "Python 3.9+ not found — installing..."
    case "$OS_FAMILY" in
        debian)
            $PKG_INSTALL python3.11 python3.11-venv python3.11-dev 2>/dev/null || \
            install_python_debian
            ;;
        rhel)     install_python_rhel ;;
        fedora)   install_python_fedora ;;
        suse)     install_python_suse ;;
        arch)     install_python_arch ;;
    esac
    detect_python || err "Python 3.9+ could not be installed"
fi

# Ensure venv module is available (needed for Debian-family)
if [[ "$OS_FAMILY" == "debian" ]]; then
    if ! "$PYTHON_BIN" -m venv --help &>/dev/null 2>&1; then
        PY_SHORT=$("$PYTHON_BIN" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        $PKG_INSTALL "python${PY_SHORT}-venv" 2>/dev/null || \
        $PKG_INSTALL python3-venv 2>/dev/null || true
    fi
fi

# pip
if ! command -v pip3 &>/dev/null; then
    curl -sS https://bootstrap.pypa.io/get-pip.py | "$PYTHON_BIN" - --quiet 2>/dev/null || true
fi
ok "Python: $("$PYTHON_BIN" --version)"

# ══════════════════════════════════════════════════════════════════════════════
# ── MariaDB Installation ─────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
step "Installing & configuring MariaDB"

install_mariadb() {
    if command -v mariadb &>/dev/null || command -v mysql &>/dev/null; then
        local db_version
        db_version=$(mariadb --version 2>/dev/null || mysql --version 2>/dev/null)
        ok "Database already installed: ${db_version}"
        return
    fi

    log "Installing MariaDB Server..."
    case "$OS_FAMILY" in
        debian)
            $PKG_INSTALL mariadb-server mariadb-client 2>/dev/null || \
                err "MariaDB could not be installed. Please install manually."
            ;;
        rhel|fedora)
            $PKG_INSTALL mariadb-server mariadb 2>/dev/null || \
                err "MariaDB could not be installed. Please install manually."
            ;;
        suse)
            $PKG_INSTALL mariadb mariadb-client 2>/dev/null || \
                err "MariaDB could not be installed. Please install manually."
            ;;
        arch)
            $PKG_INSTALL mariadb 2>/dev/null || \
                err "MariaDB could not be installed. Please install manually."
            # Arch requires explicit initialization
            if [[ ! -d /var/lib/mysql/mysql ]]; then
                mariadb-install-db --user=mysql --basedir=/usr --datadir=/var/lib/mysql 2>/dev/null || true
            fi
            ;;
    esac
    ok "MariaDB Server installed"
}

install_mariadb

# Start & enable MariaDB
if command -v systemctl &>/dev/null; then
    systemctl enable mariadb 2>/dev/null || systemctl enable mysql 2>/dev/null || true
    systemctl start  mariadb 2>/dev/null || systemctl start  mysql 2>/dev/null || true
else
    service mariadb start 2>/dev/null || service mysql start 2>/dev/null || true
fi
ok "MariaDB running"

# Enable cron (für nightly Backups + Health-Checks)
if command -v systemctl &>/dev/null; then
    systemctl enable cron 2>/dev/null || systemctl enable crond 2>/dev/null \
        || systemctl enable cronie 2>/dev/null || true
    systemctl start  cron 2>/dev/null || systemctl start  crond 2>/dev/null \
        || systemctl start  cronie 2>/dev/null || true
fi
ok "Cron service enabled"

# ══════════════════════════════════════════════════════════════════════════════
# ── Ollama (lokales LLM, optional) ───────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
LLM_ENDPOINT_DEFAULT=""
LLM_MODEL_DEFAULT=""
if [[ "$INSTALL_OLLAMA_CHOICE" == "yes" ]]; then
    step "Installing Ollama (lokales LLM)"
    if command -v ollama &>/dev/null; then
        ok "Ollama bereits installiert ($(ollama --version 2>/dev/null | head -1))"
    else
        log "Lade offiziellen Ollama-Installer..."
        if curl -fsSL https://ollama.com/install.sh | sh; then
            ok "Ollama installiert"
        else
            warn "Ollama-Installation fehlgeschlagen – überspringe Modell-Download"
            INSTALL_OLLAMA_CHOICE="no"
        fi
    fi

    if [[ "$INSTALL_OLLAMA_CHOICE" == "yes" ]]; then
        # Service aktivieren & starten
        if command -v systemctl &>/dev/null; then
            systemctl enable ollama 2>/dev/null || true
            systemctl start  ollama 2>/dev/null || true
        fi
        # Auf API warten (max. 20 s)
        for _ in {1..20}; do
            if curl -fs --max-time 2 http://127.0.0.1:11434/api/tags &>/dev/null; then
                break
            fi
            sleep 1
        done
        if curl -fs --max-time 2 http://127.0.0.1:11434/api/tags &>/dev/null; then
            ok "Ollama-API erreichbar auf http://127.0.0.1:11434"
        else
            warn "Ollama-API nicht erreichbar – Modell-Pull wird übersprungen"
            INSTALL_OLLAMA_CHOICE="no"
        fi
    fi

    if [[ "$INSTALL_OLLAMA_CHOICE" == "yes" && -n "$OLLAMA_MODEL_CHOICE" ]]; then
        log "Lade Modell '${OLLAMA_MODEL_CHOICE}' (kann einige Minuten dauern)..."
        if ollama pull "$OLLAMA_MODEL_CHOICE"; then
            ok "Modell '${OLLAMA_MODEL_CHOICE}' bereit"
            LLM_ENDPOINT_DEFAULT="http://127.0.0.1:11434/api/chat"
            LLM_MODEL_DEFAULT="$OLLAMA_MODEL_CHOICE"
        else
            warn "Modell-Pull fehlgeschlagen – kann später mit 'ollama pull ${OLLAMA_MODEL_CHOICE}' wiederholt werden"
        fi
    fi
fi

# ══════════════════════════════════════════════════════════════════════════════
# ── System User ──────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
step "Setting up system user"
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd --system --shell /bin/bash --home "$INSTALL_DIR" --create-home "$SERVICE_USER"
    ok "User '${SERVICE_USER}' created"
else
    ok "User '${SERVICE_USER}' already exists"
fi

# ══════════════════════════════════════════════════════════════════════════════
# ── Installation Directory ───────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
step "Installing bot files"
mkdir -p "$INSTALL_DIR"/{backups,logs,static}
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

# Download or copy
if [[ -f "./server.py" ]]; then
    log "Local files detected — copying..."
    # Copy all relevant files and directories
    for f in server.py trevlix_i18n.py validate_env.py requirements.txt \
              trevlix_translations.js motd.sh; do
        [[ -f "./$f" ]] && cp "./$f" "$INSTALL_DIR/$f" && ok "Copied: $f"
    done
    for d in app routes services templates static docker tests; do
        if [[ -d "./$d" ]]; then
            cp -r "./$d" "$INSTALL_DIR/$d" && ok "Copied: $d/"
        fi
    done
elif command -v git &>/dev/null; then
    log "Cloning repository: $REPO_URL"
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR/src" 2>/dev/null || \
        warn "Git clone failed — please copy files manually to $INSTALL_DIR"
else
    warn "No source files found. Please copy server.py & co. to $INSTALL_DIR."
fi

# ══════════════════════════════════════════════════════════════════════════════
# ── Python Virtual Environment ───────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
step "Creating Python virtual environment"
VENV_DIR="$INSTALL_DIR/venv"

if [[ ! -d "$VENV_DIR" ]]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR" || err "venv creation failed"
fi
ok "venv: $VENV_DIR"

VENV_PY="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

# pip upgrade
"$VENV_PIP" install --quiet --upgrade pip wheel setuptools

# ══════════════════════════════════════════════════════════════════════════════
# ── Python Packages ──────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
step "Installing Python dependencies"

# Always prefer requirements.txt; fall back to hardcoded list only if missing
if [[ -f "$INSTALL_DIR/requirements.txt" ]]; then
    log "Installing from requirements.txt..."
    "$VENV_PIP" install --quiet -r "$INSTALL_DIR/requirements.txt" && \
        ok "requirements.txt installed" || \
        warn "Some packages from requirements.txt failed"
else
    warn "requirements.txt not found — installing core packages individually"
    # Fallback core packages (eventlet intentionally excluded — server uses threading mode)
    CORE_PKGS=(
        "flask>=3.0.0"
        "flask-socketio>=5.3.6"
        "flask-cors>=4.0.0"
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
    for pkg in "${CORE_PKGS[@]}"; do
        "$VENV_PIP" install --quiet "$pkg" && ok "$pkg" || warn "Failed: $pkg"
    done
fi

# TensorFlow optional
if [[ "$SKIP_TF" == "false" && "$AUTO_NO" == "false" ]]; then
    echo ""
    read -rp "$(echo -e "${YELLOW}Install TensorFlow? (LSTM + Transformer AI, ~1.5GB) [y/N]:${RESET} ")" TF_CHOICE
    [[ "${TF_CHOICE,,}" == "y" || "${TF_CHOICE,,}" == "j" ]] && SKIP_TF=false || SKIP_TF=true
fi
if [[ "$SKIP_TF" == "false" ]]; then
    log "Installing TensorFlow (this may take several minutes)..."
    "$VENV_PIP" install --quiet tensorflow && ok "TensorFlow installed" || warn "TensorFlow failed — AI will run without LSTM"
else
    ok "TensorFlow skipped (--no-tf)"
fi

# SHAP optional
if [[ "$SKIP_SHAP" == "false" && "$AUTO_NO" == "false" ]]; then
    echo ""
    read -rp "$(echo -e "${YELLOW}Install SHAP? (AI explanations, ~200MB) [y/N]:${RESET} ")" SHAP_CHOICE
    [[ "${SHAP_CHOICE,,}" == "y" || "${SHAP_CHOICE,,}" == "j" ]] && SKIP_SHAP=false || SKIP_SHAP=true
fi
if [[ "$SKIP_SHAP" == "false" ]]; then
    "$VENV_PIP" install --quiet shap && ok "SHAP installed" || warn "SHAP failed"
else
    ok "SHAP skipped (--no-shap)"
fi

# ══════════════════════════════════════════════════════════════════════════════
# ── Generate Passwords & Secrets ─────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
step "Generating secure passwords & secrets"

if command -v openssl &>/dev/null; then
    DB_PASS=$(openssl rand -base64 18 | tr -d '/+=' | head -c 24)
    DB_ROOT_PASS=$(openssl rand -base64 18 | tr -d '/+=' | head -c 24)
    JWT_SECRET=$(openssl rand -hex 32)
    FLASK_SECRET=$(openssl rand -hex 32)
    DASH_SECRET=$(openssl rand -hex 32)
else
    DB_PASS="$(head -c 64 /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 24)"
    DB_ROOT_PASS="$(head -c 64 /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 24)"
    JWT_SECRET="$(head -c 128 /dev/urandom | tr -dc 'a-f0-9' | head -c 64)"
    FLASK_SECRET="$(head -c 128 /dev/urandom | tr -dc 'a-f0-9' | head -c 64)"
    DASH_SECRET="$(head -c 128 /dev/urandom | tr -dc 'a-f0-9' | head -c 64)"
fi

# Generate Fernet key (after venv creation, cryptography is now available)
if "$VENV_PY" -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" &>/dev/null 2>&1; then
    ENCRYPTION_KEY=$("$VENV_PY" -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
elif command -v openssl &>/dev/null; then
    ENCRYPTION_KEY=$(openssl rand -base64 32)
else
    ENCRYPTION_KEY="$(head -c 64 /dev/urandom | base64 | head -c 44)"
fi
ok "All secrets generated"

# ══════════════════════════════════════════════════════════════════════════════
# ── MariaDB Database & User Setup ────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
step "Setting up MariaDB database & user"

# Determine the MariaDB/MySQL client command
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
    ok "Database 'trevlix' and user created"
else
    warn "DB setup failed — please run manually: sudo $DB_CLIENT -u root"
fi

# Import schema if mysql-init.sql is present
INIT_SQL=""
if [[ -f "$INSTALL_DIR/docker/mysql-init.sql" ]]; then
    INIT_SQL="$INSTALL_DIR/docker/mysql-init.sql"
elif [[ -f "./docker/mysql-init.sql" ]]; then
    INIT_SQL="./docker/mysql-init.sql"
fi

if [[ -n "$INIT_SQL" ]]; then
    if $DB_CLIENT -u trevlix -p"${DB_PASS}" trevlix < "$INIT_SQL" 2>/dev/null; then
        ok "Database schema imported"
    else
        warn "Schema import failed — tables will be created automatically on first start"
    fi
fi

# ══════════════════════════════════════════════════════════════════════════════
# ── Create .env ──────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
step "Creating .env configuration file"

# Determine ALLOWED_ORIGINS
if [[ "$USE_DOMAIN" == "true" ]]; then
    ALLOWED_ORIGINS="https://${DOMAIN}"
else
    ALLOWED_ORIGINS="http://localhost:5000"
fi

if [[ ! -f "$INSTALL_DIR/.env" ]]; then
    cat > "$INSTALL_DIR/.env" << ENV_EOF
# TREVLIX v3.0.0 – Auto-generated on $(date)
# Never commit to git! (listed in .gitignore)

# ── Exchange (configure now!) ──────────────────────────────────
EXCHANGE=${EXCHANGE_CHOICE}
API_KEY=${EXCHANGE_API_KEY}
API_SECRET=${EXCHANGE_API_SECRET}

# ── MariaDB (auto-generated) ──────────────────────────────────
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=trevlix
MYSQL_PASS=${DB_PASS}
MYSQL_DB=trevlix

# ── Security (auto-generated) ─────────────────────────────────
ADMIN_USERNAME=${ADMIN_USER}
ADMIN_PASSWORD=${ADMIN_PASS}
DASHBOARD_SECRET=${DASH_SECRET}
JWT_SECRET=${JWT_SECRET}
SECRET_KEY=${FLASK_SECRET}
ENCRYPTION_KEY=${ENCRYPTION_KEY}
SESSION_TIMEOUT_MIN=30
ALLOWED_ORIGINS=${ALLOWED_ORIGINS}

# ── Trading (recommendation: start with paper trading!) ────────
PAPER_TRADING=${PAPER_TRADING_CHOICE}

# ── Registration ───────────────────────────────────────────────
ALLOW_REGISTRATION=false

# ── Features (optional) ───────────────────────────────────────
DISCORD_WEBHOOK=${DISCORD_WEBHOOK_CHOICE}
TELEGRAM_TOKEN=${TELEGRAM_TOKEN_CHOICE}
TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID_CHOICE}
CRYPTOPANIC_TOKEN=${CRYPTOPANIC_TOKEN_CHOICE}
CRYPTOPANIC_API_PLAN=free
BLOCKNATIVE_KEY=
LLM_ENDPOINT=${LLM_ENDPOINT_DEFAULT}
LLM_API_KEY=
LLM_MODEL=${LLM_MODEL_DEFAULT}
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=${OLLAMA_MODEL_CHOICE}

# ── Server ─────────────────────────────────────────────────────
PORT=5000
LANGUAGE=de
AUTO_START=${AUTO_START_CHOICE}
LOG_LEVEL=INFO
JSON_LOGS=false
COLOR_LOGS=true
ENV_EOF
    chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/.env"
    chmod 600 "$INSTALL_DIR/.env"
    ok ".env created (passwords auto-generated)"
else
    ok ".env already exists — not overwritten"
fi

# Update .env.example reference if present
if [[ -f "$INSTALL_DIR/.env.example" ]]; then
    ok ".env.example present"
fi

# ══════════════════════════════════════════════════════════════════════════════
# ── Systemd Service ──────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
step "Setting up systemd service"

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

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=${INSTALL_DIR}

[Install]
WantedBy=multi-user.target
SERVICE_EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
ok "Systemd service configured"
ok "Bot will start automatically after reboot"

# ══════════════════════════════════════════════════════════════════════════════
# ── Permissions ──────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
step "Setting permissions"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
chmod 750 "$INSTALL_DIR"
chmod 600 "$INSTALL_DIR/.env"
ok "Permissions set"

# ══════════════════════════════════════════════════════════════════════════════
# ── Cronjobs (Backup · Health-Check · Logrotate) ─────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
step "Installing cronjobs"

# 1) Nightly MariaDB-Backup-Skript
BACKUP_SCRIPT="${INSTALL_DIR}/scripts/backup_db.sh"
mkdir -p "${INSTALL_DIR}/scripts" "${INSTALL_DIR}/backups"
cat > "$BACKUP_SCRIPT" << 'BACKUP_EOF'
#!/usr/bin/env bash
# TREVLIX – Nightly DB backup (installed by install.sh)
set -euo pipefail
INSTALL_DIR="__INSTALL_DIR__"
ENV_FILE="${INSTALL_DIR}/.env"
BACKUP_DIR="${INSTALL_DIR}/backups"
mkdir -p "$BACKUP_DIR"
# .env einlesen (ohne export von Kommentaren)
set -a
# shellcheck disable=SC1090
[[ -f "$ENV_FILE" ]] && . "$ENV_FILE"
set +a
TS=$(date +%Y%m%d_%H%M%S)
OUT="${BACKUP_DIR}/trevlix_${TS}.sql.gz"
if command -v mariadb-dump &>/dev/null; then
    DUMP=mariadb-dump
elif command -v mysqldump &>/dev/null; then
    DUMP=mysqldump
else
    echo "no mysqldump / mariadb-dump available" >&2
    exit 1
fi
"$DUMP" -h "${MYSQL_HOST:-localhost}" -P "${MYSQL_PORT:-3306}" \
        -u "${MYSQL_USER:-trevlix}" "-p${MYSQL_PASS:-}" \
        --single-transaction --quick --lock-tables=false \
        "${MYSQL_DB:-trevlix}" 2>/dev/null | gzip > "$OUT"
# Alte Backups ausmisten (>14 Tage)
find "$BACKUP_DIR" -name 'trevlix_*.sql.gz' -mtime +14 -delete 2>/dev/null || true
BACKUP_EOF
sed -i "s|__INSTALL_DIR__|${INSTALL_DIR}|g" "$BACKUP_SCRIPT"
chmod 750 "$BACKUP_SCRIPT"
chown "${SERVICE_USER}:${SERVICE_USER}" "$BACKUP_SCRIPT"
ok "Backup-Skript: ${BACKUP_SCRIPT}"

# 2) Health-Check-Skript (neustart bei API-Ausfall)
HEALTH_SCRIPT="${INSTALL_DIR}/scripts/health_check.sh"
cat > "$HEALTH_SCRIPT" << 'HEALTH_EOF'
#!/usr/bin/env bash
# TREVLIX – Health-Check. Restartet den Service, wenn /api/v1/status nicht antwortet.
set -euo pipefail
PORT=$(grep -i '^PORT=' __INSTALL_DIR__/.env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]"')
PORT="${PORT:-5000}"
if ! curl -fs --max-time 5 "http://127.0.0.1:${PORT}/api/v1/status" >/dev/null; then
    logger -t trevlix-health "API nicht erreichbar – Service-Neustart"
    systemctl restart trevlix 2>/dev/null || true
fi
HEALTH_EOF
sed -i "s|__INSTALL_DIR__|${INSTALL_DIR}|g" "$HEALTH_SCRIPT"
chmod 750 "$HEALTH_SCRIPT"
chown "root:root" "$HEALTH_SCRIPT"
ok "Health-Check-Skript: ${HEALTH_SCRIPT}"

# 3) Cron-Datei in /etc/cron.d (systemweit, definierte User)
CRON_FILE="/etc/cron.d/trevlix"
cat > "$CRON_FILE" << CRON_EOF
# TREVLIX – Automatische Wartungsjobs (auto-generated)
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
MAILTO=""
# Nightly DB-Backup um 03:17
17 3 * * * ${SERVICE_USER} ${BACKUP_SCRIPT} >> ${INSTALL_DIR}/logs/backup.log 2>&1
# Health-Check alle 5 Minuten (root, damit Neustart funktioniert)
*/5 * * * * root ${HEALTH_SCRIPT} >> ${INSTALL_DIR}/logs/health.log 2>&1
CRON_EOF
chmod 644 "$CRON_FILE"
ok "Cron-Datei: ${CRON_FILE}"

# 4) Logrotate
LOGROTATE_FILE="/etc/logrotate.d/trevlix"
if [[ -d /etc/logrotate.d ]]; then
    cat > "$LOGROTATE_FILE" << LOGR_EOF
${INSTALL_DIR}/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
    su ${SERVICE_USER} ${SERVICE_USER}
}
LOGR_EOF
    chmod 644 "$LOGROTATE_FILE"
    ok "Logrotate konfiguriert: ${LOGROTATE_FILE}"
fi

# Cron neu laden
if command -v systemctl &>/dev/null; then
    systemctl reload cron 2>/dev/null || systemctl reload crond 2>/dev/null \
        || systemctl restart cron 2>/dev/null || systemctl restart crond 2>/dev/null || true
fi

# ══════════════════════════════════════════════════════════════════════════════
# ── Nginx + SSL (Domain Setup) ───────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
if [[ "$USE_DOMAIN" == "true" ]]; then
    step "Setting up Nginx reverse proxy"

    # Install Nginx
    if ! command -v nginx &>/dev/null; then
        case "$OS_FAMILY" in
            debian)  $PKG_INSTALL nginx || err "Nginx could not be installed" ;;
            rhel|fedora) $PKG_INSTALL nginx || err "Nginx could not be installed" ;;
            suse)    $PKG_INSTALL nginx || err "Nginx could not be installed" ;;
            arch)    $PKG_INSTALL nginx || err "Nginx could not be installed" ;;
        esac
    fi
    ok "Nginx installed"

    # Determine sites directory (Debian-style vs conf.d)
    NGINX_SITES_AVAILABLE="/etc/nginx/sites-available"
    NGINX_SITES_ENABLED="/etc/nginx/sites-enabled"
    NGINX_USE_CONFD=false

    if [[ ! -d "$NGINX_SITES_AVAILABLE" ]]; then
        # RHEL/Fedora/SUSE/Arch use conf.d
        NGINX_USE_CONFD=true
        mkdir -p /etc/nginx/conf.d
    fi

    # Write Nginx configuration
    if [[ "$NGINX_USE_CONFD" == "true" ]]; then
        NGINX_CONF="/etc/nginx/conf.d/trevlix.conf"
    else
        NGINX_CONF="$NGINX_SITES_AVAILABLE/trevlix"
    fi

    cat > "$NGINX_CONF" << NGINX_EOF
# TREVLIX – Nginx Reverse Proxy (auto-generated)
# Domain: ${DOMAIN}

# Rate-Limiting
limit_req_zone \$binary_remote_addr zone=trevlix_login:10m rate=5r/m;
limit_req_zone \$binary_remote_addr zone=trevlix_api:10m rate=30r/s;

# Upstream
upstream trevlix_backend {
    server 127.0.0.1:5000;
    keepalive 32;
}

# HTTP → HTTPS Redirect (adjusted by Certbot)
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

    # SSL certificates (inserted by Certbot)
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

    # General proxy settings
    proxy_set_header Host              \$host;
    proxy_set_header X-Real-IP         \$remote_addr;
    proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;

    proxy_buffer_size          128k;
    proxy_buffers              4 256k;
    proxy_busy_buffers_size    256k;

    # Login & Registration (Rate-Limited)
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

    # Static Assets (Cache)
    location /static/ {
        proxy_pass http://trevlix_backend;
        proxy_cache_valid 200 1h;
        add_header Cache-Control "public, max-age=3600";
    }

    # All other routes
    location / {
        proxy_pass         http://trevlix_backend;
        proxy_read_timeout 120s;
    }

    # Error pages
    error_page 502 503 504 /50x.html;
    location = /50x.html {
        root /usr/share/nginx/html;
        internal;
    }

    # Block hidden files
    location ~ /\. {
        deny all;
        return 404;
    }
}
NGINX_EOF

    # Enable site (Debian-style symlink)
    if [[ "$NGINX_USE_CONFD" == "false" ]]; then
        ln -sf "$NGINX_SITES_AVAILABLE/trevlix" "$NGINX_SITES_ENABLED/trevlix"
        rm -f "$NGINX_SITES_ENABLED/default" 2>/dev/null || true
    fi
    ok "Nginx configuration created for ${DOMAIN}"

    # ── Certbot SSL Certificate ──────────────────────────────────────────
    step "SSL certificate with Let's Encrypt (Certbot)"

    # Install Certbot
    if ! command -v certbot &>/dev/null; then
        case "$OS_FAMILY" in
            debian)
                $PKG_INSTALL certbot python3-certbot-nginx || \
                    warn "Certbot could not be installed"
                ;;
            rhel|fedora)
                $PKG_INSTALL certbot python3-certbot-nginx || \
                    warn "Certbot could not be installed"
                ;;
            suse)
                $PKG_INSTALL certbot python3-certbot-nginx || \
                    warn "Certbot could not be installed"
                ;;
            arch)
                $PKG_INSTALL certbot certbot-nginx || \
                    warn "Certbot could not be installed"
                ;;
        esac
    fi

    if command -v certbot &>/dev/null; then
        log "Creating SSL certificate for ${DOMAIN}..."
        echo ""
        read -rp "$(echo -e "${CYAN}E-mail for Let's Encrypt (for renewal notices): ${RESET}")" LE_EMAIL

        if [[ -n "$LE_EMAIL" ]]; then
            # Temporary Nginx config without SSL for Certbot
            if [[ "$NGINX_USE_CONFD" == "true" ]]; then
                TEMP_CONF="/etc/nginx/conf.d/trevlix-temp.conf"
            else
                TEMP_CONF="$NGINX_SITES_AVAILABLE/trevlix-temp"
            fi

            cat > "$TEMP_CONF" << TEMP_EOF
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

            if [[ "$NGINX_USE_CONFD" == "false" ]]; then
                ln -sf "$TEMP_CONF" "$NGINX_SITES_ENABLED/trevlix"
            else
                # Temporarily disable main config
                mv "$NGINX_CONF" "${NGINX_CONF}.bak" 2>/dev/null || true
            fi

            nginx -t 2>/dev/null && systemctl restart nginx 2>/dev/null || true

            if certbot certonly --nginx -d "$DOMAIN" --non-interactive \
                --agree-tos --email "$LE_EMAIL" --redirect 2>/dev/null; then
                ok "SSL certificate created for ${DOMAIN}"

                # Restore full Nginx config
                if [[ "$NGINX_USE_CONFD" == "false" ]]; then
                    ln -sf "$NGINX_SITES_AVAILABLE/trevlix" "$NGINX_SITES_ENABLED/trevlix"
                    rm -f "$TEMP_CONF"
                else
                    mv "${NGINX_CONF}.bak" "$NGINX_CONF" 2>/dev/null || true
                    rm -f "$TEMP_CONF"
                fi

                # Check Certbot auto-renewal timer
                if systemctl is-active --quiet certbot.timer 2>/dev/null; then
                    ok "Certbot auto-renewal active"
                else
                    systemctl enable --now certbot.timer 2>/dev/null || true
                    ok "Certbot auto-renewal enabled"
                fi
            else
                warn "SSL certificate could not be created"
                warn "Ensure that domain ${DOMAIN} points to this server (DNS A record)"
                warn "Try manually later: sudo certbot --nginx -d ${DOMAIN}"
                # Keep temp config (works without SSL)
                if [[ "$NGINX_USE_CONFD" == "true" ]]; then
                    mv "${NGINX_CONF}.bak" "$NGINX_CONF" 2>/dev/null || true
                    rm -f "$TEMP_CONF"
                else
                    ln -sf "$TEMP_CONF" "$NGINX_SITES_ENABLED/trevlix"
                fi
            fi
        else
            warn "No email provided — SSL certificate will not be created"
            warn "Create manually: sudo certbot --nginx -d ${DOMAIN}"
        fi
    else
        warn "Certbot not available — SSL must be configured manually"
    fi

    # Start/restart Nginx
    nginx -t 2>/dev/null && systemctl enable nginx && systemctl restart nginx && \
        ok "Nginx started" || warn "Nginx start failed — check config: sudo nginx -t"
fi

# ══════════════════════════════════════════════════════════════════════════════
# ── UFW Firewall ─────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
step "Configuring UFW firewall"

if ! command -v ufw &>/dev/null; then
    case "$OS_FAMILY" in
        debian)  $PKG_INSTALL ufw || warn "UFW could not be installed" ;;
        rhel|fedora) $PKG_INSTALL ufw 2>/dev/null || warn "UFW not available — consider using firewalld" ;;
        suse)    $PKG_INSTALL ufw 2>/dev/null || warn "UFW not available — consider using firewalld" ;;
        arch)    $PKG_INSTALL ufw || warn "UFW could not be installed" ;;
    esac
fi

if command -v ufw &>/dev/null; then
    # Don't delete existing rules, only add
    ufw default deny incoming 2>/dev/null || true
    ufw default allow outgoing 2>/dev/null || true

    # Always allow SSH (prevent lockout!)
    ufw allow ssh comment "SSH" 2>/dev/null || true
    ok "UFW: SSH allowed"

    if [[ "$USE_DOMAIN" == "true" ]]; then
        # With domain: HTTP/HTTPS for Nginx, no direct port 5000
        ufw allow 80/tcp comment "HTTP (Nginx)" 2>/dev/null || true
        ufw allow 443/tcp comment "HTTPS (Nginx)" 2>/dev/null || true
        ok "UFW: HTTP (80) and HTTPS (443) opened"

        # Port 5000 internal only (Nginx proxy) — no external access needed
        ufw deny 5000/tcp comment "TREVLIX internal (via Nginx only)" 2>/dev/null || true
        ok "UFW: Port 5000 internal only via Nginx"
    else
        # Without domain: open port 5000 directly
        ufw allow 5000/tcp comment "TREVLIX Dashboard" 2>/dev/null || true
        ok "UFW: Port 5000 opened"
    fi

    # Enable UFW (non-interactive)
    echo "y" | ufw enable 2>/dev/null || true
    ok "UFW firewall enabled"
else
    warn "UFW not available — configure firewall manually"
    # Hint for firewalld users
    if command -v firewall-cmd &>/dev/null; then
        log "firewalld detected — applying basic rules..."
        firewall-cmd --permanent --add-service=ssh 2>/dev/null || true
        if [[ "$USE_DOMAIN" == "true" ]]; then
            firewall-cmd --permanent --add-service=http 2>/dev/null || true
            firewall-cmd --permanent --add-service=https 2>/dev/null || true
        else
            firewall-cmd --permanent --add-port=5000/tcp 2>/dev/null || true
        fi
        firewall-cmd --reload 2>/dev/null || true
        ok "firewalld rules applied"
    fi
fi

# ══════════════════════════════════════════════════════════════════════════════
# ── Fail2ban ─────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
step "Installing & configuring Fail2ban"

if ! command -v fail2ban-client &>/dev/null; then
    case "$OS_FAMILY" in
        debian)      $PKG_INSTALL fail2ban || warn "Fail2ban could not be installed" ;;
        rhel|fedora) $PKG_INSTALL fail2ban || warn "Fail2ban could not be installed" ;;
        suse)        $PKG_INSTALL fail2ban || warn "Fail2ban could not be installed" ;;
        arch)        $PKG_INSTALL fail2ban || warn "Fail2ban could not be installed" ;;
    esac
fi

if command -v fail2ban-client &>/dev/null; then
    # Determine auth log path (varies by OS)
    AUTH_LOG="/var/log/auth.log"
    if [[ ! -f "$AUTH_LOG" ]]; then
        # RHEL/Fedora/SUSE use /var/log/secure or journald
        if [[ -f /var/log/secure ]]; then
            AUTH_LOG="/var/log/secure"
        fi
    fi

    # Determine banaction based on available firewall
    FAIL2BAN_BANACTION="ufw"
    if ! command -v ufw &>/dev/null; then
        if command -v firewall-cmd &>/dev/null; then
            FAIL2BAN_BANACTION="firewallcmd-ipset"
        else
            FAIL2BAN_BANACTION="iptables-multiport"
        fi
    fi

    # Jail configuration for Trevlix + SSH
    cat > /etc/fail2ban/jail.local << F2B_EOF
# TREVLIX Fail2ban Configuration (auto-generated)
[DEFAULT]
bantime  = 3600
findtime = 600
maxretry = 5
banaction = ${FAIL2BAN_BANACTION}

# ── SSH Protection ─────────────────────────────────────────────
[sshd]
enabled  = true
port     = ssh
filter   = sshd
logpath  = ${AUTH_LOG}
maxretry = 3
bantime  = 7200
F2B_EOF

    # Nginx filter only for domain setup
    if [[ "$USE_DOMAIN" == "true" ]]; then
        cat >> /etc/fail2ban/jail.local << F2B_NGINX_EOF

# ── Nginx Protection ──────────────────────────────────────────
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

    # Trevlix login protection filter
    cat > /etc/fail2ban/filter.d/trevlix-login.conf << F2B_FILTER_EOF
# Fail2ban filter for TREVLIX failed login attempts
[Definition]
failregex = ^.*Login fehlgeschlagen.*IP=<HOST>.*$
            ^.*Failed login.*IP=<HOST>.*$
            ^.*401.*<HOST>.*login.*$
ignoreregex =
F2B_FILTER_EOF

    cat >> /etc/fail2ban/jail.local << F2B_TREVLIX_EOF

# ── TREVLIX Login Protection ──────────────────────────────────
[trevlix-login]
enabled  = true
port     = 5000
filter   = trevlix-login
logpath  = ${INSTALL_DIR}/logs/trevlix.log
maxretry = 5
bantime  = 3600
findtime = 300
F2B_TREVLIX_EOF

    # Start Fail2ban
    systemctl enable fail2ban 2>/dev/null || true
    systemctl restart fail2ban 2>/dev/null || true
    ok "Fail2ban installed and configured"
    ok "SSH: max 3 attempts (2h ban)"
    if [[ "$USE_DOMAIN" == "true" ]]; then
        ok "Nginx: HTTP-Auth, bot protection, rate-limit"
    fi
    ok "Trevlix: max 5 login attempts (1h ban)"
else
    warn "Fail2ban not available"
fi

# ══════════════════════════════════════════════════════════════════════════════
# ── MOTD Installation ────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
step "Installing MOTD"

if [[ -f "$INSTALL_DIR/motd.sh" ]]; then
    if bash "$INSTALL_DIR/motd.sh" --install 2>/dev/null; then
        ok "MOTD installed successfully"
    else
        warn "MOTD installation failed (non-critical)"
    fi
else
    ok "motd.sh not found — skipping MOTD installation"
fi

# ══════════════════════════════════════════════════════════════════════════════
# ── Save Credentials to File ─────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
step "Saving credentials"

CREDENTIALS_FILE="$INSTALL_DIR/.credentials"
cat > "$CREDENTIALS_FILE" << CRED_EOF
# ══════════════════════════════════════════════════════════════════
# TREVLIX v3.0.0 – Credentials (auto-generated on $(date))
# KEEP THIS FILE SAFE! Delete after noting down credentials.
# ══════════════════════════════════════════════════════════════════

# ── Admin Login ────────────────────────────────────────────────
Admin Username: ${ADMIN_USER}
Admin Password: ${ADMIN_PASS}

# ── MariaDB ────────────────────────────────────────────────────
Database:       trevlix
DB User:        trevlix
DB Password:    ${DB_PASS}
DB Root Pass:   ${DB_ROOT_PASS}
CRED_EOF

chown "$SERVICE_USER:$SERVICE_USER" "$CREDENTIALS_FILE"
chmod 600 "$CREDENTIALS_FILE"
ok "Credentials saved to ${CREDENTIALS_FILE} (chmod 600)"

# ══════════════════════════════════════════════════════════════════════════════
# ── Start Bot ────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
step "Starting TREVLIX"
systemctl start "$SERVICE_NAME" && ok "Bot started (systemctl)" || \
    warn "Start failed — check manually: sudo systemctl status trevlix"

# Installation successful – deactivate trap
_CLEANUP_DONE=true

# ══════════════════════════════════════════════════════════════════════════════
# ── Summary ──────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

echo ""
echo -e "${JADE}╔══════════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${JADE}║${RESET}  ${BOLD}${GREEN}TREVLIX SUCCESSFULLY INSTALLED!${RESET}                                ${JADE}║${RESET}"
echo -e "${JADE}╠══════════════════════════════════════════════════════════════════╣${RESET}"

if [[ "$USE_DOMAIN" == "true" ]]; then
    echo -e "${JADE}║${RESET}  ${BOLD}Dashboard:${RESET}    https://${DOMAIN}                                   ${JADE}║${RESET}"
else
    echo -e "${JADE}║${RESET}  ${BOLD}Dashboard:${RESET}    http://${IP}:5000                                   ${JADE}║${RESET}"
fi

echo -e "${JADE}║${RESET}  ${BOLD}Install-Dir:${RESET}  ${INSTALL_DIR}                                         ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}  ${BOLD}OS:${RESET}           ${OS_ID} ${OS_VER} (${OS_FAMILY})                      ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}                                                                  ${JADE}║${RESET}"
echo -e "${JADE}╠══════════════════════════════════════════════════════════════════╣${RESET}"
echo -e "${JADE}║${RESET}  ${BOLD}${CYAN}CREDENTIALS${RESET}                                                    ${JADE}║${RESET}"
echo -e "${JADE}╠══════════════════════════════════════════════════════════════════╣${RESET}"
echo -e "${JADE}║${RESET}  ${BOLD}Admin Login:${RESET}                                                   ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}    Username:  ${BOLD}${ADMIN_USER}${RESET}                                             ${JADE}║${RESET}"

if [[ "$ADMIN_PASS_GENERATED" == "true" ]]; then
    echo -e "${JADE}║${RESET}    Password:  ${BOLD}(see ${CREDENTIALS_FILE})${RESET}            ${JADE}║${RESET}"
else
    echo -e "${JADE}║${RESET}    Password:  ${BOLD}(as entered)${RESET}                                          ${JADE}║${RESET}"
fi

echo -e "${JADE}║${RESET}                                                                  ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}  ${BOLD}MariaDB:${RESET}                                                       ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}    Database:  ${BOLD}trevlix${RESET}                                              ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}    User:      ${BOLD}trevlix${RESET}                                              ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}    Password:  ${BOLD}(see ${CREDENTIALS_FILE})${RESET}            ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}                                                                  ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}  ${YELLOW}All credentials saved to:${RESET}                                      ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}  ${BOLD}${CREDENTIALS_FILE}${RESET}                               ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}                                                                  ${JADE}║${RESET}"
echo -e "${JADE}╠══════════════════════════════════════════════════════════════════╣${RESET}"
echo -e "${JADE}║${RESET}  ${YELLOW}Next steps:${RESET}                                                    ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}  1. Add API keys:          nano ${INSTALL_DIR}/.env                 ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}  2. Restart bot:            systemctl restart trevlix               ${JADE}║${RESET}"

if [[ "$USE_DOMAIN" == "true" ]]; then
    echo -e "${JADE}║${RESET}  3. Check DNS:              ${DOMAIN} -> ${IP}                   ${JADE}║${RESET}"
fi

echo -e "${JADE}╠══════════════════════════════════════════════════════════════════╣${RESET}"
echo -e "${JADE}║${RESET}  ${DIM}Bot commands:${RESET}                                                   ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}    systemctl status trevlix    ${DIM}# Status${RESET}                           ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}    systemctl restart trevlix   ${DIM}# Restart${RESET}                          ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}    journalctl -u trevlix -f    ${DIM}# Live logs${RESET}                        ${JADE}║${RESET}"

if [[ "$USE_DOMAIN" == "true" ]]; then
    echo -e "${JADE}║${RESET}    certbot renew --dry-run    ${DIM}# Test SSL${RESET}                       ${JADE}║${RESET}"
fi

echo -e "${JADE}║${RESET}    fail2ban-client status      ${DIM}# Firewall status${RESET}                  ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}    ufw status                  ${DIM}# UFW rules${RESET}                        ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}                                                                  ${JADE}║${RESET}"
echo -e "${JADE}║${RESET}  ${DIM}Log: ${LOG_FILE}${RESET}                                  ${JADE}║${RESET}"
echo -e "${JADE}╚══════════════════════════════════════════════════════════════════╝${RESET}"
echo ""
echo -e "  ${RED}IMPORTANT: Start with paper trading mode first!${RESET}"
echo -e "  ${DIM}PAPER_TRADING=true is already set in .env.${RESET}"
echo ""
echo -e "  ${DIM}Multi-Exchange: Crypto.com, Binance, Bybit, OKX, KuCoin${RESET}"
echo -e "  ${DIM}Configure: nano ${INSTALL_DIR}/.env${RESET}"
echo ""
