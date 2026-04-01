#!/usr/bin/env bash
# ECHO installer bootstrap
# Usage: curl -fsSL https://raw.githubusercontent.com/Percona-Lab/ECHO/main/install.sh | bash
set -euo pipefail

echo ""
echo "ECHO - Explore Calls, Hearings & Observations"
echo ""

# Install uv if needed
if ! command -v uv &>/dev/null; then
  echo "  Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  if ! command -v uv &>/dev/null; then
    echo "  uv installed but not in PATH. Restart your shell and re-run."
    exit 1
  fi
fi

# Download and run the Python installer
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

curl -fsSL "https://raw.githubusercontent.com/Percona-Lab/ECHO/main/installer.py" -o "$TMPDIR/installer.py"
uv run --python 3.12 "$TMPDIR/installer.py"
