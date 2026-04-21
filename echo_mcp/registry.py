"""Client ID resolver.

Resolves the Zoom OAuth Client ID from either:
1. ZOOM_CLIENT_ID environment variable (explicit override)
2. Registry lookup using ZOOM_SUBDOMAIN

The registry is fetched from the public GitHub repo and cached locally
to avoid hitting the network on every call.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx

REGISTRY_URL = (
    "https://raw.githubusercontent.com/Percona-Lab/ECHO/main/client_registry.json"
)
CACHE_DIR = Path.home() / ".echo"
CACHE_FILE = CACHE_DIR / "registry_cache.json"
CACHE_TTL_SECONDS = 24 * 3600  # 24 hours


class RegistryError(Exception):
    """Raised when the Client ID cannot be resolved."""


def _load_cache() -> dict | None:
    """Load the cached registry if it's still fresh."""
    if not CACHE_FILE.exists():
        return None
    try:
        data = json.loads(CACHE_FILE.read_text())
        if time.time() - data.get("_cached_at", 0) < CACHE_TTL_SECONDS:
            return data.get("registry")
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _save_cache(registry: dict) -> None:
    """Save the registry to the local cache."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(
            json.dumps({"_cached_at": time.time(), "registry": registry}, indent=2)
        )
    except OSError:
        pass  # Cache is best-effort


def _fetch_registry() -> dict:
    """Fetch the registry from GitHub."""
    with httpx.Client(timeout=10) as client:
        resp = client.get(REGISTRY_URL)
        resp.raise_for_status()
        return resp.json()


def get_registry(force_refresh: bool = False) -> dict:
    """Get the registry, using cache when possible."""
    if not force_refresh:
        cached = _load_cache()
        if cached is not None:
            return cached
    registry = _fetch_registry()
    _save_cache(registry)
    return registry


def _lookup_org(subdomain: str) -> dict | None:
    """Look up an org entry in the registry.

    Registry entries can be either a bare string (just client_id) or a
    dict with {client_id, bff_url}. Returns a normalized dict or None.
    """
    try:
        registry = get_registry()
    except Exception as e:
        raise RegistryError(
            f"Could not fetch the ECHO client registry: {e}\n"
            f"Check your internet connection or set ZOOM_CLIENT_ID manually."
        )
    orgs = registry.get("orgs", {})
    entry = orgs.get(subdomain)
    if entry is None:
        return None
    if isinstance(entry, str):
        return {"client_id": entry, "bff_url": None}
    return {
        "client_id": entry.get("client_id", ""),
        "bff_url": entry.get("bff_url"),
    }


def resolve_client_id() -> str:
    """Resolve the Zoom OAuth Client ID.

    Priority:
    1. ZOOM_CLIENT_ID env var (explicit override)
    2. Registry lookup via ZOOM_SUBDOMAIN env var

    Also sets ECHO_BFF_URL in the process environment if the registry
    entry for the org includes a bff_url and no explicit ECHO_BFF_URL is
    already set.

    Raises RegistryError with guidance if neither works.
    """
    # 1. Explicit Client ID always wins
    explicit = os.environ.get("ZOOM_CLIENT_ID", "").strip()
    if explicit and not explicit.startswith("your_"):
        return explicit

    # 2. Registry lookup
    subdomain = os.environ.get("ZOOM_SUBDOMAIN", "").strip().lower()
    if subdomain:
        # Strip common mistakes: full URL, .zoom.us suffix
        subdomain = subdomain.replace("https://", "").replace("http://", "")
        subdomain = subdomain.split(".")[0]

        entry = _lookup_org(subdomain)
        if entry and entry["client_id"]:
            # Apply the BFF URL from the registry if the user hasn't set one
            if entry.get("bff_url") and not os.environ.get("ECHO_BFF_URL"):
                os.environ["ECHO_BFF_URL"] = entry["bff_url"]
            return entry["client_id"]

        raise RegistryError(
            f"Your org '{subdomain}' is not in the ECHO registry yet.\n\n"
            f"Two options:\n"
            f"  1. Ask your Zoom admin to create an OAuth app, then set "
            f"ZOOM_CLIENT_ID in this extension's settings.\n"
            f"  2. Submit a PR to add '{subdomain}' to the registry:\n"
            f"     https://github.com/Percona-Lab/ECHO/blob/main/client_registry.json"
        )

    raise RegistryError(
        "ECHO is not configured.\n"
        "Set ZOOM_SUBDOMAIN (e.g. 'acme' for acme.zoom.us) so ECHO can look up\n"
        "your org's OAuth Client ID. If your org isn't registered, also set\n"
        "ZOOM_CLIENT_ID directly."
    )
