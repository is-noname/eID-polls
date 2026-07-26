#!/usr/bin/env bash
# Startet die eID-Umfrage und oeffnet den Browser.
# Nur auf diesem Rechner:      bash app/start.sh
# Im LAN fuer Probandentests:  EIDPOLL_HOST=0.0.0.0 EIDPOLL_ADMIN_TOKEN=<eigenes-token> bash app/start.sh
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${EIDPOLL_PORT:-8731}"
HOST="${EIDPOLL_HOST:-127.0.0.1}"
ADMIN_TOKEN="${EIDPOLL_ADMIN_TOKEN:-admin}"
LOCAL_URL="http://127.0.0.1:${PORT}/"

# Sichtbar im LAN, aber noch das Standard-Admin-Token? Das ist im LAN keine
# Zugangskontrolle mehr, sondern eine offene Tuer (EIP-T-009). Start verweigern.
if [[ "$HOST" != "127.0.0.1" && "$HOST" != "localhost" && "$ADMIN_TOKEN" == "admin" ]]; then
  echo "Fehler: EIDPOLL_HOST=${HOST} macht die App im Netz erreichbar, aber das" >&2
  echo "Admin-Token steht noch auf der Voreinstellung 'admin'." >&2
  echo "Vor dem Start ein eigenes Token setzen, z. B.:" >&2
  echo "  EIDPOLL_HOST=${HOST} EIDPOLL_ADMIN_TOKEN=\$(openssl rand -hex 8) bash app/start.sh" >&2
  exit 1
fi

# Laufende Instanz auf demselben Port beenden
if command -v fuser >/dev/null 2>&1; then
  fuser -k "${PORT}/tcp" >/dev/null 2>&1 || true
  sleep 0.5
fi

cd "$APP_DIR"
python3 -m uvicorn web:app --host "$HOST" --port "$PORT" --log-level warning &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT

for _ in $(seq 1 40); do
  if curl -sf "$LOCAL_URL" >/dev/null 2>&1; then break; fi
  sleep 0.25
done

echo "eID-Umfrage laeuft (lokal):  $LOCAL_URL"

if [[ "$HOST" != "127.0.0.1" && "$HOST" != "localhost" ]]; then
  LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  if [[ -n "$LAN_IP" ]]; then
    LAN_URL="http://${LAN_IP}:${PORT}/"
    echo ""
    echo "Teilnahme-URL fuers LAN:     $LAN_URL"
    if command -v qrencode >/dev/null 2>&1; then
      qrencode -t ANSIUTF8 "$LAN_URL"
    else
      echo "(qrencode nicht installiert - QR-Code entfaellt, URL manuell verteilen)"
    fi
  else
    echo "Konnte keine LAN-IP ermitteln (hostname -I leer) - Teilnahme-URL manuell nachschlagen."
  fi
  echo "Admin-Token:                 $ADMIN_TOKEN"
else
  echo "Admin-Token:                 $ADMIN_TOKEN"
fi

echo "Beenden:                     Knopf oben rechts in der App (nur lokal bedienbar), oder hier Strg+C"

if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$LOCAL_URL" >/dev/null 2>&1 || true
fi

wait $SERVER_PID
