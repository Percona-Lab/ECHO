"""DXT entry point for ECHO.

This file bootstraps the ECHO MCP server when launched by Claude Desktop
(or any DXT-compatible host). It adds the bundled dependencies to sys.path
then hands off to the real server.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB = HERE / "lib"

# Prefer bundled deps when available
if LIB.exists():
    sys.path.insert(0, str(LIB))

# Make the bundled package importable
sys.path.insert(0, str(HERE))

# Empty-string env vars from DXT user_config should behave like "not set"
for key in ("ZOOM_CLIENT_ID", "ZOOM_SUBDOMAIN"):
    if os.environ.get(key, "").strip() == "":
        os.environ.pop(key, None)

from echo_mcp.mcp_server import mcp  # noqa: E402


if __name__ == "__main__":
    mcp.run()
