#!/usr/bin/env bash
# Gera o pacote .deb do gltd-kid-control-client.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="0.1.0"
PKG="gltd-kid-control-client"
BUILD="$(mktemp -d)"
DEST="$ROOT/dist"
mkdir -p "$DEST"

# ---- estrutura do pacote ----
mkdir -p "$BUILD/DEBIAN"
mkdir -p "$BUILD/usr/lib/python3/dist-packages/gltd_kid_client"
mkdir -p "$BUILD/usr/bin"
mkdir -p "$BUILD/usr/share/gltd-kid-control/icons"
mkdir -p "$BUILD/usr/share/gltd-kid-control/extension"
mkdir -p "$BUILD/usr/share/applications"
mkdir -p "$BUILD/usr/share/gltd-kid-control"

# código python
cp "$ROOT/gltd_kid_client"/*.py "$BUILD/usr/lib/python3/dist-packages/gltd_kid_client/"

# binários
cat > "$BUILD/usr/bin/gltd-kid-client" <<'EOF'
#!/usr/bin/env bash
exec python3 -m gltd_kid_client "$@"
EOF
cat > "$BUILD/usr/bin/gltd-kid-client-tray" <<'EOF'
#!/usr/bin/env bash
exec python3 -m gltd_kid_client.tray
EOF
cat > "$BUILD/usr/bin/gltd-kid-client-status" <<'EOF'
#!/usr/bin/env bash
S=$(gltd-kid-client status 2>/dev/null)
notify-send -i gltd-kid-control "GLTD Kid Control" "$S" 2>/dev/null || echo "$S"
EOF
chmod 755 "$BUILD/usr/bin/gltd-kid-client" "$BUILD/usr/bin/gltd-kid-client-tray" "$BUILD/usr/bin/gltd-kid-client-status"

# ícones
cp "$ROOT/icons/gltd-kid-control.png" "$BUILD/usr/share/gltd-kid-control/icons/"
cp "$ROOT/icons/gltd-kid-control-blocked.png" "$BUILD/usr/share/gltd-kid-control/icons/"

# extensão (YouTube)
cp "$ROOT/extension/manifest.json" "$ROOT/extension/content.js" \
   "$ROOT/extension/popup.html" "$ROOT/extension/icon16.png" \
   "$ROOT/extension/icon48.png" "$ROOT/extension/icon128.png" \
   "$BUILD/usr/share/gltd-kid-control/extension/"
if [ -f "$ROOT/extension/gltd.crx" ]; then
  cp "$ROOT/extension/gltd.crx" "$BUILD/usr/share/gltd-kid-control/extension/"
fi

# serviço systemd
cp "$ROOT/scripts/gltd-kid-client.service" "$BUILD/usr/share/gltd-kid-control/"

# atalho no menu
cat > "$BUILD/usr/share/applications/gltd-kid-control-client.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Version=1.0
Name=GLTD Kid Control
Name[pt_BR]=GLTD Kid Control
GenericName=Controle Parental
GenericName[pt_BR]=Controle Parental
Comment=Status da proteção parental
Comment[pt_BR]=Status da proteção parental
Exec=/usr/bin/gltd-kid-client-status
Icon=/usr/share/gltd-kid-control/icons/gltd-kid-control.png
Terminal=false
Categories=Network;Utility;
EOF

# template de autostart (criado na home da criança pelo setup)
cat > "$BUILD/usr/share/gltd-kid-control/autostart.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=GLTD Kid Control (status)
Exec=/usr/bin/gltd-kid-client-tray
Icon=/usr/share/gltd-kid-control/icons/gltd-kid-control.png
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

# ---- metadados ----
cat > "$BUILD/DEBIAN/control" <<EOF
Package: ${PKG}
Version: ${VERSION}
Section: net
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), libnotify-bin
Maintainer: GLTD
Description: Cliente de controle parental GLTD Kid Control
 Cliente que roda na máquina da criança: bloqueia navegadores não
 autorizados e reporta histórico/uso ao servidor da família.
EOF

cp "$ROOT/scripts/postinst" "$BUILD/DEBIAN/postinst"
chmod 755 "$BUILD/DEBIAN/postinst"

dpkg-deb --root-owner-group --build "$BUILD" "$DEST/${PKG}_${VERSION}_all.deb"
echo "Pacote gerado em $DEST/${PKG}_${VERSION}_all.deb"
rm -rf "$BUILD"
