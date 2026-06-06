"""
config.py - configuration loader for the Claude SEO Pro chat connector (Feature 4).

Two files, both owner-only under ~/.config/claude-seo/ (never in the repo):
  slack.json       - SECRETS: {"signing_secret": "...", "bot_token": "xoxb-..."}
                     (written by the onboarding wizard's `slack` provider)
  connector.json   - non-secret operating config:
                     {
                       "run_backend": "claude-cli",
                       "claude_bin": "claude",
                       "model": null,                       # optional override; else CC default
                       "enabled_commands": ["audit","page","schema","geo","local","keyword"],
                       "allowed_users": ["U0123..."],       # Slack user IDs allowed to trigger
                       "allowed_channels": ["C0123..."],    # and/or channels
                       "timeout_seconds": 1800,
                       "max_concurrent": 2
                     }

Security default: if BOTH allow-lists are empty, NO ONE is authorized (audits cost
money/credits — deny by default until the operator opts people in).

Stdlib only.
"""

from __future__ import annotations

import json
import os

CONFIG_DIR = os.path.expanduser("~/.config/claude-seo")
SLACK_PATH = os.path.join(CONFIG_DIR, "slack.json")
CONNECTOR_PATH = os.path.join(CONFIG_DIR, "connector.json")

DEFAULTS = {
    "run_backend": "claude-cli",
    "claude_bin": "claude",
    "model": None,
    "enabled_commands": ["audit", "page", "schema", "geo", "local", "keyword"],
    "allowed_users": [],
    "allowed_channels": [],
    "timeout_seconds": 1800,
    "max_concurrent": 2,
}


def _read(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def slack_creds() -> dict:
    """{'signing_secret':..., 'bot_token':...} or {} if not onboarded."""
    c = _read(SLACK_PATH)
    # env fallback for headless/CI deploys
    return {
        "signing_secret": c.get("signing_secret") or os.environ.get("SLACK_SIGNING_SECRET", ""),
        "bot_token": c.get("bot_token") or os.environ.get("SLACK_BOT_TOKEN", ""),
    }


def connector() -> dict:
    cfg = dict(DEFAULTS)
    cfg.update({k: v for k, v in _read(CONNECTOR_PATH).items() if v is not None})
    return cfg


def is_configured() -> dict:
    sc = slack_creds()
    cc = connector()
    return {
        "slack_signing_secret": bool(sc["signing_secret"]),
        "slack_bot_token": bool(sc["bot_token"]),
        "authorization_open": bool(cc["allowed_users"] or cc["allowed_channels"]),
        "enabled_commands": cc["enabled_commands"],
        "run_backend": cc["run_backend"],
    }


if __name__ == "__main__":
    print(json.dumps(is_configured(), indent=2))
