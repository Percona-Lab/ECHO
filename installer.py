#!/usr/bin/env python3
"""ECHO interactive installer. Run via: curl -fsSL .../install.sh | bash"""

# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx"]
# ///

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# ── Colors ──────────────────────────────────────────────────

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BOLD = "\033[1m"
DIM = "\033[2m"
NC = "\033[0m"


def info(msg: str) -> None:
    print(f"  {msg}")


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{NC} {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}⚠{NC} {msg}")


def die(msg: str) -> None:
    print(f"  {RED}Error: {msg}{NC}", file=sys.stderr)
    sys.exit(1)


def ask(prompt: str, default: str = "") -> str:
    display = f" [{default}]" if default else ""
    try:
        value = input(f"  {prompt}{display}: ").strip()
        return value if value else default
    except (EOFError, KeyboardInterrupt):
        print()
        return default


def ask_yn(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    try:
        value = input(f"  {prompt} ({hint}): ").strip().lower()
        if not value:
            return default
        return value in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print()
        return default


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, **kwargs)


def banner() -> None:
    print()
    print(f"  {BOLD}ECHO{NC} - Explore Calls, Hearings & Observations")
    print(f"  {DIM}Search your Zoom meeting transcripts from any MCP-compatible AI tool.{NC}")
    print()


# ── Step 1: Install location ────────────────────────────────

def step_install(home: Path) -> Path:
    print(f"{BOLD}Step 1: Install location{NC}")
    default = str(home / "echo-mcp")
    install_dir = Path(ask("Install directory", default))

    if (install_dir / ".git").exists():
        info(f"{YELLOW}Existing installation found. Updating...{NC}")
        run(["git", "-C", str(install_dir), "pull", "--ff-only"])
    else:
        info("Cloning ECHO...")
        run(["git", "clone", "https://github.com/Percona-Lab/ECHO.git", str(install_dir)])

    ok(f"Installed at {install_dir}")
    return install_dir


# ── Step 2: Dependencies ────────────────────────────────────

def step_deps(install_dir: Path) -> None:
    print()
    print(f"{BOLD}Step 2: Dependencies{NC}")
    info("Installing Python dependencies...")
    run(["uv", "sync", "--quiet"], cwd=install_dir)
    ok("Dependencies installed")


# ── Step 3: Zoom OAuth ──────────────────────────────────────

def step_zoom_oauth(install_dir: Path) -> str | None:
    print()
    print(f"{BOLD}Step 3: Zoom OAuth Setup{NC}")

    env_file = install_dir / ".env"

    # Check for existing config
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("ZOOM_CLIENT_ID=") and len(line.split("=", 1)[1].strip()) > 0:
                existing = line.split("=", 1)[1].strip()
                ok(f"Client ID already configured: {DIM}{existing[:8]}...{NC}")
                if ask_yn("Keep this Client ID?"):
                    return existing

    info("ECHO needs a Zoom OAuth Client ID to connect to your account.")
    info("Let's check if your organization has already registered one.")
    print()

    zoom_domain = ask("Your Zoom domain (e.g. acme.zoom.us)", "")
    client_id = None

    if zoom_domain:
        # Extract org slug
        org_slug = zoom_domain.replace("https://", "").replace(".zoom.us", "").strip()

        # Look up in registry
        registry_file = install_dir / "client_registry.json"
        if registry_file.exists():
            try:
                registry = json.loads(registry_file.read_text())
                entry = registry.get("orgs", {}).get(org_slug, {})
                client_id = entry.get("client_id", "")
                org_name = entry.get("name", org_slug)
                if client_id:
                    ok(f"Found registered Client ID for {BOLD}{org_name}{NC}")
            except (json.JSONDecodeError, KeyError):
                pass

        if not client_id:
            # Try remote registry in case local is outdated
            try:
                import httpx
                resp = httpx.get(
                    "https://raw.githubusercontent.com/Percona-Lab/ECHO/main/client_registry.json",
                    timeout=5,
                )
                if resp.status_code == 200:
                    registry = resp.json()
                    entry = registry.get("orgs", {}).get(org_slug, {})
                    client_id = entry.get("client_id", "")
                    org_name = entry.get("name", org_slug)
                    if client_id:
                        ok(f"Found registered Client ID for {BOLD}{org_name}{NC}")
            except Exception:
                pass

        if not client_id:
            warn(f"No registered Client ID found for {BOLD}{org_slug}{NC}")
            print()
            info("Someone with Zoom admin access needs to create a General App (OAuth 2.0):")
            info(f"{DIM}  1. Go to https://marketplace.zoom.us > Develop > Build App{NC}")
            info(f"{DIM}  2. Select General App, set redirect URL: http://localhost:8090/callback{NC}")
            info(f"{DIM}  3. Add scopes: recording:read, user:read{NC}")
            info(f"{DIM}  4. Activate the app and copy the Client ID{NC}")
            print()
            info("To register it for your whole org, submit a PR to client_registry.json")
            info("so others in your organization can skip this step.")
            print()
            client_id = ask("Zoom OAuth Client ID (leave blank to configure later)", "")
    else:
        print()
        info(f"{DIM}No domain entered. You can enter a Client ID directly instead.{NC}")
        info(f"{DIM}Create a Zoom OAuth app at https://marketplace.zoom.us{NC}")
        print()
        client_id = ask("Zoom OAuth Client ID (leave blank to configure later)", "")

    if client_id:
        env_file.write_text(f"ZOOM_CLIENT_ID={client_id}\n")
        ok("Client ID saved to .env")
        return client_id
    else:
        # Copy example if no .env yet
        example = install_dir / ".env.example"
        if not env_file.exists() and example.exists():
            env_file.write_text(example.read_text())
        warn("Skipped. Add your Client ID to .env later.")
        return None


# ── Step 4: Authenticate ────────────────────────────────────

def step_auth(install_dir: Path, client_id: str | None) -> None:
    print()
    print(f"{BOLD}Step 4: Zoom Authentication{NC}")

    token_file = Path.home() / ".echo" / "tokens.json"

    if token_file.exists():
        ok("Already authenticated (tokens found at ~/.echo/tokens.json)")
    elif client_id:
        if ask_yn("Log in to Zoom now?"):
            run(["uv", "run", "echo-login"], cwd=install_dir)
        else:
            info(f"{DIM}Run 'uv run echo-login' later to authenticate.{NC}")
    else:
        info(f"{DIM}Skipped (no Client ID configured yet).{NC}")
        info(f"{DIM}After adding your Client ID to .env, run: uv run echo-login{NC}")


# ── Step 5: Configure AI client ─────────────────────────────

def step_configure_client(install_dir: Path) -> None:
    print()
    print(f"{BOLD}Step 5: Configure AI Client{NC}")

    mcp_entry = {
        "type": "stdio",
        "command": "uv",
        "args": ["run", "--directory", str(install_dir), "echo-mcp"],
    }

    # Claude Code
    claude_settings = Path.home() / ".claude" / "settings.json"
    has_claude_code = claude_settings.exists() or _command_exists("claude")

    if has_claude_code:
        if ask_yn("Configure Claude Code?"):
            _merge_mcp_config(claude_settings, "echo", mcp_entry)
            ok("Claude Code configured")

    # Claude Desktop
    claude_desktop = _find_claude_desktop_config()
    if claude_desktop and claude_desktop.exists():
        if ask_yn("Configure Claude Desktop?"):
            _merge_mcp_config(claude_desktop, "echo", mcp_entry)
            ok("Claude Desktop configured (restart to apply)")

    if not has_claude_code and not (claude_desktop and claude_desktop.exists()):
        info("No AI clients detected. Add ECHO to your MCP client config manually:")
        info(f'{DIM}  "echo": {json.dumps(mcp_entry)}{NC}')


def _merge_mcp_config(path: Path, name: str, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        cfg = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        cfg = {}
    cfg.setdefault("mcpServers", {})[name] = entry
    path.write_text(json.dumps(cfg, indent=2) + "\n")
    info(f"Updated {path}")


def _find_claude_desktop_config() -> Path | None:
    import platform

    if platform.system() == "Darwin":
        p = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    else:
        p = Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
    return p if p.exists() else None


def _command_exists(cmd: str) -> bool:
    try:
        run(["which", cmd], capture_output=True)
        return True
    except Exception:
        return False


# ── Done ────────────────────────────────────────────────────

def step_done(install_dir: Path) -> None:
    token_file = Path.home() / ".echo" / "tokens.json"

    print()
    print(f"  {GREEN}{BOLD}ECHO installed!{NC}")
    print()
    info(f"{DIM}Location:{NC}    {install_dir}")
    if token_file.exists():
        info(f"{DIM}Auth:{NC}        Authenticated")
    else:
        info(f"{DIM}Auth:{NC}        Run 'uv run echo-login' to connect your Zoom account")
    print()
    info(f'{DIM}Usage:{NC}       Ask your AI assistant about your Zoom meetings.')
    info(f'{DIM}Example:{NC}     "Search my Zoom calls for quarterly roadmap"')
    print()


# ── Main ────────────────────────────────────────────────────

def main() -> None:
    banner()
    home = Path.home()
    install_dir = step_install(home)
    step_deps(install_dir)
    client_id = step_zoom_oauth(install_dir)
    step_auth(install_dir, client_id)
    step_configure_client(install_dir)
    step_done(install_dir)


if __name__ == "__main__":
    main()
