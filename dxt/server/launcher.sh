#!/bin/bash
# ECHO DXT launcher.
#
# Finds a Python 3.10+ interpreter or uses uv if available.
# macOS's /usr/bin/python3 is 3.9 which is too old for the mcp library
# (uses match/case statements from 3.10+), so we search harder.

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

# Prefer uv when present — it manages Python versions and packages cleanly.
# Common install locations first, then PATH.
for uv_candidate in \
  "$HOME/.local/bin/uv" \
  "$HOME/.cargo/bin/uv" \
  "/opt/homebrew/bin/uv" \
  "/usr/local/bin/uv" \
  "$(command -v uv 2>/dev/null)"
do
  if [ -n "$uv_candidate" ] && [ -x "$uv_candidate" ]; then
    # Let uv ensure a 3.12 runtime and install our deps from pyproject
    cd "$DIR/.."  # pyproject.toml lives next to server/
    exec "$uv_candidate" run --quiet --python 3.12 \
      --with-requirements "$DIR/requirements.txt" \
      "$DIR/main.py"
  fi
done

# Fall back: find any Python 3.10+ on PATH.
# Use bundled deps in $DIR/lib via PYTHONPATH (set by manifest env).
for py in python3.14 python3.13 python3.12 python3.11 python3.10 python3 python; do
  if command -v "$py" >/dev/null 2>&1; then
    if "$py" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      exec "$py" "$DIR/main.py"
    fi
  fi
done

# Nothing worked — tell the user what to do.
cat >&2 <<'EOF'
ERROR: ECHO requires Python 3.10 or newer, or the 'uv' tool.

macOS's built-in /usr/bin/python3 is Python 3.9 (too old). Install one of:

  Option 1 (recommended): install uv
    curl -LsSf https://astral.sh/uv/install.sh | sh

  Option 2: install a modern Python via Homebrew
    brew install python@3.12

Then quit and reopen Claude Desktop to retry.
EOF
exit 1
