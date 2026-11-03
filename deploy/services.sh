#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# NQA — voir et redémarrer les services
#
#   ./services.sh status        # affiche les PID, dossiers et noms de services
#   ./services.sh restart       # redémarre frontend + API + nginx
#   ./services.sh restart-web   # redémarre seulement le frontend Next.js
#   ./services.sh restart-api   # redémarre seulement l'API Django
#   ./services.sh restart-nginx # redémarre seulement nginx
#
# Variables :
#   WEB_PORT=3000
#   API_PORT=8010
# ---------------------------------------------------------------------------
set -euo pipefail

WEB_PORT="${WEB_PORT:-3000}"
API_PORT="${API_PORT:-8010}"

die()  { echo "ERREUR: $*" >&2; exit 1; }
info() { echo "==> $*"; }

usage() {
  cat <<EOF
Usage: $0 <commande>

Commandes :
  status         Affiche le frontend, l'API, nginx et les noms de services
  restart        Redémarre frontend + API + nginx
  restart-web    Redémarre seulement le frontend Next.js
  restart-api    Redémarre seulement l'API Django
  restart-nginx  Redémarre seulement nginx

Variables :
  WEB_PORT=$WEB_PORT
  API_PORT=$API_PORT

Exemples :
  $0 status
  sudo $0 restart
  sudo $0 restart-web
EOF
}

find_pid() {
  local port="$1"
  ss -ltnp 2>/dev/null \
    | sed -n "s/.*:${port} .*pid=\([0-9]*\).*/\1/p" \
    | head -1
}

cwd_of() {
  readlink -f "/proc/$1/cwd" 2>/dev/null || true
}

cmdline_of() {
  tr '\0' ' ' < "/proc/$1/cmdline" 2>/dev/null || true
}

# systemd place le service dans /proc/<pid>/cgroup :
#   0::/system.slice/nqa.service
unit_from_cgroup() {
  local pid="$1"
  local cgroup
  cgroup="$(head -1 "/proc/$pid/cgroup" 2>/dev/null || true)"
  [[ -n "$cgroup" ]] || return 1
  echo "$cgroup" | sed -n 's#.*/\([^/]*\.service\)$#\1#p' | head -1
}

pm2_name_for_pid() {
  local pid="$1"
  command -v pm2 >/dev/null 2>&1 || return 1
  pm2 jlist 2>/dev/null | python3 -c '
import json, sys
pid = int(sys.argv[1])
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(1)
for proc in data:
    if proc.get("pid") == pid:
        print(proc.get("name", ""))
        sys.exit(0)
sys.exit(1)
' "$pid" 2>/dev/null
}

# Retourne "systemd:<unit>", "pm2:<nom>" ou "manual:"
detect_manager() {
  local pid="$1"
  local unit name

  unit="$(unit_from_cgroup "$pid" || true)"
  if [[ -n "$unit" ]] && systemctl cat "$unit" >/dev/null 2>&1; then
    echo "systemd:$unit"
    return 0
  fi

  name="$(pm2_name_for_pid "$pid" || true)"
  if [[ -n "$name" ]]; then
    echo "pm2:$name"
    return 0
  fi

  echo "manual:"
}

show_service() {
  local label="$1" port="$2"
  local pid manager

  echo
  echo "── $label (port $port) ─────────────────────────"
  pid="$(find_pid "$port" || true)"
  if [[ -z "$pid" ]]; then
    echo "  Aucun processus en écoute sur le port $port."
    return 1
  fi

  echo "  PID      : $pid"
  echo "  Dossier  : $(cwd_of "$pid")"
  echo "  Commande : $(cmdline_of "$pid")"

  manager="$(detect_manager "$pid")"
  case "$manager" in
    systemd:*) echo "  Service  : ${manager#systemd:} (systemd)" ;;
    pm2:*)     echo "  Service  : ${manager#pm2:} (pm2)" ;;
    *)         echo "  Service  : aucun gestionnaire détecté (processus manuel)" ;;
  esac
}

restart_service() {
  local label="$1" port="$2"
  local pid manager

  pid="$(find_pid "$port" || true)"
  if [[ -z "$pid" ]]; then
    echo "  $label : aucun processus sur le port $port, rien à redémarrer."
    return 0
  fi

  manager="$(detect_manager "$pid")"
  case "$manager" in
    systemd:*)
      local unit="${manager#systemd:}"
      info "Redémarrage $label : systemctl restart $unit"
      systemctl restart "$unit"
      ;;
    pm2:*)
      local name="${manager#pm2:}"
      info "Redémarrage $label : pm2 restart $name"
      pm2 restart "$name"
      ;;
    *)
      echo "  $label : processus manuel détecté."
      echo "  Commande : $(cmdline_of "$pid")"
      echo "  Dossier  : $(cwd_of "$pid")"
      echo "  Redémarre-le manuellement : kill $pid, puis relance la commande."
      return 1
      ;;
  esac
}

show_nginx() {
  echo
  echo "── nginx ──────────────────────────────────────"
  if systemctl cat nginx >/dev/null 2>&1; then
    if systemctl is-active nginx >/dev/null 2>&1; then
      echo "  Service  : nginx (actif)"
    else
      echo "  Service  : nginx (inactif)"
    fi
  else
    echo "  Service nginx introuvable via systemd."
  fi
}

status_all() {
  show_service "Frontend Next.js" "$WEB_PORT" || true
  show_service "API Django" "$API_PORT" || true
  show_nginx
}

restart_all() {
  [[ "${EUID:-$(id -u)}" -eq 0 ]] || die "lance en root : sudo $0 restart"

  restart_service "Frontend Next.js" "$WEB_PORT" || true
  restart_service "API Django" "$API_PORT" || true

  info "Redémarrage nginx : systemctl restart nginx"
  systemctl restart nginx

  echo
  info "État après redémarrage :"
  status_all
}

restart_web() {
  [[ "${EUID:-$(id -u)}" -eq 0 ]] || die "lance en root : sudo $0 restart-web"
  restart_service "Frontend Next.js" "$WEB_PORT"
  show_service "Frontend Next.js" "$WEB_PORT" || true
}

restart_api() {
  [[ "${EUID:-$(id -u)}" -eq 0 ]] || die "lance en root : sudo $0 restart-api"
  restart_service "API Django" "$API_PORT"
  show_service "API Django" "$API_PORT" || true
}

restart_nginx() {
  [[ "${EUID:-$(id -u)}" -eq 0 ]] || die "lance en root : sudo $0 restart-nginx"
  info "Redémarrage nginx : systemctl restart nginx"
  systemctl restart nginx
  show_nginx
}

case "${1:-status}" in
  status)        status_all ;;
  restart)       restart_all ;;
  restart-web)   restart_web ;;
  restart-api)   restart_api ;;
  restart-nginx) restart_nginx ;;
  help|-h|--help) usage ;;
  *) usage; exit 1 ;;
esac
