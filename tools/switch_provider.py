#!/usr/bin/env python3
"""
switch_provider.py - switch the model backend between Anthropic first-party and
OpenRouter, on demand. The system always runs on Claude Code; only the backend the
CLI talks to changes (spec: docs/SPEC-provider-switching.md).

    python tools/switch_provider.py status
    python tools/switch_provider.py use anthropic
    python tools/switch_provider.py use openrouter [--profile claude|custom] [--force]
    python tools/switch_provider.py set-models --opus <slug> --sonnet <slug> --haiku <slug> [--subagent <slug>]
    python tools/switch_provider.py restore     # restore ~/.claude/settings.json from latest backup

Mechanism: Claude Code reads ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN (+ per-alias
model vars) from the env block of ~/.claude/settings.json - ONCE, at startup. So:
every switch requires restarting Claude Code, and /logout before going to OpenRouter
/ /login after coming back (cached auth conflicts). This tool prints those steps.

Safety: validates the key AND every model slug live BEFORE writing; backs up
settings.json (keeps last 5); merges/removes exactly the seven managed env keys and
touches nothing else; refuses to overwrite a foreign ANTHROPIC_BASE_URL without
--force; refuses to operate on unparseable settings.json.
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import sys
import urllib.request
import urllib.error

HOME = os.path.expanduser("~")
SETTINGS = os.path.join(HOME, ".claude", "settings.json")
CONFIG_DIR = os.path.join(HOME, ".config", "claude-seo")
OPENROUTER_CFG = os.path.join(CONFIG_DIR, "openrouter.json")
STATE = os.path.join(CONFIG_DIR, "provider-state.json")
OR_BASE = "https://openrouter.ai/api"

# the only env keys this tool manages — nothing else in settings.json is touched
MANAGED_KEYS = [
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "CLAUDE_CODE_SUBAGENT_MODEL",
]

# Default profile: same Claude family, billed via OpenRouter ("~" = OpenRouter's
# documented latest-aliases, so this tracks model releases without code changes).
CLAUDE_PROFILE = {
    "opus": "~anthropic/claude-opus-latest",
    "sonnet": "~anthropic/claude-sonnet-latest",
    "haiku": "~anthropic/claude-haiku-latest",
    "subagent": "~anthropic/claude-sonnet-latest",
}


# ---------- pure functions (unit-tested in tests/test_owned_components.py) ----------

def build_env(api_key: str, models: dict) -> dict:
    """The exact env block for OpenRouter mode."""
    return {
        "ANTHROPIC_BASE_URL": OR_BASE,
        "ANTHROPIC_AUTH_TOKEN": api_key,
        "ANTHROPIC_API_KEY": "",  # must be explicitly empty (auth-conflict prevention)
        "ANTHROPIC_DEFAULT_OPUS_MODEL": models["opus"],
        "ANTHROPIC_DEFAULT_SONNET_MODEL": models["sonnet"],
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": models["haiku"],
        "CLAUDE_CODE_SUBAGENT_MODEL": models.get("subagent", models["sonnet"]),
    }


def merge_settings(settings: dict, env_updates: dict) -> dict:
    """Return a NEW settings dict with env_updates merged into the env block.
    Everything else preserved verbatim."""
    out = dict(settings)
    env = dict(out.get("env") or {})
    env.update(env_updates)
    out["env"] = env
    return out


def strip_settings(settings: dict) -> dict:
    """Return a NEW settings dict with all managed keys removed from env.
    Drops the env block entirely if it ends up empty."""
    out = dict(settings)
    env = {k: v for k, v in (out.get("env") or {}).items() if k not in MANAGED_KEYS}
    if env:
        out["env"] = env
    else:
        out.pop("env", None)
    return out


def foreign_base_url(settings: dict) -> str | None:
    """A BASE_URL we didn't set (some other gateway) -> its value, else None."""
    cur = (settings.get("env") or {}).get("ANTHROPIC_BASE_URL", "")
    if cur and cur.rstrip("/") != OR_BASE:
        return cur
    return None


# ---------- IO helpers ----------

def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_settings() -> dict:
    if not os.path.exists(SETTINGS):
        return {}
    try:
        with open(SETTINGS, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[x] REFUSING to touch {SETTINGS}: cannot parse it ({e}).")
        print("    Fix the JSON (or restore a backup) and retry.")
        sys.exit(2)


def save_settings(settings: dict) -> None:
    # backup first, keep last 5
    if os.path.exists(SETTINGS):
        bak = SETTINGS + ".bak-" + _now()
        with open(SETTINGS, "rb") as src, open(bak, "wb") as dst:
            dst.write(src.read())
        baks = sorted(glob.glob(SETTINGS + ".bak-*"))
        for old in baks[:-5]:
            try:
                os.remove(old)
            except OSError:
                pass
    os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
    with open(SETTINGS, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")


def load_state() -> dict:
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"provider": "anthropic", "profile": None, "models": {}}


def save_state(state: dict) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _fetch(url: str, key: str | None = None, timeout: int = 25):
    """Tiny GET helper -> (status, parsed_json_or_text). Injectable in tests."""
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(raw)
            except json.JSONDecodeError:
                return r.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return None, str(e)


# ---------- live validation (spec 3.2 steps 2-3) ----------

def validate_key_live(api_key: str, fetch=_fetch) -> tuple[bool, str]:
    status, body = fetch(OR_BASE + "/v1/key", api_key)
    if status is None:
        return False, f"network error: {body}"
    if status in (401, 403):
        return False, "OpenRouter rejected the key (401/403)"
    if status == 200:
        data = body.get("data", {}) if isinstance(body, dict) else {}
        usage, limit = data.get("usage"), data.get("limit")
        msg = "key valid"
        if isinstance(usage, (int, float)):
            msg += f" (used ${usage:.2f}" + (f" of ${limit:.2f})" if isinstance(limit, (int, float)) else ")")
        return True, msg
    return False, f"unexpected response HTTP {status}"


def validate_models_live(models: dict, api_key: str, fetch=_fetch) -> tuple[bool, str]:
    """Every non-alias slug must exist on OpenRouter right now. '~' prefixed values
    are OpenRouter's documented latest-aliases and are accepted as-is."""
    to_check = sorted({m for m in models.values() if not m.startswith("~")})
    if not to_check:
        return True, "all slugs are OpenRouter latest-aliases"
    status, body = fetch(OR_BASE + "/v1/models", api_key)
    if status != 200 or not isinstance(body, dict):
        return False, f"could not list models (HTTP {status}) - cannot verify slugs"
    available = {m.get("id", "") for m in body.get("data", [])}
    missing = [m for m in to_check if m not in available]
    if missing:
        hints = []
        for m in missing:
            tail = m.split("/")[-1][:6].lower()
            close = [a for a in available if tail and tail in a.lower()][:3]
            hints.append(f"{m} (close: {', '.join(close) or 'none found'})")
        return False, "unknown model slug(s): " + "; ".join(hints)
    return True, f"{len(to_check)} slug(s) verified live"


# ---------- commands ----------

RESTART_BOX = """
  +----------------------------------------------------------------+
  |  REQUIRED NEXT STEPS (the endpoint is read ONCE at startup):   |
  |    1. In Claude Code:  /logout      (clears cached auth)       |
  |    2. Exit Claude Code completely                              |
  |    3. Start it again:  claude                                  |
  +----------------------------------------------------------------+"""

RESTART_BOX_BACK = """
  +----------------------------------------------------------------+
  |  REQUIRED NEXT STEPS:                                          |
  |    1. Exit Claude Code completely                              |
  |    2. Start it again:  claude                                  |
  |    3. In Claude Code:  /login       (restore Anthropic auth)   |
  +----------------------------------------------------------------+"""


def cmd_status() -> int:
    state = load_state()
    settings = load_settings()
    env = settings.get("env") or {}
    base = env.get("ANTHROPIC_BASE_URL", "")
    effective = "openrouter" if base.rstrip("/") == OR_BASE else ("foreign-gateway" if base else "anthropic")
    print(f"Backend (settings.json): {effective}" + (f"  [{base}]" if effective == "foreign-gateway" else ""))
    print(f"State file:              {state.get('provider')} (profile: {state.get('profile') or '-'})")
    if effective != state.get("provider") and effective != "foreign-gateway":
        print("[!] DRIFT: settings.json and provider-state.json disagree - re-run 'use <provider>' to realign.")
    if effective == "openrouter":
        for k in ("ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL",
                  "ANTHROPIC_DEFAULT_HAIKU_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL"):
            print(f"  {k.split('_')[-2].lower():>8} -> {env.get(k, '?')}")
        if not os.path.exists(OPENROUTER_CFG):
            print("[!] BROKEN: in openrouter mode but openrouter.json is gone - run 'use anthropic'.")
        else:
            key = _load_or_key()
            if key:
                ok, msg = validate_key_live(key)
                print(f"  key check: {msg}")
    cm = load_state().get("models") or {}
    if cm:
        print(f"Custom model map: {json.dumps(cm)}")
    print(f"Backups: {len(glob.glob(SETTINGS + '.bak-*'))} (restore with: switch_provider.py restore)")
    return 0


def _load_or_key() -> str:
    try:
        with open(OPENROUTER_CFG, encoding="utf-8") as f:
            return (json.load(f).get("api_key") or "").strip()
    except (OSError, json.JSONDecodeError):
        return ""


def cmd_use(provider: str, profile: str, force: bool) -> int:
    settings = load_settings()

    if provider == "anthropic":
        new = strip_settings(settings)
        if new == settings:
            print("[=] already on Anthropic first-party (no managed keys present).")
        else:
            save_settings(new)
            print("[+] switched backend -> Anthropic first-party (managed env keys removed).")
        save_state({"provider": "anthropic", "profile": None,
                    "models": load_state().get("models") or {}, "switched_utc": _now()})
        print(RESTART_BOX_BACK)
        return 0

    # provider == openrouter
    key = _load_or_key()
    if not key:
        print("[x] OpenRouter is not configured (or was deferred).")
        print("    Attach it now:  python ~/.claude/skills/seo/onboarding/setup_wizard.py --provider openrouter")
        return 2

    fb = foreign_base_url(settings)
    if fb and not force:
        print(f"[x] settings.json already routes to a DIFFERENT gateway: {fb}")
        print("    If you intend to replace it, re-run with --force.")
        return 2

    state = load_state()
    if profile == "custom":
        models = state.get("models") or {}
        required = {"opus", "sonnet", "haiku"}
        if not required.issubset(models):
            print("[x] custom profile has no model map yet. Set it first:")
            print("    python tools/switch_provider.py set-models --opus <slug> --sonnet <slug> --haiku <slug>")
            return 2
    else:
        models = CLAUDE_PROFILE

    print("[1/3] validating OpenRouter key (live)...")
    ok, msg = validate_key_live(key)
    if not ok:
        print(f"[x] {msg} - NOT switching (a dead key would brick your next session).")
        return 1
    print(f"      {msg}")

    print("[2/3] validating model map (live)...")
    ok, msg = validate_models_live(models, key)
    if not ok:
        print(f"[x] {msg} - NOT switching.")
        return 1
    print(f"      {msg}")

    print("[3/3] writing settings.json (backup kept)...")
    save_settings(merge_settings(settings, build_env(key, models)))
    save_state({"provider": "openrouter", "profile": profile, "models": state.get("models") or {},
                "switched_utc": _now()})
    print(f"[+] switched backend -> OpenRouter (profile: {profile})")
    for tier in ("opus", "sonnet", "haiku", "subagent"):
        print(f"      {tier:>8} -> {models.get(tier, models['sonnet'])}")
    if profile == "claude":
        print("      (same Claude models, billed via OpenRouter - slight premium vs first-party)")
    print(RESTART_BOX)
    return 0


def cmd_set_models(opus: str, sonnet: str, haiku: str, subagent: str | None) -> int:
    models = {"opus": opus, "sonnet": sonnet, "haiku": haiku,
              "subagent": subagent or sonnet}
    key = _load_or_key()
    if key:
        ok, msg = validate_models_live(models, key)
        print(("[+] " if ok else "[!] ") + msg)
        if not ok:
            print("    Map NOT saved. Check slugs at https://openrouter.ai/models")
            return 1
    else:
        print("[!] OpenRouter key not configured - slugs stored UNVERIFIED (verified at switch time).")
    state = load_state()
    state["models"] = models
    save_state(state)
    print("[+] custom model map saved. Activate with: python tools/switch_provider.py use openrouter --profile custom")
    print("    Quality note: frontier-grade models only (e.g. Kimi K2.6 class) - see the /seo-provider skill.")
    return 0


def cmd_restore() -> int:
    baks = sorted(glob.glob(SETTINGS + ".bak-*"))
    if not baks:
        print("[x] no backups found.")
        return 1
    latest = baks[-1]
    with open(latest, "rb") as src, open(SETTINGS, "wb") as dst:
        dst.write(src.read())
    print(f"[+] restored {SETTINGS} from {os.path.basename(latest)}")
    print("    Restart Claude Code for it to take effect.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Switch model backend: Anthropic <-> OpenRouter")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("status")
    u = sub.add_parser("use")
    u.add_argument("provider", choices=["anthropic", "openrouter"])
    u.add_argument("--profile", choices=["claude", "custom"], default="claude")
    u.add_argument("--force", action="store_true")
    m = sub.add_parser("set-models")
    m.add_argument("--opus", required=True)
    m.add_argument("--sonnet", required=True)
    m.add_argument("--haiku", required=True)
    m.add_argument("--subagent")
    sub.add_parser("restore")
    args = ap.parse_args(argv)

    if args.cmd == "use":
        return cmd_use(args.provider, args.profile, args.force)
    if args.cmd == "set-models":
        return cmd_set_models(args.opus, args.sonnet, args.haiku, args.subagent)
    if args.cmd == "restore":
        return cmd_restore()
    return cmd_status()


if __name__ == "__main__":
    raise SystemExit(main())
