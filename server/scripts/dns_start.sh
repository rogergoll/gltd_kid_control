#!/usr/bin/env bash
# Inicia o DNS local do GLTD Kid Control (bloqueio de domínios).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PORT="${1:-5300}"
LOG="$ROOT/data/dns.log"
mkdir -p "$ROOT/data"

if pgrep -f "dns_serve[r].py" >/dev/null 2>&1; then
  echo "DNS já está rodando."
  exit 0
fi

setsid -f python3 -u "$ROOT/server/scripts/dns_server.py" --port "$PORT" </dev/null >>"$LOG" 2>&1
sleep 1
if pgrep -f "dns_serve[r].py" >/dev/null 2>&1; then
  echo "DNS ativo na porta $PORT."
else
  echo "Falha ao iniciar o DNS. Veja $LOG" >&2
  exit 1
fi
