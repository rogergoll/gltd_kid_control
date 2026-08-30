#!/usr/bin/env bash
# Gera o pacote .deb do gltd-kid-control-server (esboço inicial).
# Requer: dpkg-deb, python3, pip (opcional).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="0.1.0"
PKG="gltd-kid-control-server"
BUILD_DIR="$(mktemp -d)"
DEST="${ROOT}/dist"
mkdir -p "$DEST"

# Estrutura do pacote
mkdir -p "$BUILD_DIR/DEBIAN"
mkdir -p "$BUILD_DIR/usr/lib/gltd-kid-control"
mkdir -p "$BUILD_DIR/usr/bin"
mkdir -p "$BUILD_DIR/usr/share/gltd-kid-control"

# Copia o código
cp -r "$ROOT/gltd_kid_server" "$BUILD_DIR/usr/lib/gltd-kid-control/"
cp -r "$ROOT/../lists" "$BUILD_DIR/usr/share/gltd-kid-control/lists"
cp -r "$ROOT/../config" "$BUILD_DIR/usr/share/gltd-kid-control/config"

# Entrypoint
cat > "$BUILD_DIR/usr/bin/gltd-kid-server" <<'EOF'
#!/usr/bin/env bash
exec python3 -m gltd_kid_server "$@"
EOF
chmod 755 "$BUILD_DIR/usr/bin/gltd-kid-server"

# Metadados DEBIAN
cat > "$BUILD_DIR/DEBIAN/control" <<EOF
Package: ${PKG}
Version: ${VERSION}
Section: net
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), mariadb-server, mariadb-client, python3-pymysql
Maintainer: GLTD
Description: Servidor de controle parental da família (GLTD Kid Control)
EOF

dpkg-deb --build "$BUILD_DIR" "$DEST/${PKG}_${VERSION}_all.deb"
echo "Pacote gerado em $DEST/${PKG}_${VERSION}_all.deb"
rm -rf "$BUILD_DIR"
