"""Zoom API connector using user OAuth tokens (PKCE flow).

No org-level secrets on the user's machine. The connector uses tokens
obtained via the OAuth Authorization Code + PKCE flow, stored in
~/.echo/tokens.json.
"""

from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv

from .auth import load_tokens, tokens_valid, refresh_access_token

load_dotenv()

BASE_URL = "https://api.zoom.us/v2"


class ZoomConnector:
    """Handles Zoom API requests using user OAuth tokens."""

    def __init__(self) -> None:
        self.client_id = os.environ.get("ZOOM_CLIENT_ID", "")
        self._tokens: dict | None = None

    def _load_or_fail(self) -> dict:
        """Load tokens, refreshing if needed."""
        if self._tokens and tokens_valid(self._tokens):
            return self._tokens

        tokens = load_tokens()
        if tokens is None:
            raise RuntimeError(
                "Not authenticated. Run: echo-login\n"
                "This will open Zoom in your browser to authorize ECHO."
            )
        self._tokens = tokens
        return tokens

    async def _ensure_valid_token(self) -> str:
        """Get a valid access token, refreshing if expired."""
        tokens = self._load_or_fail()

        if not tokens_valid(tokens):
            tokens = await refresh_access_token(self.client_id, tokens)
            self._tokens = tokens

        return tokens["access_token"]

    async def _request(
        self, method: str, path: str, params: dict | None = None
    ) -> dict:
        """Make an authenticated request to the Zoom API."""
        token = await self._ensure_valid_token()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.request(
                method,
                f"{BASE_URL}{path}",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            return resp.json()

    async def list_recordings(
        self, from_date: str, to_date: str, page_size: int = 30
    ) -> dict:
        """List cloud recordings for the authenticated user.

        Uses /users/me/ which resolves to whoever owns the OAuth token.

        Args:
            from_date: Start date (YYYY-MM-DD). Max range is 1 month.
            to_date: End date (YYYY-MM-DD).
            page_size: Number of results per page (max 300).
        """
        return await self._request(
            "GET",
            "/users/me/recordings",
            params={"from": from_date, "to": to_date, "page_size": page_size},
        )

    async def get_meeting_recordings(self, meeting_id: str) -> dict:
        """Get recording files (including transcript) for a specific meeting."""
        return await self._request("GET", f"/meetings/{meeting_id}/recordings")

    async def get_transcript_content(self, download_url: str) -> str:
        """Download the VTT transcript content from a recording download URL."""
        token = await self._ensure_valid_token()
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(
                download_url,
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            return resp.text
