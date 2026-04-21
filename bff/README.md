# ECHO BFF

Backend-for-Frontend for Zoom OAuth. Holds client secrets so they never
leave the server. The ECHO MCP client on each user's machine sends the
authorization code (plus PKCE verifier) here; the BFF injects the secret
and forwards to Zoom.

## Endpoints

- `POST /exchange` — exchange authorization code for access/refresh tokens
- `POST /refresh` — use a refresh token to get a new access token
- `GET /health` — liveness check

## Deploy

Run `./deploy.sh` from a machine with SSH access to SHERPA. It:

1. Uploads `app.py`, `requirements.txt`, the systemd service, and the nginx config
2. Creates a Python venv and installs deps
3. Enables the systemd service
4. Installs the nginx config and reloads

## Configuration

Secrets live in `/home/dennis.kittrell/echo-bff/secrets.env` on SHERPA:

```
ZOOM_CLIENTS_JSON={"<client_id_1>": "<secret_1>", "<client_id_2>": "<secret_2>"}
```

Each entry is one Zoom OAuth app — typically one per org. To add a new
org: SSH to SHERPA, edit `secrets.env`, and `sudo systemctl restart echo-bff`.

## Security model

- Secrets are only on SHERPA. The file is mode 600, readable only by
  `dennis.kittrell`.
- The BFF only accepts `redirect_uri=http://localhost:8090/callback` to
  prevent open-redirect abuse.
- Client IDs not in `ZOOM_CLIENTS_JSON` get 401 with no hint about
  whether the ID is close-but-wrong.
- SHERPA is VPN-only, so only Perconians can reach the BFF.
