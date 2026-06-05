"""
configure_mcp.py - register provider MCP servers in ~/.claude/settings.json.

Safe-merge semantics:
  * Reads the existing settings.json (preserving model, theme, permissions, and any
    other user keys verbatim).
  * Ensures an "mcpServers" object and inserts/updates ONLY the provider's entry.
  * Writes a timestamped .bak before the first change in a run.
  * Never removes servers it didn't add.

Secrets in settings.json: Claude Code reads MCP env from this file, so the API keys
DO land here as well as in ~/.config/claude-seo/. settings.json is user-space
(0600-restricted by this module) and must never be committed — the repo .gitignore
covers it, but it lives outside the repo anyway.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

try:
    from . import providers, secure_store
except ImportError:  # allow running as a plain script
    import providers
    import secure_store

SETTINGS_PATH = Path(os.path.expanduser("~")) / ".claude" / "settings.json"


def _load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        return {}
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8-sig") as fh:  # tolerate BOM
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def _backup_once(done={"v": False}):
    if done["v"] or not SETTINGS_PATH.exists():
        return
    bak = SETTINGS_PATH.with_suffix(".json.claude-seo.bak")
    try:
        shutil.copy2(SETTINGS_PATH, bak)
        done["v"] = True
    except OSError:
        pass


def _save_settings(data: dict) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _backup_once()
    with open(SETTINGS_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    # settings.json carries MCP secrets -> restrict like any credential file.
    secure_store._restrict_permissions(SETTINGS_PATH)


def configure(provider_id: str) -> dict:
    """Register the MCP server for `provider_id` using its stored config.

    Returns {"changed": bool, "name": str|None, "detail": str}.
    """
    prov = providers.by_id(provider_id)
    if not prov:
        return {"changed": False, "name": None, "detail": f"unknown provider {provider_id}"}
    mcp = prov.get("mcp")
    if not mcp:
        return {"changed": False, "name": None, "detail": "provider has no MCP server (script-based)"}

    cfg = secure_store.load(provider_id)
    if not cfg:
        return {"changed": False, "name": mcp["name"], "detail": "no stored credentials; run the wizard first"}

    entry = mcp["builder"](cfg)
    name = mcp["name"]

    settings = _load_settings()
    servers = settings.get("mcpServers")
    if not isinstance(servers, dict):
        servers = {}
    changed = servers.get(name) != entry
    servers[name] = entry
    settings["mcpServers"] = servers
    if changed:
        _save_settings(settings)
    return {
        "changed": changed,
        "name": name,
        "detail": "registered" if changed else "already up to date",
    }


def remove(provider_id: str) -> dict:
    prov = providers.by_id(provider_id)
    mcp = prov.get("mcp") if prov else None
    if not mcp:
        return {"changed": False, "name": None, "detail": "no MCP server for provider"}
    settings = _load_settings()
    servers = settings.get("mcpServers", {})
    if isinstance(servers, dict) and mcp["name"] in servers:
        del servers[mcp["name"]]
        settings["mcpServers"] = servers
        _save_settings(settings)
        return {"changed": True, "name": mcp["name"], "detail": "removed"}
    return {"changed": False, "name": mcp["name"], "detail": "not present"}


def configured_servers() -> list[str]:
    return sorted((_load_settings().get("mcpServers") or {}).keys())


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(json.dumps(configure(sys.argv[1]), indent=2))
    else:
        print("Configured MCP servers:", configured_servers())
        print("Usage: python configure_mcp.py <provider-id>")
