"""ECHO BFF — Backend-for-Frontend for Zoom OAuth.

Holds Zoom OAuth client secrets and proxies token exchange/refresh for
the ECHO MCP client. Users never see the secret; it lives only here.

Each Zoom OAuth app (one per registered org) is configured via env vars:

    ZOOM_CLIENTS_JSON='{"<client_id>": "<client_secret>", ...}'

The client sends requests with its `client_id`; the BFF looks up the
matching secret and forwards to Zoom.

Endpoints:
    POST /exchange  -- exchange authorization code for tokens
    POST /refresh   -- refresh access token
    GET  /health    -- liveness check
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

ZOOM_TOKEN_URL = "https://zoom.us/oauth/token"

# Map of client_id -> client_secret, loaded from ZOOM_CLIENTS_JSON
try:
    CLIENTS: dict[str, str] = json.loads(os.environ.get("ZOOM_CLIENTS_JSON", "{}"))
except json.JSONDecodeError:
    print("FATAL: ZOOM_CLIENTS_JSON is not valid JSON", file=sys.stderr)
    sys.exit(1)

if not CLIENTS:
    print(
        "WARN: ZOOM_CLIENTS_JSON is empty — no clients will be accepted",
        file=sys.stderr,
    )

ALLOWED_REDIRECTS = {"http://localhost:8090/callback"}

app = FastAPI(
    title="ECHO BFF",
    description="Proxy for Zoom OAuth token exchange. Secrets never leave this server.",
    version="0.1.0",
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ExchangeRequest(BaseModel):
    client_id: str
    code: str
    code_verifier: str
    redirect_uri: str


class RefreshRequest(BaseModel):
    client_id: str
    refresh_token: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_secret(client_id: str) -> str:
    secret = CLIENTS.get(client_id)
    if not secret:
        # Avoid revealing whether the client_id is partially recognized
        raise HTTPException(status_code=401, detail="Unknown or unauthorized client_id")
    return secret


async def _forward_to_zoom(data: dict[str, Any]) -> dict[str, Any]:
    """POST to Zoom's /oauth/token and return the parsed JSON response."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            ZOOM_TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}

    if resp.status_code != 200:
        # Pass Zoom's error through so the client can surface it
        raise HTTPException(status_code=resp.status_code, detail=body)
    return body


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "clients_configured": len(CLIENTS),
        "timestamp": int(time.time()),
    }


@app.post("/exchange")
async def exchange(req: ExchangeRequest) -> dict[str, Any]:
    """Exchange an OAuth authorization code for tokens.

    The client sends the code + PKCE verifier; we add the client_secret
    and forward to Zoom.
    """
    if req.redirect_uri not in ALLOWED_REDIRECTS:
        raise HTTPException(
            status_code=400,
            detail=f"redirect_uri not allowed: {req.redirect_uri}",
        )

    secret = _resolve_secret(req.client_id)
    return await _forward_to_zoom({
        "grant_type": "authorization_code",
        "code": req.code,
        "redirect_uri": req.redirect_uri,
        "client_id": req.client_id,
        "client_secret": secret,
        "code_verifier": req.code_verifier,
    })


@app.post("/refresh")
async def refresh(req: RefreshRequest) -> dict[str, Any]:
    """Refresh an expired access token."""
    secret = _resolve_secret(req.client_id)
    return await _forward_to_zoom({
        "grant_type": "refresh_token",
        "refresh_token": req.refresh_token,
        "client_id": req.client_id,
        "client_secret": secret,
    })
