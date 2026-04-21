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

echo "→ Copying manifest, entry point, and launcher"
cp "$DXT_DIR/manifest.json" "$BUILD/manifest.json"
cp "$DXT_DIR/server/main.py" "$BUILD/server/main.py"
cp "$DXT_DIR/server/launcher.sh" "$BUILD/server/launcher.sh"
chmod +x "$BUILD/server/launcher.sh"

# Optional icon
if [[ -f "$DXT_DIR/icon.png" ]]; then
  cp "$DXT_DIR/icon.png" "$BUILD/icon.png"
fi

echo "→ Writing requirements.txt (used by uv path in launcher)"
cat > "$BUILD/server/requirements.txt" <<'EOF'
mcp[cli]>=1.2.0
httpx>=0.27.0
python-dotenv>=1.0.0
EOF

echo "→ Installing Python dependencies into server/lib (fallback path)"
# Use a known-modern Python to build deps so the match-statement-using
# code works at runtime (macOS's /usr/bin/python3 is 3.9 — too old).
BUILD_PY=""
for py in /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3.13 \
          /opt/homebrew/bin/python3.14 python3.12 python3.13 python3.14 \
          /opt/homebrew/bin/python3 python3; do
  if command -v "$py" >/dev/null 2>&1; then
    if "$py" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      BUILD_PY="$py"
      break
    fi
  fi
done
if [[ -z "$BUILD_PY" ]]; then
  echo "No Python 3.10+ found on this machine to build deps." >&2
  exit 1
fi
echo "  Using $BUILD_PY"
"$BUILD_PY" -m pip install \
  --target "$BUILD/server/lib" \
  --quiet \
  --no-compile \
  -r "$BUILD/server/requirements.txt"

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
