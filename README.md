# Claude SEO Pro

**An evidence-verified SEO command center for Claude Code — built so one SEO manager can run enterprise-grade audits from a single CLI.**

Claude SEO Pro is a hardened, client-ready distribution of the open-source
[Claude SEO](https://github.com/AgriciDaniel/claude-seo) system (25 sub-skills,
18 specialist agents). It adds three things that matter when you ship SEO to a
real client:

1. **Guided onboarding** — a wizard that securely collects and wires up the
   APIs the system uses (DataForSEO, Google PSI/CrUX/GSC/GA4, Firecrawl, Exa),
   validating each key against the live API before storing it.
2. **Secure credential storage** — keys live only in `~/.config/claude-seo/`
   with owner-only permissions, never in the repo, never in chat.
3. **Evidence Integrity Protocol** — an anti-fabrication layer in the audit
   pipeline so every finding traces to evidence on disk or a live API field.
   No more "typical patterns" guessing when a fetch fails.

> **License & origin.** MIT, built on top of MIT-licensed Claude SEO by
> Agrici Daniel. See [`NOTICE`](NOTICE) for full attribution and a list of what
> this distribution adds. All upstream skills/agents are preserved.

---

## Who this is for

- **An in-house SEO manager** who wants to supercharge their workflow with
  Claude without standing up infrastructure — install, run `/seo-setup`, audit.
- **Agencies / consultants** shipping a repeatable SEO system to clients, one
  seat at a time, with credentials kept on the client's own machine.

## Requirements

- [Claude Code CLI](https://claude.ai/claude-code)
- Python 3.10+
- Node.js (only for the DataForSEO / Firecrawl / Exa MCP servers)
- Your own API accounts for any provider you choose to enable (all optional)

## Install

**Windows (PowerShell):**
```powershell
git clone https://github.com/creator-imran/claude-seo-pro.git
powershell -ExecutionPolicy Bypass -File claude-seo-pro\install.ps1
```

**macOS / Linux:**
```bash
git clone https://github.com/creator-imran/claude-seo-pro.git
bash claude-seo-pro/install.sh
```

The installer copies the skills, agents, scripts, and onboarding wizard into
`~/.claude/`, then offers to run guided onboarding. Add `-NoOnboard`
(PowerShell) or `--no-onboard` (bash) to skip the wizard and do it later.

## First-run onboarding

After install, configure your APIs. Two equivalent paths:

**A) In Claude Code (recommended):**
```
/seo-setup
```
Claude walks you through each provider — what it unlocks, where to get the key —
and verifies the result. (Secrets are entered in your terminal, never pasted
into chat.)

**B) Directly in a terminal:**
```bash
python ~/.claude/skills/seo/onboarding/setup_wizard.py
```
The wizard prompts for each key with masked input, validates it live, stores it
under `~/.config/claude-seo/` (owner-only), and registers the MCP servers.

Check status any time:
```bash
python ~/.claude/skills/seo/onboarding/setup_wizard.py --check
```

| Provider | Unlocks | Where to get a key |
|---|---|---|
| **DataForSEO** | Live SERP positions, backlinks/DR, business listings, AI-mention tracking | https://app.dataforseo.com/register |
| **Google APIs** | Real Core Web Vitals field data (CrUX), PageSpeed; GSC/GA4 at higher tiers | https://console.cloud.google.com/apis/credentials |
| **Firecrawl** | Full-site crawling + JS rendering for large/SPA sites | https://www.firecrawl.dev/app/api-keys |
| **Exa** | Neural web search for competitor discovery + entity research | https://dashboard.exa.ai/api-keys |

> **DataForSEO note:** DataForSEO accounts often enable an **IP whitelist**. A
> valid key can still have every *data* call blocked (error `40207`) until your
> machine's public IP is added at
> [app.dataforseo.com/api-access](https://app.dataforseo.com/api-access). The
> onboarding validator detects and reports this distinctly.

## Quick start

```bash
claude
/seo-setup verify                  # confirm everything is wired
/seo audit https://yourclient.com  # full, evidence-verified audit
/seo page https://yourclient.com/  # deep single-page analysis
/seo schema https://yourclient.com # schema detection/validation/generation
/seo geo https://yourclient.com    # AI-search / GEO readiness
```

The full command surface (27 commands across the orchestrator and sub-skills)
is unchanged from upstream — see [`docs/`](docs/) and the command tables in
[`CLAUDE.md`](CLAUDE.md).

## What's different from upstream

A short, honest changelog lives in
[`docs/WHATS-DIFFERENT.md`](docs/WHATS-DIFFERENT.md). In one line: **the skills
and agents are upstream; the value we add is onboarding, secure storage, and the
Evidence Integrity Protocol.**

### Staying current with upstream

This is a vendored fork, but upstream fixes are one command away — and CI pulls
them in for you as a reviewable PR:

```bash
python tools/sync_upstream.py --dry-run     # preview upstream changes
python tools/sync_upstream.py --tag vX.Y.Z  # vendor + re-apply our overlay
```

Our additions are protected from being overwritten, and our one in-place change
(the `seo-audit` patch) re-applies automatically as an idempotent overlay. A
weekly GitHub Action (`.github/workflows/sync-upstream.yml`) syncs to the latest
upstream release and opens a PR. Details in
[`docs/WHATS-DIFFERENT.md`](docs/WHATS-DIFFERENT.md#staying-current-with-upstream).

## Security

- Credentials are stored only under `~/.config/claude-seo/*.json` (owner-only)
  and, for MCP servers, `~/.claude/settings.json` (owner-only). Both are outside
  the repo and gitignored.
- Nothing is transmitted anywhere except each provider's own API endpoints.
- Full details and threat model: [`docs/SECURITY.md`](docs/SECURITY.md).

## Documentation

- [Onboarding guide](docs/ONBOARDING.md)
- [Security model](docs/SECURITY.md)
- [What's different from upstream](docs/WHATS-DIFFERENT.md)
- [Project instructions](CLAUDE.md) · [Attribution](NOTICE) · [License](LICENSE)

## Credits

Built on [Claude SEO](https://github.com/AgriciDaniel/claude-seo) by Agrici
Daniel and its community contributors (see [`CONTRIBUTORS.md`](CONTRIBUTORS.md)).
Distribution, onboarding, and hardening by
[creator-imran](https://github.com/creator-imran).
