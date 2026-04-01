# ECHO — Explore Calls, Hearings & Observations

MCP server for searching your Zoom meeting transcripts. Part of the **Alpine Toolkit**.

Uses OAuth 2.0 + PKCE so **no secrets ever touch your machine** — you log in with
your own Zoom account and ECHO can only see your recordings.

## Tools

| Tool | Description |
|------|-------------|
| `auth_status` | Check if ECHO is connected to your Zoom account |
| `list_meetings` | List your recent meetings with cloud recordings |
| `get_transcript` | Get the full transcript for a specific meeting |
| `search_transcripts` | Search across your meeting transcripts by keyword/phrase |
| `meeting_summary` | Get participants and condensed conversation flow |

## Setup

### 1. IT creates a Zoom OAuth App (one-time)

Ask IT to create a **General App** (OAuth) in the Zoom Marketplace:

1. Go to [Zoom Marketplace](https://marketplace.zoom.us/) → **Develop** → **Build App**
2. Choose **General App** (OAuth 2.0)
3. Set redirect URL to: `http://localhost:8090/callback`
4. Under **Scopes**, add:
   - `recording:read` — read user's own recordings
   - `user:read` — read user's own profile
5. Enable PKCE (if the option is shown)
6. Activate the app
7. Share the **Client ID** with you (this is a public identifier, not a secret)

> **IT keeps the Client Secret.** It never leaves the Zoom admin console.
> The PKCE flow means the user's machine never needs it.

### 2. Configure

```bash
cd /path/to/ECHO
cp .env.example .env
# Paste the Client ID from IT
```

### 3. Authenticate (one-time)

```bash
uv run echo-login
```

This opens Zoom in your browser. You sign in with **your** account and authorize
ECHO. Your personal tokens are saved to `~/.echo/tokens.json` (mode 600).

### 4. Add to Claude Code

Add to `~/.claude/settings.json` or your project `.mcp.json`:

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

### 5. Use it

```
> search my Zoom calls for "quarterly roadmap"
> list my recent meetings
> get the transcript from meeting 12345678
> summarize what was discussed in meeting 12345678
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `uv run echo-login` | Authorize ECHO with your Zoom account |
| `uv run echo-logout` | Remove stored tokens |
| `uv run echo-mcp` | Run the MCP server |

## Security Model

```
┌──────────────┐     ┌───────────────┐     ┌──────────────┐
│  Zoom Admin   │     │  Your Machine  │     │   Zoom API   │
│  (IT)         │     │               │     │              │
│               │     │  Client ID    │────▶│  /authorize  │
│  Client ID ──────▶  │  (public)     │     │              │
│  Client Secret│     │               │◀────│  auth code   │
│  (stays here) │     │  PKCE verifier│────▶│  /token      │
│               │     │               │◀────│  user token  │
│               │     │  ~/.echo/     │────▶│  /users/me/  │
│               │     │  tokens.json  │     │  recordings  │
└──────────────┘     └───────────────┘     └──────────────┘
```

- **Client Secret** never leaves IT's Zoom admin console
- **Your tokens** are scoped to your Zoom account only
- **`/users/me/`** endpoint means ECHO can only see your recordings
- **Tokens** are stored with `600` permissions (owner-read only)

## Development

```bash
uv sync
uv run echo-mcp                                          # Run server
npx @modelcontextprotocol/inspector uv run echo-mcp      # MCP Inspector
```

## Built with

- [FastMCP](https://github.com/jlowin/fastmcp) — Python MCP framework
- [CAIRN](https://github.com/Percona-Lab/CAIRN) — Alpine Toolkit scaffolder
