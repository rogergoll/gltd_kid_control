#!/usr/bin/env bash
# Instalação manual (sem .deb) do server em modo desenvolvimento.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_DIR="/usr/lib/gltd-kid-control"
DATA_DIR="/var/lib/gltd-kid-control"

echo "Instalando gltd-kid-control-server em $INSTALL_DIR ..."
sudo mkdir -p "$INSTALL_DIR" "$DATA_DIR"
sudo cp -r "$ROOT/gltd_kid_server" "$INSTALL_DIR/"
sudo cp -r "$ROOT/../lists" "/usr/share/gltd-kid-control/lists" 2>/dev/null || sudo cp -r "$ROOT/../lists" "$INSTALL_DIR/lists"

sudo tee /usr/bin/gltd-kid-server >/dev/null <<'EOF'
#!/usr/bin/env bash
exec python3 -m gltd_kid_server "$@"
EOF
sudo chmod 755 /usr/bin/gltd-kid-server

echo "Instalação concluída."
echo "Configure: sudo gltd-kid-server --config /etc/gltd-kid-control/config.json"
