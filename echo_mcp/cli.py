"""CLI entry points for ECHO login/logout."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv


def _get_client_id() -> str:
    load_dotenv()
    client_id = os.environ.get("ZOOM_CLIENT_ID", "")
    if not client_id:
        print("Error: ZOOM_CLIENT_ID not set.")
        print("Add it to your .env file or set the environment variable.")
        print("(Your IT team provides this — it's a public app identifier, not a secret.)")
        sys.exit(1)
    return client_id


def login_cli():
    """Entry point for `echo-login`."""
    from .auth import login

    client_id = _get_client_id()
    print("ECHO — Explore Calls, Hearings & Observations")
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
