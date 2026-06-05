#!/usr/bin/env python3
"""
setup_wizard.py - guided onboarding for Claude SEO Pro.

Collects API credentials for the configured providers (DataForSEO, Google APIs,
Firecrawl, Exa), validates each against the live API, stores them securely under
~/.config/claude-seo/ (0600), and registers MCP servers in ~/.claude/settings.json.

Modes:
  python setup_wizard.py                 # interactive wizard (default)
  python setup_wizard.py --check         # show current credential + MCP status, exit
  python setup_wizard.py --provider exa  # configure a single provider
  python setup_wizard.py --from-env      # non-interactive: read keys from env vars
  python setup_wizard.py --no-mcp        # configure creds only, skip settings.json
  python setup_wizard.py --no-validate   # store without hitting the live APIs

Designed to be driven either directly by an SEO manager in a terminal, or by Claude
via the `seo-setup` skill (which calls --check and --from-env).
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import sys

try:
    from . import providers, validate, secure_store, configure_mcp
except ImportError:
    import providers, validate, secure_store, configure_mcp


# ---------- presentation helpers ----------

def _supports_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


C = {
    "h": "\033[96m", "ok": "\033[92m", "warn": "\033[93m",
    "err": "\033[91m", "dim": "\033[90m", "b": "\033[1m", "x": "\033[0m",
} if _supports_color() else {k: "" for k in ["h", "ok", "warn", "err", "dim", "b", "x"]}


def banner():
    print(f"""{C['h']}{C['b']}
==============================================================
   Claude SEO Pro  -  Guided Onboarding
   Secure API setup for your SEO command center
=============================================================={C['x']}
""")


def say(msg=""): print(msg)
def ok(msg): print(f"  {C['ok']}[OK]{C['x']} {msg}")
def warn(msg): print(f"  {C['warn']}[!]{C['x']} {msg}")
def err(msg): print(f"  {C['err']}[x]{C['x']} {msg}")
def head(msg): print(f"\n{C['h']}{C['b']}{msg}{C['x']}")


# ---------- prerequisite checks ----------

def check_prereqs() -> bool:
    head("Step 1 - Checking prerequisites")
    all_ok = True
    py = sys.version_info
    if py >= (3, 10):
        ok(f"Python {py.major}.{py.minor}")
    else:
        err(f"Python {py.major}.{py.minor} - need 3.10+")
        all_ok = False
    for tool, why, fatal in [
        ("node", "required for MCP servers (DataForSEO/Firecrawl/Exa)", False),
        ("npx", "runs the MCP servers", False),
        ("claude", "Claude Code CLI - where you run /seo", False),
    ]:
        if shutil.which(tool):
            ok(f"{tool} found ({why})")
        else:
            warn(f"{tool} NOT found - {why}. Install before using MCP-backed features.")
    return all_ok


# ---------- per-provider flow ----------

def _collect_interactive(prov: dict) -> dict | None:
    head(f"Configure: {prov['label']}")
    say(f"  {C['dim']}{prov['why']}{C['x']}")
    say(f"  Get a key: {prov['signup_url']}")
    say(f"  Docs:      {prov['docs_url']}")
    ans = input(f"  Configure {prov['label']} now? [Y/n]: ").strip().lower()
    if ans in ("n", "no", "skip", "s"):
        say(f"  {C['dim']}skipped{C['x']}")
        return None
    cfg = {}
    for f in prov["fields"]:
        prompt = f"    {f['prompt']}: "
        val = getpass.getpass(prompt) if f.get("secret") else input(prompt)
        cfg[f["key"]] = val.strip()
    return cfg


def _collect_from_env(prov: dict) -> dict | None:
    cfg = {}
    for f in prov["fields"]:
        val = os.environ.get(f["env"], "").strip()
        if val:
            cfg[f["key"]] = val
    # require all fields present to consider it configured non-interactively
    if len(cfg) == len(prov["fields"]):
        return cfg
    return None


def configure_provider(prov: dict, args) -> str:
    """Returns 'configured' | 'skipped' | 'failed'."""
    cfg = _collect_from_env(prov) if args.from_env else _collect_interactive(prov)
    if cfg is None:
        return "skipped"
    if any(not v for v in cfg.values()):
        warn("blank value provided; skipping")
        return "skipped"

    if not args.no_validate:
        say("  validating against live API...")
        res = validate.validate(prov["id"], cfg)
        if res["ok"]:
            ok(res["detail"])
            if res.get("warn"):
                warn(res["warn"])
        else:
            err(res["detail"])
            if not args.from_env:
                retry = input("  Save anyway / retry / skip? [save/R/skip]: ").strip().lower()
                if retry in ("r", "retry", ""):
                    return configure_provider(prov, args)
                if retry not in ("save", "s-a-v-e"):
                    return "failed"
            else:
                return "failed"

    path = secure_store.save(prov["id"], cfg)
    ok(f"stored -> {path} (owner-only)")

    if prov.get("mcp") and not args.no_mcp:
        mres = configure_mcp.configure(prov["id"])
        if mres["changed"]:
            ok(f"MCP server '{mres['name']}' registered in settings.json")
        else:
            say(f"  {C['dim']}MCP '{mres['name']}': {mres['detail']}{C['x']}")

    for note in prov.get("notes", []):
        warn(note)
    return "configured"


# ---------- status ----------

def print_status():
    head("Credential status (~/.config/claude-seo/)")
    st = secure_store.status()
    if not st:
        warn("no credentials stored yet")
    for prov in providers.PROVIDERS:
        s = st.get(prov["id"])
        if s:
            perms = "perms OK" if s["permissions_ok"] else "PERMS TOO OPEN"
            ok(f"{prov['label']}: keys={','.join(s['keys'])} ({perms})")
        else:
            say(f"  {C['dim']}- {prov['label']}: not configured{C['x']}")
    head("MCP servers in ~/.claude/settings.json")
    servers = configure_mcp.configured_servers()
    say("  " + (", ".join(servers) if servers else f"{C['dim']}none{C['x']}"))


# ---------- main ----------

def main(argv=None):
    ap = argparse.ArgumentParser(description="Claude SEO Pro guided onboarding")
    ap.add_argument("--check", action="store_true", help="print status and exit")
    ap.add_argument("--provider", help="configure only this provider id")
    ap.add_argument("--from-env", action="store_true", help="non-interactive: read keys from env vars")
    ap.add_argument("--no-mcp", action="store_true", help="skip writing MCP servers to settings.json")
    ap.add_argument("--no-validate", action="store_true", help="store without live validation")
    ap.add_argument("--json", action="store_true", help="machine-readable status (with --check)")
    args = ap.parse_args(argv)

    if args.check:
        if args.json:
            print(json.dumps({
                "credentials": secure_store.status(),
                "mcp_servers": configure_mcp.configured_servers(),
            }, indent=2))
        else:
            print_status()
        return 0

    banner()
    check_prereqs()

    targets = providers.PROVIDERS
    if args.provider:
        prov = providers.by_id(args.provider)
        if not prov:
            err(f"unknown provider '{args.provider}'. Known: {', '.join(providers.ids())}")
            return 1
        targets = [prov]

    head("Step 2 - Configure API providers")
    say(f"  {C['dim']}You can skip any provider and add it later with "
        f"`python setup_wizard.py --provider <id>`.{C['x']}")

    results = {}
    for prov in targets:
        results[prov["id"]] = configure_provider(prov, args)

    head("Done")
    for pid, status in results.items():
        label = providers.by_id(pid)["label"]
        mark = {"configured": ok, "skipped": say, "failed": err}.get(status, say)
        if status == "skipped":
            say(f"  {C['dim']}- {label}: skipped{C['x']}")
        else:
            mark(f"{label}: {status}")

    say(f"""
{C['b']}Next steps:{C['x']}
  1. Restart Claude Code so it picks up the new MCP servers.
  2. In Claude, run:  {C['h']}/seo-setup verify{C['x']}   (confirms everything is wired)
  3. Then run an audit:  {C['h']}/seo audit https://yourclient.com{C['x']}

Credentials live in ~/.config/claude-seo/ (owner-only) and are never committed.
Re-run this wizard any time to add or rotate keys.
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
