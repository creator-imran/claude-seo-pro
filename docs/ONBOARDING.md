# Onboarding Guide

Claude SEO Pro works with **zero** API keys — the core audit runs locally. APIs
add off-site data (rankings, backlinks, real field CWV, crawling, neural search).
Onboard only what the engagement needs; add the rest later.

## The wizard

```bash
python ~/.claude/skills/seo/onboarding/setup_wizard.py
```

What it does for each provider you choose:
1. Explains what the API unlocks and where to get a key.
2. Prompts for the key with **masked input** (never shown, never logged).
3. **Validates** it against the live API (fast, near-zero cost).
4. **Stores** it at `~/.config/claude-seo/<provider>.json` with owner-only perms.
5. **Registers** the MCP server in `~/.claude/settings.json` (DataForSEO,
   Firecrawl, Exa). Google uses bundled scripts, not an MCP server.

### Useful flags

| Command | Purpose |
|---|---|
| `--check` | Print what's configured + MCP status, then exit. |
| `--check --json` | Same, machine-readable (used by `/seo-setup verify`). |
| `--provider <id>` | Configure/rotate a single provider (`dataforseo`, `google-api`, `firecrawl`, `exa`). |
| `--from-env` | Non-interactive: read keys from env vars (see below). |
| `--no-mcp` | Store credentials but don't touch `settings.json`. |
| `--no-validate` | Store without the live API check (offline setup). |

### Non-interactive (CI / scripted seats)

```bash
export DATAFORSEO_USERNAME="you@agency.com"
export DATAFORSEO_PASSWORD="..."
export GOOGLE_API_KEY="..."
export FIRECRAWL_API_KEY="fc-..."
export EXA_API_KEY="..."
python ~/.claude/skills/seo/onboarding/setup_wizard.py --from-env
```
A provider is only configured if **all** its env vars are present.

## Provider-by-provider

### DataForSEO (`dataforseo`)
- **Get it:** https://app.dataforseo.com/register → use the API **password**
  (not your dashboard login password) shown under API Access.
- **Whitelist:** Most accounts enable an IP whitelist. If validation says
  *"credentials valid, but data is blocked: IP not whitelisted (40207)"*, add
  your public IP at https://app.dataforseo.com/api-access. Find your IP with
  `curl -s https://api.ipify.org`. Dynamic IP? Consider disabling the whitelist
  or re-adding after each network change.

### Google APIs (`google-api`)
- **Get it:** Cloud Console → APIs & Services → Credentials → Create API key.
- **Enable:** "PageSpeed Insights API" and "Chrome UX Report API" on the key's
  project. Tier 0 (this key) covers PSI + CrUX + CrUX History.
- **Higher tiers:** Search Console, Indexing API, GA4 need OAuth or a Service
  Account — run `/seo google setup` after onboarding for that wizard.

### Firecrawl (`firecrawl`)
- **Get it:** https://www.firecrawl.dev/app/api-keys (keys start with `fc-`).
- **Cost:** crawling consumes credits; large sites can be expensive. The audit
  honors the 30-page warning / 50-page hard-stop guardrails.

### Exa (`exa`)
- **Get it:** https://dashboard.exa.ai/api-keys.
- **Cost:** search is metered per request; validation uses one 1-result query.

## After onboarding

1. **Restart Claude Code** — MCP servers load only at startup.
2. In Claude: `/seo-setup verify` to confirm everything is wired.
3. Run your first audit: `/seo audit https://yourclient.com`.

## Rotating or removing a key

- **Rotate:** `python .../setup_wizard.py --provider <id>` overwrites + re-validates.
- **Remove:** delete `~/.config/claude-seo/<provider>.json` and the matching
  `mcpServers` entry in `~/.claude/settings.json` (a `.bak` was written before
  the wizard's first change).
