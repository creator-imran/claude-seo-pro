# What's different from upstream Claude SEO

This is an honest, file-level account of how Claude SEO Pro differs from the
upstream [`AgriciDaniel/claude-seo`](https://github.com/AgriciDaniel/claude-seo)
it is built on. The short version: **the 25 skills and 18 agents are upstream's
work, preserved. Our value is in onboarding, secure storage, and audit
integrity — not in rewriting the skill library.**

## Added (new in this distribution)

| Path | What it is |
|---|---|
| `onboarding/secure_store.py` | Owner-only (0600) credential storage under `~/.config/claude-seo/`, with Windows ACL hardening and atomic writes. |
| `onboarding/providers.py` | Registry of the four onboarded APIs (DataForSEO, Google, Firecrawl, Exa): fields, signup URLs, MCP specs, caveats. |
| `onboarding/validate.py` | Live connectivity validators per provider. Distinguishes bad credentials from valid-credentials-but-IP-blocked (DataForSEO `40207`). |
| `onboarding/configure_mcp.py` | Safe-merge MCP servers into `~/.claude/settings.json` (backup first, never clobbers existing keys). |
| `onboarding/setup_wizard.py` | The guided CLI: collect → validate → store → wire MCP. Interactive, `--check`, `--from-env`, per-provider, `--no-mcp` modes. |
| `skills/seo-setup/SKILL.md` | The `/seo-setup` Claude Code skill that drives onboarding conversationally and never handles raw secrets in chat. |
| `onboarding/gbp_auth.py` | Google Business Profile (first-party) OAuth + performance metrics (`business.manage` scope), with an honest DataForSEO fallback. |
| `skills/seo-audit/references/business-intelligence.md` | **Phase 0** — infer business model, country of origin, target markets, ICPs, seed keywords → `business-profile.json` before any audit work. |
| `skills/seo-audit/references/audit-playbook.md` | Templatized per-category checklists + smart LLM orchestration (model tiering, parallel specialists, adversarial verification). |
| `skills/seo-audit/references/keyword-research.md` | Full DataForSEO keyword-research suite, multi-locale, tiered into opportunities — a standard report section. |
| `skills/seo-audit/references/local-gbp-audit.md` | Local SEO + GBP phase: first-party GBP API primary, DataForSEO/`seo-maps` fallback, `seo-local` on-page. |
| `scripts/keyword_research.py` | DataForSEO multi-locale keyword orchestrator with `--plan` (cost preview), preflight, and honest "Data pending" on IP-block. |
| `skills/seo-audit/references/report-template.md` + `assets/report-template.html` | **The report depth contract** — 14 mandatory sections with minimum table depths (per-page on-page table for ALL money pages, position distribution, ≥10-row quick-wins, multi-market seeds, competitor gap, field-vs-lab CWV, per-category detail, strengths, call-log appendix), extracted from the gold-standard Strokes Exhibits report. Every full audit must render the HTML skeleton (exact gold-standard styling) and deliver a PDF; a summary-only report is a contract violation. |
| `tools/lint_report.py` | **Deterministic report-contract linter** — machine-checks a generated report against the 14-section contract: FAILs on missing sections, leftover `{{PLACEHOLDERS}}`, or summary-only compression; warns on depth-floor shortfalls and uncaused "Data pending" markers. Validated against ground truth (gold-depth report PASSes; the known-shallow report FAILs with 11 missing sections; the raw template FAILs). Mandatory pre-delivery step in the contract; CI self-tests it. The LLM-judge (semantic) half is deferred until calibrated. |
| `tools/check_install.py` + installer version stamp | **Install drift guard** — hashes the Pro-owned surface in the repo vs `~/.claude` and reports FRESH/STALE (caught a real stale-install incident). Installers stamp `~/.config/claude-seo/install-manifest.json`. Wired into `/seo-setup verify`. |
| `onboarding/branding.py` | **White-label config** — agencies rebrand client reports (preparer, colors, logo, footer) via `~/.config/claude-seo/branding.json`; defaults are the neutral product brand. Report generation loads it as step 0. |
| `.claude-plugin/marketplace.json` (rebranded) | **Plugin-marketplace distribution** — `/plugin marketplace add creator-imran/claude-seo-pro` then `/plugin install claude-seo-pro@creator-imran-claude-seo-pro`. (Upstream's marketplace file shipped verbatim before; it advertised the upstream identity.) |
| `tests/` + `.github/workflows/ci.yml` | **CI regression gate** — 68-assertion adversarial component suite + repo integrity (compile-all, JSON, secret-scan, no-client-data) + overlay check + linter self-test on every push/PR. Stdlib-only, offline. |
| `knowledge/` | **Persistent client knowledge store + computed-data cache** (Feature 1 of the agent roadmap). `store.py` = per-client business understanding + evidence-tagged learned facts + audit-score history, surviving model switches AND sessions (the real "long-term memory" — distinct from the ephemeral, model-scoped prompt cache). `cache.py` = on-disk cache of expensive API results (DataForSEO/PSI/HTML) with TTL + provenance, so repeat audits don't re-pay; expired entry = miss (no stale reads). Data lives owner-only under `~/.config/claude-seo/clients|cache/`, never in the repo. |
| `skills/seo-knowledge/SKILL.md` | The `/seo-knowledge` skill — recall what we know about a client, record evidence-tagged facts, inspect/purge the cache. The full audit reads it in Phase 0 and writes back after. |
| `agents/seo-learn.md` + `skills/seo-learn/SKILL.md` + `knowledge/learn.py` | **Client-business learning agent** (Feature 2). After an audit (or via `/seo-learn`), it distills DURABLE, evidence-tagged facts about the client into the knowledge store and **supersedes stale beliefs** (via `replace_tag`) so memory gets more accurate, not just bigger. `learn.py` guards memory hygiene: transient metrics and secret-looking strings are rejected, unsourced facts forced to `low`, with a `preview` (dry-run) before `ingest`. Dispatched as the always-on write-back step of a full audit. |
| `routing/model_router.py` + `skills/seo-models/SKILL.md` | **Smart model-routing policy** (Feature 3). A dispatch-time policy the orchestrator consults to run each task on the cheapest capable model — Haiku for extraction, Sonnet for reasoning/verification, Opus for synthesis — keeping the **main loop fixed** to preserve the prompt cache (the daemon form is impossible/counterproductive; this is the correct form per the Anthropic guidance). `route --agent X` returns model+effort; `estimate` shows the saving vs all-Opus (e.g. an extraction task: $0.08 Haiku vs $0.40 Opus). `/seo-models` lets the manager inspect/override (`--force-model opus` for a flagship report, per-agent remaps, reset). Overrides persist at `~/.config/claude-seo/model-policy.json`. |
| `connector/` + `skills/seo-connect/SKILL.md` + `docs/CONNECTOR.md` + `slack` onboarding provider | **Chat connector** (Feature 4) — run audits from **Slack** (`/seo audit example.com`) for managers who avoid the terminal. A separate webhook service: verifies the Slack HMAC signature (replay-windowed), parses+validates the command, authorizes the user/channel (**deny-by-default**), acks <3s, then runs the task **headlessly** (`claude -p`, reusing the same skills) and posts the result back. `handle_slash()` is a pure, unit-tested decision path; signature verification, parsing, authorization, and the headless command builder are all tested offline. Slack creds onboarded into `slack.json` (owner-only); operating config + allow-list in `connector.json`. WhatsApp documented as a future adapter on the same transport-agnostic runner. Live end-to-end (real Slack app + `claude -p` run) is the operator's deployment step, documented honestly in CONNECTOR.md. |
| `NOTICE` | MIT attribution to upstream + list of additions. |
| `docs/ONBOARDING.md`, `docs/SECURITY.md`, this file | Client-facing docs. |

### Onboarding now also collects (new providers)
- `google-oauth` — Search Console + Indexing + GA4 (OAuth/service-account), **skippable / attach-later**.
- `gbp` — Google Business Profile API (owner OAuth, `business.manage`), **skippable → DataForSEO fallback**.
- Deferred providers store a *pending* marker (`secure_store.mark_pending`) surfaced by `--check`, so the audit degrades gracefully instead of failing.

### Audit workflow is now a 4-phase Pro pipeline
Phase 0 Business Intelligence → templatized playbook audit → full DataForSEO keyword
research → Local/GBP (when `is_local_business`). The `seo-audit/SKILL.md` change is a
thin anchored "Pro Workflow" section (overlay change #0); all depth lives in the owned
reference files above.

## Changed

| Path | Change | Why |
|---|---|---|
| `skills/seo-audit/SKILL.md` | (1) Fixed the shared-script fetch path to `~/.claude/skills/seo/scripts/fetch_page.py` and mandated pre-fetch in the main session. (2) Added the **Evidence Integrity Protocol** (8 rules) + WAF/subagent error-handling rows. | The upstream relative path (`scripts/fetch_page.py`) resolves wrong once installed — subagents that can't fetch may guess. This was the root cause of a real fabricated audit. The protocol makes "no evidence → no finding" structural. |
| `install.ps1`, `install.sh` | Rewritten to be **self-contained** (install from this repo, not clone upstream) and to launch onboarding at the end. | A client distribution shouldn't depend on a third-party repo being available at install time. |
| `.claude-plugin/plugin.json` | Rebranded to `claude-seo-pro` with `based_on` attribution to upstream. | Identity + license clarity. |
| `.gitignore` | Added safety-net ignores for `*-api.json` / provider config filenames. | Prevent a client ever committing a key dropped in the working tree. |
| `CLAUDE.md` (repo topology section) | Replaced upstream's public/private dual-remote release workflow with this repo's single-remote model. | Upstream's workflow is specific to their org. |

## NOT changed (preserved from upstream, verbatim content)

- All 25 sub-skills' analysis logic and all 18 agents (aside from the two notes
  below).
- All Python scripts in `scripts/` (Google APIs, backlinks, drift, schema, etc.).
- Schema templates, references, hooks, PDF report generator, tests.

> **A note on the two upstream agents** `seo-dataforseo.md` and
> `seo-image-gen.md`: in some upstream installs these lost their `model:` and
> `maxTurns:` frontmatter during install-time copying. This distribution ships
> them as committed in upstream's repo. If you want those two agents pinned to a
> specific model or turn cap, add the frontmatter back explicitly.

## Staying current with upstream

This is a vendored fork, so upstream fixes don't appear by magic — but pulling them
in is a **single command**, and CI does it for you.

### How sync stays safe across a refresh

Our changes are split into two kinds so a re-vendor never loses them:

1. **Additive files we own** (`onboarding/`, `skills/seo-setup/`, `tools/`, our docs,
   installers, `NOTICE`, etc.). These are listed in `OVERLAY_PROTECTED` in
   `tools/sync_upstream.py` and are **never overwritten** by an upstream pull.
2. **The one in-place change** to `skills/seo-audit/SKILL.md` (Evidence Integrity
   Protocol + fetch-path fix). This is expressed as an **idempotent overlay** in
   `tools/apply_overlay.py` — after upstream's pristine file is vendored in, the
   overlay re-injects our content using text anchors. If upstream moves an anchor,
   the tool reports `FAILED` for that change so you fix it deliberately instead of
   silently losing it.

### Manual sync

```bash
python tools/sync_upstream.py --dry-run        # preview what upstream would change
python tools/sync_upstream.py --tag v2.1.0     # vendor that release + re-apply overlay
python tools/apply_overlay.py --check          # confirm the overlay is intact
# then: review `git diff`, run tests, commit
```
`upstream.json` records the currently pinned upstream tag.

### Automatic sync (CI)

`.github/workflows/sync-upstream.yml` runs every Monday (and on demand). It resolves
upstream's **latest release**, runs the sync, re-applies the overlay, and opens a
**pull request** — so upstream fixes arrive as a reviewable PR, never an unreviewed
push. If the overlay step fails, the PR body tells you exactly which anchor moved.

### Re-verifying the fork is still "upstream + overlay only"

To confirm nothing drifted: `python tools/sync_upstream.py --dry-run` should report
only `skills/seo-audit/SKILL.md` as changed (pristine-vs-overlaid) and zero other
content differences against the pinned tag.
