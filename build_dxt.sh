#!/usr/bin/env bash
# Build the ECHO Desktop Extension (.dxt) bundle.
#
# Produces: dist/echo.dxt — a zip file installable by double-click in
# Claude Desktop (and any other DXT-compatible host).
#
# Usage: ./build_dxt.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
DXT_DIR="$ROOT/dxt"
DIST="$ROOT/dist"
BUILD="$ROOT/.dxt_build"

echo "→ Cleaning previous build"
rm -rf "$BUILD" "$DIST/echo.dxt"
mkdir -p "$BUILD/server/echo_mcp" "$BUILD/server/lib" "$DIST"

echo "→ Copying ECHO package"
cp -r "$ROOT/echo_mcp/"*.py "$BUILD/server/echo_mcp/"

echo "→ Copying manifest and entry point"
cp "$DXT_DIR/manifest.json" "$BUILD/manifest.json"
cp "$DXT_DIR/server/main.py" "$BUILD/server/main.py"

# Optional icon
if [[ -f "$DXT_DIR/icon.png" ]]; then
  cp "$DXT_DIR/icon.png" "$BUILD/icon.png"
fi

echo "→ Installing Python dependencies into server/lib"
python3 -m pip install \
  --target "$BUILD/server/lib" \
  --quiet \
  --no-compile \
  "mcp[cli]>=1.2.0" \
  "httpx>=0.27.0" \
  "python-dotenv>=1.0.0"

echo "→ Stripping test/cache files to keep bundle small"
find "$BUILD" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD" -type d -name "test" -exec rm -rf {} + 2>/dev/null || true

echo "→ Creating dist/echo.dxt"
cd "$BUILD"
zip -r -q "$DIST/echo.dxt" .
cd "$ROOT"

SIZE="$(du -h "$DIST/echo.dxt" | cut -f1)"
echo ""
echo "✓ Built dist/echo.dxt (${SIZE})"
echo ""
echo "To install: double-click dist/echo.dxt in Finder (or open it"
echo "via Claude Desktop > Settings > Extensions > Install from file)."
