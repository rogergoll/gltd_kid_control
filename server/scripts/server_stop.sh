#!/usr/bin/env bash
# Encerra o servidor GLTD Kid Control.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PID_FILE="$ROOT/data/server.pid"

# padrão com [r] evita casar com o próprio processo do script
if pgrep -f "gltd_kid_serve[r]" >/dev/null 2>&1; then
  pkill -f "gltd_kid_serve[r]"
  echo "Servidor encerrado."
else
  echo "Servidor não está rodando."
fi
rm -f "$PID_FILE"
