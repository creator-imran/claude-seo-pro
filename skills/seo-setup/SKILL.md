---
name: seo-setup
description: "Guided installation and API onboarding for Claude SEO Pro. Walks an SEO manager through securely configuring the DataForSEO, Google (PSI/CrUX/GSC/GA4), Firecrawl, and Exa APIs, verifies connectivity, and wires up MCP servers. Use when the user says setup, onboarding, configure APIs, add API keys, get started, install, or /seo-setup. Also handles 'verify' (status check) and 'rotate' (replace a key)."
user-invokable: true
argument-hint: "[verify | setup | rotate <provider>]"
license: MIT
metadata:
  author: creator-imran
  version: "1.0.0"
  category: seo
---

# Claude SEO Pro — Guided Setup

This skill onboards a new SEO manager onto the system: it securely collects the API
keys the audit pipeline can use, validates each against the live API, and registers
the MCP servers Claude Code needs. It is the front door for a new install.

**Wizard location (after install):** `~/.claude/skills/seo/onboarding/setup_wizard.py`
Run it with the user's Python (`python` or `py -3`).

## Golden rule: never handle raw secrets in chat

API keys are secrets. **Do not ask the user to paste keys into the conversation, and
never echo a key back.** Secret entry happens in the user's own terminal via the
wizard, which masks input (`getpass`). Your job is to guide, verify, and explain —
not to collect the secret values yourself.

If the user pastes a key anyway, warn them it is now in the transcript and recommend
rotating it after setup.

## Modes

### `verify` (default when unsure) — status check
1. Run: `python ~/.claude/skills/seo/onboarding/setup_wizard.py --check --json`
2. Parse the JSON. Report, per provider: configured? permissions OK? MCP registered?
3. For any provider that is configured, optionally confirm live connectivity by
   noting the `--check` does not re-validate; offer to run a validation pass.
4. Summarize what is ready and what is missing. Recommend next action.

### `setup` — full guided onboarding
Walk the providers in this order. For EACH one:

1. **Explain what it unlocks** (see table below) so the manager can decide if they
   need it. All are optional; the core audit runs without any, just with less data.
2. **Point them to the key** — give the signup URL and what scope/format to expect.
3. **Have them run the wizard themselves.** Tell the user to run this in their
   terminal (in Claude Code they can prefix with `!`):
   ```
   python ~/.claude/skills/seo/onboarding/setup_wizard.py
   ```
   Key-based providers prompt for a masked key, validate it live, store it under
   `~/.config/claude-seo/` (owner-only), and register the MCP server. OAuth providers
   (GSC/GA4, GBP) guide a browser auth flow and support **"attach later"**. To
   configure just one: add `--provider <id>`.
4. **After they finish**, run `--check --json` again to confirm storage + MCP/pending,
   and report the result.
5. **Remind them to restart Claude Code** so new MCP servers load.

| Provider | id | Unlocks | Get a key |
|---|---|---|---|
| DataForSEO | `dataforseo` | Off-site engine: SERP, **keyword-research suite**, backlinks/DR, business listings, AI mentions | https://app.dataforseo.com/register |
| Google API key | `google-api` | Real Core Web Vitals field data (CrUX) + PageSpeed | https://console.cloud.google.com/apis/credentials |
| Google Search Console + GA4 (OAuth) | `google-oauth` | Indexation status, search performance (clicks/impr/CTR/pos), GA4 organic traffic. **Skippable / attach later.** | OAuth client_secret.json from Cloud Console |
| Google Business Profile (OAuth) | `gbp` | First-party local insights (impressions/calls/directions, profile, reviews). **Owner access; skippable → DataForSEO fallback.** | OAuth client_secret.json + GBP API enabled |
| Firecrawl | `firecrawl` | Full-site crawling + JS rendering for large/SPA sites | https://www.firecrawl.dev/app/api-keys |
| Exa | `exa` | Neural web search for competitor discovery + entity research | https://dashboard.exa.ai/api-keys |

**OAuth & "attach later".** `google-oauth` and `gbp` can't be a single pasted key —
they need a `client_secret.json` and a one-time browser consent. In the wizard the
user picks **[N]ow / attach [L]ater / [S]kip**. "Attach later" records a *pending*
marker (shown by `--check`) and the audit degrades gracefully:
- No GSC/GA4 → indexation/traffic sections are "Data pending"; CWV still uses CrUX.
- No GBP → the Local/GBP phase runs the **DataForSEO (seo-maps) fallback** on public data.
To complete OAuth later:
`python ~/.claude/skills/seo/scripts/google_auth.py --auth --creds <client_secret.json>` (GSC/GA4)
or `python ~/.claude/skills/seo/onboarding/gbp_auth.py --auth --creds <client_secret.json>` (GBP).

### `rotate <provider>` — replace a key
Tell the user to run:
`python ~/.claude/skills/seo/onboarding/setup_wizard.py --provider <id>`
This overwrites the stored key and re-validates. Then run `--check` to confirm.

## Known gotchas to surface proactively

- **DataForSEO IP whitelist (error 40207).** DataForSEO can authenticate the
  credentials yet still block every *data* call until the machine's public IP is on
  the account whitelist. The wizard's validator reports this distinctly ("credentials
  valid, but data is blocked: IP not whitelisted"). If you see it, tell the user to
  add their public IP at https://app.dataforseo.com/api-access (or disable the
  whitelist). To find their IP, they can run `curl -s https://api.ipify.org`.
- **Google API not enabled.** A valid key still needs "PageSpeed Insights API" and
  "Chrome UX Report API" enabled on its Cloud project. Higher Google tiers (Search
  Console, Indexing, GA4) need OAuth/Service Account — direct them to `/seo google
  setup` after this.
- **Node/npx missing.** MCP servers (DataForSEO, Firecrawl, Exa) run via `npx`. If
  `node`/`npx` aren't installed, creds still store but MCP features won't load until
  Node is installed.
- **MCP loads at startup only.** A newly registered MCP server is not available until
  Claude Code restarts.

## What "done" looks like

Report a short scorecard at the end:
- Credentials stored (per provider) with owner-only perms — yes/no
- MCP servers registered — list
- Live validation — pass / pass-with-whitelist-warning / fail
- Action items remaining (e.g. "whitelist IP", "enable CrUX API", "restart Claude")

Then point them to their first run: `/seo audit https://theirclient.com`.

## Security summary (tell the user once)

- Keys live only in `~/.config/claude-seo/*.json` (owner-only) and, for MCP servers,
  in `~/.claude/settings.json` (owner-only). Both are outside the repo and gitignored.
- Nothing is transmitted anywhere except the respective provider's own API endpoints.
- To remove everything, delete the files in `~/.config/claude-seo/` and the relevant
  `mcpServers` entries in `settings.json` (the wizard wrote a `.bak` before changes).
