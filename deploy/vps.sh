#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# NQA — commandes utiles sur le VPS
#
# Usage :
#   ./vps.sh diagnose          # état du backend, de la base et de nginx
#   ./vps.sh superuser         # crée / répare le superuser
#   ./vps.sh import-products   # importe le catalogue de démo
#   ./vps.sh fix-nginx         # /admin/ -> Next.js, /django-admin/ -> Django
#
# Variables surchargeables :
#   PORT=8010
#   SUPERUSER_EMAIL=admin@nqa.cd
#   SUPERUSER_PASSWORD=admin12345
#   SUPERUSER_USERNAME=admin
#   SUPERUSER_FIRST_NAME=Admin
#   SUPERUSER_LAST_NAME=NQA
#   NGINX_SITE=/etc/nginx/sites-available/nqahardware.com
# ---------------------------------------------------------------------------
set -euo pipefail

PORT="${PORT:-8010}"
SUPERUSER_EMAIL="${SUPERUSER_EMAIL:-admin@nqa.cd}"
SUPERUSER_PASSWORD="${SUPERUSER_PASSWORD:-admin12345}"
SUPERUSER_USERNAME="${SUPERUSER_USERNAME:-admin}"
SUPERUSER_FIRST_NAME="${SUPERUSER_FIRST_NAME:-Admin}"
SUPERUSER_LAST_NAME="${SUPERUSER_LAST_NAME:-NQA}"
NGINX_SITE="${NGINX_SITE:-/etc/nginx/sites-available/nqahardware.com}"

BACKEND_DIR=""
PYTHON_BIN=""

die() {
  echo "ERREUR: $*" >&2
  exit 1
}

info() {
  echo "==> $*"
}

usage() {
  cat <<EOF
Usage: $0 <commande>

Commandes :
  diagnose          Affiche le processus backend, son dossier et ses variables (sans secrets)
  superuser         Crée ou met à jour le superuser
  import-products   Importe le catalogue de démo avec les prix
  fix-nginx         Corrige le routage nginx (/admin/ vs /django-admin/)

Variables :
  PORT=$PORT
  SUPERUSER_EMAIL=$SUPERUSER_EMAIL
  SUPERUSER_USERNAME=$SUPERUSER_USERNAME
  SUPERUSER_FIRST_NAME=$SUPERUSER_FIRST_NAME
  SUPERUSER_LAST_NAME=$SUPERUSER_LAST_NAME
  NGINX_SITE=$NGINX_SITE

Exemples :
  $0 diagnose
  SUPERUSER_PASSWORD='MotDePasseFort!2026' $0 superuser
  $0 import-products
  sudo $0 fix-nginx
EOF
}

find_backend_pid() {
  local pid
  pid="$(ss -ltnp 2>/dev/null | sed -n "s/.*:${PORT} .*pid=\([0-9]*\).*/\1/p" | head -1)"
  if [[ -z "$pid" ]]; then
    die "aucun processus en écoute sur le port ${PORT}. Vérifie avec : ss -ltnp | grep ${PORT}"
  fi
  echo "$pid"
}

load_backend_context() {
  local pid="$1"

  BACKEND_DIR="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
  [[ -n "$BACKEND_DIR" && -d "$BACKEND_DIR" ]] || die "impossible de trouver le dossier du processus $pid"

  # Charge uniquement les variables utiles (jamais affichées).
  while IFS= read -r -d '' line; do
    case "$line" in
      DJANGO_*|DATABASE_*|FRONTEND_URL=*|PAYMENTS_*|FLUTTERWAVE_*|PG*) export "$line" ;;
    esac
  done < "/proc/$pid/environ"

  # Priorité au venv du projet, sinon au Python du processus, sinon python3.
  local exe
  exe="$(readlink -f "/proc/$pid/exe" 2>/dev/null || true)"

  if [[ -x "$BACKEND_DIR/venv/bin/python" ]]; then
    PYTHON_BIN="$BACKEND_DIR/venv/bin/python"
  elif [[ -n "$exe" && -x "$exe" ]]; then
    PYTHON_BIN="$exe"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    die "aucun interpréteur Python trouvé"
  fi

  [[ -f "$BACKEND_DIR/manage.py" ]] || die "manage.py introuvable dans $BACKEND_DIR"
}

cmd_diagnose() {
  local pid
  pid="$(find_backend_pid)"
  load_backend_context "$pid"

  echo "PID          : $pid"
  echo "Dossier      : $BACKEND_DIR"
  echo "Commande     : $(tr '\0' ' ' < "/proc/$pid/cmdline")"
  echo "Python       : $PYTHON_BIN"
  echo
  echo "Variables DB / Django (valeurs masquées) :"
  tr '\0' '\n' < "/proc/$pid/environ" \
    | grep -E '^(DJANGO_|DATABASE_|FRONTEND_URL=|PAYMENTS_|FLUTTERWAVE_|PG)' \
    | sed 's/=.*/=<masqué>/' \
    | sort || true

  echo
  echo "Test de connexion à la base :"
  (cd "$BACKEND_DIR" && "$PYTHON_BIN" manage.py shell -c "
from django.db import connection
settings = connection.settings_dict
print('ENGINE :', settings.get('ENGINE'))
print('NAME   :', settings.get('NAME'))
print('USER   :', settings.get('USER'))
print('HOST   :', settings.get('HOST'))
print('PORT   :', settings.get('PORT'))
" 2>&1 | sed 's/^/  /') || true

  echo
  echo "Comptes existants :"
  (cd "$BACKEND_DIR" && "$PYTHON_BIN" manage.py shell -c "
from accounts.models import User
for u in User.objects.order_by('email'):
    print(f'  {u.email} | active={u.is_active} | staff={u.is_staff} | superuser={u.is_superuser}')
" 2>&1) || true

  echo
  echo "Routage nginx (${NGINX_SITE}) :"
  if [[ -f "$NGINX_SITE" ]]; then
    grep -nE 'location.*(admin|django-admin|/api/|/health|_next)' "$NGINX_SITE" || true
  else
    echo "  fichier introuvable : $NGINX_SITE"
  fi
}

cmd_superuser() {
  local pid
  pid="$(find_backend_pid)"
  load_backend_context "$pid"

  info "Backend : $BACKEND_DIR"
  info "Création / mise à jour du superuser : $SUPERUSER_EMAIL"

  (
    cd "$BACKEND_DIR"
    NQA_SUPERUSER_EMAIL="$SUPERUSER_EMAIL" \
    NQA_SUPERUSER_PASSWORD="$SUPERUSER_PASSWORD" \
    NQA_SUPERUSER_USERNAME="$SUPERUSER_USERNAME" \
    NQA_SUPERUSER_FIRST_NAME="$SUPERUSER_FIRST_NAME" \
    NQA_SUPERUSER_LAST_NAME="$SUPERUSER_LAST_NAME" \
    "$PYTHON_BIN" manage.py shell <<'PY'
import os
from accounts.models import User

email = os.environ["NQA_SUPERUSER_EMAIL"].strip().lower()
password = os.environ["NQA_SUPERUSER_PASSWORD"]
username = os.environ.get("NQA_SUPERUSER_USERNAME", "admin").strip()
first_name = os.environ.get("NQA_SUPERUSER_FIRST_NAME", "Admin").strip()
last_name = os.environ.get("NQA_SUPERUSER_LAST_NAME", "NQA").strip()

u = User.objects.filter(email__iexact=email).first()
if u is None:
    u = User(email=email, username=username, first_name=first_name, last_name=last_name)
else:
    if not u.username:
        u.username = username

u.is_active = True
u.is_staff = True
u.is_superuser = True
u.set_password(password)
u.save()

print(f"OK : {u.email} | is_staff={u.is_staff} | is_superuser={u.is_superuser}")
PY
  )

  info "Test de l'API :"
  curl -s -o /dev/null -w "  HTTP %{http_code}\n" \
    -X POST "https://${DOMAIN:-nqahardware.com}/api/v1/auth/token/" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"${SUPERUSER_EMAIL}\",\"password\":\"${SUPERUSER_PASSWORD}\"}" || true
}

cmd_import_products() {
  local pid
  pid="$(find_backend_pid)"
  load_backend_context "$pid"

  [[ -f "$BACKEND_DIR/demo_prices.json" ]] \
    || die "demo_prices.json introuvable dans $BACKEND_DIR (fais un git pull)"

  info "Backend : $BACKEND_DIR"
  info "Import du catalogue de démo…"

  (
    cd "$BACKEND_DIR"
    "$PYTHON_BIN" manage.py import_products --prices demo_prices.json
  )
}

cmd_fix_nginx() {
  [[ "${EUID:-$(id -u)}" -eq 0 ]] || die "lance cette commande en root : sudo $0 fix-nginx"
  [[ -f "$NGINX_SITE" ]] || die "fichier nginx introuvable : $NGINX_SITE"

  local backup
  backup="/root/$(basename "$NGINX_SITE").backup-$(date +%F-%H%M%S)"
  cp "$NGINX_SITE" "$backup"
  info "Sauvegarde : $backup"

  if grep -q 'location \^~ /django-admin/' "$NGINX_SITE"; then
    info "La route /django-admin/ existe déjà."
  elif grep -q 'location \^~ /admin/' "$NGINX_SITE"; then
    sed -i 's|location \^~ /admin/ {|location ^~ /django-admin/ {|' "$NGINX_SITE"
    info "Route /admin/ remplacée par /django-admin/."
  else
    die "aucun bloc 'location ^~ /admin/' trouvé dans $NGINX_SITE"
  fi

  nginx -t
  systemctl reload nginx
  info "nginx rechargé."

  echo
  info "Vérifications :"
  curl -s -o /dev/null -w "  /admin/login    -> HTTP %{http_code}\n" "https://${DOMAIN:-nqahardware.com}/admin/login" || true
  curl -s -o /dev/null -w "  /django-admin/  -> HTTP %{http_code}\n" "https://${DOMAIN:-nqahardware.com}/django-admin/" || true
}

case "${1:-}" in
  diagnose) cmd_diagnose ;;
  superuser) cmd_superuser ;;
  import-products) cmd_import_products ;;
  fix-nginx) cmd_fix_nginx ;;
  help|-h|--help|"") usage ;;
  *) usage; exit 1 ;;
esac
