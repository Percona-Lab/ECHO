#!/usr/bin/env bash
# ECHO installer - Explore Calls, Hearings & Observations
# Usage: curl -fsSL https://raw.githubusercontent.com/Percona-Lab/ECHO/main/install.sh | bash
set -euo pipefail

# Re-exec with /dev/tty if piped (enables interactive prompts via curl | bash)
if [ ! -t 0 ]; then
  exec bash <(curl -fsSL "https://raw.githubusercontent.com/Percona-Lab/ECHO/main/install.sh") </dev/tty
fi

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

banner() {
  echo ""
  echo -e "${BOLD}ECHO${NC} - Explore Calls, Hearings & Observations"
  echo -e "${DIM}Search your Zoom meeting transcripts from any MCP-compatible AI tool.${NC}"
  echo ""
}

ask() {
  local prompt="$1" default="$2"
  local display=""
  [ -n "$default" ] && display=" [$default]"
  printf "  %s%s: " "$prompt" "$display" > /dev/tty
  read -r value < /dev/tty
  echo "${value:-$default}"
}

ask_yn() {
  local prompt="$1" default="${2:-y}"
  local hint="Y/n"
  [ "$default" = "n" ] && hint="y/N"
  printf "  %s (%s): " "$prompt" "$hint" > /dev/tty
  read -r value < /dev/tty
  value="${value:-$default}"
  case "$value" in
    [yY]|[yY]es) return 0 ;;
    *) return 1 ;;
  esac
}

die() { echo -e "${RED}Error: $1${NC}" >&2; exit 1; }

# ── Banner ──────────────────────────────────────────────────
banner

# ── Step 1: Check prerequisites ─────────────────────────────
echo -e "${BOLD}Step 1: Prerequisites${NC}"

if ! command -v uv &>/dev/null; then
  echo -e "  ${YELLOW}uv not found. Installing...${NC}"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  command -v uv &>/dev/null || die "Failed to install uv. Install manually: https://docs.astral.sh/uv/"
fi
echo -e "  ${GREEN}✓${NC} uv found: $(uv --version)"

# ── Step 2: Install location ────────────────────────────────
echo ""
echo -e "${BOLD}Step 2: Install location${NC}"
INSTALL_DIR=$(ask "Install directory" "$HOME/echo-mcp")

if [ -d "$INSTALL_DIR/.git" ]; then
  echo -e "  ${YELLOW}Existing installation found. Updating...${NC}"
  git -C "$INSTALL_DIR" pull --ff-only
else
  echo -e "  Cloning ECHO..."
  git clone https://github.com/Percona-Lab/ECHO.git "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# ── Step 3: Install dependencies ────────────────────────────
echo ""
echo -e "${BOLD}Step 3: Dependencies${NC}"
echo -e "  Installing Python dependencies..."
uv sync --quiet
echo -e "  ${GREEN}✓${NC} Dependencies installed"

# ── Step 4: Zoom OAuth Client ID ────────────────────────────
echo ""
echo -e "${BOLD}Step 4: Zoom OAuth Setup${NC}"

REGISTRY_URL="https://raw.githubusercontent.com/Percona-Lab/ECHO/main/client_registry.json"

if [ -f .env ] && grep -q "ZOOM_CLIENT_ID=." .env 2>/dev/null; then
  EXISTING_ID=$(grep "ZOOM_CLIENT_ID=" .env | cut -d= -f2)
  echo -e "  ${GREEN}✓${NC} Client ID already configured: ${DIM}${EXISTING_ID:0:8}...${NC}"
  if ! ask_yn "Keep this Client ID?" "y"; then
    CLIENT_ID=$(ask "Zoom OAuth Client ID" "")
    [ -z "$CLIENT_ID" ] && die "Client ID is required."
    echo "ZOOM_CLIENT_ID=$CLIENT_ID" > .env
  fi
else
  echo -e "  ECHO needs a Zoom OAuth Client ID to connect to your account."
  echo -e "  Let's check if your organization has already registered one."
  echo ""
  ZOOM_DOMAIN=$(ask "Your Zoom domain (e.g. acme.zoom.us)" "")

  CLIENT_ID=""
  if [ -n "$ZOOM_DOMAIN" ]; then
    # Extract org slug: "acme.zoom.us" -> "acme", "acme" -> "acme"
    ORG_SLUG=$(echo "$ZOOM_DOMAIN" | sed 's/\.zoom\.us$//' | sed 's/^https:\/\///')

    # Look up in registry (try local first, then remote)
    if [ -f "$INSTALL_DIR/client_registry.json" ]; then
      REGISTRY_FILE="$INSTALL_DIR/client_registry.json"
    else
      REGISTRY_FILE=$(mktemp)
      curl -fsSL "$REGISTRY_URL" -o "$REGISTRY_FILE" 2>/dev/null || true
    fi

    CLIENT_ID=$(uv run python -c "
import json, sys
try:
    with open('$REGISTRY_FILE') as f:
        registry = json.load(f)
    cid = registry.get('orgs', {}).get('$ORG_SLUG', {}).get('client_id', '')
    print(cid)
except:
    print('')
" 2>/dev/null)

    if [ -n "$CLIENT_ID" ]; then
      ORG_NAME=$(uv run python -c "
import json
with open('$REGISTRY_FILE') as f:
    registry = json.load(f)
print(registry.get('orgs', {}).get('$ORG_SLUG', {}).get('name', '$ORG_SLUG'))
" 2>/dev/null)
      echo -e "  ${GREEN}✓${NC} Found registered Client ID for ${BOLD}${ORG_NAME}${NC}"
      echo "ZOOM_CLIENT_ID=$CLIENT_ID" > .env
      echo -e "  ${GREEN}✓${NC} Client ID saved to .env"
    else
      echo -e "  ${YELLOW}⚠${NC} No registered Client ID found for ${BOLD}${ORG_SLUG}${NC}"
      echo ""
      echo -e "  Someone with Zoom admin access needs to create a General App (OAuth 2.0):"
      echo -e "  ${DIM}  1. Go to https://marketplace.zoom.us > Develop > Build App${NC}"
      echo -e "  ${DIM}  2. Select General App, set redirect URL: http://localhost:8090/callback${NC}"
      echo -e "  ${DIM}  3. Add scopes: recording:read, user:read${NC}"
      echo -e "  ${DIM}  4. Activate the app and copy the Client ID${NC}"
      echo ""
      echo -e "  Once you have it, you can enter it now or add it to .env later."
      echo -e "  To register it for your whole org, submit a PR to client_registry.json"
      echo -e "  so others in your organization can skip this step."
      echo ""
      CLIENT_ID=$(ask "Zoom OAuth Client ID (leave blank to configure later)" "")
    fi
  else
    echo ""
    echo -e "  ${DIM}No domain entered. You can enter a Client ID directly instead.${NC}"
    echo -e "  ${DIM}Create a Zoom OAuth app at https://marketplace.zoom.us${NC}"
    echo ""
    CLIENT_ID=$(ask "Zoom OAuth Client ID (leave blank to configure later)" "")
  fi

  if [ -n "$CLIENT_ID" ] && ! grep -q "ZOOM_CLIENT_ID=$CLIENT_ID" .env 2>/dev/null; then
    echo "ZOOM_CLIENT_ID=$CLIENT_ID" > .env
    echo -e "  ${GREEN}✓${NC} Client ID saved to .env"
  elif [ -z "$CLIENT_ID" ]; then
    cp -n .env.example .env 2>/dev/null || true
    echo -e "  ${YELLOW}⚠${NC} Skipped. Add your Client ID to .env later."
  fi
fi

# ── Step 5: Authenticate with Zoom ──────────────────────────
echo ""
echo -e "${BOLD}Step 5: Zoom Authentication${NC}"

if [ -f "$HOME/.echo/tokens.json" ]; then
  echo -e "  ${GREEN}✓${NC} Already authenticated (tokens found at ~/.echo/tokens.json)"
elif grep -q "ZOOM_CLIENT_ID=." .env 2>/dev/null; then
  if ask_yn "Log in to Zoom now?" "y"; then
    uv run echo-login
  else
    echo -e "  ${DIM}Run 'uv run echo-login' later to authenticate.${NC}"
  fi
else
  echo -e "  ${DIM}Skipped (no Client ID configured yet).${NC}"
  echo -e "  ${DIM}After adding your Client ID to .env, run: uv run echo-login${NC}"
fi

# ── Step 6: Configure AI client ─────────────────────────────
echo ""
echo -e "${BOLD}Step 6: Configure AI Client${NC}"

MCP_ENTRY="{\"type\":\"stdio\",\"command\":\"uv\",\"args\":[\"run\",\"--directory\",\"$INSTALL_DIR\",\"echo-mcp\"]}"

# Claude Code
CLAUDE_SETTINGS="$HOME/.claude/settings.json"
if [ -f "$CLAUDE_SETTINGS" ] || command -v claude &>/dev/null; then
  if ask_yn "Configure Claude Code?" "y"; then
    if [ -f "$CLAUDE_SETTINGS" ]; then
      # Use python to safely merge into existing settings
      uv run python -c "
import json, sys
path = '$CLAUDE_SETTINGS'
try:
    with open(path) as f: cfg = json.load(f)
except: cfg = {}
cfg.setdefault('mcpServers', {})['echo'] = json.loads('$MCP_ENTRY')
with open(path, 'w') as f: json.dump(cfg, f, indent=2)
print('  Updated', path)
"
    else
      mkdir -p "$HOME/.claude"
      echo "{\"mcpServers\":{\"echo\":$MCP_ENTRY}}" | uv run python -m json.tool > "$CLAUDE_SETTINGS"
      echo -e "  Created $CLAUDE_SETTINGS"
    fi
    echo -e "  ${GREEN}✓${NC} Claude Code configured"
  fi
fi

# Claude Desktop
CLAUDE_DESKTOP=""
if [ "$(uname)" = "Darwin" ]; then
  CLAUDE_DESKTOP="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
elif [ -f "$HOME/.config/Claude/claude_desktop_config.json" ]; then
  CLAUDE_DESKTOP="$HOME/.config/Claude/claude_desktop_config.json"
fi

if [ -n "$CLAUDE_DESKTOP" ] && [ -f "$CLAUDE_DESKTOP" ]; then
  if ask_yn "Configure Claude Desktop?" "y"; then
    uv run python -c "
import json
path = '''$CLAUDE_DESKTOP'''
try:
    with open(path) as f: cfg = json.load(f)
except: cfg = {}
cfg.setdefault('mcpServers', {})['echo'] = json.loads('$MCP_ENTRY')
with open(path, 'w') as f: json.dump(cfg, f, indent=2)
print('  Updated', path)
"
    echo -e "  ${GREEN}✓${NC} Claude Desktop configured (restart to apply)"
  fi
fi

# ── Done ────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}ECHO installed!${NC}"
echo ""
echo -e "  ${DIM}Location:${NC}    $INSTALL_DIR"
[ -f "$HOME/.echo/tokens.json" ] && echo -e "  ${DIM}Auth:${NC}        Authenticated" || echo -e "  ${DIM}Auth:${NC}        Run 'uv run echo-login' to connect your Zoom account"
echo ""
echo -e "  ${DIM}Usage:${NC}       Ask your AI assistant about your Zoom meetings."
echo -e "  ${DIM}Example:${NC}     \"Search my Zoom calls for quarterly roadmap\""
echo ""
