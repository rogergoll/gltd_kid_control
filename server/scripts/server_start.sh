#!/usr/bin/env bash
# Sobe o servidor GLTD Kid Control (sem abrir navegador).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CONFIG="$ROOT/config/server.json"
PORT=8123
URL="http://localhost:$PORT"
LOG="$ROOT/data/server.log"
PID_FILE="$ROOT/data/server.pid"
mkdir -p "$ROOT/data"

health() { curl -s -o /dev/null --max-time 2 "$URL/api/health" 2>/dev/null; }

if health; then
  echo "Servidor já está rodando."
  exit 0
fi

(cd "$ROOT/server" && setsid -f python3 -u -m gltd_kid_server --config "$CONFIG" \
   >> "$LOG" 2>&1 < /dev/null)

for _ in $(seq 1 15); do
  sleep 1
  health && break
done

if ! health; then
  echo "Falha ao subir o servidor. Veja $LOG" >&2
  exit 1
fi

pgrep -nf "gltd_kid_serve[r]" > "$PID_FILE" 2>/dev/null || true
echo "Servidor ativo."
