#!/usr/bin/env bash
# Deploy the ECHO BFF to SHERPA.
#
# Requires:
#   - SSH access to SHERPA (host alias `sherpa` in ~/.ssh/config)
#   - Sudo on SHERPA (for systemd + nginx)
#
# Usage: ./deploy.sh
#
# On first run you'll be prompted to create secrets.env with Zoom client
# credentials. On subsequent runs it just updates code and restarts.

set -euo pipefail

HOST="sherpa"
REMOTE_USER="dennis.kittrell"
REMOTE_DIR="/home/${REMOTE_USER}/echo-bff"
SERVICE="echo-bff"

HERE="$(cd "$(dirname "$0")" && pwd)"

echo "==> Uploading files to ${HOST}:${REMOTE_DIR}"
ssh "$HOST" "mkdir -p ${REMOTE_DIR}"
rsync -az --delete \
  --exclude 'venv/' \
  --exclude 'secrets.env' \
  --exclude '__pycache__/' \
  --exclude 'deploy.sh' \
  "$HERE/" "$HOST:${REMOTE_DIR}/"

echo "==> Creating venv + installing deps"
ssh "$HOST" "cd ${REMOTE_DIR} && \
  (test -d venv || python3 -m venv venv) && \
  ./venv/bin/pip install --quiet --upgrade pip && \
  ./venv/bin/pip install --quiet -r requirements.txt"

echo "==> Installing systemd service"
ssh "$HOST" "sudo cp ${REMOTE_DIR}/${SERVICE}.service /etc/systemd/system/${SERVICE}.service && \
  sudo systemctl daemon-reload"

# Check for secrets file; warn if missing
if ! ssh "$HOST" "test -f ${REMOTE_DIR}/secrets.env"; then
  echo ""
  echo "⚠️  No secrets.env yet. Create it with:"
  echo ""
  echo "    ssh $HOST"
  echo "    cat > ${REMOTE_DIR}/secrets.env <<'EOF'"
  echo "    ZOOM_CLIENTS_JSON={\"<client_id>\":\"<client_secret>\"}"
  echo "    EOF"
  echo "    chmod 600 ${REMOTE_DIR}/secrets.env"
  echo ""
  echo "Then: sudo systemctl restart ${SERVICE}"
  echo ""
  exit 0
fi

echo "==> Installing nginx config"
ssh "$HOST" "sudo cp ${REMOTE_DIR}/nginx.conf /etc/nginx/sites-available/${SERVICE} && \
  sudo ln -sf /etc/nginx/sites-available/${SERVICE} /etc/nginx/sites-enabled/${SERVICE} && \
  sudo nginx -t && \
  sudo systemctl reload nginx"

echo "==> Restarting ${SERVICE}"
ssh "$HOST" "sudo systemctl enable --now ${SERVICE} && \
  sudo systemctl restart ${SERVICE} && \
  sleep 1 && \
  systemctl is-active ${SERVICE}"

echo "==> Smoke test /health"
ssh "$HOST" "curl -s http://127.0.0.1:3100/health && echo"

echo ""
echo "✓ ECHO BFF is live on SHERPA."
echo "  Internal URL: http://sherpa.tp.int.percona.com/health"
echo "  Service:      systemctl status ${SERVICE}  (on sherpa)"
echo "  Logs:         journalctl -u ${SERVICE} -f  (on sherpa)"
