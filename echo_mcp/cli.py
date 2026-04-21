"""CLI entry points for ECHO login/logout."""

from __future__ import annotations

import sys

from dotenv import load_dotenv


def _get_client_id() -> str:
    """Resolve Client ID from env or registry."""
    from .registry import resolve_client_id, RegistryError

    load_dotenv()
    try:
        return resolve_client_id()
    except RegistryError as e:
        print(f"Error: {e}")
        sys.exit(1)


def login_cli():
    """Entry point for `echo-login`."""
    from .auth import login

    client_id = _get_client_id()
    print("ECHO - Explore Calls, Hearings & Observations")
    print("=" * 48)
    try:
        login(client_id)
    except Exception as e:
        print(f"\nLogin failed: {e}")
        sys.exit(1)


def logout_cli():
    """Entry point for `echo-logout`."""
    from .auth import logout

    logout()
