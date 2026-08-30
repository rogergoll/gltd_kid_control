#!/usr/bin/env bash
# GLTD Kid Control — atalho do painel admin (sobe server + abre Brave).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
URL="http://localhost:8123"

"$ROOT/server/scripts/server_start.sh"

echo "Abrindo painel em $URL"
if command -v brave-browser >/dev/null 2>&1; then
  setsid brave-browser "$URL" >/dev/null 2>&1 &
else
  setsid xdg-open "$URL" >/dev/null 2>&1 &
fi
