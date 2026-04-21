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

# Make the bundled echo_mcp package importable (always needed).
sys.path.insert(0, str(HERE))

# Bundled deps in lib/ are a LAST-RESORT fallback. If the launcher used
# uv (or any other mechanism that put deps earlier on sys.path), those
# should win — the bundled wheels are built for a specific Python
# version and may fail on others (e.g. pydantic_core's C extension).
# So we append lib/ to the END.
if LIB.exists():
    sys.path.append(str(LIB))

# Empty-string env vars from DXT user_config should behave like "not set"
for key in ("ZOOM_CLIENT_ID", "ZOOM_SUBDOMAIN"):
    if os.environ.get(key, "").strip() == "":
        os.environ.pop(key, None)

from echo_mcp.mcp_server import mcp  # noqa: E402


if __name__ == "__main__":
    mcp.run()
