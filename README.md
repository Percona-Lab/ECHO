# ECHO - Explore Calls, Hearings & Observations

MCP server for searching your Zoom meeting transcripts from any MCP-compatible AI tool. Part of the [Alpine Toolkit](https://github.com/Percona-Lab).

Uses OAuth 2.0 + PKCE so no secrets ever touch your machine. You log in with your own Zoom account and ECHO can only see your recordings.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/Percona-Lab/ECHO/main/install.sh | bash
```

The installer will guide you through:
1. Cloning the repo and installing dependencies
2. Configuring your Zoom OAuth Client ID
3. Authenticating with your Zoom account
4. Auto-detecting and configuring your AI client (Claude Code, Claude Desktop)

## Prerequisites

You need a **Zoom OAuth Client ID** from a General App (OAuth 2.0). If you have admin or owner access to your Zoom account, you can create this yourself. If not, ask your Zoom admin.

### Creating a Zoom OAuth App

1. Go to [marketplace.zoom.us](https://marketplace.zoom.us) > **Develop** > **Build App**
2. Select **General App** (OAuth 2.0)
3. Set redirect URL to `http://localhost:8090/callback`
4. Add scopes: `recording:read` and `user:read`
5. Activate the app
6. Copy the **Client ID** (you do not need the Client Secret)

The PKCE flow means the Client Secret stays in the Zoom admin console and never needs to be shared.

### Organization registry

If your org has already set up the Zoom OAuth app, the installer will find the Client ID automatically when you enter your Zoom domain (e.g. `percona.zoom.us`).

To register your org's Client ID so others can skip this step, submit a PR adding your org to `client_registry.json`:

```json
{
  "orgs": {
    "yourcompany": {
      "name": "Your Company",
      "client_id": "YOUR_CLIENT_ID_HERE"
    }
  }
}
```

Client IDs are public identifiers, safe to commit.

## Tools

| Tool | Description |
|------|-------------|
| `auth_status` | Check if ECHO is connected to your Zoom account |
| `list_meetings` | List your recent meetings with cloud recordings |
| `get_transcript` | Get the full transcript for a specific meeting |
| `search_transcripts` | Search across your meeting transcripts by keyword or phrase |
| `meeting_summary` | Get participants and a condensed conversation flow |

## CLI Commands

| Command | Description |
|---------|-------------|
| `uv run echo-login` | Authorize ECHO with your Zoom account |
| `uv run echo-logout` | Remove stored tokens |
| `uv run echo-mcp` | Run the MCP server |

## Security Model

ECHO is designed so that no org-level secrets ever touch your machine.

| What | Where | Who controls it |
|------|-------|-----------------|
| Client Secret | Zoom admin console | Zoom admin (never shared) |
| Client ID | Your `.env` file | You (public identifier, safe to share) |
| OAuth tokens | `~/.echo/tokens.json` (mode 600) | You (scoped to your account only) |

How it works:
- You authenticate by signing into Zoom in your browser (OAuth + PKCE)
- ECHO uses `/users/me/` endpoints, so it can only see your recordings
- Tokens auto-refresh so you stay logged in without re-authenticating

## Manual Setup

If you prefer not to use the installer:

```bash
git clone https://github.com/Percona-Lab/ECHO.git
cd ECHO
uv sync
cp .env.example .env        # Add your Zoom Client ID
uv run echo-login            # Authenticate with Zoom
```

Then add to your MCP client config:

```json
{
  "mcpServers": {
    "echo": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ECHO", "echo-mcp"]
    }
  }
}
```

## Development

```bash
uv sync
uv run echo-mcp                                          # Run server
npx @modelcontextprotocol/inspector uv run echo-mcp      # MCP Inspector
```

## Built with

- [FastMCP](https://github.com/jlowin/fastmcp) - Python MCP framework
- [CAIRN](https://github.com/Percona-Lab/CAIRN) - Alpine Toolkit scaffolder
