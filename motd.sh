#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TREVLIX – Message of the Day (MOTD)                                        ║
# ║  Ubuntu 16.04–24.04 kompatibel                                              ║
# ║  Installation: sudo bash motd.sh --install                                  ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

set -euo pipefail

# ── Farben ─────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'
JADE='\033[38;5;47m'
ORANGE='\033[38;5;214m'

# ── Konfiguration ──────────────────────────────────────────────────────────────
INSTALL_DIR="/opt/trevlix"
SERVICE_NAME="trevlix"
MOTD_SCRIPT="/etc/update-motd.d/99-trevlix"
MOTD_STATIC="/etc/motd"

# ── Installation / Deinstallation ─────────────────────────────────────────────
if [[ "${1:-}" == "--install" ]]; then
    if [[ $EUID -ne 0 ]]; then
        echo "Bitte als root ausführen: sudo bash motd.sh --install"
        exit 1
    fi

    # Altes statisches MOTD deaktivieren
    if [[ -f "$MOTD_STATIC" ]]; then
        cp "$MOTD_STATIC" "${MOTD_STATIC}.bak"
        : > "$MOTD_STATIC"
    fi

    # Eventuell vorhandene Standard-MOTD-Skripte deaktivieren
    for f in /etc/update-motd.d/10-help-text \
              /etc/update-motd.d/50-landscape-sysinfo \
              /etc/update-motd.d/51-cloudguest \
              /etc/update-motd.d/80-livepatch; do
        [[ -f "$f" ]] && chmod -x "$f" 2>/dev/null || true
    done

    # Dieses Skript als MOTD-Provider einrichten
    cp "$(realpath "$0")" "$MOTD_SCRIPT"
    chmod +x "$MOTD_SCRIPT"

    echo -e "${GREEN}✓ TREVLIX MOTD installiert: ${MOTD_SCRIPT}${RESET}"
    echo -e "${DIM}  Aktiv beim nächsten SSH-Login.${RESET}"
    exit 0
fi

if [[ "${1:-}" == "--uninstall" ]]; then
    if [[ $EUID -ne 0 ]]; then
        echo "Bitte als root ausführen: sudo bash motd.sh --uninstall"
        exit 1
    fi
    rm -f "$MOTD_SCRIPT"
    [[ -f "${MOTD_STATIC}.bak" ]] && cp "${MOTD_STATIC}.bak" "$MOTD_STATIC" || true
    echo -e "${GREEN}✓ TREVLIX MOTD entfernt.${RESET}"
    exit 0
fi

# ── Hilfsfunktionen ────────────────────────────────────────────────────────────

# Servicestatus ermitteln (systemd + SysV kompatibel)
_service_status() {
    local svc="$1"
    if command -v systemctl &>/dev/null && systemctl is-active --quiet "$svc" 2>/dev/null; then
        echo "running"
    elif command -v service &>/dev/null && service "$svc" status &>/dev/null 2>&1; then
        echo "running"
    else
        echo "stopped"
    fi
}

# RAM-Nutzung in MB
_ram_used_mb() {
    awk '/MemTotal/{t=$2} /MemAvailable/{a=$2} END{printf "%d", (t-a)/1024}' /proc/meminfo 2>/dev/null || echo "?"
}
_ram_total_mb() {
    awk '/MemTotal/{printf "%d", $2/1024}' /proc/meminfo 2>/dev/null || echo "?"
}

# Festplattennutzung für /
_disk_used() {
    df -h / 2>/dev/null | awk 'NR==2{print $3"/"$2" ("$5")"}' || echo "?"
}

# Systemlast
_load_avg() {
    if [[ -f /proc/loadavg ]]; then
        awk '{print $1" "$2" "$3}' /proc/loadavg
    else
        uptime | awk -F'load average[s]?:' '{print $2}' | xargs
    fi
}

# Uptime in menschenlesbarem Format
_uptime_human() {
    if command -v uptime &>/dev/null; then
        uptime -p 2>/dev/null || uptime | sed 's/.*up \([^,]*\).*/\1/'
    else
        echo "?"
    fi
}

# IP-Adressen (erste IPv4, exkl. loopback)
_ip_addr() {
    hostname -I 2>/dev/null | tr ' ' '\n' | grep -v '^$' | grep -v '^127\.' | head -1 || echo "?"
}

# Anzahl offener Sessions
_sessions() {
    who 2>/dev/null | wc -l || echo "?"
}

# Letzter Login (nur wenn last verfügbar)
_last_login() {
    last -1 -w 2>/dev/null | head -1 | awk '{print $1" "$3" "$4" "$5" "$6}' 2>/dev/null || echo "?"
}

# Trevlix Bot-Version aus INSTALL_DIR oder Git
_trevlix_version() {
    local ver_file="${INSTALL_DIR}/VERSION"
    if [[ -f "$ver_file" ]]; then
        cat "$ver_file" | tr -d '[:space:]'
    elif [[ -f "${INSTALL_DIR}/.git/HEAD" ]]; then
        git -C "$INSTALL_DIR" describe --tags --abbrev=4 2>/dev/null || echo "dev"
    else
        echo "1.0.4"
    fi
}

# Trading-Modus aus .env lesen
_trading_mode() {
    local env_file="${INSTALL_DIR}/.env"
    if [[ -f "$env_file" ]]; then
        local paper
        paper=$(grep -i '^PAPER_TRADING=' "$env_file" 2>/dev/null | cut -d= -f2 | tr -d '[:space:]"' || echo "true")
        if [[ "${paper,,}" == "true" || "${paper,,}" == "1" ]]; then
            echo "PAPER"
        else
            echo "LIVE"
        fi
    else
        echo "N/A"
    fi
}

# Exchange aus .env lesen
_exchange() {
    local env_file="${INSTALL_DIR}/.env"
    if [[ -f "$env_file" ]]; then
        grep -i '^EXCHANGE=' "$env_file" 2>/dev/null | cut -d= -f2 | tr -d '[:space:]"' | tr '[:lower:]' '[:upper:]' || echo "N/A"
    else
        echo "N/A"
    fi
}

# Dashboard-Port aus .env lesen
_dashboard_port() {
    local env_file="${INSTALL_DIR}/.env"
    if [[ -f "$env_file" ]]; then
        grep -i '^PORT=' "$env_file" 2>/dev/null | cut -d= -f2 | tr -d '[:space:]"' || echo "5000"
    else
        echo "5000"
    fi
}

# ── Daten sammeln ─────────────────────────────────────────────────────────────
HOSTNAME_VAL=$(hostname -s 2>/dev/null || echo "?")
OS_PRETTY=$(grep PRETTY_NAME /etc/os-release 2>/dev/null | cut -d'"' -f2 || echo "Linux")
KERNEL=$(uname -r 2>/dev/null || echo "?")
UPTIME=$(_uptime_human)
LOAD=$(_load_avg)
RAM_USED=$(_ram_used_mb)
RAM_TOTAL=$(_ram_total_mb)
DISK=$(_disk_used)
IP=$(_ip_addr)
SESSIONS=$(_sessions)
DATE_NOW=$(date '+%A, %d. %B %Y · %H:%M Uhr' 2>/dev/null || date)

TREVLIX_STATUS=$(_service_status "$SERVICE_NAME")
TREVLIX_VERSION=$(_trevlix_version)
TRADING_MODE=$(_trading_mode)
EXCHANGE=$(_exchange)
DASH_PORT=$(_dashboard_port)

# ── Status-Farbe ──────────────────────────────────────────────────────────────
if [[ "$TREVLIX_STATUS" == "running" ]]; then
    STATUS_COLOR="${GREEN}"
    STATUS_ICON="●"
    STATUS_TEXT="Aktiv"
else
    STATUS_COLOR="${RED}"
    STATUS_ICON="○"
    STATUS_TEXT="Gestoppt"
fi

if [[ "$TRADING_MODE" == "LIVE" ]]; then
    MODE_COLOR="${RED}"
else
    MODE_COLOR="${CYAN}"
fi

# ── MOTD Ausgabe ──────────────────────────────────────────────────────────────
echo ""
echo -e "${JADE}  ████████╗██████╗ ███████╗██╗   ██╗██╗     ██╗██╗  ██╗${RESET}"
echo -e "${JADE}     ██╔══╝██╔══██╗██╔════╝██║   ██║██║     ██║╚██╗██╔╝${RESET}"
echo -e "${JADE}     ██║   ██████╔╝█████╗  ██║   ██║██║     ██║ ╚███╔╝ ${RESET}"
echo -e "${JADE}     ██║   ██╔══██╗██╔══╝  ╚██╗ ██╔╝██║     ██║ ██╔██╗ ${RESET}"
echo -e "${JADE}     ██║   ██║  ██║███████╗ ╚████╔╝ ███████╗██║██╔╝ ██╗${RESET}"
echo -e "${JADE}     ╚═╝   ╚═╝  ╚═╝╚══════╝  ╚═══╝  ╚══════╝╚═╝╚═╝  ╚═╝${RESET}"
echo -e "  ${DIM}Algorithmic Trading Intelligence  ·  v${TREVLIX_VERSION}${RESET}"
echo ""

echo -e "${JADE}╔══════════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${JADE}║${RESET}  ${BOLD}${DATE_NOW}${RESET}"
echo -e "${JADE}╠══════════════════════════════════════════════════════════════════╣${RESET}"

# System-Infos
printf "${JADE}║${RESET}  %-18s ${DIM}%s${RESET}\n" "Hostname:"    "$HOSTNAME_VAL"
printf "${JADE}║${RESET}  %-18s ${DIM}%s${RESET}\n" "System:"      "$OS_PRETTY"
printf "${JADE}║${RESET}  %-18s ${DIM}%s${RESET}\n" "Kernel:"      "$KERNEL"
printf "${JADE}║${RESET}  %-18s ${DIM}%s${RESET}\n" "IP-Adresse:"  "$IP"
printf "${JADE}║${RESET}  %-18s ${DIM}%s${RESET}\n" "Uptime:"      "$UPTIME"
printf "${JADE}║${RESET}  %-18s ${DIM}%s${RESET}\n" "Load (1/5/15):" "$LOAD"
printf "${JADE}║${RESET}  %-18s ${DIM}%s MB / %s MB${RESET}\n" "RAM:"    "$RAM_USED" "$RAM_TOTAL"
printf "${JADE}║${RESET}  %-18s ${DIM}%s${RESET}\n" "Festplatte:"  "$DISK"
printf "${JADE}║${RESET}  %-18s ${DIM}%s aktiv${RESET}\n" "Sessions:"  "$SESSIONS"

echo -e "${JADE}╠══════════════════════════════════════════════════════════════════╣${RESET}"

# Trevlix Bot-Status
printf "${JADE}║${RESET}  %-18s ${STATUS_COLOR}${BOLD}${STATUS_ICON} %s${RESET}\n" "Trevlix Bot:" "$STATUS_TEXT"
printf "${JADE}║${RESET}  %-18s ${MODE_COLOR}${BOLD}%s${RESET}\n" "Trading-Modus:" "$TRADING_MODE"
printf "${JADE}║${RESET}  %-18s ${DIM}%s${RESET}\n" "Exchange:" "$EXCHANGE"
printf "${JADE}║${RESET}  %-18s ${CYAN}http://%s:%s${RESET}\n" "Dashboard:" "$IP" "$DASH_PORT"

echo -e "${JADE}╠══════════════════════════════════════════════════════════════════╣${RESET}"

# Quick-Reference
echo -e "${JADE}║${RESET}  ${BOLD}Schnellbefehle:${RESET}"
echo -e "${JADE}║${RESET}  ${GREEN}systemctl status  trevlix${RESET}   # Bot-Status"
echo -e "${JADE}║${RESET}  ${GREEN}systemctl restart trevlix${RESET}   # Neustart"
echo -e "${JADE}║${RESET}  ${GREEN}journalctl -u trevlix -f${RESET}    # Live-Logs"
printf "${JADE}║${RESET}  ${GREEN}%-26s${RESET} # Konfiguration\n" "nano ${INSTALL_DIR}/.env"

if [[ "$TRADING_MODE" == "LIVE" ]]; then
    echo -e "${JADE}╠══════════════════════════════════════════════════════════════════╣${RESET}"
    echo -e "${JADE}║${RESET}  ${RED}${BOLD}⚠  LIVE-TRADING AKTIV – Trades werden mit echtem Geld ausgeführt!${RESET}"
fi

echo -e "${JADE}╚══════════════════════════════════════════════════════════════════╝${RESET}"
echo ""
