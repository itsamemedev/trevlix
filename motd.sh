#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TREVLIX – Message of the Day (MOTD) v2.0.0                                ║
# ║  Kompatibel mit: Debian, Ubuntu, Raspberry Pi OS, CentOS, Rocky, Alma,    ║
# ║                  Fedora, RHEL, openSUSE, Arch Linux, Linux Mint            ║
# ║                                                                              ║
# ║  Installation:    sudo bash motd.sh --install                               ║
# ║  Deinstallation:  sudo bash motd.sh --uninstall                             ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

# Keine strict mode im MOTD-Betrieb (wird bei jedem Login ausgeführt –
# ein Fehler darf nicht den Login blockieren)
if [[ "${1:-}" == "--install" || "${1:-}" == "--uninstall" ]]; then
    set -euo pipefail
fi

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
BLUE='\033[38;5;33m'
MAGENTA='\033[38;5;165m'

# ── Konfiguration ──────────────────────────────────────────────────────────────
INSTALL_DIR="${TREVLIX_DIR:-/opt/trevlix}"
SERVICE_NAME="trevlix"
MOTD_SCRIPT="/etc/update-motd.d/99-trevlix"
MOTD_STATIC="/etc/motd"
MOTD_PROFILE="/etc/profile.d/99-trevlix-motd.sh"

# ── Installation ─────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--install" ]]; then
    if [[ $EUID -ne 0 ]]; then
        echo "Bitte als root ausführen: sudo bash motd.sh --install"
        exit 1
    fi

    echo -e "${JADE}[TREVLIX]${RESET} MOTD installieren..."

    # Altes statisches MOTD deaktivieren
    if [[ -f "$MOTD_STATIC" && -s "$MOTD_STATIC" ]]; then
        cp "$MOTD_STATIC" "${MOTD_STATIC}.bak" 2>/dev/null || true
        : > "$MOTD_STATIC"
        echo -e "${GREEN}  ✓${RESET} Statisches MOTD deaktiviert"
    fi

    # Methode 1: update-motd.d (Debian/Ubuntu/Raspberry Pi OS/Mint)
    if [[ -d /etc/update-motd.d ]]; then
        # Standard-MOTD-Skripte deaktivieren
        for f in /etc/update-motd.d/10-help-text \
                  /etc/update-motd.d/50-landscape-sysinfo \
                  /etc/update-motd.d/50-motd-news \
                  /etc/update-motd.d/51-cloudguest \
                  /etc/update-motd.d/80-livepatch \
                  /etc/update-motd.d/80-esm \
                  /etc/update-motd.d/91-release-upgrade; do
            if [[ -f "$f" ]]; then
                chmod -x "$f" 2>/dev/null || true
            fi
        done

        cp "$(realpath "$0")" "$MOTD_SCRIPT"
        chmod +x "$MOTD_SCRIPT"
        echo -e "${GREEN}  ✓${RESET} Installiert: ${MOTD_SCRIPT}"

    # Methode 2: profile.d (RHEL/CentOS/Rocky/Alma/Fedora/openSUSE/Arch)
    else
        SCRIPT_PATH="/usr/local/share/trevlix/motd.sh"
        mkdir -p "$(dirname "$SCRIPT_PATH")"
        cp "$(realpath "$0")" "$SCRIPT_PATH"
        chmod +x "$SCRIPT_PATH"

        cat > "$MOTD_PROFILE" << 'PROFILE_EOF'
# TREVLIX MOTD – Wird bei jedem Login angezeigt
if [ -x /usr/local/share/trevlix/motd.sh ] && [ -t 0 ]; then
    /usr/local/share/trevlix/motd.sh 2>/dev/null || true
fi
PROFILE_EOF
        chmod 644 "$MOTD_PROFILE"
        echo -e "${GREEN}  ✓${RESET} Installiert: ${MOTD_PROFILE} → ${SCRIPT_PATH}"
    fi

    echo -e "${GREEN}  ✓${RESET} TREVLIX MOTD aktiv beim nächsten Login."
    exit 0
fi

# ── Deinstallation ───────────────────────────────────────────────────────────
if [[ "${1:-}" == "--uninstall" ]]; then
    if [[ $EUID -ne 0 ]]; then
        echo "Bitte als root ausführen: sudo bash motd.sh --uninstall"
        exit 1
    fi
    rm -f "$MOTD_SCRIPT" 2>/dev/null || true
    rm -f "$MOTD_PROFILE" 2>/dev/null || true
    rm -f "/usr/local/share/trevlix/motd.sh" 2>/dev/null || true
    [[ -f "${MOTD_STATIC}.bak" ]] && cp "${MOTD_STATIC}.bak" "$MOTD_STATIC" 2>/dev/null || true
    echo -e "${GREEN}✓ TREVLIX MOTD entfernt.${RESET}"
    exit 0
fi

# ══════════════════════════════════════════════════════════════════════════════
#  MOTD ANZEIGE (wird bei jedem SSH-Login ausgeführt)
# ══════════════════════════════════════════════════════════════════════════════

# ── Hilfsfunktionen (alle mit Fallback bei Fehler) ───────────────────────────

_service_status() {
    local svc="$1"
    if command -v systemctl &>/dev/null && systemctl is-active --quiet "$svc" 2>/dev/null; then
        echo "running"
    elif command -v service &>/dev/null && service "$svc" status &>/dev/null 2>&1; then
        echo "running"
    elif command -v rc-service &>/dev/null && rc-service "$svc" status &>/dev/null 2>&1; then
        echo "running"
    else
        echo "stopped"
    fi
}

_ram_used_mb() {
    if [[ -f /proc/meminfo ]]; then
        awk '/MemTotal/{t=$2} /MemAvailable/{a=$2} END{if(t>0) printf "%d", (t-a)/1024; else print "?"}' /proc/meminfo 2>/dev/null
    else
        echo "?"
    fi
}

_ram_total_mb() {
    if [[ -f /proc/meminfo ]]; then
        awk '/MemTotal/{printf "%d", $2/1024}' /proc/meminfo 2>/dev/null
    else
        echo "?"
    fi
}

_disk_used() {
    df -h / 2>/dev/null | awk 'NR==2{print $3"/"$2" ("$5")"}' || echo "?"
}

_load_avg() {
    if [[ -f /proc/loadavg ]]; then
        awk '{print $1" "$2" "$3}' /proc/loadavg
    elif command -v uptime &>/dev/null; then
        uptime | sed 's/.*load average[s]\{0,1\}: *//' | cut -d, -f1-3 | xargs
    else
        echo "?"
    fi
}

_uptime_human() {
    if command -v uptime &>/dev/null; then
        local raw
        raw=$(uptime -p 2>/dev/null) && echo "$raw" && return
        # Fallback: parse uptime output
        uptime | sed 's/.*up \([^,]*\),.*/\1/' 2>/dev/null || echo "?"
    else
        echo "?"
    fi
}

_ip_addr() {
    # Methode 1: hostname -I (Debian/Ubuntu)
    if command -v hostname &>/dev/null; then
        local ip
        ip=$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -v '^$' | grep -v '^127\.' | grep -v ':' | head -1)
        [[ -n "$ip" ]] && echo "$ip" && return
    fi
    # Methode 2: ip command
    if command -v ip &>/dev/null; then
        ip -4 addr show 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v '^127\.' | head -1 && return
    fi
    # Methode 3: ifconfig
    if command -v ifconfig &>/dev/null; then
        ifconfig 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v '^127\.' | head -1 && return
    fi
    echo "?"
}

_sessions() {
    if command -v who &>/dev/null; then
        who 2>/dev/null | wc -l
    else
        echo "?"
    fi
}

_cpu_info() {
    if [[ -f /proc/cpuinfo ]]; then
        local model cores
        model=$(grep -m1 'model name' /proc/cpuinfo 2>/dev/null | cut -d: -f2 | xargs)
        cores=$(grep -c '^processor' /proc/cpuinfo 2>/dev/null)
        if [[ -n "$model" ]]; then
            echo "${model} (${cores} cores)"
        else
            echo "${cores} cores"
        fi
    else
        echo "?"
    fi
}

_cpu_temp() {
    # Raspberry Pi und andere ARM-Boards
    if [[ -f /sys/class/thermal/thermal_zone0/temp ]]; then
        local raw
        raw=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null)
        if [[ -n "$raw" && "$raw" -gt 0 ]]; then
            echo "$((raw / 1000))°C"
            return
        fi
    fi
    # x86 via sensors
    if command -v sensors &>/dev/null; then
        sensors 2>/dev/null | grep -m1 'Core 0' | grep -oP '\+\d+\.\d+°C' | head -1 && return
    fi
    echo ""
}

_is_raspberry_pi() {
    if [[ -f /sys/firmware/devicetree/base/model ]]; then
        grep -qi "raspberry" /sys/firmware/devicetree/base/model 2>/dev/null && return 0
    fi
    if [[ -f /proc/cpuinfo ]]; then
        grep -qi "raspberry\|BCM2" /proc/cpuinfo 2>/dev/null && return 0
    fi
    return 1
}

_trevlix_version() {
    local ver_file="${INSTALL_DIR}/VERSION"
    local ver_md="${INSTALL_DIR}/VERSION.md"
    if [[ -f "$ver_file" ]]; then
        tr -d '[:space:]' < "$ver_file"
    elif [[ -f "$ver_md" ]]; then
        grep -oE '[0-9]+\.[0-9]+\.[0-9]+' "$ver_md" 2>/dev/null | head -1 || echo "dev"
    elif [[ -d "${INSTALL_DIR}/.git" ]]; then
        git -C "$INSTALL_DIR" describe --tags --abbrev=4 2>/dev/null || echo "dev"
    else
        echo "1.7.1"
    fi
}

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

_exchange() {
    local env_file="${INSTALL_DIR}/.env"
    if [[ -f "$env_file" ]]; then
        # Multi-Exchange prüfen
        local multi
        multi=$(grep -i '^EXCHANGES_ENABLED=' "$env_file" 2>/dev/null | cut -d= -f2 | tr -d '[:space:]"')
        if [[ -n "$multi" ]]; then
            echo "$multi" | tr '[:lower:]' '[:upper:]' | tr ',' ' + '
            return
        fi
        grep -i '^EXCHANGE=' "$env_file" 2>/dev/null | cut -d= -f2 | tr -d '[:space:]"' | tr '[:lower:]' '[:upper:]' || echo "N/A"
    else
        echo "N/A"
    fi
}

_dashboard_url() {
    local env_file="${INSTALL_DIR}/.env"
    local port="5000"
    local domain=""
    if [[ -f "$env_file" ]]; then
        port=$(grep -i '^PORT=' "$env_file" 2>/dev/null | cut -d= -f2 | tr -d '[:space:]"' || echo "5000")
        # Domain aus ALLOWED_ORIGINS ableiten
        local origins
        origins=$(grep -i '^ALLOWED_ORIGINS=' "$env_file" 2>/dev/null | cut -d= -f2 | tr -d '"')
        if [[ "$origins" == https://* ]]; then
            domain=$(echo "$origins" | cut -d, -f1)
            echo "$domain"
            return
        fi
    fi
    local ip
    ip=$(_ip_addr)
    echo "http://${ip}:${port}"
}

_open_positions() {
    # Versuche Positionen via API zu lesen (nur wenn Bot läuft)
    if command -v curl &>/dev/null; then
        local port
        port=$(grep -i '^PORT=' "${INSTALL_DIR}/.env" 2>/dev/null | cut -d= -f2 | tr -d '[:space:]"' || echo "5000")
        local resp
        resp=$(curl -s --max-time 2 "http://127.0.0.1:${port}/api/v1/status" 2>/dev/null) || true
        if [[ -n "$resp" ]]; then
            echo "$resp" | grep -oP '"open_positions"\s*:\s*\K\d+' 2>/dev/null || echo "?"
            return
        fi
    fi
    echo "?"
}

_api_get() {
    local path="$1"
    local port resp
    port=$(grep -i '^PORT=' "${INSTALL_DIR}/.env" 2>/dev/null | cut -d= -f2 | tr -d '[:space:]"' || echo "5000")
    resp=$(curl -s --max-time 2 "http://127.0.0.1:${port}${path}" 2>/dev/null) || true
    echo "$resp"
}

_json_value() {
    local json="$1"
    local key="$2"
    echo "$json" | grep -oP "\"${key}\"\\s*:\\s*\"?\\K[^\",}]+" 2>/dev/null | head -1
}

_redis_status() {
    # Prüft sowohl Service als auch Response über redis-cli
    # Rückgabe: "running", "stopped" oder "absent" (nicht installiert)
    local have_cli=false have_svc=false
    if command -v redis-cli &>/dev/null; then
        have_cli=true
        local pong
        pong=$(redis-cli -t 1 ping 2>/dev/null)
        if [[ "$pong" == "PONG" ]]; then
            echo "running"
            return
        fi
    fi
    local svc
    for svc in redis redis-server; do
        if command -v systemctl &>/dev/null; then
            if systemctl cat "$svc" &>/dev/null; then
                have_svc=true
                if systemctl is-active --quiet "$svc" 2>/dev/null; then
                    echo "running"
                    return
                fi
            fi
        fi
    done
    if [[ "$have_cli" == "true" || "$have_svc" == "true" ]]; then
        echo "stopped"
    else
        echo "absent"
    fi
}

_ollama_status() {
    # Ollama ist nur relevant, wenn binary vorhanden
    if ! command -v ollama &>/dev/null; then
        echo "absent"
        return
    fi
    # HTTP-Check auf Standard-Port 11434
    if command -v curl &>/dev/null; then
        if curl -s --max-time 2 "http://127.0.0.1:11434/api/tags" &>/dev/null; then
            echo "running"
            return
        fi
    fi
    if command -v systemctl &>/dev/null && systemctl is-active --quiet ollama 2>/dev/null; then
        echo "running"
        return
    fi
    echo "stopped"
}

_ollama_models() {
    # Gibt die erste geladene Modell-ID zurück (oder leer)
    if ! command -v curl &>/dev/null; then return; fi
    local resp
    resp=$(curl -s --max-time 2 "http://127.0.0.1:11434/api/tags" 2>/dev/null) || return
    echo "$resp" | grep -oP '"name"\s*:\s*"\K[^"]+' 2>/dev/null | head -3 | tr '\n' ',' | sed 's/,$//'
}

_cron_status() {
    local svc
    for svc in cron crond cronie; do
        if command -v systemctl &>/dev/null; then
            if systemctl cat "$svc" &>/dev/null; then
                if systemctl is-active --quiet "$svc" 2>/dev/null; then
                    echo "running"
                    return
                fi
            fi
        fi
    done
    # Fallback: Prozess-Check
    if pgrep -x "cron\|crond" &>/dev/null; then
        echo "running"
        return
    fi
    echo "stopped"
}

_mysql_status() {
    # Prüft MariaDB / MySQL Service
    local svc
    for svc in mariadb mysql mysqld; do
        if command -v systemctl &>/dev/null && systemctl is-active --quiet "$svc" 2>/dev/null; then
            echo "running"
            return
        fi
    done
    # Optional: Port-Check 3306
    if command -v ss &>/dev/null && ss -tlnH 2>/dev/null | grep -q ':3306'; then
        echo "running"
        return
    fi
    echo "stopped"
}

_last_backup() {
    local env_file="${INSTALL_DIR}/.env"
    local backup_dir=""
    if [[ -f "$env_file" ]]; then
        backup_dir=$(grep -i '^BACKUP_DIR=' "$env_file" 2>/dev/null | cut -d= -f2 | tr -d '[:space:]"')
    fi
    [[ -z "$backup_dir" ]] && backup_dir="${INSTALL_DIR}/backups"
    if [[ ! -d "$backup_dir" ]]; then
        echo "—"
        return
    fi
    local newest
    newest=$(ls -t "$backup_dir"/*.sql* "$backup_dir"/*.gz "$backup_dir"/*.tar* 2>/dev/null | head -1)
    if [[ -z "$newest" ]]; then
        echo "—"
        return
    fi
    local mtime age_hours
    mtime=$(stat -c %Y "$newest" 2>/dev/null || echo "0")
    age_hours=$(( ( $(date +%s) - mtime ) / 3600 ))
    if [[ "$age_hours" -lt 1 ]]; then
        echo "vor <1h"
    elif [[ "$age_hours" -lt 24 ]]; then
        echo "vor ${age_hours}h"
    else
        echo "vor $((age_hours / 24))d"
    fi
}

_disk_free_mb() {
    # Verfügbarer Speicher in MB auf der Root-Partition
    df -Pm / 2>/dev/null | awk 'NR==2{print $4}' || echo "0"
}

# ── Daten sammeln ──────────────────────────────────────────────────────────
HOSTNAME_VAL=$(hostname -s 2>/dev/null || cat /etc/hostname 2>/dev/null || echo "?")
OS_PRETTY=$(grep PRETTY_NAME /etc/os-release 2>/dev/null | cut -d'"' -f2 || echo "Linux")
KERNEL=$(uname -r 2>/dev/null || echo "?")
ARCH=$(uname -m 2>/dev/null || echo "?")
UPTIME=$(_uptime_human)
LOAD=$(_load_avg)
RAM_USED=$(_ram_used_mb)
RAM_TOTAL=$(_ram_total_mb)
DISK=$(_disk_used)
IP=$(_ip_addr)
SESSIONS=$(_sessions)
CPU=$(_cpu_info)
CPU_TEMP=$(_cpu_temp)
DATE_NOW=$(date '+%A, %d. %B %Y · %H:%M' 2>/dev/null || date)

TREVLIX_STATUS=$(_service_status "$SERVICE_NAME")
TREVLIX_VERSION=$(_trevlix_version)
TRADING_MODE=$(_trading_mode)
EXCHANGE=$(_exchange)
DASH_URL=$(_dashboard_url)
REDIS_STATUS=$(_redis_status)
MYSQL_STATUS=$(_mysql_status)
OLLAMA_STATUS=$(_ollama_status)
OLLAMA_MODELS=$(_ollama_models)
CRON_STATUS=$(_cron_status)
LAST_BACKUP=$(_last_backup)
DISK_FREE_MB=$(_disk_free_mb)
STATUS_JSON=$(_api_get "/api/v1/status")
SHARED_AI_JSON=$(_api_get "/api/v1/ai/shared/status")
OPEN_POS=$(_json_value "${STATUS_JSON}" "open_positions")
WIN_RATE=$(_json_value "${STATUS_JSON}" "win_rate")
TOTAL_PNL=$(_json_value "${STATUS_JSON}" "total_pnl")
LAST_SIGNAL=$(_json_value "${STATUS_JSON}" "last_signal")
SHARED_AI_VER=$(_json_value "${SHARED_AI_JSON}" "shared_version")
SHARED_AI_READY=$(_json_value "${SHARED_AI_JSON}" "ready")

# Raspberry Pi Erkennung
IS_PI=false
PI_MODEL=""
if _is_raspberry_pi; then
    IS_PI=true
    PI_MODEL=$(tr -d '\0' < /sys/firmware/devicetree/base/model 2>/dev/null || echo "Raspberry Pi")
fi

# ── Status-Farben ─────────────────────────────────────────────────────────
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
    MODE_ICON="🔴"
else
    MODE_COLOR="${CYAN}"
    MODE_ICON="📝"
fi

# RAM-Warnung bei >80%
RAM_WARN=""
if [[ "$RAM_USED" != "?" && "$RAM_TOTAL" != "?" && "$RAM_TOTAL" -gt 0 ]]; then
    RAM_PCT=$((RAM_USED * 100 / RAM_TOTAL))
    if [[ $RAM_PCT -gt 80 ]]; then
        RAM_WARN="${RED} ⚠${RESET}"
    fi
fi

# ── MOTD Ausgabe ──────────────────────────────────────────────────────────
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
printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${DIM}%s${RESET}\n" "Hostname:" "$HOSTNAME_VAL"
printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${DIM}%s${RESET}\n" "System:" "$OS_PRETTY"
if [[ "$IS_PI" == "true" ]]; then
    printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${MAGENTA}%s${RESET}\n" "Hardware:" "$PI_MODEL"
fi
printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${DIM}%s (%s)${RESET}\n" "Kernel:" "$KERNEL" "$ARCH"
printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${DIM}%s${RESET}\n" "CPU:" "$CPU"
if [[ -n "$CPU_TEMP" ]]; then
    if [[ "${CPU_TEMP%%°*}" =~ ^[0-9]+$ ]] && [[ "${CPU_TEMP%%°*}" -gt 70 ]]; then
        printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${RED}%s ⚠${RESET}\n" "CPU-Temp:" "$CPU_TEMP"
    else
        printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${DIM}%s${RESET}\n" "CPU-Temp:" "$CPU_TEMP"
    fi
fi
printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${DIM}%s${RESET}\n" "IP:" "$IP"
printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${DIM}%s${RESET}\n" "Uptime:" "$UPTIME"
printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${DIM}%s${RESET}\n" "Load:" "$LOAD"
printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${DIM}%s MB / %s MB${RESET}%b\n" "RAM:" "$RAM_USED" "$RAM_TOTAL" "$RAM_WARN"
printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${DIM}%s${RESET}\n" "Disk:" "$DISK"
printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${DIM}%s aktiv${RESET}\n" "Sessions:" "$SESSIONS"

echo -e "${JADE}╠══════════════════════════════════════════════════════════════════╣${RESET}"

# Trevlix Bot-Status
printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${STATUS_COLOR}${BOLD}${STATUS_ICON} %s${RESET}\n" "Bot:" "$STATUS_TEXT"
printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${MODE_COLOR}${BOLD}%s %s${RESET}\n" "Modus:" "$MODE_ICON" "$TRADING_MODE"
printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${DIM}%s${RESET}\n" "Exchange:" "$EXCHANGE"
printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${CYAN}%s${RESET}\n" "Dashboard:" "$DASH_URL"
if [[ -n "$OPEN_POS" || -n "$WIN_RATE" || -n "$TOTAL_PNL" ]]; then
    [[ -z "$OPEN_POS" ]] && OPEN_POS="?"
    [[ -z "$WIN_RATE" ]] && WIN_RATE="?"
    [[ -z "$TOTAL_PNL" ]] && TOTAL_PNL="?"
    printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${DIM}%s · WR %s%% · PnL %s${RESET}\n" "Dashboard:" "Open ${OPEN_POS}" "${WIN_RATE}" "${TOTAL_PNL}"
fi
if [[ -n "$LAST_SIGNAL" ]]; then
    printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${DIM}%s${RESET}\n" "Signal:" "$LAST_SIGNAL"
fi
if [[ -n "$SHARED_AI_READY" || -n "$SHARED_AI_VER" ]]; then
    [[ -z "$SHARED_AI_READY" ]] && SHARED_AI_READY="?"
    [[ -z "$SHARED_AI_VER" ]] && SHARED_AI_VER="?"
    printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${DIM}%s (v%s)${RESET}\n" "Shared AI:" "$SHARED_AI_READY" "$SHARED_AI_VER"
fi

echo -e "${JADE}╠══════════════════════════════════════════════════════════════════╣${RESET}"

# Infrastruktur-Services
# Redis nur anzeigen, wenn installiert (optional)
if [[ "$REDIS_STATUS" == "running" ]]; then
    printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${GREEN}● OK${RESET}\n" "Redis:"
elif [[ "$REDIS_STATUS" == "stopped" ]]; then
    printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${RED}○ gestoppt${RESET}\n" "Redis:"
fi
if [[ "$MYSQL_STATUS" == "running" ]]; then
    printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${GREEN}● OK${RESET}\n" "MariaDB:"
else
    printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${RED}○ gestoppt${RESET}\n" "MariaDB:"
fi
# Ollama (nur wenn installiert)
if [[ "$OLLAMA_STATUS" == "running" ]]; then
    if [[ -n "$OLLAMA_MODELS" ]]; then
        printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${GREEN}● OK${RESET} ${DIM}(%s)${RESET}\n" "Ollama:" "$OLLAMA_MODELS"
    else
        printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${GREEN}● OK${RESET}\n" "Ollama:"
    fi
elif [[ "$OLLAMA_STATUS" == "stopped" ]]; then
    printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${ORANGE}○ installiert, nicht aktiv${RESET}\n" "Ollama:"
fi
# Cron-Dienst
if [[ "$CRON_STATUS" == "running" ]]; then
    printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${GREEN}● OK${RESET}\n" "Cron:"
else
    printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${RED}○ gestoppt${RESET}\n" "Cron:"
fi
printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${DIM}%s${RESET}\n" "Letztes Backup:" "$LAST_BACKUP"
# Disk-Free-Warnung bei <1GB (1024 MB)
if [[ "$DISK_FREE_MB" =~ ^[0-9]+$ ]]; then
    if [[ "$DISK_FREE_MB" -lt 1024 ]]; then
        printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${RED}%s MB ⚠ (kritisch)${RESET}\n" "Disk frei:" "$DISK_FREE_MB"
    elif [[ "$DISK_FREE_MB" -lt 5120 ]]; then
        printf "${JADE}║${RESET}  ${BOLD}%-14s${RESET} ${ORANGE}%s MB${RESET}\n" "Disk frei:" "$DISK_FREE_MB"
    fi
fi

echo -e "${JADE}╠══════════════════════════════════════════════════════════════════╣${RESET}"

# Quick-Reference
echo -e "${JADE}║${RESET}  ${BOLD}Schnellbefehle:${RESET}"
echo -e "${JADE}║${RESET}  ${GREEN}systemctl status  trevlix${RESET}   ${DIM}# Bot-Status${RESET}"
echo -e "${JADE}║${RESET}  ${GREEN}systemctl restart trevlix${RESET}   ${DIM}# Neustart${RESET}"
echo -e "${JADE}║${RESET}  ${GREEN}journalctl -u trevlix -f${RESET}    ${DIM}# Live-Logs${RESET}"
printf "${JADE}║${RESET}  ${GREEN}%-26s${RESET} ${DIM}# Dashboard-Status JSON${RESET}\n" "curl -s ${DASH_URL}/api/v1/status"
printf "${JADE}║${RESET}  ${GREEN}%-26s${RESET} ${DIM}# Shared-AI Status${RESET}\n" "curl -s ${DASH_URL}/api/v1/ai/shared/status"
printf "${JADE}║${RESET}  ${GREEN}%-26s${RESET} ${DIM}# Konfiguration${RESET}\n" "nano ${INSTALL_DIR}/.env"

# LIVE-Trading Warnung
if [[ "$TRADING_MODE" == "LIVE" ]]; then
    echo -e "${JADE}╠══════════════════════════════════════════════════════════════════╣${RESET}"
    echo -e "${JADE}║${RESET}  ${RED}${BOLD}⚠  LIVE-TRADING AKTIV — Echtes Geld wird eingesetzt!${RESET}"
fi

# Raspberry Pi Temperatur-Warnung
if [[ "$IS_PI" == "true" && -n "$CPU_TEMP" ]]; then
    local_temp="${CPU_TEMP%%°*}"
    if [[ "$local_temp" =~ ^[0-9]+$ ]] && [[ "$local_temp" -gt 75 ]]; then
        echo -e "${JADE}╠══════════════════════════════════════════════════════════════════╣${RESET}"
        echo -e "${JADE}║${RESET}  ${ORANGE}${BOLD}🌡 CPU-Temperatur hoch (${CPU_TEMP}) — Kühlung prüfen!${RESET}"
    fi
fi

echo -e "${JADE}╚══════════════════════════════════════════════════════════════════╝${RESET}"
echo ""
